"""Unit tests for services/import_service.py."""

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _minimal_product(name="Test Product", ean="1234567890123"):
    """Return a minimal product dict suitable for import."""
    return {"name": name, "type": "Snacks", "ean": ean}


# ── _pick_emoji_for_category ───────────────────────────────────────────────────


class TestPickEmojiForCategory:
    def test_juice_returns_drink_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Orange Juice") == "\U0001f9c3"

    def test_coffee_returns_coffee_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Black Coffee") == "\u2615"

    def test_chocolate_returns_chocolate_emoji(self):
        from services.import_service import _pick_emoji_for_category
        # Use Norwegian "sjokolade" which matches chocolate keyword without "te" ambiguity
        assert _pick_emoji_for_category("Sjokolade") == "\U0001f36b"

    def test_milk_returns_milk_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Whole Milk") == "\U0001f95b"

    def test_bread_returns_bread_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Whole Grain Bread") == "\U0001f35e"

    def test_unknown_returns_box_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("unknownxyz") == "\U0001f4e6"

    def test_case_insensitive(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("MILK") == _pick_emoji_for_category("milk")

    def test_empty_string_returns_box_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("") == "\U0001f4e6"

    def test_fish_returns_fish_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Fresh Salmon") == "\U0001f41f"

    def test_chicken_returns_poultry_emoji(self):
        from services.import_service import _pick_emoji_for_category
        assert _pick_emoji_for_category("Chicken Breast") == "\U0001f357"


# ── import_products: input validation ─────────────────────────────────────────


class TestImportProductsValidation:
    def test_none_data_raises_value_error(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError, match="Invalid import file"):
            import_products(None)

    def test_empty_dict_raises_value_error(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError, match="Invalid import file"):
            import_products({})

    def test_missing_products_key_raises_value_error(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError, match="Invalid import file"):
            import_products({"categories": []})

    def test_empty_products_list_returns_message(self, app_ctx):
        from services.import_service import import_products
        msg = import_products({"products": []})
        assert "0" in msg

    def test_name_too_long_raises_value_error(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError, match="name exceeds max length"):
            import_products({"products": [{"name": "x" * 201, "type": "Snacks"}]})

    def test_ingredients_too_long_raises(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Valid", "type": "Snacks", "ingredients": "i" * 10001}
            ]})

    def test_taste_note_too_long_raises(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Valid", "type": "Snacks", "taste_note": "n" * 2001}
            ]})

    def test_invalid_nutrition_value_raises(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Bad", "type": "Snacks", "kcal": "not_a_number"}
            ]})

    def test_non_finite_nutrition_value_raises(self, app_ctx):
        from services.import_service import import_products
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Bad", "type": "Snacks", "kcal": float("inf")}
            ]})

    def test_invalid_match_criteria_defaults_to_both(self, app_ctx):
        from services.import_service import import_products
        msg = import_products({"products": [_minimal_product(ean="0000000000001")]},
                               match_criteria="invalid")
        assert "Imported" in msg

    def test_invalid_on_duplicate_defaults_to_skip(self, app_ctx):
        from services.import_service import import_products
        msg = import_products({"products": [_minimal_product(ean="0000000000002")]},
                               on_duplicate="bad_value")
        assert "Imported" in msg

    def test_invalid_merge_priority_defaults_to_keep_existing(self, app_ctx):
        from services.import_service import import_products
        msg = import_products({"products": [_minimal_product(ean="0000000000003")]},
                               merge_priority="bad_value")
        assert "Imported" in msg


# ── import_products: successful import ────────────────────────────────────────


class TestImportProductsSuccess:
    def test_single_product_imported(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [_minimal_product(ean="1111111111111")]})
        row = db.execute(
            "SELECT p.name FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            ("1111111111111",)
        ).fetchone()
        assert row is not None
        assert row["name"] == "Test Product"

    def test_multiple_products_imported(self, app_ctx, db):
        from services.import_service import import_products
        products = [
            _minimal_product(name=f"Product {i}", ean=f"111111111{i:04d}")
            for i in range(5)
        ]
        msg = import_products({"products": products})
        assert "5" in msg

    def test_product_with_numeric_fields(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [{
            "name": "Nutrition Product", "type": "Snacks",
            "kcal": 250.5, "protein": 12.3, "fat": 8.0,
        }]})
        row = db.execute("SELECT kcal FROM products WHERE name='Nutrition Product'").fetchone()
        assert abs(row["kcal"] - 250.5) < 0.01

    def test_returns_message_with_count(self, app_ctx):
        from services.import_service import import_products
        msg = import_products({"products": [_minimal_product(ean="2222222222222")]})
        assert "Imported 1 products" in msg

    def test_transaction_rollback_on_error(self, app_ctx, db):
        """Failed import rolls back: no partial data committed."""
        from services.import_service import import_products
        initial_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Good Product", "type": "Snacks", "ean": "9988776655443"},
                {"name": "x" * 201, "type": "Snacks"},  # this fails
            ]})
        final_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert final_count == initial_count


