"""Tests for services/category_weight_service.py and related blueprint routes."""

import pytest


class TestGetCategoryWeights:
    def test_returns_none_for_unknown_category(self, app_ctx):
        from services.category_weight_service import get_category_weights

        assert get_category_weights("NonExistent") is None

    def test_returns_list_for_existing_category(self, app_ctx, seed_category):
        from services.category_weight_service import get_category_weights
        from config import SCORE_CONFIG

        result = get_category_weights(seed_category)
        assert isinstance(result, list)
        assert len(result) == len(SCORE_CONFIG)

    def test_all_entries_have_required_keys(self, app_ctx, seed_category):
        from services.category_weight_service import get_category_weights

        result = get_category_weights(seed_category)
        for entry in result:
            assert "field" in entry
            assert "enabled" in entry
            assert "weight" in entry
            assert "direction" in entry
            assert "formula" in entry
            assert "formula_min" in entry
            assert "formula_max" in entry
            assert "is_overridden" in entry

    def test_no_overrides_returns_is_overridden_false(self, app_ctx, seed_category):
        from services.category_weight_service import get_category_weights

        result = get_category_weights(seed_category)
        for entry in result:
            assert entry["is_overridden"] is False

    def test_override_appears_as_is_overridden_true(self, app_ctx, seed_category, db):
        from services.category_weight_service import get_category_weights, update_category_weights

        update_category_weights(
            seed_category,
            [{"field": "kcal", "enabled": True, "weight": 200.0,
              "direction": "lower", "formula": "minmax",
              "formula_min": 0, "formula_max": 0, "is_overridden": True}],
        )
        result = get_category_weights(seed_category)
        kcal = next(e for e in result if e["field"] == "kcal")
        assert kcal["is_overridden"] is True
        assert kcal["weight"] == 200.0
        assert kcal["enabled"] is True

    def test_global_value_used_when_not_overridden(self, app_ctx, seed_category):
        from services.category_weight_service import get_category_weights
        from services.weight_service import get_weights

        global_weights = {w["field"]: w for w in get_weights()}
        result = get_category_weights(seed_category)
        taste = next(e for e in result if e["field"] == "taste_score")
        g = global_weights["taste_score"]
        assert taste["enabled"] == g["enabled"]
        assert taste["weight"] == g["weight"]


