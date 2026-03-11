"""Service for product CRUD and scored listing."""

import json
import math
import re

from db import get_db
from config import (
    PRODUCT_COLS_NO_IMAGE, INSERT_FIELDS, INSERT_PLACEHOLDERS,
    ALL_PRODUCT_FIELDS, _VALID_COLUMNS, _TEXT_FIELD_LIMITS,
    SCORE_CONFIG_MAP, COMPUTED_FIELDS, COMPLETENESS_FIELDS,
    ADVANCED_FILTER_OPS, TEXT_FIELDS, NUMERIC_FIELDS, FILTERABLE_FIELDS, POST_QUERY_FIELDS,
    MAX_FILTER_DEPTH, MAX_FILTER_CONDITIONS,
)
from services import flag_service
from helpers import _num, _safe_float

_TEXT_FIELD_SET = frozenset(_TEXT_FIELD_LIMITS.keys())
_FLAG_FIELD_PREFIX = "flag:"


def _get_product_flags(cur, product_ids: list) -> dict:
    """Batch-fetch flags for a list of product IDs. Returns {pid: [flag, ...]}."""
    if not product_ids:
        return {}
    placeholders = ",".join("?" * len(product_ids))
    rows = cur.execute(
        f"SELECT product_id, flag FROM product_flags WHERE product_id IN ({placeholders})",
        product_ids,
    ).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r["product_id"], []).append(r["flag"])
    return result


def _set_user_flags(conn, pid: int, flags: list) -> None:
    """Replace all user flags for a product. Ignores unknown or system flags."""
    user_flags = flag_service.get_user_flag_names()
    valid_flags = [f for f in flags if f in user_flags]
    # Delete existing user flags only
    if user_flags:
        conn.execute(
            f"DELETE FROM product_flags WHERE product_id = ? AND flag IN ({','.join('?' * len(user_flags))})",
            [pid] + list(user_flags),
        )
    for flag in valid_flags:
        conn.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid, flag),
        )


def set_system_flag(pid: int, flag_name: str, value: bool) -> None:
    """Set or clear a system flag for a product. For programmatic use only."""
    if flag_name not in flag_service.get_all_flag_names():
        raise ValueError(f"Unknown flag: {flag_name!r}")
    conn = get_db()
    if value:
        conn.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid, flag_name),
        )
    else:
        conn.execute(
            "DELETE FROM product_flags WHERE product_id = ? AND flag = ?",
            (pid, flag_name),
        )
    conn.commit()


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


def _compute_completeness(p: dict) -> int:
    """Compute completeness percentage (0-100) based on filled fields."""
    filled = 0
    total = len(COMPLETENESS_FIELDS)
    for field in COMPLETENESS_FIELDS:
        if field == "image":
            if p.get("has_image"):
                filled += 1
        else:
            val = p.get(field)
            if val is not None and val != "":
                filled += 1
    return round(filled / total * 100) if total > 0 else 0


def _parse_condition(c: dict) -> tuple:
    """Parse and validate a single filter condition.

    Returns (field, op, value_str, sql_op) after validation.
    For flag fields, op is always "=" and value is "true" or "false".
    """
    field = c.get("field", "")
    op = c.get("op", "")
    value = c.get("value", "")

    # Build dynamic flag fields from DB
    all_flag_names = flag_service.get_all_flag_names()
    flag_fields = frozenset(f"flag:{n}" for n in all_flag_names)
    filterable = FILTERABLE_FIELDS | flag_fields

    if field not in filterable:
        raise ValueError(f"Invalid filter field: {field}")

    # Flag fields: only op "=" with value "true"/"false"
    if field in flag_fields:
        flag_name = field[len(_FLAG_FIELD_PREFIX):]
        if flag_name not in all_flag_names:
            raise ValueError(f"Unknown flag: {flag_name}")
        if op != "=":
            raise ValueError(f"Operator '{op}' not valid for flag field '{field}'")
        val_str = str(value).strip().lower()
        if val_str not in ("true", "false"):
            raise ValueError(f"Flag value must be 'true' or 'false', got '{value}'")
        return field, op, val_str, "="

    if op not in ADVANCED_FILTER_OPS:
        raise ValueError(f"Invalid filter operator: {op}")
    if value is None or str(value).strip() == "":
        raise ValueError(f"Filter value required for {field}")

    return field, op, str(value).strip(), ADVANCED_FILTER_OPS[op]