# ── import_products: on_duplicate=skip ────────────────────────────────────────


class TestImportProductsSkipDuplicate:
    def test_skip_duplicate_by_ean(self, app_ctx):
        from services.import_service import import_products
        data = {"products": [_minimal_product(ean="3333333333333")]}
        import_products(data)
        msg = import_products(data)
        assert "skipped" in msg

    def test_skip_duplicate_by_name(self, app_ctx):
        from services.import_service import import_products
        data = {"products": [{"name": "Unique Snack", "type": "Snacks"}]}
        import_products(data)
        msg = import_products(data, match_criteria="name")
        assert "skipped" in msg

    def test_skip_by_both_ean_and_name(self, app_ctx):
        from services.import_service import import_products
        data = {"products": [_minimal_product(name="Duo", ean="4444444444444")]}
        import_products(data)
        msg = import_products(data, match_criteria="both")
        assert "skipped" in msg

    def test_different_ean_same_name_not_skipped_with_ean_only(self, app_ctx):
        from services.import_service import import_products
        import_products({"products": [{"name": "Alpha", "type": "Snacks", "ean": "1111"}]})
        msg = import_products({"products": [{"name": "Alpha", "type": "Snacks", "ean": "2222"}]},
                               match_criteria="ean")
        assert "skipped" not in msg

    def test_skip_does_not_modify_existing_product(self, app_ctx, db):
        from services.import_service import import_products
        ean = "5555555555555"
        import_products({"products": [{"name": "Original", "type": "Snacks", "ean": ean}]})
        import_products({"products": [{"name": "Changed", "type": "Snacks", "ean": ean}]})
        row = db.execute(
            "SELECT p.name FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        assert row["name"] == "Original"


# ── import_products: on_duplicate=overwrite ───────────────────────────────────


class TestImportProductsOverwrite:
    def test_overwrite_updates_existing_product(self, app_ctx, db):
        from services.import_service import import_products
        ean = "6666666666666"
        import_products({"products": [{"name": "Old Name", "type": "Snacks", "ean": ean}]})
        import_products({"products": [{"name": "New Name", "type": "Snacks", "ean": ean}]},
                        on_duplicate="overwrite")
        row = db.execute(
            "SELECT p.name FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        assert row["name"] == "New Name"

    def test_overwrite_returns_overwritten_count(self, app_ctx):
        from services.import_service import import_products
        import_products({"products": [_minimal_product(ean="7777777777777")]})
        msg = import_products({"products": [_minimal_product(ean="7777777777777", name="Updated")]},
                               on_duplicate="overwrite")
        assert "overwritten" in msg

    def test_overwrite_replaces_flags(self, app_ctx, db):
        from services.import_service import import_products
        ean = "8888888888888"
        import_products({"products": [{
            "name": "Flagged", "type": "Snacks", "ean": ean,
            "flags": ["is_synced_with_off"],
        }]})
        import_products({"products": [{"name": "Unflagged", "type": "Snacks", "ean": ean}]},
                        on_duplicate="overwrite")
        prod = db.execute(
            "SELECT p.id FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        flag = db.execute(
            "SELECT flag FROM product_flags WHERE product_id=? AND flag='is_synced_with_off'",
            (prod["id"],)
        ).fetchone()
        assert flag is None


# ── import_products: on_duplicate=allow_duplicate ─────────────────────────────


class TestImportProductsAllowDuplicate:
    def test_allow_duplicate_inserts_new_row(self, app_ctx, db):
        from services.import_service import import_products
        product = {"name": "Dupe Product", "type": "Snacks", "ean": "9999000000000"}
        import_products({"products": [product]})
        import_products({"products": [product]}, on_duplicate="allow_duplicate")
        count = db.execute("SELECT COUNT(*) FROM products WHERE name='Dupe Product'").fetchone()[0]
        assert count == 2

    def test_allow_duplicate_message_contains_imported(self, app_ctx):
        from services.import_service import import_products
        p = {"name": "DupeCheck", "type": "Snacks", "ean": "9999000000001"}
        import_products({"products": [p]})
        msg = import_products({"products": [p]}, on_duplicate="allow_duplicate")
        assert "Imported" in msg


# ── import_products: on_duplicate=merge ───────────────────────────────────────


class TestImportProductsMerge:
    def test_merge_fills_empty_fields(self, app_ctx, db):
        from services.import_service import import_products
        ean = "1000000000001"
        import_products({"products": [{"name": "Merge Me", "type": "Snacks", "ean": ean}]})
        import_products(
            {"products": [{"name": "Merge Me", "type": "Snacks", "ean": ean, "brand": "BrandX"}]},
            on_duplicate="merge"
        )
        row = db.execute(
            "SELECT p.brand FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        assert row["brand"] == "BrandX"

    def test_merge_keep_existing_priority(self, app_ctx, db):
        from services.import_service import import_products
        ean = "1000000000002"
        import_products({"products": [{"name": "Keep Me", "type": "Snacks", "ean": ean, "brand": "Original"}]})
        import_products(
            {"products": [{"name": "Other", "type": "Snacks", "ean": ean, "brand": "Imported"}]},
            on_duplicate="merge", merge_priority="keep_existing"
        )
        row = db.execute(
            "SELECT p.brand FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        assert row["brand"] == "Original"

    def test_merge_use_imported_priority(self, app_ctx, db):
        from services.import_service import import_products
        ean = "1000000000003"
        import_products({"products": [{"name": "Replace Me", "type": "Snacks", "ean": ean, "brand": "Old"}]})
        import_products(
            {"products": [{"name": "New", "type": "Snacks", "ean": ean, "brand": "New"}]},
            on_duplicate="merge", merge_priority="use_imported"
        )
        row = db.execute(
            "SELECT p.brand FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        assert row["brand"] == "New"

    def test_merge_returns_merged_count(self, app_ctx):
        from services.import_service import import_products
        ean = "1000000000004"
        import_products({"products": [_minimal_product(ean=ean)]})
        msg = import_products({"products": [_minimal_product(ean=ean)]}, on_duplicate="merge")
        assert "merged" in msg

    def test_merge_additive_flags(self, app_ctx, db):
        from services.import_service import import_products
        ean = "1000000000005"
        import_products({"products": [{"name": "P", "type": "Snacks", "ean": ean}]})
        import_products(
            {"products": [{"name": "P", "type": "Snacks", "ean": ean, "flags": ["is_synced_with_off"]}]},
            on_duplicate="merge"
        )
        prod = db.execute(
            "SELECT p.id FROM products p JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            (ean,)
        ).fetchone()
        flag = db.execute(
            "SELECT flag FROM product_flags WHERE product_id=? AND flag='is_synced_with_off'",
            (prod["id"],)
        ).fetchone()
        assert flag is not None


# ── import_products: category handling ────────────────────────────────────────


class TestImportProductsCategories:
    def test_auto_creates_missing_category(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [{"name": "P", "type": "NewAutoCategory"}]})
        row = db.execute("SELECT name FROM categories WHERE name='NewAutoCategory'").fetchone()
        assert row is not None

    def test_existing_category_not_duplicated(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [{"name": "P1", "type": "Snacks"}]})
        import_products({"products": [{"name": "P2", "type": "Snacks"}]})
        count = db.execute("SELECT COUNT(*) FROM categories WHERE name='Snacks'").fetchone()[0]
        assert count == 1

    def test_explicit_categories_in_import_data(self, app_ctx, db):
        from services.import_service import import_products
        import_products({
            "categories": [{"name": "ExplicitCat", "emoji": "\U0001f3af"}],
            "products": [],
        })
        row = db.execute("SELECT emoji FROM categories WHERE name='ExplicitCat'").fetchone()
        assert row["emoji"] == "\U0001f3af"

    def test_emoji_auto_assigned_by_keyword(self, app_ctx, db):
        from services.import_service import import_products
        # Use "Sjokolade" (Norwegian) which matches the chocolate keyword without "te" ambiguity
        import_products({"products": [{"name": "P", "type": "Sjokolade Bars"}]})
        row = db.execute("SELECT emoji FROM categories WHERE name='Sjokolade Bars'").fetchone()
        assert row["emoji"] == "\U0001f36b"

    def test_duplicate_explicit_category_silently_ignored(self, app_ctx):
        from services.import_service import import_products
        from db import get_db
        import_products({"categories": [{"name": "Snacks"}], "products": []})
        import_products({"categories": [{"name": "Snacks"}], "products": []})
        count = get_db().execute(
            "SELECT COUNT(*) FROM categories WHERE name='Snacks'"
        ).fetchone()[0]
        assert count == 1  # duplicate was not inserted


# ── import_products: flag handling ────────────────────────────────────────────


class TestImportProductsFlagHandling:
    def test_valid_flag_is_applied(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [{
            "name": "Flagged", "type": "Snacks",
            "flags": ["is_synced_with_off"],
        }]})
        prod = db.execute("SELECT id FROM products WHERE name='Flagged'").fetchone()
        flag = db.execute(
            "SELECT flag FROM product_flags WHERE product_id=? AND flag='is_synced_with_off'",
            (prod["id"],)
        ).fetchone()
        assert flag is not None

    def test_invalid_flag_is_ignored(self, app_ctx, db):
        from services.import_service import import_products
        import_products({"products": [{
            "name": "NoFlag", "type": "Snacks",
            "flags": ["nonexistent_flag_xyz"],
        }]})
        prod = db.execute("SELECT id FROM products WHERE name='NoFlag'").fetchone()
        flags = db.execute("SELECT flag FROM product_flags WHERE product_id=?", (prod["id"],)).fetchall()
        assert len(flags) == 0
