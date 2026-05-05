"""Tests for services/weight_service.py — score weight management."""

import pytest


class TestGetWeights:
    def test_returns_all_weights(self, app_ctx):
        from services.weight_service import get_weights
        from config import SCORE_CONFIG

        weights = get_weights()
        assert len(weights) == len(SCORE_CONFIG)
        for w in weights:
            assert "field" in w
            assert "enabled" in w
            assert "weight" in w
            assert "direction" in w
            assert "formula" in w

    def test_taste_score_enabled_by_default(self, app_ctx):
        from services.weight_service import get_weights

        weights = get_weights()
        taste = next(w for w in weights if w["field"] == "taste_score")
        assert taste["enabled"] is True
        assert taste["weight"] == 100.0


class TestUpdateWeights:
    def test_valid_update(self, app_ctx):
        from services.weight_service import update_weights, get_weights

        update_weights(
            [
                {
                    "field": "kcal",
                    "enabled": True,
                    "weight": 50.0,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }
            ]
        )
        weights = get_weights()
        kcal = next(w for w in weights if w["field"] == "kcal")
        assert kcal["enabled"] is True
        assert kcal["weight"] == 50.0

    def test_invalid_direction(self, app_ctx):
        from services.weight_service import update_weights

        with pytest.raises(ValueError, match="Invalid direction"):
            update_weights([{"field": "kcal", "direction": "sideways"}])

    def test_invalid_formula(self, app_ctx):
        from services.weight_service import update_weights

        with pytest.raises(ValueError, match="Invalid formula"):
            update_weights([{"field": "kcal", "formula": "invalid"}])

    def test_weight_out_of_range(self, app_ctx):
        from services.weight_service import update_weights

        with pytest.raises(ValueError, match="Weight must be between"):
            update_weights([{"field": "kcal", "weight": 5000}])

    def test_not_list_raises(self, app_ctx):
        from services.weight_service import update_weights

        with pytest.raises(ValueError, match="Expected array"):
            update_weights("not a list")

    def test_unknown_field_ignored(self, app_ctx):
        from services.weight_service import update_weights
        from db import get_db

        update_weights([{"field": "nonexistent_field", "weight": 10}])
        row = get_db().execute(
            "SELECT weight FROM score_weights WHERE field='nonexistent_field'"
        ).fetchone()
        assert row is None
