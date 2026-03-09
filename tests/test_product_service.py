"""Tests for services/product_service.py — scoring engine and product CRUD."""

import pytest


class TestLoadWeightConfig:
    def test_returns_enabled_weights(self, db):
        from services.product_service import _load_weight_config
        cur = db.cursor()
        enabled_weights, weight_config, enabled_fields = _load_weight_config(cur)
        # taste_score is enabled by default
        assert "taste_score" in enabled_weights
        assert "taste_score" in weight_config
        assert "taste_score" in enabled_fields

    def test_disabled_weights_excluded(self, db):
        from services.product_service import _load_weight_config
        cur = db.cursor()
        # kcal is disabled by default
        enabled_weights, _, _ = _load_weight_config(cur)
        assert "kcal" not in enabled_weights


class TestScoreProduct:
    def test_direct_formula_higher(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "taste_score": 4.5}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher", "formula": "direct",
                "formula_min": 0, "formula_max": 6,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["total_score"] > 0
        assert "taste_score" in p["scores"]
        assert not p["has_missing_scores"]

    def test_direct_formula_lower(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "salt": 1.0}
        enabled_fields = ["salt"]
        enabled_weights = {"salt": 50.0}
        weight_config = {
            "salt": {
                "direction": "lower", "formula": "direct",
                "formula_min": 0, "formula_max": 5,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        # Lower salt should score higher when direction is "lower"
        assert p["scores"]["salt"] > 0

    def test_minmax_formula(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "protein": 15.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 80.0}
        weight_config = {
            "protein": {
                "direction": "higher", "formula": "minmax",
                "formula_min": 0, "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"protein": (5.0, 25.0)}}
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        # protein=15 in range [5,25] => raw = (15-5)/(25-5) = 0.5
        assert p["scores"]["protein"] == pytest.approx(40.0, abs=0.1)

    def test_missing_field(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "protein": None}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 80.0}
        weight_config = {
            "protein": {
                "direction": "higher", "formula": "minmax",
                "formula_min": 0, "formula_max": 0,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["has_missing_scores"]
        assert "protein" in p["missing_fields"]
        assert p["total_score"] == 0

    def test_zero_range_skipped(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "protein": 10.0}
        enabled_fields = ["protein"]
        enabled_weights = {"protein": 80.0}
        weight_config = {
            "protein": {
                "direction": "higher", "formula": "minmax",
                "formula_min": 0, "formula_max": 0,
            }
        }
        cat_ranges = {"Snacks": {"protein": (10.0, 10.0)}}  # zero range
        _score_product(p, enabled_fields, enabled_weights, weight_config, cat_ranges)
        assert p["total_score"] == 0

    def test_direct_formula_max_le_min_skipped(self):
        from services.product_service import _score_product
        p = {"type": "Snacks", "taste_score": 3.0}
        enabled_fields = ["taste_score"]
        enabled_weights = {"taste_score": 100.0}
        weight_config = {
            "taste_score": {
                "direction": "higher", "formula": "direct",
                "formula_min": 5, "formula_max": 5,
            }
        }
        _score_product(p, enabled_fields, enabled_weights, weight_config, {})
        assert p["total_score"] == 0


class TestComputeCategoryRanges:
    def test_returns_ranges(self, app_ctx, db, seed_product):
        from services.product_service import _compute_category_ranges
        cur = db.cursor()
        ranges = _compute_category_ranges(cur, ["kcal", "protein"])
        assert "Snacks" in ranges
        assert "kcal" in ranges["Snacks"]
        assert "protein" in ranges["Snacks"]

    def test_empty_enabled_fields(self, app_ctx, db):
        from services.product_service import _compute_category_ranges
        cur = db.cursor()
        ranges = _compute_category_ranges(cur, [])
        assert ranges == {}

    def test_computed_fields_excluded(self, app_ctx, db, seed_product):
        from services.product_service import _compute_category_ranges
        cur = db.cursor()
        # pct_protein_cal is a computed field, should be excluded from DB query
        ranges = _compute_category_ranges(cur, ["pct_protein_cal"])
        assert ranges == {}


class TestListProducts:
    def test_returns_products(self, app_ctx):
        from services.product_service import list_products
        result = list_products(None, None)
        assert len(result) >= 1
        assert "total_score" in result[0]
        assert "scores" in result[0]

    def test_search_filter(self, app_ctx):
        from services.product_service import list_products
        result = list_products("Popcorn", None)
        assert len(result) >= 1
        assert "Popcorn" in result[0]["name"]

    def test_search_no_match(self, app_ctx):
        from services.product_service import list_products
        result = list_products("ZZZZNOTFOUND", None)
        assert result == []

    def test_type_filter(self, app_ctx):
        from services.product_service import list_products
        result = list_products(None, "Snacks")
        assert all(p["type"] == "Snacks" for p in result)

    def test_multi_type_filter(self, app_ctx):
        from services.product_service import list_products
        result = list_products(None, "Snacks,NonExistent")
        assert all(p["type"] == "Snacks" for p in result)


class TestAddProduct:
    def test_valid_product(self, app_ctx, seed_category):
        from services.product_service import add_product
        result = add_product({
            "type": "Snacks", "name": "Test Product",
            "ean": "12345678", "brand": "TestBrand",
        })
        assert "id" in result
        assert result["id"] > 0

    def test_missing_type(self, app_ctx):
        from services.product_service import add_product
        with pytest.raises(ValueError, match="type and name"):
            add_product({"name": "Test"})

    def test_missing_name(self, app_ctx):
        from services.product_service import add_product
        with pytest.raises(ValueError, match="type and name"):
            add_product({"type": "Snacks"})

    def test_invalid_ean(self, app_ctx, seed_category):
        from services.product_service import add_product
        with pytest.raises(ValueError, match="EAN"):
            add_product({"type": "Snacks", "name": "Test", "ean": "abc"})

    def test_text_too_long(self, app_ctx, seed_category):
        from services.product_service import add_product
        with pytest.raises(ValueError, match="exceeds max length"):
            add_product({"type": "Snacks", "name": "x" * 300})

    def test_nonexistent_category(self, app_ctx):
        from services.product_service import add_product
        with pytest.raises(ValueError, match="Category does not exist"):
            add_product({"type": "NoSuchCategory", "name": "Test"})


class TestUpdateProduct:
    def test_valid_update(self, app_ctx, seed_product):
        from services.product_service import update_product
        update_product(seed_product, {"name": "Updated Popcorn"})
        from db import get_db
        row = get_db().execute("SELECT name FROM products WHERE id=?", (seed_product,)).fetchone()
        assert row["name"] == "Updated Popcorn"

    def test_update_numeric_field(self, app_ctx, seed_product):
        from services.product_service import update_product
        update_product(seed_product, {"kcal": 500.0})

    def test_invalid_field(self, app_ctx, seed_product):
        from services.product_service import update_product
        with pytest.raises(ValueError, match="Invalid field"):
            update_product(seed_product, {"nonexistent_field": "value"})

    def test_product_not_found(self, app_ctx):
        from services.product_service import update_product
        with pytest.raises(LookupError, match="Product not found"):
            update_product(99999, {"name": "Test"})

    def test_nothing_to_update(self, app_ctx, seed_product):
        from services.product_service import update_product
        with pytest.raises(ValueError, match="Nothing to update"):
            update_product(seed_product, {})

    def test_ean_validation(self, app_ctx, seed_product):
        from services.product_service import update_product
        with pytest.raises(ValueError, match="EAN"):
            update_product(seed_product, {"ean": "abc"})

    def test_nonexistent_category(self, app_ctx, seed_product):
        from services.product_service import update_product
        with pytest.raises(ValueError, match="Category does not exist"):
            update_product(seed_product, {"type": "NoSuchCat"})

    def test_null_numeric_field(self, app_ctx, seed_product):
        from services.product_service import update_product
        update_product(seed_product, {"kcal": None})
        from db import get_db
        row = get_db().execute("SELECT kcal FROM products WHERE id=?", (seed_product,)).fetchone()
        assert row["kcal"] is None


class TestDeleteProduct:
    def test_delete_existing(self, app_ctx, seed_product):
        from services.product_service import delete_product
        assert delete_product(seed_product) is True

    def test_delete_nonexistent(self, app_ctx):
        from services.product_service import delete_product
        assert delete_product(99999) is False
