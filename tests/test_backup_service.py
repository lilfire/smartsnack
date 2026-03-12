"""Tests for services/backup_service.py — backup, restore, and import."""

import pytest


class TestPickEmojiForCategory:
    def test_drinks(self):
        from services.backup_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("Juice") == "🧃"

    def test_snacks(self):
        from services.backup_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("Chips") == "🍿"

    def test_unknown_default(self):
        from services.backup_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("ZZZZZ") == "📦"

    def test_case_insensitive(self):
        from services.backup_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("COFFEE") == "☕"


class TestOptFloat:
    def test_none(self):
        from services.backup_service import _opt_float

        assert _opt_float(None) is None

    def test_valid(self):
        from services.backup_service import _opt_float

        assert _opt_float(3.14) == pytest.approx(3.14)

    def test_string(self):
        from services.backup_service import _opt_float

        assert _opt_float("42") == 42.0


class TestCreateBackup:
    def test_backup_structure(self, app_ctx, seed_product):
        from services.backup_service import create_backup

        backup = create_backup()
        assert "version" in backup
        assert "exported_at" in backup
        assert "products" in backup
        assert "categories" in backup
        assert "score_weights" in backup
        assert "protein_quality" in backup
        assert len(backup["products"]) >= 1

    def test_backup_without_images(self, app_ctx, seed_product):
        from services.backup_service import create_backup

        backup = create_backup(include_images=False)
        product = backup["products"][0]
        assert "image" not in product

    def test_backup_with_images(self, app_ctx, seed_product):
        from services.backup_service import create_backup

        backup = create_backup(include_images=True)
        product = backup["products"][0]
        assert "image" in product


class TestValidateBackup:
    def test_valid_backup(self):
        from services.backup_service import _validate_backup

        _validate_backup({"products": []})

    def test_missing_products(self):
        from services.backup_service import _validate_backup

        with pytest.raises(ValueError, match="Invalid backup"):
            _validate_backup({})

    def test_products_not_list(self):
        from services.backup_service import _validate_backup

        with pytest.raises(ValueError, match="products must be an array"):
            _validate_backup({"products": "not a list"})

    def test_empty_data(self):
        from services.backup_service import _validate_backup

        with pytest.raises(ValueError, match="Invalid backup"):
            _validate_backup(None)

    def test_score_weights_not_list(self):
        from services.backup_service import _validate_backup

        with pytest.raises(ValueError, match="score_weights must be an array"):
            _validate_backup({"products": [], "score_weights": "bad"})


class TestRestoreBackup:
    def test_full_restore(self, app_ctx, seed_product, translations_dir):
        from services.backup_service import create_backup, restore_backup

        backup = create_backup()
        # Modify something
        from db import get_db

        get_db().execute("DELETE FROM products")
        get_db().commit()
        # Restore
        msg = restore_backup(backup)
        assert "Restored" in msg
        count = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert count >= 1

    def test_restore_invalid_data(self, app_ctx):
        from services.backup_service import restore_backup

        with pytest.raises(ValueError):
            restore_backup({})


class TestRestoreProduct:
    def test_restore_product(self, app_ctx, db, seed_category):
        from services.backup_service import _restore_product

        cur = db.cursor()
        _restore_product(
            cur,
            {
                "type": "Snacks",
                "name": "Restored Item",
                "ean": "12345678",
                "brand": "Test",
            },
        )
        db.commit()
        row = db.execute(
            "SELECT name FROM products WHERE name='Restored Item'"
        ).fetchone()
        assert row is not None

    def test_text_too_long_raises(self, app_ctx, db):
        from services.backup_service import _restore_product

        cur = db.cursor()
        with pytest.raises(ValueError, match="exceeds max length"):
            _restore_product(cur, {"type": "Snacks", "name": "x" * 300})


