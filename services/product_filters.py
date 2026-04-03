"""Advanced filtering logic for products."""

import json
import math

from config import (
    ADVANCED_FILTER_OPS,
    TEXT_FIELDS,
    FILTERABLE_FIELDS,
    POST_QUERY_FIELDS,
    MAX_FILTER_DEPTH,
    MAX_FILTER_CONDITIONS,
)
from services import flag_service

_FLAG_FIELD_PREFIX = "flag:"

_OP_FNS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
}


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
    if op in ("is_not_set", "is_set"):
        return field, op, "", ADVANCED_FILTER_OPS[op]
    # Allow empty value for type field (uncategorized products)
    if field == "type" and op in ("=", "!=") and (value is None or str(value).strip() == ""):
        return field, op, "", ADVANCED_FILTER_OPS[op]
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

    if op == "is_not_set":
        if field in TEXT_FIELDS:
            return f"({field} IS NULL OR {field} = '')", None
        else:
            return f"{field} IS NULL", None

    if op == "is_set":
        if field in TEXT_FIELDS:
            return f"({field} IS NOT NULL AND {field} != '')", None
        else:
            return f"{field} IS NOT NULL", None

    if field in TEXT_FIELDS:
        if op == "contains":
            escaped = (
                value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            return f"LOWER({field}) LIKE ? ESCAPE '\\'", f"%{escaped.lower()}%"
        elif op == "!contains":
            escaped = (
                value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            return f"LOWER({field}) NOT LIKE ? ESCAPE '\\'", f"%{escaped.lower()}%"
        elif op in ("=", "!="):
            return f"LOWER({field}) {sql_op} LOWER(?)", value
        else:
            raise ValueError(f"Operator '{op}' not valid for text field '{field}'")
    else:
        if op in ("contains", "!contains"):
            raise ValueError(
                f"Operator '{op}' not valid for numeric field '{field}'"
            )
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
    For flag fields, returns (field, op, "true"/"false") where value is a string.
    """
    if field.startswith(_FLAG_FIELD_PREFIX):
        return field, op, value
    if op in ("is_not_set", "is_set"):
        return field, op, None
    if op in ("contains", "!contains"):
        raise ValueError(f"Operator '{op}' not valid for numeric field '{field}'")
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
                children.append(
                    {
                        "logic": g.get("logic", "and"),
                        "children": g["conditions"],
                    }
                )
        return {"logic": logic, "children": children}

    raise ValueError("Unrecognised filter format")


def _count_conditions(node: dict) -> int:
    """Recursively count leaf conditions in a filter tree."""
    if "field" in node:
        return 1
    return sum(
        _count_conditions(c) for c in node.get("children", []) if isinstance(c, dict)
    )


def _node_to_post(node: dict) -> dict:
    """Convert an entire filter node tree to a post-filter spec (no SQL)."""
    if "field" in node:
        field, op, value, _sql_op = _parse_condition(node)
        return {
            "field": field,
            "op": op,
            "val": _condition_to_post(field, op, value)[2],
        }

    logic = node.get("logic", "and").upper()
    children = node.get("children", [])
    post_children = [_node_to_post(c) for c in children if isinstance(c, dict)]
    return {"logic": logic, "children": post_children}


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
            return (
                None,
                [],
                {
                    "field": field,
                    "op": op,
                    "val": _condition_to_post(field, op, value)[2],
                },
            )
        frag, param = _condition_to_sql(field, op, value, sql_op)
        return f"({frag})", [] if param is None else [param], None

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
        post_node = (
            {"logic": logic, "children": post_parts}
            if len(post_parts) > 1
            else post_parts[0]
        )

    return sql_fragment, all_params, post_node


def _parse_advanced_filters(filters_json: str) -> tuple:
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


def _evaluate_post_node(node: dict, product: dict) -> bool:
    """Recursively evaluate a post-filter node against a product."""
    if "field" in node:
        field = node["field"]
        if field.startswith(_FLAG_FIELD_PREFIX):
            flag_name = field[len(_FLAG_FIELD_PREFIX):]
            has_flag = flag_name in (product.get("flags") or [])
            return has_flag if node["val"] == "true" else not has_flag
        pval = product.get(field)
        if node["op"] == "is_not_set":
            return pval is None or pval == ""
        if node["op"] == "is_set":
            return pval is not None and pval != ""
        if pval is None:
            return False
        return _OP_FNS[node["op"]](float(pval), node["val"])

    logic = node.get("logic", "AND")
    children = node.get("children", [])
    results = [_evaluate_post_node(c, product) for c in children]
    if not results:
        return True
    return all(results) if logic == "AND" else any(results)


def _apply_post_filters(results: list, post_filter_spec) -> list:
    """Filter results in Python for computed fields like total_score.

    post_filter_spec is a recursive node tree:
      {"logic": "AND", "children": [{"field":..,"op":..,"val":..}, ...]}
    or a single leaf: {"field":..,"op":..,"val":..}
    """
    if not post_filter_spec:
        return results
    return [p for p in results if _evaluate_post_node(post_filter_spec, p)]
