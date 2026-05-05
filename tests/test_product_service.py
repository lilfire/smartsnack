"""Tests for services/product_service.py — scoring engine and product CRUD."""

import pytest


class TestLoadWeightConfig:
    def test_returns_enabled_weights(self, db):
        from services.product_service import _load_weight_config

        cur = db.cursor()
        enabled_weights, weight_config, enabled_fields, _ = _load_weight_config(cur)
        # taste_score is enabled by default
        assert "taste_score" in enabled_weights
        assert "taste_score" in weight_config
        assert "taste_score" in enabled_fields

    def test_disabled_weights_excluded(self, db):
        from services.product_service import _load_weight_config

        cur = db.cursor()
        # kcal is disabled by default
        enabled_weights, _, _, _ = _load_weight_config(cur)
        assert "kcal" not in enabled_weights


class TestScoreProduct:
    def test_direct_formula_higher(self):
        from services.product_service import _score_product

        p = {"type": "Snacks", "taste_score": 4.5}
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
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 5,
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
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
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
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
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
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
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
                "direction": "higher",
                "formula": "direct",
                "formula_min": 5,
                "formula_max": 5,
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
        products = result["products"]
        assert len(products) >= 1
        assert "total_score" in products[0]
        assert "scores" in products[0]

    def test_search_filter(self, app_ctx):
        from services.product_service import list_products

        result = list_products("Popcorn", None)
        products = result["products"]
        assert len(products) >= 1
        assert "Popcorn" in products[0]["name"]

    def test_search_no_match(self, app_ctx):
        from services.product_service import list_products

        result = list_products("ZZZZNOTFOUND", None)
        assert result["products"] == []

    def test_type_filter(self, app_ctx):
        from services.product_service import list_products

        result = list_products(None, "Snacks")
        assert all(p["type"] == "Snacks" for p in result["products"])

    def test_multi_type_filter(self, app_ctx):
        from services.product_service import list_products

        result = list_products(None, "Snacks,NonExistent")
        assert all(p["type"] == "Snacks" for p in result["products"])


class TestAddProduct:
    def test_valid_product(self, app_ctx, seed_category):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "Test Product",
                "ean": "12345678",
                "brand": "TestBrand",
            }
        )
        assert "id" in result
        assert result["id"] > 0

    def test_missing_type_creates_uncategorized(self, app_ctx):
        from services.product_service import add_product

        result = add_product({"name": "Test Uncategorized"})
        assert result["id"] is not None

    def test_missing_name(self, app_ctx):
        from services.product_service import add_product

        with pytest.raises(ValueError, match="name is required"):
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

        row = (
            get_db()
            .execute("SELECT name FROM products WHERE id=?", (seed_product,))
            .fetchone()
        )
        assert row["name"] == "Updated Popcorn"

    def test_update_numeric_field(self, app_ctx, seed_product):
        from services.product_service import update_product
        from db import get_db

        update_product(seed_product, {"kcal": 500.0})
        row = get_db().execute("SELECT kcal FROM products WHERE id=?", (seed_product,)).fetchone()
        assert row["kcal"] == 500.0

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

        row = (
            get_db()
            .execute("SELECT kcal FROM products WHERE id=?", (seed_product,))
            .fetchone()
        )
        assert row["kcal"] is None