class TestUpdateCategoryWeights:
    def test_raises_for_non_list(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        with pytest.raises(ValueError, match="Expected array"):
            update_category_weights(seed_category, "not a list")

    def test_raises_for_unknown_category(self, app_ctx):
        from services.category_weight_service import update_category_weights

        with pytest.raises(LookupError):
            update_category_weights("DoesNotExist", [])

    def test_raises_for_invalid_field(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        with pytest.raises(ValueError, match="Invalid field"):
            update_category_weights(
                seed_category,
                [{"field": "not_a_real_field", "is_overridden": True}],
            )

    def test_raises_for_invalid_direction(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        with pytest.raises(ValueError, match="Invalid direction"):
            update_category_weights(
                seed_category,
                [{"field": "kcal", "direction": "sideways", "is_overridden": True}],
            )

    def test_raises_for_invalid_formula(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        with pytest.raises(ValueError, match="Invalid formula"):
            update_category_weights(
                seed_category,
                [{"field": "kcal", "formula": "magic", "is_overridden": True}],
            )

    def test_raises_for_weight_out_of_range(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        with pytest.raises(ValueError, match="Weight must be between"):
            update_category_weights(
                seed_category,
                [{"field": "kcal", "weight": 9999, "is_overridden": True}],
            )

    def test_upsert_creates_override(self, app_ctx, seed_category, db):
        from services.category_weight_service import update_category_weights

        update_category_weights(
            seed_category,
            [{"field": "protein", "enabled": True, "weight": 150.0,
              "direction": "higher", "formula": "minmax",
              "formula_min": 0, "formula_max": 0, "is_overridden": True}],
        )
        row = db.execute(
            "SELECT * FROM category_score_weights WHERE category=? AND field=?",
            (seed_category, "protein"),
        ).fetchone()
        assert row is not None
        assert row["weight"] == 150.0

    def test_delete_removes_override(self, app_ctx, seed_category, db):
        from services.category_weight_service import update_category_weights

        update_category_weights(
            seed_category,
            [{"field": "protein", "enabled": True, "weight": 150.0,
              "direction": "higher", "formula": "minmax",
              "formula_min": 0, "formula_max": 0, "is_overridden": True}],
        )
        update_category_weights(
            seed_category,
            [{"field": "protein", "is_overridden": False}],
        )
        row = db.execute(
            "SELECT * FROM category_score_weights WHERE category=? AND field=?",
            (seed_category, "protein"),
        ).fetchone()
        assert row is None

    def test_empty_list_is_noop(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights

        update_category_weights(seed_category, [])

    def test_invalidates_scoring_cache(self, app_ctx, seed_category):
        from services.category_weight_service import update_category_weights
        import services.product_scoring as ps

        ps._weight_cache = ("dummy",)
        update_category_weights(seed_category, [])
        assert ps._weight_cache is None


class TestCategoryWeightsBlueprintGet:
    def test_404_for_missing_category(self, client):
        resp = client.get("/api/categories/NonExistent/weights")
        assert resp.status_code == 404

    def test_200_for_existing_category(self, client):
        resp = client.get("/api/categories/Snacks/weights")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_response_has_is_overridden(self, client):
        resp = client.get("/api/categories/Snacks/weights")
        data = resp.get_json()
        for entry in data:
            assert "is_overridden" in entry

    def test_400_for_invalid_name(self, client):
        resp = client.get("/api/categories/\x00bad/weights")
        assert resp.status_code == 400


class TestCategoryWeightsBlueprintPut:
    def test_400_for_non_json(self, client):
        resp = client.put(
            "/api/categories/Snacks/weights",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_400_for_invalid_field(self, client):
        resp = client.put(
            "/api/categories/Snacks/weights",
            json=[{"field": "bad_field", "is_overridden": True}],
        )
        assert resp.status_code == 400

    def test_404_for_unknown_category(self, client):
        resp = client.put(
            "/api/categories/NonExistent/weights",
            json=[{"field": "kcal", "is_overridden": False}],
        )
        assert resp.status_code == 404

    def test_200_on_valid_override(self, client):
        resp = client.put(
            "/api/categories/Snacks/weights",
            json=[
                {
                    "field": "kcal",
                    "enabled": True,
                    "weight": 200.0,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                    "is_overridden": True,
                }
            ],
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_roundtrip_get_after_put(self, client):
        client.put(
            "/api/categories/Snacks/weights",
            json=[
                {
                    "field": "sugar",
                    "enabled": True,
                    "weight": 75.0,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                    "is_overridden": True,
                }
            ],
        )
        resp = client.get("/api/categories/Snacks/weights")
        data = resp.get_json()
        sugar = next(e for e in data if e["field"] == "sugar")
        assert sugar["is_overridden"] is True
        assert sugar["weight"] == 75.0


class TestScoringWithCategoryOverrides:
    def test_category_override_affects_score(self, app_ctx, db, seed_category):
        from services.product_scoring import _score_product

        enabled_weights = {"kcal": 100.0}
        weight_config = {
            "kcal": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 500,
            }
        }
        enabled_fields = ["kcal"]
        category_overrides = {
            (seed_category, "kcal"): {
                "enabled": 1,
                "weight": 200.0,
                "direction": None,
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        p = {"type": seed_category, "kcal": 100.0}
        _score_product(p, enabled_fields, enabled_weights, weight_config, {}, category_overrides)
        assert p["scores"]["kcal"] > 0

    def test_override_disabled_skips_field(self, app_ctx, seed_category):
        from services.product_scoring import _score_product

        enabled_weights = {"kcal": 100.0}
        weight_config = {
            "kcal": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 500,
            }
        }
        enabled_fields = ["kcal"]
        category_overrides = {
            (seed_category, "kcal"): {
                "enabled": 0,
                "weight": None,
                "direction": None,
                "formula": None,
                "formula_min": None,
                "formula_max": None,
            }
        }
        p = {"type": seed_category, "kcal": 100.0}
        _score_product(p, enabled_fields, enabled_weights, weight_config, {}, category_overrides)
        assert "kcal" not in p["scores"]
        assert p["total_score"] == 0

    def test_no_override_uses_global(self, app_ctx, seed_category):
        from services.product_scoring import _score_product

        enabled_weights = {"kcal": 100.0}
        weight_config = {
            "kcal": {
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 500,
            }
        }
        p = {"type": seed_category, "kcal": 100.0}
        _score_product(p, ["kcal"], enabled_weights, weight_config, {}, {})
        assert "kcal" in p["scores"]
