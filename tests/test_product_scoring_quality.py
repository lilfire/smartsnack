"""Quality audit tests for product scoring formula and edge cases.

These tests specifically verify:
- The weight-as-amplifier invariant (documented in CLAUDE.md)
- Minmax lower direction (previously uncovered)
- Invalid field validation in _compute_category_ranges
- Boundary value handling
- Multi-field scoring formula correctness
"""
import pytest


class TestScoreProductMinmaxLowerDirection:
    """Tests for minmax formula with lower direction (line 133 was uncovered)."""

    def test_minmax_lower_direction_basic(self):
        from services.product_service import _score_product

        # Lower direction: lower values are better
        # protein=5, range=[0,20], raw=(20-5)/(20-0)=0.75
        p = {"type": "Snacks", "protein": 5.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 100.0}
        weight_config = {
            "protein": {
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"protein": (0.0, 20.0)}}
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        # raw = (20 - 5) / (20 - 0) = 0.75, s = 75
        # scores["protein"] = 75 * 100 / 100 = 75.0
        assert p["scores"]["protein"] == pytest.approx(75.0, abs=0.1)
        assert p["total_score"] == pytest.approx(75.0, abs=0.1)

    def test_minmax_lower_direction_highest_value_scores_lowest(self):
        from services.product_service import _score_product

        # At max value, lower direction should score 0
        p = {"type": "Snacks", "fat": 20.0}
        enabled_fields = ["fat"]
        enabled_weights = {"fat": 100.0}
        weight_config = {
            "fat": {
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"fat": (0.0, 20.0)}}
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        # raw = (20 - 20) / (20 - 0) = 0.0
        assert p["scores"]["fat"] == pytest.approx(0.0, abs=0.1)

    def test_minmax_lower_direction_lowest_value_scores_highest(self):
        from services.product_service import _score_product

        # At min value, lower direction should score 100
        p = {"type": "Snacks", "fat": 0.0}
        enabled_fields = ["fat"]
        enabled_weights = {"fat": 100.0}
        weight_config = {
            "fat": {
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"fat": (0.0, 20.0)}}
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        # raw = (20 - 0) / (20 - 0) = 1.0
        assert p["scores"]["fat"] == pytest.approx(100.0, abs=0.1)

    def test_minmax_lower_clamped_above_max(self):
        from services.product_service import _score_product

        # Value above max: raw clamps to 0
        p = {"type": "Snacks", "fat": 30.0}
        enabled_fields = ["fat"]
        enabled_weights = {"fat": 100.0}
        weight_config = {
            "fat": {
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"fat": (0.0, 20.0)}}
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        # raw = (20 - 30) / (20 - 0) = -0.5, clamped to 0.0
        assert p["scores"]["fat"] == pytest.approx(0.0, abs=0.1)


class TestScoreProductWeightAsAmplifier:
    """Tests for the weight-as-amplifier invariant documented in CLAUDE.md.

    Weights > 100 amplify total_score above the field's raw percentage.
    Weights < 100 reduce it. This is intentional design.
    """

    def test_weight_200_amplifies_total_score(self):
        from services.product_service import _score_product

        # With direct formula: val at midpoint → s=50
        # weight=200: total_score = (50*200)/(1*100) = 100
        p = {"type": "Snacks", "taste_score": 3.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 200.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 50, total_score = (50 * 200) / (1 * 100) = 100
        assert p["total_score"] == pytest.approx(100.0, abs=0.5)

    def test_weight_50_reduces_total_score(self):
        from services.product_service import _score_product

        # With weight=50 and s=100 (perfect score):
        # total_score = (100*50)/(1*100) = 50
        p = {"type": "Snacks", "taste_score": 6.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 50.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 100, total_score = (100*50)/(1*100) = 50
        assert p["total_score"] == pytest.approx(50.0, abs=0.5)

    def test_weight_100_baseline_equals_field_percentage(self):
        from services.product_service import _score_product

        # weight=100 is baseline: total_score equals field raw percentage
        p = {"type": "Snacks", "taste_score": 3.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s = 50, total_score = (50*100)/(1*100) = 50
        assert p["total_score"] == pytest.approx(50.0, abs=0.5)

    def test_multi_field_denominator_is_num_scored_not_weight_sum(self):
        from services.product_service import _score_product

        # 2 fields with weight=100, both at max → each s=100
        # total_score = (100*100 + 100*100) / (2*100) = 20000/200 = 100
        p = {
            "type": "Snacks",
            "taste_score": 6.0,
            "salt": 0.0,  # lower direction
        }
        enabled_fields = ["taste_score", "salt"]
        enabled_weights = {"taste_score": 100.0, "salt": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            },
            "salt": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 5,
            },
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["total_score"] == pytest.approx(100.0, abs=0.5)
        assert len(p["scores"]) == 2

    def test_higher_weight_field_pulls_total_above_simple_average(self):
        from services.product_service import _score_product

        # Field A at s=100 with weight=200, Field B at s=0 (missing)
        # Only A is scored: total_score = (100*200)/(1*100) = 200, capped conceptually
        # But since scores are summed not averaged, this demonstrates amplification
        p = {"type": "Snacks", "taste_score": 6.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 200.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # s=100, total_score = (100*200)/(1*100) = 200 — shows weight amplification
        assert p["total_score"] > 100


class TestComputeCategoryRangesInvalidField:
    """Test invalid field validation (line 77 was uncovered)."""

    def test_invalid_field_raises_value_error(self, app_ctx, db):
        from services.product_service import _compute_category_ranges

        cur = db.cursor()
        with pytest.raises(ValueError, match="Invalid field"):
            _compute_category_ranges(cur, ["nonexistent_field_xyz"])

    def test_valid_field_does_not_raise(self, app_ctx, db):
        from services.product_service import _compute_category_ranges

        cur = db.cursor()
        # Should not raise
        ranges = _compute_category_ranges(cur, ["protein"])
        # Result can be empty dict if no products, or have ranges
        assert isinstance(ranges, dict)


class TestScoreProductBoundaryValues:
    """Tests for direct formula boundary values."""

    def test_direct_value_at_fmin_higher_scores_0(self):
        from services.product_service import _score_product

        p = {"type": "Snacks", "taste_score": 0.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["scores"]["taste_score"] == pytest.approx(0.0, abs=0.1)

    def test_direct_value_at_fmax_higher_scores_100(self):
        from services.product_service import _score_product

        p = {"type": "Snacks", "taste_score": 6.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["scores"]["taste_score"] == pytest.approx(100.0, abs=0.1)

    def test_direct_value_below_fmin_clamped_to_0(self):
        from services.product_service import _score_product

        p = {"type": "Snacks", "taste_score": -5.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # raw = (-5 - 0)/(6 - 0) = -0.83 → clamped to 0
        assert p["scores"]["taste_score"] == pytest.approx(0.0, abs=0.1)

    def test_direct_value_above_fmax_clamped_to_100(self):
        from services.product_service import _score_product

        p = {"type": "Snacks", "taste_score": 100.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # raw = (100 - 0)/(6 - 0) = 16.67 → clamped to 1.0
        assert p["scores"]["taste_score"] == pytest.approx(100.0, abs=0.1)