class TestImportProducts:
    def test_import_adds_products(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        before = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        msg = import_products(
            {
                "products": [
                    {"type": "Snacks", "name": "Imported A"},
                    {"type": "Snacks", "name": "Imported B"},
                ]
            }
        )
        after = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert after == before + 2
        assert "Imported 2" in msg

    def test_import_creates_categories(self, app_ctx, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        import_products(
            {
                "products": [{"type": "NewCat", "name": "Item"}],
            }
        )
        row = (
            get_db()
            .execute("SELECT name FROM categories WHERE name='NewCat'")
            .fetchone()
        )
        assert row is not None

    def test_import_invalid_data(self, app_ctx):
        from services.backup_service import import_products

        with pytest.raises(ValueError, match="Invalid import"):
            import_products({})


class TestImportDuplicateControl:
    """Tests for match_criteria and on_duplicate parameters of import_products."""

    def _insert_product(self, db, name, ean="", cat="Snacks"):
        from config import INSERT_WITH_IMAGE_SQL

        db.execute(
            INSERT_WITH_IMAGE_SQL,
            (cat, name, ean, "", "", "", "", None, None, None, None, None,
             None, None, None, None, None, None, None, None, None, None, None, ""),
        )
        db.commit()

    def test_default_skips_ean_duplicate(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Existing", ean="1234567890123")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Different", "ean": "1234567890123"}]}
        )
        assert "1 skipped" in msg

    def test_default_skips_name_duplicate(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Existing Product")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "existing product"}]}
        )
        assert "1 skipped" in msg

    def test_match_ean_only_allows_same_name(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Same Name")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Same Name", "ean": "9999999999999"}]},
            match_criteria="ean",
        )
        assert "Imported 1" in msg

    def test_match_name_only_allows_same_ean(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Product A", ean="1111111111111")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Product B", "ean": "1111111111111"}]},
            match_criteria="name",
        )
        assert "Imported 1" in msg

    def test_overwrite_updates_existing(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Overwrite Me", ean="2222222222222")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Overwrite Me", "ean": "2222222222222", "brand": "NewBrand"}]},
            on_duplicate="overwrite",
        )
        assert "1 overwritten" in msg
        row = get_db().execute(
            "SELECT brand FROM products WHERE ean = '2222222222222'"
        ).fetchone()
        assert row["brand"] == "NewBrand"

    def test_allow_duplicate_creates_new(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Dup Product", ean="3333333333333")
        before = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Dup Product", "ean": "3333333333333"}]},
            on_duplicate="allow_duplicate",
        )
        after = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert after == before + 1
        assert "Imported 1" in msg

    def test_invalid_params_fall_back_to_defaults(self, app_ctx, seed_category, translations_dir):
        from services.backup_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Fallback Test", ean="4444444444444")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Fallback Test", "ean": "4444444444444"}]},
            match_criteria="invalid",
            on_duplicate="invalid",
        )
        assert "1 skipped" in msg


class TestRestoreScoreWeights:
    def test_restore_weights(self, app_ctx, db):
        from services.backup_service import _restore_score_weights

        cur = db.cursor()
        _restore_score_weights(
            cur,
            [
                {
                    "field": "kcal",
                    "enabled": 1,
                    "weight": 75,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                },
            ],
        )
        db.commit()
        row = db.execute(
            "SELECT weight FROM score_weights WHERE field='kcal'"
        ).fetchone()
        assert row["weight"] == 75

    def test_unknown_field_skipped(self, app_ctx, db):
        from services.backup_service import _restore_score_weights

        cur = db.cursor()
        # Should not raise
        _restore_score_weights(cur, [{"field": "nonexistent_field"}])
        db.commit()


class TestRestoreCategories:
    def test_restore_categories(self, app_ctx, db, translations_dir):
        from services.backup_service import _restore_categories

        cur = db.cursor()
        _restore_categories(
            cur,
            [
                {"name": "Fruits", "emoji": "🍎"},
            ],
        )
        db.commit()
        row = db.execute("SELECT emoji FROM categories WHERE name='Fruits'").fetchone()
        assert row["emoji"] == "🍎"