def _condition_to_sql(field: str, op: str, value: str, sql_op: str) -> tuple:
    """Convert a validated condition to a SQL fragment and param.

    Returns (sql_fragment, param).
    """
    if field.startswith(_FLAG_FIELD_PREFIX):
        flag_name = field[len(_FLAG_FIELD_PREFIX):]
        subquery = "SELECT 1 FROM product_flags pf WHERE pf.product_id = products.id AND pf.flag = ?"
        if value == "true":
            return f"EXISTS ({subquery})", flag_name
        else:
            return f"NOT EXISTS ({subquery})", flag_name

    if field in TEXT_FIELDS:
        if op == "contains":
            escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return f"LOWER({field}) LIKE ? ESCAPE '\\'", f"%{escaped.lower()}%"
        elif op in ("=", "!="):
            return f"LOWER({field}) {sql_op} LOWER(?)", value
        else:
            raise ValueError(f"Operator '{op}' not valid for text field '{field}'")
    else:
        if op == "contains":
            raise ValueError(f"Operator 'contains' not valid for numeric field '{field}'")
        try:
            num_val = float(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric value for {field}") from e
        if not math.isfinite(num_val):
            raise ValueError(f"Non-finite value for {field}")
        return f"{field} {sql_op} ?", num_val


def _condition_to_post(field: str, op: str, value: str) -> tuple:
    """Convert a validated condition to a post-filter tuple.

    Returns (field, op, num_val).
    """
    if op == "contains":
        raise ValueError(f"Operator 'contains' not valid for numeric field '{field}'")
    try:
        num_val = float(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid numeric value for {field}") from e
    if not math.isfinite(num_val):
        raise ValueError(f"Non-finite value for {field}")
    return field, op, num_val


def _convert_legacy_format(data: dict) -> dict:
    """Convert legacy filter formats to the new recursive format.

    Legacy flat:   {"logic": "and", "conditions": [...]}
    Old grouped:   {"logic": "and", "groups": [{"logic": ..., "conditions": [...]}, ...]}
    New recursive: {"logic": "and", "children": [...]}
    """
    if "children" in data:
        return data  # already new format

    logic = data.get("logic", "and")

    if "conditions" in data and "groups" not in data:
        # Legacy flat: single group with conditions as direct children
        return {"logic": logic, "children": data["conditions"]}

    if "groups" in data:
        # Old grouped format: convert each group to a nested group node
        children = []
        for g in data["groups"]:
            if isinstance(g, dict) and g.get("conditions"):
                children.append({
                    "logic": g.get("logic", "and"),
                    "children": g["conditions"],
                })
        return {"logic": logic, "children": children}

    raise ValueError("Unrecognised filter format")


def _count_conditions(node: dict) -> int:
    """Recursively count leaf conditions in a filter tree."""
    if "field" in node:
        return 1
    return sum(_count_conditions(c) for c in node.get("children", []) if isinstance(c, dict))


def _process_node(node: dict, depth: int = 0) -> tuple:
    """Recursively process a filter node.

    Returns (sql_fragment | None, sql_params, post_node | None).
    - sql_fragment: SQL WHERE fragment for DB-filterable conditions
    - sql_params: list of query parameters
    - post_node: recursive post-filter spec for computed fields
    """
    if depth > MAX_FILTER_DEPTH:
        raise ValueError(f"Filter nesting too deep (max {MAX_FILTER_DEPTH})")

    # Leaf condition
    if "field" in node:
        field, op, value, sql_op = _parse_condition(node)
        if field in POST_QUERY_FIELDS:
            return None, [], {"field": field, "op": op, "val": _condition_to_post(field, op, value)[2]}
        frag, param = _condition_to_sql(field, op, value, sql_op)
        return f"({frag})", [param], None

    # Group node
    logic = node.get("logic", "and").upper()
    if logic not in ("AND", "OR"):
        raise ValueError("logic must be 'and' or 'or'")

    children = node.get("children")
    if not isinstance(children, list) or not children:
        return None, [], None

    sql_parts = []
    all_params = []
    post_parts = []

    for child in children:
        if not isinstance(child, dict):
            raise ValueError("Each filter node must be a JSON object")
        child_sql, child_params, child_post = _process_node(child, depth + 1)
        if child_sql:
            sql_parts.append(child_sql)
            all_params.extend(child_params)
        if child_post:
            post_parts.append(child_post)

    # If OR logic mixes SQL and post-query nodes, move everything to post-filter
    if logic == "OR" and sql_parts and post_parts:
        # Re-process all children as post-filter only
        post_children = []
        for child in children:
            if not isinstance(child, dict):
                continue
            post_children.append(_node_to_post(child))
        return None, [], {"logic": logic, "children": post_children}

    # Build SQL fragment for this group
    sql_fragment = None
    if sql_parts:
        combined = f" {logic} ".join(sql_parts)
        sql_fragment = f"({combined})" if len(sql_parts) > 1 else sql_parts[0]

    # Build post-filter node for this group
    post_node = None
    if post_parts:
        post_node = {"logic": logic, "children": post_parts} if len(post_parts) > 1 else post_parts[0]

    return sql_fragment, all_params, post_node


def _node_to_post(node: dict) -> dict:
    """Convert an entire filter node tree to a post-filter spec (no SQL)."""
    if "field" in node:
        field, op, value, _sql_op = _parse_condition(node)
        return {"field": field, "op": op, "val": _condition_to_post(field, op, value)[2]}

    logic = node.get("logic", "and").upper()
    children = node.get("children", [])
    post_children = [_node_to_post(c) for c in children if isinstance(c, dict)]
    return {"logic": logic, "children": post_children}


def _parse_advanced_filters(filters_json: str) -> tuple[str, list, dict | None]:
    """Parse advanced filter JSON and return (sql_fragment, params, post_filter_spec).

    Supports three formats (auto-detected):
      Legacy flat:   {"logic": "and"|"or", "conditions": [...]}
      Old grouped:   {"logic": "and"|"or", "groups": [{"logic": ..., "conditions": [...]}, ...]}
      New recursive: {"logic": "and"|"or", "children": [<condition | group>, ...]}

    post_filter_spec is None or a recursive dict:
      {"logic": "AND", "children": [{"field":..,"op":..,"val":..}, {"logic":..,"children":[...]}, ...]}
    """
    try:
        data = json.loads(filters_json)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError("Invalid filters JSON") from e

    if not isinstance(data, dict):
        raise ValueError("Filters must be a JSON object")

    # Convert legacy formats to new recursive format
    data = _convert_legacy_format(data)

    # Validate total condition count
    total = _count_conditions(data)
    if total > MAX_FILTER_CONDITIONS:
        raise ValueError(f"Too many filter conditions (max {MAX_FILTER_CONDITIONS})")

    sql_fragment, params, post_node = _process_node(data, depth=0)
    return sql_fragment or "", params, post_node


_OP_FNS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
}


def _evaluate_post_node(node: dict, product: dict) -> bool:
    """Recursively evaluate a post-filter node against a product."""
    if "field" in node:
        pval = product.get(node["field"])
        if pval is None:
            return False
        return _OP_FNS[node["op"]](float(pval), node["val"])

    logic = node.get("logic", "AND")
    children = node.get("children", [])
    results = [_evaluate_post_node(c, product) for c in children]
    if not results:
        return True
    return all(results) if logic == "AND" else any(results)


def _apply_post_filters(results: list, post_filter_spec: dict | None) -> list:
    """Filter results in Python for computed fields like total_score.

    post_filter_spec is a recursive node tree:
      {"logic": "AND", "children": [{"field":..,"op":..,"val":..}, ...]}
    or a single leaf: {"field":..,"op":..,"val":..}
    """
    if not post_filter_spec:
        return results
    return [p for p in results if _evaluate_post_node(post_filter_spec, p)]


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
    post_filter_spec = None
    if advanced_filters:
        af_sql, af_params, post_filter_spec = _parse_advanced_filters(advanced_filters)
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
        p["completeness"] = _compute_completeness(p)
        results.append(p)

    results = _apply_post_filters(results, post_filter_spec)

    # Attach flags
    pids = [p["id"] for p in results]
    flags_map = _get_product_flags(cur, pids)
    for p in results:
        p["flags"] = flags_map.get(p["id"], [])

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
    name = data["name"].strip()
    if ean:
        dup = cur.execute("SELECT id, name FROM products WHERE ean = ?", (ean,)).fetchone()
        if dup:
            raise ValueError(f"A product with EAN {ean} already exists: {dup[1]}")
    dup_name = cur.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
    if dup_name:
        raise ValueError(f"A product with name '{name}' already exists")
    cur.execute(
        f"INSERT INTO products ({INSERT_FIELDS}) VALUES ({INSERT_PLACEHOLDERS})",
        (data["type"].strip(), data["name"].strip(), data.get("ean", "").strip(),
         data.get("brand", "").strip(), data.get("stores", "").strip(), data.get("ingredients", "").strip(),
         data.get("taste_note", "").strip(),
         _num(data, "taste_score"), _num(data, "kcal"),
         _num(data, "energy_kj"), _num(data, "carbs"),
         _num(data, "sugar"), _num(data, "fat"),
         _num(data, "saturated_fat"), _num(data, "protein"),
         _num(data, "fiber"), _num(data, "salt"),
         _num(data, "volume"), _num(data, "price"),
         _num(data, "weight"), _num(data, "portion"),
         _num(data, "est_pdcaas"), _num(data, "est_diaas")))
    new_id = cur.lastrowid
    if "flags" in data and isinstance(data["flags"], list):
        _set_user_flags(conn, new_id, data["flags"])
    if data.get("from_off"):
        set_system_flag(new_id, "is_synced_with_off", True)
    conn.commit()
    return {"id": new_id, "message": "Product added"}


def update_product(pid: int, data: dict) -> None:
    """Update a product's fields by ID."""
    # Extract flags before field validation loop
    incoming_flags = data.pop("flags", None)
    from_off = data.pop("from_off", False)

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
    if not updates and incoming_flags is None:
        raise ValueError("Nothing to update")
    conn = get_db()
    if "type" in data:
        cat_exists = conn.execute("SELECT 1 FROM categories WHERE name = ?", (data["type"],)).fetchone()
        if not cat_exists:
            raise ValueError("Category does not exist")
    if updates:
        vals.append(pid)
        cur = conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals)
        if cur.rowcount == 0:
            raise LookupError("Product not found")
    else:
        # Only flags are being updated — verify product exists
        exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
        if not exists:
            raise LookupError("Product not found")
    if incoming_flags is not None and isinstance(incoming_flags, list):
        _set_user_flags(conn, pid, incoming_flags)
    conn.commit()
    if from_off:
        set_system_flag(pid, "is_synced_with_off", True)


def delete_product(pid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
    return cur.rowcount > 0