class TestFindDuplicate:
    def test_ean_match(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate

        # The seed product has EAN "7000000000001"
        result = _find_duplicate("7000000000001", "Some Other Name")
        assert result is not None
        assert result["match_type"] == "ean"
        assert result["id"] == seed_product

    def test_name_match_case_insensitive(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate

        result = _find_duplicate("", "classic popcorn")
        assert result is not None
        assert result["match_type"] == "name"
        assert result["id"] == seed_product

    def test_no_match(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate

        result = _find_duplicate("9999999999999", "Nonexistent Product")
        assert result is None

    def test_exclude_id(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate

        result = _find_duplicate("7000000000001", "Classic Popcorn", exclude_id=seed_product)
        assert result is None

    def test_synced_flag_detected(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate, set_system_flag

        set_system_flag(seed_product, "is_synced_with_off", True)
        result = _find_duplicate("7000000000001", "")
        assert result is not None
        assert result["is_synced_with_off"] is True

    def test_unsynced_flag(self, app_ctx, seed_product):
        from services.product_service import _find_duplicate

        result = _find_duplicate("7000000000001", "")
        assert result is not None
        assert result["is_synced_with_off"] is False


class TestAddProductDuplicate:
    def test_synced_ean_duplicate_returns_409_no_actions(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product, set_system_flag

        set_system_flag(seed_product, "is_synced_with_off", True)
        result = add_product({"type": "Snacks", "name": "New Name", "ean": "7000000000001"})
        assert "duplicate" in result
        assert result["duplicate"]["is_synced_with_off"] is True
        assert result["actions"] == []

    def test_synced_name_duplicate_returns_409_no_actions(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product, set_system_flag

        set_system_flag(seed_product, "is_synced_with_off", True)
        result = add_product({"type": "Snacks", "name": "Classic Popcorn"})
        assert "duplicate" in result
        assert result["duplicate"]["is_synced_with_off"] is True
        assert result["actions"] == []

    def test_synced_duplicate_overwrite_raises(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product, set_system_flag

        set_system_flag(seed_product, "is_synced_with_off", True)
        with pytest.raises(ValueError, match="Cannot overwrite"):
            add_product(
                {"type": "Snacks", "name": "New Name", "ean": "7000000000001"},
                on_duplicate="overwrite",
            )

    def test_unsynced_duplicate_returns_409_info(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product

        result = add_product({"type": "Snacks", "name": "Classic Popcorn"})
        assert "duplicate" in result
        assert result["duplicate"]["id"] == seed_product
        assert "overwrite" in result["actions"]

    def test_unsynced_duplicate_from_off_no_create_new(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product

        result = add_product({"type": "Snacks", "name": "Classic Popcorn", "from_off": True})
        assert "duplicate" in result
        assert "create_new" not in result["actions"]

    def test_unsynced_duplicate_manual_has_create_new(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product

        result = add_product({"type": "Snacks", "name": "Classic Popcorn"})
        assert "duplicate" in result
        assert "create_new" in result["actions"]

    def test_overwrite_merges_into_existing(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product
        from db import get_db

        result = add_product(
            {"type": "Snacks", "name": "Classic Popcorn", "brand": "NewBrand", "kcal": 999},
            on_duplicate="overwrite",
        )
        assert result["merged"] is True
        assert result["id"] == seed_product
        row = get_db().execute("SELECT brand, kcal FROM products WHERE id=?", (seed_product,)).fetchone()
        assert row["brand"] == "NewBrand"
        assert row["kcal"] == 999

    def test_allow_duplicate_creates_new(self, app_ctx, seed_category, seed_product):
        from services.product_service import add_product
        from db import get_db

        result = add_product(
            {"type": "Snacks", "name": "Classic Popcorn"},
            on_duplicate="allow_duplicate",
        )
        assert "id" in result
        assert result["id"] != seed_product
        count = get_db().execute("SELECT COUNT(*) FROM products WHERE LOWER(name) = LOWER('Classic Popcorn')").fetchone()[0]
        assert count == 2


class TestDeleteProduct:
    def test_delete_existing(self, app_ctx, seed_product):
        from services.product_service import delete_product

        assert delete_product(seed_product) is True

    def test_delete_nonexistent(self, app_ctx):
        from services.product_service import delete_product

        assert delete_product(99999) is False


class TestCheckDuplicateForEdit:
    def test_returns_duplicate_ean_match(self, app_ctx, seed_product):
        from services.product_service import check_duplicate_for_edit, add_product
        from db import get_db

        other = add_product({"type": "Snacks", "name": "Other Product", "ean": "7000000000002"})
        result, a_synced = check_duplicate_for_edit(other["id"], "7000000000001", "No Match")
        assert result is not None
        assert result["match_type"] == "ean"
        assert result["id"] == seed_product
        assert a_synced is False

    def test_returns_duplicate_name_match(self, app_ctx, seed_product):
        from services.product_service import check_duplicate_for_edit, add_product

        other = add_product({"type": "Snacks", "name": "Other Product", "ean": "7000000000002"})
        result, a_synced = check_duplicate_for_edit(other["id"], "", "Classic Popcorn")
        assert result is not None
        assert result["match_type"] == "name"
        assert result["id"] == seed_product
        assert a_synced is False

    def test_returns_none_no_match(self, app_ctx, seed_product):
        from services.product_service import check_duplicate_for_edit

        result, a_synced = check_duplicate_for_edit(seed_product, "9999999999999", "Nonexistent")
        assert result is None
        assert a_synced is False

    def test_excludes_current_product(self, app_ctx, seed_product):
        from services.product_service import check_duplicate_for_edit

        result, a_synced = check_duplicate_for_edit(seed_product, "7000000000001", "Classic Popcorn")
        assert result is None
        assert a_synced is False

    def test_returns_a_synced_status(self, app_ctx, seed_product):
        from services.product_service import check_duplicate_for_edit, add_product, set_system_flag

        other = add_product({"type": "Snacks", "name": "Other Product", "ean": "7000000000002"})
        set_system_flag(other["id"], "is_synced_with_off", True)
        result, a_synced = check_duplicate_for_edit(other["id"], "7000000000001", "No Match")
        assert result is not None
        assert a_synced is True


class TestMergeProducts:
    def test_merges_fields_into_target(self, app_ctx, seed_category):
        from services.product_service import add_product, merge_products
        from db import get_db

        target = add_product({"type": "Snacks", "name": "Target", "ean": "8000000000001", "brand": ""})
        source = add_product({"type": "Snacks", "name": "Source", "ean": "8000000000002", "brand": "SourceBrand", "kcal": 200})
        merge_products(target["id"], source["id"])
        row = get_db().execute("SELECT brand, kcal FROM products WHERE id=?", (target["id"],)).fetchone()
        assert row["brand"] == "SourceBrand"
        assert row["kcal"] == 200

    def test_does_not_overwrite_existing_fields(self, app_ctx, seed_category):
        from services.product_service import add_product, merge_products
        from db import get_db

        target = add_product({"type": "Snacks", "name": "Target", "ean": "8000000000001", "brand": "TargetBrand"})
        source = add_product({"type": "Snacks", "name": "Source", "ean": "8000000000002", "brand": "SourceBrand"})
        merge_products(target["id"], source["id"])
        row = get_db().execute("SELECT brand FROM products WHERE id=?", (target["id"],)).fetchone()
        assert row["brand"] == "TargetBrand"

    def test_deletes_source_after_merge(self, app_ctx, seed_category):
        from services.product_service import add_product, merge_products
        from db import get_db

        target = add_product({"type": "Snacks", "name": "Target", "ean": "8000000000001"})
        source = add_product({"type": "Snacks", "name": "Source", "ean": "8000000000002"})
        source_id = source["id"]
        merge_products(target["id"], source_id)
        row = get_db().execute("SELECT id FROM products WHERE id=?", (source_id,)).fetchone()
        assert row is None

    def test_source_not_found_raises(self, app_ctx, seed_product):
        from services.product_service import merge_products

        with pytest.raises(LookupError):
            merge_products(seed_product, 99999)

    def test_target_not_found_raises(self, app_ctx, seed_product):
        from services.product_service import merge_products

        with pytest.raises(LookupError):
            merge_products(99999, seed_product)
