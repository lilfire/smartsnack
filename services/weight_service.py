from db import get_db
from config import SCORE_CONFIG, SCORE_CONFIG_MAP
from translations import _t, _get_current_lang
from helpers import _safe_float


def get_weights():
    conn = get_db()
    rows = conn.execute("SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights ORDER BY field").fetchall()
    db_map = {r["field"]: {"enabled": bool(r["enabled"]), "weight": r["weight"], "direction": r["direction"], "formula": r["formula"], "formula_min": r["formula_min"], "formula_max": r["formula_max"]} for r in rows}
    lang = _get_current_lang()
    result = []
    for sc in SCORE_CONFIG:
        f = sc["field"]
        w = db_map.get(f, {"enabled": False, "weight": 0, "direction": sc["direction"], "formula": sc["formula"], "formula_min": sc["formula_min"], "formula_max": sc["formula_max"]})
        result.append({
            "field": f,
            "label": _t(sc["label_key"], lang),
            "desc": _t(sc["desc_key"], lang),
            "enabled": w["enabled"],
            "weight": w["weight"],
            "direction": w["direction"],
            "formula": w["formula"],
            "formula_min": w["formula_min"],
            "formula_max": w["formula_max"],
        })
    return result


def update_weights(data):
    if not isinstance(data, list):
        raise ValueError("Expected array of weights")
    conn = get_db()
    _VALID_DIRECTIONS = {"lower", "higher"}
    _VALID_FORMULAS = {"minmax", "direct"}
    for item in data:
        f = item.get("field", "")
        if f not in SCORE_CONFIG_MAP:
            continue
        direction = item.get("direction", SCORE_CONFIG_MAP[f]["direction"])
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}")
        formula = item.get("formula", SCORE_CONFIG_MAP[f]["formula"])
        if formula not in _VALID_FORMULAS:
            raise ValueError(f"Invalid formula: {formula}")
        formula_min = _safe_float(item.get("formula_min", 0), "formula_min")
        formula_max = _safe_float(item.get("formula_max", 0), "formula_max")
        weight = _safe_float(item.get("weight", 0), "weight")
        if not (0 <= weight <= 1000):
            raise ValueError("Weight must be between 0 and 1000")
        enabled = 1 if item.get("enabled") else 0
        conn.execute(
            "INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(field) DO UPDATE SET enabled=excluded.enabled, weight=excluded.weight, direction=excluded.direction, formula=excluded.formula, formula_min=excluded.formula_min, formula_max=excluded.formula_max",
            (f, enabled, weight, direction, formula, formula_min, formula_max)
        )
    conn.commit()
