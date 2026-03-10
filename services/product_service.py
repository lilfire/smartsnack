"""Service for product CRUD and scored listing."""

import json
import math
import re

from db import get_db
from config import (
    PRODUCT_COLS_NO_IMAGE, INSERT_FIELDS, INSERT_PLACEHOLDERS,
    ALL_PRODUCT_FIELDS, _VALID_COLUMNS, _TEXT_FIELD_LIMITS,
    SCORE_CONFIG_MAP, COMPUTED_FIELDS,
    ADVANCED_FILTER_OPS, TEXT_FIELDS, NUMERIC_FIELDS, FILTERABLE_FIELDS, POST_QUERY_FIELDS,
)
from helpers import _num, _safe_float

_TEXT_FIELD_SET = frozenset(_TEXT_FIELD_LIMITS.keys())


def _load_weight_config(cur: object) -> tuple:
    """Load enabled score weights and their config from the database."""
    weight_rows = cur.execute(
        "SELECT field, enabled, weight, direction, formula, "
        "formula_min, formula_max FROM score_weights"
    ).fetchall()
    enabled_weights = {}
    weight_config = {}
    for r in weight_rows:
        if r["enabled"]:
            enabled_weights[r["field"]] = r["weight"]
            weight_config[r["field"]] = {
                "direction": r["direction"],
                "formula": r["formula"],
                "formula_min": r["formula_min"],
                "formula_max": r["formula_max"],
            }
    enabled_fields = [f for f in enabled_weights if f in SCORE_CONFIG_MAP]
    return enabled_weights, weight_config, enabled_fields


def _compute_category_ranges(
    cur: object, enabled_fields: list,
) -> dict:
    """Compute min/max ranges per category for minmax scoring."""
    cat_ranges = {}
    db_fields = [f for f in enabled_fields if f not in COMPUTED_FIELDS]
    if db_fields:
        for f in db_fields:
            if f not in _VALID_COLUMNS:
                raise ValueError(f"Invalid field: {f!r}")
        agg = ", ".join(
            f"MIN({f}) as min_{f}, MAX({f}) as max_{f}" for f in db_fields
        )
        type_rows = cur.execute(
            f"SELECT type, {agg} FROM products GROUP BY type"
        ).fetchall()
        for tr in type_rows:
            cat_ranges[tr["type"]] = {
                f: (tr[f"min_{f}"] or 0, tr[f"max_{f}"] or 0)
                for f in db_fields
            }
    return cat_ranges


def _score_product(
    p: dict, enabled_fields: list, enabled_weights: dict,
    weight_config: dict, cat_ranges: dict,
) -> None:
    """Compute and attach scores to a product dict in-place."""
    scores = {}
    weighted_score_sum = 0.0
    num_scored_fields = 0
    missing_fields = []
    ranges = cat_ranges.get(p["type"], {})
    for field in enabled_fields:
        cfg = weight_config[field]
        weight = enabled_weights[field]
        val = p.get(field)
        if val is None:
            missing_fields.append(field)
            continue

        formula = cfg["formula"]
        direction = cfg["direction"]

        if formula == "direct":
            fmin = cfg["formula_min"]
            fmax = cfg["formula_max"]
            if fmax <= fmin:
                continue
            if direction == "lower":
                raw = (fmax - val) / (fmax - fmin)
            else:
                raw = (val - fmin) / (fmax - fmin)
            raw = max(0.0, min(1.0, raw))
            s = raw * 100
        else:
            # minmax
            mn, mx = ranges.get(field, (0, 0))
            if mx - mn <= 0:
                continue
            if direction == "lower":
                raw = (mx - val) / (mx - mn)
            else:
                raw = (val - mn) / (mx - mn)
            raw = max(0.0, min(1.0, raw))
            s = raw * 100

        scores[field] = round(s * weight / 100, 1)
        weighted_score_sum += s * weight
        num_scored_fields += 1

    p["scores"] = scores
    p["total_score"] = (
        round(weighted_score_sum / (num_scored_fields * 100), 1)
        if num_scored_fields > 0 else 0
    )
    p["has_missing_scores"] = bool(missing_fields)
    p["missing_fields"] = missing_fields


