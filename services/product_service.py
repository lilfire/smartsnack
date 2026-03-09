"""Service for product CRUD and scored listing."""

import re

from db import get_db
from config import (
    PRODUCT_COLS_NO_IMAGE, INSERT_FIELDS, INSERT_PLACEHOLDERS,
    ALL_PRODUCT_FIELDS, _VALID_COLUMNS, _TEXT_FIELD_LIMITS,
    SCORE_CONFIG_MAP, COMPUTED_FIELDS,
)
from helpers import _num, _safe_float

_TEXT_FIELD_SET = frozenset(
    {"type", "name", "ean", "brand", "stores", "ingredients"}
)


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


def list_products(search: str | None, type_filter: str | None) -> list:
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
    conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals)
    conn.commit()


def delete_product(pid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
    return cur.rowcount > 0
