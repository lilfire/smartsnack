"""Edge case tests for product scoring formula (services/product_scoring.py).

Covers scenarios not addressed in test_product_scoring_quality.py:
- All scoring fields disabled
- Mix of weights > 100 and < 100 simultaneously
- Extreme weight values (0, 1000)
- Products with only 1 scored field
"""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _direct_cfg(direction="higher", fmin=0, fmax=100):
    return {"direction": direction, "formula": "direct", "formula_min": fmin, "formula_max": fmax}


def _score(product, fields, weights, weight_config, cat_ranges=None):
    from services.product_scoring import _score_product
    _score_product(product, fields, weights, weight_config, cat_ranges or {})
    return product


# ---------------------------------------------------------------------------
# All scoring fields disabled
# ---------------------------------------------------------------------------


class TestAllFieldsDisabled:
    """When enabled_fields is empty, total_score must be 0 and scores must be {}."""

    def test_total_score_is_zero(self):
        p = {"type": "Snacks", "protein": 20, "kcal": 200}
        result = _score(p, [], {}, {})
        assert result["total_score"] == 0

    def test_scores_dict_is_empty(self):
        p = {"type": "Snacks", "protein": 20}
        result = _score(p, [], {}, {})
        assert result["scores"] == {}

    def test_missing_fields_is_empty(self):
        p = {"type": "Snacks"}
        result = _score(p, [], {}, {})
        assert result["missing_fields"] == []

    def test_has_missing_scores_is_false(self):
        p = {"type": "Snacks"}
        result = _score(p, [], {}, {})
        assert result["has_missing_scores"] is False


# ---------------------------------------------------------------------------
# Mix of weights > 100 and < 100
# ---------------------------------------------------------------------------


class TestMixedWeights:
    """Weight > 100 amplifies, weight < 100 reduces relative to baseline."""

    def test_high_and_low_weight_cancel_to_baseline(self):
        # Field A: weight=200, s=50 → contribution 200*50=10000
        # Field B: weight=0, s=100 → contribution 0*100=0
        # total_score = (10000 + 0) / (2 * 100) = 50
        p = {"type": "Snacks", "protein": 5.0, "kcal": 100.0}
        fields = ["protein", "kcal"]
        weights = {"protein": 200.0, "kcal": 0.0}
        cfg = {
            "protein": _direct_cfg("higher", 0, 10),
            "kcal": _direct_cfg("higher", 0, 100),
        }
        result = _score(p, fields, weights, cfg)
        # protein: raw=(5-0)/(10-0)=0.5, s=50, contribution=50*200=10000
        # kcal: weight=0 → skip (fmax > fmin but weight contributes 0*s)
        # total = 10000/(1*100)=100? No wait...
        # Actually: kcal weight=0, so scores["kcal"] = round(s * 0 / 100, 1) = 0
        # weighted_score_sum += s * 0 = 0, num_scored_fields += 1
        # total = (10000 + 0) / (2 * 100) = 50
        assert result["scores"]["protein"] == pytest.approx(100.0, abs=0.5)  # 50 * 200 / 100 = 100
        assert result["scores"]["kcal"] == pytest.approx(0.0, abs=0.1)      # 100 * 0 / 100 = 0
        assert result["total_score"] == pytest.approx(50.0, abs=0.5)        # (50*200 + 100*0)/(2*100)

    def test_weight_above_100_scores_above_weight_100_baseline(self):
        p = {"type": "Snacks", "protein": 10.0}
        fields = ["protein"]
        weights_high = {"protein": 150.0}
        weights_base = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        r_high = _score(dict(p), fields, weights_high, cfg)
        r_base = _score(dict(p), fields, weights_base, cfg)
        assert r_high["total_score"] > r_base["total_score"]

    def test_weight_below_100_scores_below_weight_100_baseline(self):
        p = {"type": "Snacks", "protein": 10.0}
        fields = ["protein"]
        weights_low = {"protein": 50.0}
        weights_base = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        r_low = _score(dict(p), fields, weights_low, cfg)
        r_base = _score(dict(p), fields, weights_base, cfg)
        assert r_low["total_score"] < r_base["total_score"]

    def test_mix_high_and_low_weights_average_effect(self):
        # Two fields: one weight=200, one weight=50
        # Both at max → s=100 each
        # total = (100*200 + 100*50) / (2*100) = 25000/200 = 125
        p = {"type": "Snacks", "protein": 10.0, "fat": 0.0}
        fields = ["protein", "fat"]
        weights = {"protein": 200.0, "fat": 50.0}
        cfg = {
            "protein": _direct_cfg("higher", 0, 10),
            "fat": _direct_cfg("lower", 0, 5),
        }
        result = _score(p, fields, weights, cfg)
        # protein: s=100, fat: raw=(5-0)/(5-0)=1.0, s=100
        assert result["total_score"] == pytest.approx(125.0, abs=0.5)


