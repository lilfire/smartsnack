"""Service for managing per-category score weight overrides."""

from config import SCORE_CONFIG, SCORE_CONFIG_MAP
from db import get_db
from helpers import _safe_float
from services.product_scoring import invalidate_scoring_cache

_VALID_DIRECTIONS = frozenset({"lower", "higher"})
_VALID_FORMULAS = frozenset({"minmax", "direct"})


def get_category_weights(category_name: str) -> list | None:
    """Return full list of score fields with effective values and is_overridden flag.

    Returns None if the category does not exist.
    Each entry shows the effective value (override if present, else global default)
    and an is_overridden flag.
    """
    conn = get_db()
    cat = conn.execute(
        "SELECT name FROM categories WHERE name = ?", (category_name,)
    ).fetchone()
    if cat is None:
        return None

    global_rows = conn.execute(
        "SELECT field, enabled, weight, direction, formula, formula_min, formula_max "
        "FROM score_weights"
    ).fetchall()
    global_map = {
        r["field"]: {
            "enabled": bool(r["enabled"]),
            "weight": r["weight"],
            "direction": r["direction"],
            "formula": r["formula"],
            "formula_min": r["formula_min"],
            "formula_max": r["formula_max"],
        }
        for r in global_rows
    }

    override_rows = conn.execute(
        "SELECT field, enabled, weight, direction, formula, formula_min, formula_max "
        "FROM category_score_weights WHERE category = ?",
        (category_name,),
    ).fetchall()
    override_map = {
        r["field"]: {
            "enabled": r["enabled"],
            "weight": r["weight"],
            "direction": r["direction"],
            "formula": r["formula"],
            "formula_min": r["formula_min"],
            "formula_max": r["formula_max"],
        }
        for r in override_rows
    }

    result = []
    for sc in SCORE_CONFIG:
        f = sc["field"]
        g = global_map.get(
            f,
            {
                "enabled": False,
                "weight": 0,
                "direction": sc["direction"],
                "formula": sc["formula"],
                "formula_min": sc["formula_min"],
                "formula_max": sc["formula_max"],
            },
        )
        is_overridden = f in override_map
        ov = override_map.get(f, {})

        def _pick(key, global_val):
            if is_overridden and ov.get(key) is not None:
                return ov[key]
            return global_val

        result.append(
            {
                "field": f,
                "enabled": bool(_pick("enabled", g["enabled"])),
                "weight": _pick("weight", g["weight"]),
                "direction": _pick("direction", g["direction"]),
                "formula": _pick("formula", g["formula"]),
                "formula_min": _pick("formula_min", g["formula_min"]),
                "formula_max": _pick("formula_max", g["formula_max"]),
                "is_overridden": is_overridden,
            }
        )

    return result


def update_category_weights(category_name: str, data: list) -> None:
    """Upsert or delete per-category score weight overrides.

    For each item:
    - is_overridden=True  → UPSERT row into category_score_weights
    - is_overridden=False → DELETE row from category_score_weights

    Raises ValueError for invalid input. Raises LookupError if category not found.
    """
    if not isinstance(data, list):
        raise ValueError("Expected array of weights")

    conn = get_db()
    cat = conn.execute(
        "SELECT name FROM categories WHERE name = ?", (category_name,)
    ).fetchone()
    if cat is None:
        raise LookupError(f"Category not found: {category_name!r}")

    for item in data:
        f = item.get("field", "")
        if f not in SCORE_CONFIG_MAP:
            raise ValueError(f"Invalid field: {f!r}")

        is_overridden = item.get("is_overridden", False)
        if not is_overridden:
            conn.execute(
                "DELETE FROM category_score_weights WHERE category = ? AND field = ?",
                (category_name, f),
            )
        else:
            sc = SCORE_CONFIG_MAP[f]
            direction = item.get("direction", sc["direction"])
            if direction not in _VALID_DIRECTIONS:
                raise ValueError(f"Invalid direction: {direction!r}")
            formula = item.get("formula", sc["formula"])
            if formula not in _VALID_FORMULAS:
                raise ValueError(f"Invalid formula: {formula!r}")
            formula_min = _safe_float(
                item.get("formula_min", sc["formula_min"]), "formula_min"
            )
            formula_max = _safe_float(
                item.get("formula_max", sc["formula_max"]), "formula_max"
            )
            weight = _safe_float(item.get("weight", 0), "weight")
            if not (0 <= weight <= 1000):
                raise ValueError("Weight must be between 0 and 1000")
            enabled = 1 if item.get("enabled") else 0
            conn.execute(
                "INSERT INTO category_score_weights "
                "(category, field, enabled, weight, direction, formula, formula_min, formula_max) "
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(category, field) DO UPDATE SET "
                "enabled=excluded.enabled, weight=excluded.weight, "
                "direction=excluded.direction, formula=excluded.formula, "
                "formula_min=excluded.formula_min, formula_max=excluded.formula_max",
                (
                    category_name,
                    f,
                    enabled,
                    weight,
                    direction,
                    formula,
                    formula_min,
                    formula_max,
                ),
            )

    conn.commit()
    invalidate_scoring_cache()
