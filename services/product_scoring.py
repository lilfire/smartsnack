"""Scoring formula and weight computation for products."""

import sqlite3

from config import (
    SCORE_CONFIG_MAP,
    COMPLETENESS_FIELDS,
    COMPUTED_FIELDS,
    _VALID_COLUMNS,
)


def _load_weight_config(cur: sqlite3.Cursor) -> tuple:
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
    cur: sqlite3.Cursor,
    enabled_fields: list,
) -> dict:
    """Compute min/max ranges per category for minmax scoring."""
    cat_ranges = {}
    db_fields = [f for f in enabled_fields if f not in COMPUTED_FIELDS]
    if db_fields:
        for f in db_fields:
            if f not in _VALID_COLUMNS:
                raise ValueError(f"Invalid field: {f!r}")
        agg = ", ".join(f"MIN({f}) as min_{f}, MAX({f}) as max_{f}" for f in db_fields)
        type_rows = cur.execute(
            f"SELECT type, {agg} FROM products GROUP BY type"
        ).fetchall()
        for tr in type_rows:
            cat_ranges[tr["type"]] = {
                f: (tr[f"min_{f}"] or 0, tr[f"max_{f}"] or 0) for f in db_fields
            }
    return cat_ranges


def _score_product(
    p: dict,
    enabled_fields: list,
    enabled_weights: dict,
    weight_config: dict,
    cat_ranges: dict,
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
        if num_scored_fields > 0
        else 0
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
