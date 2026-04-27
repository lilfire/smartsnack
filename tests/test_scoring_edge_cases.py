"""Extended scoring edge cases for product_scoring._score_product and _compute_completeness.

Tests cover:
- Weight = 0 (zero contribution)
- Weight > 100 (amplification)
- Weight < 100 (reduction)
- All fields missing → total_score = 0
- Partially missing fields
- Category overrides: disable field, change weight, change direction
- Direct formula: fmax <= fmin (skip field)
- Minmax formula: mn == mx (skip field)
- _compute_completeness boundary values
"""

import pytest


# ── Weight = 0 ────────────────────────────────────────────────────────────────


class TestWeightZero:
    def test_weight_zero_contributes_nothing_to_total(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 0.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 50, scores["protein"] = 50 * 0 / 100 = 0
        assert p["scores"]["protein"] == pytest.approx(0.0, abs=0.01)
        # total_score = (50 * 0) / (1 * 100) = 0
        assert p["total_score"] == pytest.approx(0.0, abs=0.01)

    def test_weight_zero_field_is_still_counted_in_num_scored(self):
        """A weight=0 field that has a value is scored (even though contribution = 0)."""
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0, "fat": 50.0}
        enabled_fields = ["protein", "fat"]
        enabled_weights = {"protein": 0.0, "fat": 100.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
            "fat": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # fat scores 50 (lower direction, val=50, range 0..100, raw=(100-50)/100=0.5)
        # total = (100*0 + 50*100) / (2*100) = 25
        assert p["total_score"] == pytest.approx(25.0, abs=0.5)


# ── Weight > 100 (amplification) ──────────────────────────────────────────────


class TestWeightAmplification:
    def test_weight_200_doubles_total_for_perfect_score(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 200.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 100, total_score = (100 * 200) / (1 * 100) = 200
        assert p["total_score"] == pytest.approx(200.0, abs=0.5)

    def test_weight_150_amplifies_total_above_raw_score(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 150.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 50, total_score = (50 * 150) / (1 * 100) = 75
        assert p["total_score"] == pytest.approx(75.0, abs=0.5)
        assert p["total_score"] > 50  # amplified above raw percentage


# ── Weight < 100 (reduction) ──────────────────────────────────────────────────


class TestWeightReduction:
    def test_weight_50_reduces_total_below_raw_score(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 50.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 100, total_score = (100 * 50) / (1 * 100) = 50
        assert p["total_score"] == pytest.approx(50.0, abs=0.5)
        assert p["total_score"] < 100  # reduced below perfect raw score

    def test_weight_25_quarter_reduces_total(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 25.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["total_score"] == pytest.approx(25.0, abs=0.5)


# ── All fields missing ────────────────────────────────────────────────────────


class TestAllFieldsMissing:
    def test_no_scoreable_fields_gives_zero_total(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks"}
        enabled_fields = ["protein", "fat"]
        enabled_weights = {"protein": 100.0, "fat": 100.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
            "fat": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["total_score"] == 0
        assert p["has_missing_scores"] is True
        assert set(p["missing_fields"]) == {"protein", "fat"}
        assert p["scores"] == {}

    def test_no_enabled_fields_gives_zero(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        _score_product(p, [], {}, {}, {})
        assert p["total_score"] == 0
        assert p["has_missing_scores"] is False

    def test_partial_fields_missing_flags_correct_fields(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 20.0}  # fat missing
        enabled_fields = ["protein", "fat"]
        enabled_weights = {"protein": 100.0, "fat": 100.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
            "fat": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 100,
            },
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["has_missing_scores"] is True
        assert "fat" in p["missing_fields"]
        assert "protein" not in p["missing_fields"]
        assert p["total_score"] > 0


# ── Category overrides ────────────────────────────────────────────────────────


class TestCategoryOverrides:
    _cfg = {
        "protein": {
            "direction": "higher",
            "formula": "direct",
            "formula_min": 0,
            "formula_max": 100,
        }
    }

    def test_override_disabled_field_is_skipped(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        category_overrides = {
            ("Snacks", "protein"): {
                "enabled": False,
                "weight": None,
                "direction": None,
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, self._cfg, {}, category_overrides)
        assert "protein" not in p["scores"]
        assert p["total_score"] == 0

    def test_override_changes_weight(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        category_overrides = {
            ("Snacks", "protein"): {
                "enabled": None,
                "weight": 200.0,
                "direction": None,
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, self._cfg, {}, category_overrides)
        # s=100, weight=200 → total = (100*200)/(1*100) = 200
        assert p["total_score"] == pytest.approx(200.0, abs=0.5)

    def test_override_changes_direction(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        # Default direction is "higher" → s=100
        # Override to "lower" → s=(100-100)/(100-0)=0
        category_overrides = {
            ("Snacks", "protein"): {
                "enabled": None,
                "weight": None,
                "direction": "lower",
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, self._cfg, {}, category_overrides)
        assert p["scores"]["protein"] == pytest.approx(0.0, abs=0.1)

    def test_override_for_different_category_does_not_apply(self):
        from services.product_scoring import _score_product

        p = {"type": "Drinks", "protein": 50.0}
        category_overrides = {
            ("Snacks", "protein"): {  # Snacks override, product is Drinks
                "enabled": False,
                "weight": None,
                "direction": None,
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, self._cfg, {}, category_overrides)
        assert "protein" in p["scores"]

    def test_no_override_when_category_overrides_is_none(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 100.0}
        _score_product(p, ["protein"], {"protein": 100.0}, self._cfg, {}, None)
        assert p["scores"]["protein"] == pytest.approx(100.0, abs=0.1)


# ── Direct formula: fmax <= fmin ──────────────────────────────────────────────


class TestDirectFormulaEdgeCases:
    def test_fmax_equals_fmin_field_skipped(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 10,
                "formula_max": 10,  # equal → skip
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, weight_config, {})
        assert p["total_score"] == 0

    def test_fmax_less_than_fmin_field_skipped(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 50.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 20,
                "formula_max": 5,  # less than min → skip
            }
        }
        _score_product(p, ["protein"], {"protein": 100.0}, weight_config, {})
        assert p["total_score"] == 0

    def test_direct_lower_direction_at_fmin_scores_100(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "salt": 0.0}
        weight_config = {
            "salt": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 5,
            }
        }
        _score_product(p, ["salt"], {"salt": 100.0}, weight_config, {})
        # raw = (5 - 0) / (5 - 0) = 1.0 → s = 100
        assert p["scores"]["salt"] == pytest.approx(100.0, abs=0.1)

    def test_direct_lower_direction_at_fmax_scores_0(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "salt": 5.0}
        weight_config = {
            "salt": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 5,
            }
        }
        _score_product(p, ["salt"], {"salt": 100.0}, weight_config, {})
        assert p["scores"]["salt"] == pytest.approx(0.0, abs=0.1)


# ── Minmax formula: zero range ────────────────────────────────────────────────


class TestMinmaxZeroRange:
    def test_min_equals_max_in_category_skips_field(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 10.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        # All products have protein=10 → mn=mx=10, range=0 → skip
        cat_ranges = {"Snacks": {"protein": (10.0, 10.0)}}
        _score_product(p, ["protein"], {"protein": 100.0}, weight_config, cat_ranges)
        assert p["total_score"] == 0

    def test_no_range_data_for_category_skips_field(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "protein": 10.0}
        weight_config = {
            "protein": {
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        # No range data for "Snacks" → defaults to (0, 0) → skip
        _score_product(p, ["protein"], {"protein": 100.0}, weight_config, {})
        assert p["total_score"] == 0

    def test_minmax_lower_direction_basic(self):
        from services.product_scoring import _score_product

        p = {"type": "Snacks", "fat": 5.0}
        weight_config = {
            "fat": {
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"fat": (0.0, 20.0)}}
        _score_product(p, ["fat"], {"fat": 100.0}, weight_config, cat_ranges)
        # raw = (20 - 5) / (20 - 0) = 0.75 → s = 75
        assert p["scores"]["fat"] == pytest.approx(75.0, abs=0.5)


# ── _compute_completeness ─────────────────────────────────────────────────────


class TestComputeCompleteness:
    def test_empty_product_returns_zero(self):
        from services.product_scoring import _compute_completeness
        assert _compute_completeness({}) == 0

    def test_fully_filled_product_returns_100(self):
        from services.product_scoring import _compute_completeness
        from config import COMPLETENESS_FIELDS
        p = {}
        for f in COMPLETENESS_FIELDS:
            if f == "image":
                p["has_image"] = True
            else:
                p[f] = "value"
        assert _compute_completeness(p) == 100

    def test_image_counted_via_has_image_flag(self):
        from services.product_scoring import _compute_completeness
        p_with = {"has_image": True}
        p_without = {"has_image": False}
        assert _compute_completeness(p_with) >= _compute_completeness(p_without)

    def test_none_values_not_counted(self):
        from services.product_scoring import _compute_completeness
        from config import COMPLETENESS_FIELDS
        p = {f: None for f in COMPLETENESS_FIELDS if f != "image"}
        assert _compute_completeness(p) == 0

    def test_partial_fill_returns_partial_score(self):
        from services.product_scoring import _compute_completeness
        from config import COMPLETENESS_FIELDS
        non_image = [f for f in COMPLETENESS_FIELDS if f != "image"]
        if not non_image:
            pytest.skip("No non-image completeness fields")
        p = {non_image[0]: "value"}
        result = _compute_completeness(p)
        assert 0 < result < 100
