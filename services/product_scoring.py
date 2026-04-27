"""Scoring formula and weight computation for products."""

import sqlite3

from config import (
    SCORE_CONFIG_MAP,
    COMPLETENESS_FIELDS,
    COMPUTED_FIELDS,
    _VALID_COLUMNS,
)

_weight_cache: tuple | None = None
_weight_cache_version: int | None = None
_range_cache: dict | None = None  # keyed by frozenset(enabled_fields)
_range_cache_key: frozenset | None = None
_range_cache_version: int | None = None


def _db_data_version(cur: sqlite3.Cursor) -> int:
    """Return SQLite's data_version, which bumps on every cross-connection commit.

    Used as the cache key so that all Gunicorn workers detect writes made by
    any other worker (a TTL-only cache stays stale on non-writer workers).
    """
    return cur.execute("PRAGMA data_version").fetchone()[0]


def invalidate_scoring_cache() -> None:
    """Invalidate all in-process scoring caches.

    Cross-worker invalidation is handled by the data_version cache key in
    `_load_weight_config` / `_compute_category_ranges`; this function only
    clears the local process's caches (e.g. for tests or a same-process write).
    """
    global _weight_cache, _weight_cache_version, _range_cache, _range_cache_key, _range_cache_version
    _weight_cache = None
    _weight_cache_version = None
    _range_cache = None
    _range_cache_key = None
    _range_cache_version = None


def _load_weight_config(cur: sqlite3.Cursor) -> tuple:
    """Load score weights and their config from the database.

    Returns (enabled_weights, weight_config, enabled_fields, category_overrides).
    enabled_fields is the union of globally-enabled and override-enabled fields,
    so range computation covers any field a category override may switch on.
    Each weight_config entry carries a `globally_enabled` flag so that
    `_score_product` can gate per-product on the effective (global ∨ override) state.
    category_overrides is keyed by (category, field).
    """
    global _weight_cache, _weight_cache_version
    db_version = _db_data_version(cur)
    if _weight_cache is not None and _weight_cache_version == db_version:
        return _weight_cache
    weight_rows = cur.execute(
        "SELECT field, enabled, weight, direction, formula, "
        "formula_min, formula_max FROM score_weights"
    ).fetchall()
    global_map = {}
    for r in weight_rows:
        if r["field"] not in SCORE_CONFIG_MAP:
            continue
        global_map[r["field"]] = {
            "enabled": bool(r["enabled"]),
            "weight": r["weight"],
            "direction": r["direction"],
            "formula": r["formula"],
            "formula_min": r["formula_min"],
            "formula_max": r["formula_max"],
        }

    try:
        ov_rows = cur.execute(
            "SELECT category, field, enabled, weight, direction, formula, "
            "formula_min, formula_max FROM category_score_weights"
        ).fetchall()
    except Exception:
        ov_rows = []
    category_overrides = {}
    override_enabled_fields = set()
    for r in ov_rows:
        category_overrides[(r["category"], r["field"])] = {
            "enabled": r["enabled"],
            "weight": r["weight"],
            "direction": r["direction"],
            "formula": r["formula"],
            "formula_min": r["formula_min"],
            "formula_max": r["formula_max"],
        }
        if r["enabled"] and r["field"] in SCORE_CONFIG_MAP:
            override_enabled_fields.add(r["field"])

    enabled_fields = [
        f for f, g in global_map.items()
        if g["enabled"] or f in override_enabled_fields
    ]
    enabled_weights = {f: global_map[f]["weight"] for f in enabled_fields}
    weight_config = {
        f: {
            "direction": global_map[f]["direction"],
            "formula": global_map[f]["formula"],
            "formula_min": global_map[f]["formula_min"],
            "formula_max": global_map[f]["formula_max"],
            "globally_enabled": global_map[f]["enabled"],
        }
        for f in enabled_fields
    }

    _weight_cache = (enabled_weights, weight_config, enabled_fields, category_overrides)
    _weight_cache_version = db_version
    return _weight_cache


def _compute_category_ranges(
    cur: sqlite3.Cursor,
    enabled_fields: list,
) -> dict:
    """Compute min/max ranges per category for minmax scoring."""
    global _range_cache, _range_cache_key, _range_cache_version
    db_version = _db_data_version(cur)
    cache_key = frozenset(enabled_fields)
    if (
        _range_cache is not None
        and _range_cache_key == cache_key
        and _range_cache_version == db_version
    ):
        return _range_cache
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
    _range_cache = cat_ranges
    _range_cache_key = cache_key
    _range_cache_version = db_version
    return _range_cache


def _score_product(
    p: dict,
    enabled_fields: list,
    enabled_weights: dict,
    weight_config: dict,
    cat_ranges: dict,
    category_overrides: dict | None = None,
) -> None:
    """Compute and attach scores to a product dict in-place.

    Category overrides are *exclusive*: as soon as the product's category has
    any row in category_score_weights, only those override-enabled fields are
    scored for that product — the global enabled set is ignored. Categories
    with no override rows fall back to the global enabled set.
    """
    scores = {}
    weighted_score_sum = 0.0
    num_scored_fields = 0
    missing_fields = []
    ranges = cat_ranges.get(p["type"], {})
    product_category = p.get("type", "")

    # Collect every override row for this product's category. The mere presence
    # of any row flips the product into exclusive mode (override list replaces
    # the global enabled set); the per-row `enabled` flag then gates each field.
    ov_for_cat: dict = {}
    if category_overrides and product_category:
        for (c, f), data in category_overrides.items():
            if c == product_category:
                ov_for_cat[f] = data
    has_category_override = bool(ov_for_cat)

    for field in enabled_fields:
        cfg = dict(weight_config[field])
        # Default True preserves backward compat for callers (and tests) that build
        # weight_config by hand without the flag — those only pass globally-enabled fields.
        globally_enabled = cfg.pop("globally_enabled", True)
        weight = enabled_weights[field]

        if has_category_override:
            ov = ov_for_cat.get(field)
            if ov is None:
                # Field not in this category's override list — exclusive mode skips it.
                continue
            if ov["enabled"] is not None and not ov["enabled"]:
                # Override row exists but explicitly disables the field.
                continue
            if ov["weight"] is not None:
                weight = ov["weight"]
            if ov["direction"] is not None:
                cfg["direction"] = ov["direction"]
            if ov["formula"] is not None:
                cfg["formula"] = ov["formula"]
            if ov["formula_min"] is not None:
                cfg["formula_min"] = ov["formula_min"]
            if ov["formula_max"] is not None:
                cfg["formula_max"] = ov["formula_max"]
        elif not globally_enabled:
            # No category override for this product → fall back to globals.
            continue

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