def _parse_advanced_filters(filters_json: str) -> tuple[str, list, list]:
    """Parse advanced filter JSON and return (sql_fragment, params, post_filters).

    post_filters is a list of (field, op, value, logic) for computed fields
    that can't be filtered in SQL.

    Expected format:
      {"logic": "and"|"or", "conditions": [{"field": ..., "op": ..., "value": ...}, ...]}
    """
    try:
        data = json.loads(filters_json)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError("Invalid filters JSON") from e

    if not isinstance(data, dict):
        raise ValueError("Filters must be a JSON object")

    logic = data.get("logic", "and").upper()
    if logic not in ("AND", "OR"):
        raise ValueError("logic must be 'and' or 'or'")

    conditions = data.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("conditions must be a non-empty list")
    if len(conditions) > 20:
        raise ValueError("Too many filter conditions (max 20)")

    fragments, params, post_filters = [], [], []
    for c in conditions:
        field = c.get("field", "")
        op = c.get("op", "")
        value = c.get("value", "")

        if field not in FILTERABLE_FIELDS:
            raise ValueError(f"Invalid filter field: {field}")
        if op not in ADVANCED_FILTER_OPS:
            raise ValueError(f"Invalid filter operator: {op}")
        if value is None or str(value).strip() == "":
            raise ValueError(f"Filter value required for {field}")

        value = str(value).strip()
        sql_op = ADVANCED_FILTER_OPS[op]

        if field in POST_QUERY_FIELDS:
            if op == "contains":
                raise ValueError(f"Operator 'contains' not valid for numeric field '{field}'")
            try:
                num_val = float(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid numeric value for {field}") from e
            if not math.isfinite(num_val):
                raise ValueError(f"Non-finite value for {field}")
            post_filters.append((field, op, num_val, logic))
        elif field in TEXT_FIELDS:
            if op == "contains":
                escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                fragments.append(f"LOWER({field}) LIKE ? ESCAPE '\\'")
                params.append(f"%{escaped.lower()}%")
            elif op in ("=", "!="):
                fragments.append(f"LOWER({field}) {sql_op} LOWER(?)")
                params.append(value)
            else:
                raise ValueError(f"Operator '{op}' not valid for text field '{field}'")
        else:
            # Numeric field
            if op == "contains":
                raise ValueError(f"Operator 'contains' not valid for numeric field '{field}'")
            try:
                num_val = float(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid numeric value for {field}") from e
            if not math.isfinite(num_val):
                raise ValueError(f"Non-finite value for {field}")
            fragments.append(f"{field} {sql_op} ?")
            params.append(num_val)

    combined = f" {logic} ".join(f"({f})" for f in fragments)
    sql = f"({combined})" if combined else ""
    return sql, params, post_filters


_OP_FNS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
}


def _apply_post_filters(results: list, post_filters: list) -> list:
    """Filter results in Python for computed fields like total_score."""
    if not post_filters:
        return results
    logic = post_filters[0][3]  # all share the same logic
    filtered = []
    for p in results:
        checks = []
        for field, op, value, _ in post_filters:
            pval = p.get(field)
            if pval is None:
                checks.append(False)
            else:
                checks.append(_OP_FNS[op](float(pval), value))
        if logic == "AND" and all(checks):
            filtered.append(p)
        elif logic == "OR" and any(checks):
            filtered.append(p)
    return filtered


def list_products(search: str | None, type_filter: str | None, advanced_filters: str | None = None) -> list:
    """List products with computed scores, filtered and sorted."""
    conn = get_db()
    cur = conn.cursor()

    enabled_weights, weight_config, enabled_fields = _load_weight_config(cur)
    cat_ranges = _compute_category_ranges(cur, enabled_fields)

    conditions, params = [], []
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("(name LIKE ? ESCAPE '\\' OR ean LIKE ? ESCAPE '\\')")
        params.extend([f"%{escaped}%", f"%{escaped}%"])
    if type_filter:
        types = [t.strip() for t in type_filter.split(",") if t.strip()]
        if len(types) == 1:
            conditions.append("type = ?")
            params.append(types[0])
        elif types:
            placeholders = ",".join("?" * len(types))
            conditions.append(f"type IN ({placeholders})")
            params.extend(types)
    post_filters = []
    if advanced_filters:
        af_sql, af_params, post_filters = _parse_advanced_filters(advanced_filters)
        if af_sql:
            conditions.append(af_sql)
            params.extend(af_params)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = cur.execute(
        f"SELECT {PRODUCT_COLS_NO_IMAGE} FROM products {where} ORDER BY name",
        params,
    ).fetchall()

    results = []
    for r in rows:
        p = dict(r)
        for cf, compute_fn in COMPUTED_FIELDS.items():
            p[cf] = compute_fn(p)
        _score_product(
            p, enabled_fields, enabled_weights, weight_config, cat_ranges,
        )
        results.append(p)

    results = _apply_post_filters(results, post_filters)
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results


def add_product(data: dict) -> dict:
    if not data.get("type", "").strip() or not data.get("name", "").strip():
        raise ValueError("type and name are required")
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = data.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    ean = data.get("ean", "").strip()
    if ean and not re.fullmatch(r"\d{8,13}", ean):
        raise ValueError("EAN must be 8-13 digits")
    conn = get_db()
    cur = conn.cursor()
    cat_exists = cur.execute("SELECT 1 FROM categories WHERE name = ?", (data["type"].strip(),)).fetchone()
    if not cat_exists:
        raise ValueError("Category does not exist")
    cur.execute(
        f"INSERT INTO products ({INSERT_FIELDS}) VALUES ({INSERT_PLACEHOLDERS})",
        (data["type"].strip(), data["name"].strip(), data.get("ean", "").strip(),
         data.get("brand", "").strip(), data.get("stores", "").strip(), data.get("ingredients", "").strip(),
         _num(data, "taste_score"), _num(data, "kcal"),
         _num(data, "energy_kj"), _num(data, "carbs"),
         _num(data, "sugar"), _num(data, "fat"),
         _num(data, "saturated_fat"), _num(data, "protein"),
         _num(data, "fiber"), _num(data, "salt"),
         _num(data, "volume"), _num(data, "price"),
         _num(data, "weight"), _num(data, "portion"),
         _num(data, "est_pdcaas"), _num(data, "est_diaas")))
    conn.commit()
    return {"id": cur.lastrowid, "message": "Product added"}


def update_product(pid: int, data: dict) -> None:
    """Update a product's fields by ID."""
    updates, vals = [], []
    for f in data:
        if f in ("id", "image"):
            continue
        if f not in _VALID_COLUMNS:
            raise ValueError("Invalid field")
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        if tf in data and isinstance(data[tf], str) and len(data[tf]) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    if "ean" in data:
        ean = (data["ean"] or "").strip()
        if ean and not re.fullmatch(r"\d{8,13}", ean):
            raise ValueError("EAN must be 8-13 digits")
    for f in ALL_PRODUCT_FIELDS:
        if f in data:
            v = data[f]
            if f not in _TEXT_FIELD_SET:
                if v is None or v == "":
                    v = None
                else:
                    v = _safe_float(v, f)
            updates.append(f"{f} = ?")
            vals.append(v)
    if not updates:
        raise ValueError("Nothing to update")
    conn = get_db()
    if "type" in data:
        cat_exists = conn.execute("SELECT 1 FROM categories WHERE name = ?", (data["type"],)).fetchone()
        if not cat_exists:
            raise ValueError("Category does not exist")
    vals.append(pid)
    cur = conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals)
    if cur.rowcount == 0:
        raise LookupError("Product not found")
    conn.commit()


def delete_product(pid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
    return cur.rowcount > 0