# ---------------------------------------------------------------------------
# Extreme weight values
# ---------------------------------------------------------------------------


class TestExtremeWeights:
    """Test with extreme weight values: 0, 1, 1000."""

    def test_weight_zero_field_scores_zero_and_does_not_dominate(self):
        # weight=0: score contribution is 0, but field is still counted
        p = {"type": "Snacks", "protein": 10.0, "fat": 5.0}
        fields = ["protein", "fat"]
        weights = {"protein": 0.0, "fat": 100.0}
        cfg = {
            "protein": _direct_cfg("higher", 0, 10),
            "fat": _direct_cfg("lower", 0, 10),
        }
        result = _score(p, fields, weights, cfg)
        assert result["scores"]["protein"] == pytest.approx(0.0, abs=0.1)
        # fat: s = 50 (val=5 at midpoint of [0,10]), weight=100
        # total = (0 + 50*100) / (2*100) = 25
        assert result["total_score"] == pytest.approx(25.0, abs=0.5)

    def test_weight_one_field_has_minimal_effect(self):
        p = {"type": "Snacks", "protein": 10.0}
        fields = ["protein"]
        weights = {"protein": 1.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        # s=100, total = 100*1 / (1*100) = 1.0
        assert result["total_score"] == pytest.approx(1.0, abs=0.1)

    def test_weight_1000_amplifies_score_massively(self):
        p = {"type": "Snacks", "protein": 10.0}
        fields = ["protein"]
        weights = {"protein": 1000.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        # s=100, total = 100*1000 / (1*100) = 1000
        assert result["total_score"] == pytest.approx(1000.0, abs=0.5)

    def test_weight_1000_with_low_value_still_amplifies(self):
        p = {"type": "Snacks", "protein": 5.0}
        fields = ["protein"]
        weights = {"protein": 1000.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        # s=50, total = 50*1000 / (1*100) = 500
        assert result["total_score"] == pytest.approx(500.0, abs=0.5)


# ---------------------------------------------------------------------------
# Only 1 scored field
# ---------------------------------------------------------------------------


class TestSingleScoredField:
    """With only 1 field, denominator is 1*100 and total_score equals that field's score."""

    def test_single_field_total_matches_weighted_score(self):
        p = {"type": "Snacks", "protein": 8.0}
        fields = ["protein"]
        weights = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        # s=80, scores["protein"]=80, total=80*100/(1*100)=80
        assert result["scores"]["protein"] == pytest.approx(80.0, abs=0.1)
        assert result["total_score"] == pytest.approx(80.0, abs=0.1)

    def test_single_field_missing_yields_zero_total(self):
        p = {"type": "Snacks"}  # protein is absent
        fields = ["protein"]
        weights = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        assert result["total_score"] == 0
        assert result["missing_fields"] == ["protein"]
        assert result["has_missing_scores"] is True

    def test_single_field_at_minimum_scores_zero(self):
        p = {"type": "Snacks", "protein": 0.0}
        fields = ["protein"]
        weights = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        assert result["total_score"] == pytest.approx(0.0, abs=0.1)

    def test_single_field_at_maximum_scores_100_with_weight_100(self):
        p = {"type": "Snacks", "protein": 10.0}
        fields = ["protein"]
        weights = {"protein": 100.0}
        cfg = {"protein": _direct_cfg("higher", 0, 10)}
        result = _score(p, fields, weights, cfg)
        assert result["total_score"] == pytest.approx(100.0, abs=0.1)
