"""Tests for services/backup_service.py — backup, restore, and import."""

import pytest


class TestPickEmojiForCategory:
    def test_drinks(self):
        from services.import_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("Juice") == "🧃"

    def test_snacks(self):
        from services.import_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("Chips") == "🍿"

    def test_unknown_default(self):
        from services.import_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("ZZZZZ") == "📦"

    def test_case_insensitive(self):
        from services.import_service import _pick_emoji_for_category

        assert _pick_emoji_for_category("COFFEE") == "☕"


class TestOptFloat:
    def test_none(self):
        from services.backup_core import _opt_float

        assert _opt_float(None) is None

    def test_valid(self):
        from services.backup_core import _opt_float

        assert _opt_float(3.14) == pytest.approx(3.14)

    def test_string(self):
        from services.backup_core import _opt_float

        assert _opt_float("42") == 42.0


class TestCreateBackup:
    def test_backup_structure(self, app_ctx, seed_product):
        from services.backup_core import create_backup

        backup = create_backup()
        assert "version" in backup
        assert "exported_at" in backup
        assert "products" in backup
        assert "categories" in backup
        assert "score_weights" in backup
        assert "protein_quality" in backup
        assert len(backup["products"]) >= 1

    def test_backup_without_images(self, app_ctx, seed_product):
        from services.backup_core import create_backup

        backup = create_backup(include_images=False)
        product = backup["products"][0]
        assert "image" not in product

    def test_backup_with_images(self, app_ctx, seed_product):
        from services.backup_core import create_backup

        backup = create_backup(include_images=True)
        product = backup["products"][0]
        assert "image" in product


class TestValidateBackup:
    def test_valid_backup(self):
        from services.backup_core import _validate_backup

        _validate_backup({"products": []})

    def test_missing_products(self):
        from services.backup_core import _validate_backup

        with pytest.raises(ValueError, match="Invalid backup"):
            _validate_backup({})

    def test_products_not_list(self):
        from services.backup_core import _validate_backup

        with pytest.raises(ValueError, match="products must be an array"):
            _validate_backup({"products": "not a list"})

    def test_empty_data(self):
        from services.backup_core import _validate_backup

        with pytest.raises(ValueError, match="Invalid backup"):
            _validate_backup(None)

    def test_score_weights_not_list(self):
        from services.backup_core import _validate_backup

        with pytest.raises(ValueError, match="score_weights must be an array"):
            _validate_backup({"products": [], "score_weights": "bad"})


class TestRestoreBackup:
    def test_full_restore(self, app_ctx, seed_product, translations_dir):
        from services.backup_core import create_backup, restore_backup

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
        from services.backup_core import restore_backup

        with pytest.raises(ValueError):
            restore_backup({})


class TestRestoreProduct:
    def test_restore_product(self, app_ctx, db, seed_category):
        from services.backup_core import _restore_product

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
        from services.backup_core import _restore_product

        cur = db.cursor()
        with pytest.raises(ValueError, match="exceeds max length"):
            _restore_product(cur, {"type": "Snacks", "name": "x" * 300})

    def test_restore_product_backfills_product_eans_from_legacy_ean(
        self, app_ctx, db, seed_category
    ):
        """Legacy backups (no `eans` field) must still populate product_eans
        from the `products.ean` field, otherwise the EAN editor in the UI
        renders an empty list for restored products."""
        from services.backup_core import _restore_product

        cur = db.cursor()
        _restore_product(
            cur,
            {
                "type": "Snacks",
                "name": "LegacyEan",
                "ean": "7038010069307",
                "flags": ["is_synced_with_off"],
            },
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name='LegacyEan'"
        ).fetchone()["id"]
        rows = db.execute(
            "SELECT ean, is_primary, synced_with_off FROM product_eans "
            "WHERE product_id = ?",
            (pid,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["ean"] == "7038010069307"
        assert rows[0]["is_primary"] == 1
        # Synced flag should be inherited from product flag
        assert rows[0]["synced_with_off"] == 1

    def test_restore_product_uses_explicit_eans_list(
        self, app_ctx, db, seed_category
    ):
        """New-format backups carry an explicit `eans` list. _restore_product
        must restore every row with the right is_primary / synced_with_off."""
        from services.backup_core import _restore_product

        cur = db.cursor()
        _restore_product(
            cur,
            {
                "type": "Snacks",
                "name": "MultiEan",
                "eans": [
                    {"ean": "1111111111111", "is_primary": True, "synced_with_off": True},
                    {"ean": "2222222222222", "is_primary": False, "synced_with_off": False},
                ],
            },
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name='MultiEan'"
        ).fetchone()["id"]
        rows = db.execute(
            "SELECT ean, is_primary, synced_with_off FROM product_eans "
            "WHERE product_id = ? ORDER BY is_primary DESC, ean",
            (pid,),
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["ean"] == "1111111111111"
        assert rows[0]["is_primary"] == 1
        assert rows[0]["synced_with_off"] == 1
        assert rows[1]["ean"] == "2222222222222"
        assert rows[1]["is_primary"] == 0
        assert rows[1]["synced_with_off"] == 0


class TestBackupRoundTripEans:
    """Backup → restore must preserve product_eans rows losslessly."""

    def test_create_backup_includes_eans_field(self, app_ctx, db, seed_category):
        from services import product_service
        from services.backup_core import create_backup

        pid = product_service.add_product(
            {"type": "Snacks", "name": "ExportEans", "ean": "3333333333333"}
        )["id"]
        product_service.add_ean(pid, "4444444444444")
        backup = create_backup(include_images=False)
        product = next(p for p in backup["products"] if p["id"] == pid)
        assert "eans" in product
        assert len(product["eans"]) == 2
        primary = next(e for e in product["eans"] if e["is_primary"])
        secondary = next(e for e in product["eans"] if not e["is_primary"])
        assert primary["ean"] == "3333333333333"
        assert secondary["ean"] == "4444444444444"

    def test_round_trip_preserves_secondary_and_synced_flag(
        self, app_ctx, db, seed_category, translations_dir
    ):
        """Two EANs (one synced with OFF, one not) must survive a full
        backup→restore cycle. This is the regression test for the bug where
        restoring a backup wiped product_eans entirely."""
        from services import product_service
        from services.backup_core import create_backup, restore_backup

        pid = product_service.add_product(
            {
                "type": "Snacks",
                "name": "RoundTrip",
                "ean": "5555555555555",
                "from_off": True,  # marks the primary EAN row as synced
            }
        )["id"]
        product_service.add_ean(pid, "6666666666666")  # secondary, not synced

        backup = create_backup(include_images=False)
        # Wipe everything (simulates the user's restore-from-clean-DB scenario)
        get_db_conn = __import__("db", fromlist=["get_db"]).get_db
        get_db_conn().execute("DELETE FROM products")
        get_db_conn().commit()
        assert get_db_conn().execute(
            "SELECT COUNT(*) FROM product_eans"
        ).fetchone()[0] == 0

        restore_backup(backup)

        new_pid = get_db_conn().execute(
            "SELECT id FROM products WHERE name='RoundTrip'"
        ).fetchone()["id"]
        rows = get_db_conn().execute(
            "SELECT ean, is_primary, synced_with_off FROM product_eans "
            "WHERE product_id = ? ORDER BY is_primary DESC, ean",
            (new_pid,),
        ).fetchall()
        assert len(rows) == 2
        primary, secondary = rows[0], rows[1]
        assert primary["ean"] == "5555555555555"
        assert primary["is_primary"] == 1
        assert primary["synced_with_off"] == 1
        assert secondary["ean"] == "6666666666666"
        assert secondary["is_primary"] == 0
        assert secondary["synced_with_off"] == 0


    def test_real_backup_output_preserves_synced_off(
        self, app_ctx, db, seed_category, translations_dir
    ):
        """create_backup() output (unmodified) must restore synced_with_off=True
        on the primary EAN. Regression test for the bug where the unconditional
        top-level `ean` INSERT OR IGNORE pre-empted the `eans`-list insert and
        lost the synced flag."""
        from services import product_service
        from services.backup_core import create_backup, restore_backup

        product_service.add_product(
            {
                "type": "Snacks",
                "name": "SyncedProduct",
                "ean": "7310865004703",
                "from_off": True,
            }
        )

        backup = create_backup(include_images=False)
        # No modifications to backup — use real create_backup() output as-is

        get_db_conn = __import__("db", fromlist=["get_db"]).get_db
        get_db_conn().execute("DELETE FROM products")
        get_db_conn().commit()

        restore_backup(backup)

        new_pid = get_db_conn().execute(
            "SELECT id FROM products WHERE name='SyncedProduct'"
        ).fetchone()["id"]
        row = get_db_conn().execute(
            "SELECT ean, is_primary, synced_with_off FROM product_eans "
            "WHERE product_id = ? AND is_primary = 1",
            (new_pid,),
        ).fetchone()
        assert row is not None
        assert row["ean"] == "7310865004703"
        assert row["synced_with_off"] == 1


class TestImportSyncsProductEans:
    """Import overwrite/merge paths must keep product_eans aligned with
    products.ean. Without this, importing into a product whose EAN changes
    leaves the product_eans table stale, breaking the EAN editor."""

    def test_overwrite_updates_product_eans_when_ean_changes(
        self, app_ctx, db, seed_category, translations_dir
    ):
        from services import product_service
        from services.import_service import import_products

        pid = product_service.add_product(
            {"type": "Snacks", "name": "OverwriteEan", "ean": "7777777777777"}
        )["id"]
        import_products(
            {
                "products": [
                    {"type": "Snacks", "name": "OverwriteEan", "ean": "8888888888888"},
                ]
            },
            match_criteria="name",
            on_duplicate="overwrite",
        )
        rows = db.execute(
            "SELECT ean, is_primary FROM product_eans WHERE product_id = ?",
            (pid,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["ean"] == "8888888888888"
        assert rows[0]["is_primary"] == 1

    def test_overwrite_backfills_product_eans_when_missing(
        self, app_ctx, db, seed_category, translations_dir
    ):
        """If the existing product has products.ean set but no product_eans
        row (the data drift scenario), an overwrite import should leave it in
        a healthy state."""
        from services.import_service import import_products

        # Insert a product directly to bypass add_product's product_eans logic.
        # Use an explicit INSERT that includes the legacy ean column to
        # simulate the "drifted" state where products.ean is set but
        # product_eans is empty (INSERT_FIELDS no longer includes ean).
        from config import INSERT_FIELDS
        db.execute(
            f"INSERT INTO products ({INSERT_FIELDS}, ean, image) "
            f"VALUES ({','.join(['?'] * len(INSERT_FIELDS.split(',')))}, ?, ?)",
            ("Snacks", "DriftedProduct", "", "", "", "",
             None, None, None, None, None, None, None, None, None, None,
             None, None, None, None, None, None, "9999999999999", ""),
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name='DriftedProduct'"
        ).fetchone()["id"]
        # Sanity: product_eans is empty
        assert db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0] == 0

        import_products(
            {
                "products": [
                    {"type": "Snacks", "name": "DriftedProduct", "ean": "9999999999999"},
                ]
            },
            match_criteria="name",
            on_duplicate="overwrite",
        )
        rows = db.execute(
            "SELECT ean, is_primary FROM product_eans WHERE product_id = ?",
            (pid,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["ean"] == "9999999999999"
        assert rows[0]["is_primary"] == 1


class TestImportProducts:
    def test_import_adds_products(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
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
        from services.import_service import import_products
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
        from services.import_service import import_products

        with pytest.raises(ValueError, match="Invalid import"):
            import_products({})


class TestImportDuplicateControl:
    """Tests for match_criteria and on_duplicate parameters of import_products."""

    def _insert_product(self, db, name, ean="", cat="Snacks"):
        from config import INSERT_WITH_IMAGE_SQL

        db.execute(
            INSERT_WITH_IMAGE_SQL,
            (cat, name, "", "", "", "", None, None, None, None, None,
             None, None, None, None, None, None, None, None, None, None, None, ""),
        )
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if ean:
            db.execute(
                "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                (pid, ean),
            )
        db.commit()

    def test_default_skips_ean_duplicate(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Existing", ean="1234567890123")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Different", "ean": "1234567890123"}]}
        )
        assert "1 skipped" in msg

    def test_default_skips_name_duplicate(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Existing Product")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "existing product"}]}
        )
        assert "1 skipped" in msg

    def test_match_ean_only_allows_same_name(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Same Name")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Same Name", "ean": "9999999999999"}]},
            match_criteria="ean",
        )
        assert "Imported 1" in msg

    def test_match_name_only_allows_same_ean(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Product A", ean="1111111111111")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Product B", "ean": "1111111111111"}]},
            match_criteria="name",
        )
        assert "Imported 1" in msg

    def test_overwrite_updates_existing(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Overwrite Me", ean="2222222222222")
        # Give the existing product a brand value
        get_db().execute(
            "UPDATE products SET brand = 'OldBrand' WHERE id IN "
            "(SELECT product_id FROM product_eans WHERE ean = '2222222222222')"
        )
        get_db().commit()
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Overwrite Me", "ean": "2222222222222", "brand": "NewBrand"}]},
            on_duplicate="overwrite",
        )
        assert "1 overwritten" in msg
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '2222222222222'"
        ).fetchone()
        assert row["brand"] == "NewBrand"

    def test_overwrite_clears_fields_not_in_import(self, app_ctx, seed_category, translations_dir):
        """Overwrite replaces ALL fields — blank imported values clear existing data."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Full Product", ean="2222222222223")
        get_db().execute(
            "UPDATE products SET brand = 'ExistingBrand' WHERE id IN "
            "(SELECT product_id FROM product_eans WHERE ean = '2222222222223')"
        )
        get_db().commit()
        # Import without brand — should clear the existing brand
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Full Product", "ean": "2222222222223"}]},
            on_duplicate="overwrite",
        )
        assert "1 overwritten" in msg
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '2222222222223'"
        ).fetchone()
        assert row["brand"] == ""

    def test_allow_duplicate_creates_new(self, app_ctx, seed_category, translations_dir):
        from services.import_service import import_products
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
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Fallback Test", ean="4444444444444")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Fallback Test", "ean": "4444444444444"}]},
            match_criteria="invalid",
            on_duplicate="invalid",
        )
        assert "1 skipped" in msg


class TestImportMerge:
    """Tests for the merge on_duplicate mode with sync-aware rules."""

    def _insert_product(self, db, name, ean="", brand="", cat="Snacks", synced=False):
        from config import INSERT_WITH_IMAGE_SQL

        db.execute(
            INSERT_WITH_IMAGE_SQL,
            (cat, name, brand, "", "", "", None, None, None, None, None,
             None, None, None, None, None, None, None, None, None, None, None, ""),
        )
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if ean:
            db.execute(
                "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                (pid, ean),
            )
        if synced:
            db.execute(
                "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, 'is_synced_with_off')",
                (pid,),
            )
        db.commit()
        return pid

    def test_merge_fills_empty_fields(self, app_ctx, seed_category, translations_dir):
        """When existing field is empty, merge always fills it regardless of sync."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Product A", ean="1000000000001", brand="")
        msg = import_products(
            {"products": [{"type": "Snacks", "name": "Product A", "ean": "1000000000001", "brand": "NewBrand"}]},
            on_duplicate="merge",
        )
        assert "1 merged" in msg
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '1000000000001'"
        ).fetchone()
        assert row["brand"] == "NewBrand"

    def test_merge_existing_synced_keeps_existing(self, app_ctx, seed_category, translations_dir):
        """Existing synced + imported not synced → existing values win on conflicts."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Synced P", ean="2000000000002", brand="OldBrand", synced=True)
        import_products(
            {"products": [{"type": "Snacks", "name": "Synced P", "ean": "2000000000002", "brand": "ImportBrand"}]},
            on_duplicate="merge",
        )
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '2000000000002'"
        ).fetchone()
        assert row["brand"] == "OldBrand"

    def test_merge_imported_synced_overwrites(self, app_ctx, seed_category, translations_dir):
        """Imported synced + existing not synced → imported values win."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Local P", ean="3000000000003", brand="OldBrand", synced=False)
        import_products(
            {"products": [{
                "type": "Snacks", "name": "Local P", "ean": "3000000000003",
                "brand": "ImportBrand", "flags": ["is_synced_with_off"],
            }]},
            on_duplicate="merge",
        )
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '3000000000003'"
        ).fetchone()
        assert row["brand"] == "ImportBrand"

    def test_merge_both_synced_imported_wins(self, app_ctx, seed_category, translations_dir):
        """Both synced → imported wins."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Both Sync", ean="4000000000004", brand="OldBrand", synced=True)
        import_products(
            {"products": [{
                "type": "Snacks", "name": "Both Sync", "ean": "4000000000004",
                "brand": "ImportBrand", "flags": ["is_synced_with_off"],
            }]},
            on_duplicate="merge",
        )
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '4000000000004'"
        ).fetchone()
        assert row["brand"] == "ImportBrand"

    def test_merge_neither_synced_keep_existing(self, app_ctx, seed_category, translations_dir):
        """Neither synced + keep_existing → existing values win."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Neither A", ean="5000000000005", brand="OldBrand", synced=False)
        import_products(
            {"products": [{"type": "Snacks", "name": "Neither A", "ean": "5000000000005", "brand": "ImportBrand"}]},
            on_duplicate="merge",
            merge_priority="keep_existing",
        )
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '5000000000005'"
        ).fetchone()
        assert row["brand"] == "OldBrand"

    def test_merge_neither_synced_use_imported(self, app_ctx, seed_category, translations_dir):
        """Neither synced + use_imported → imported values win."""
        from services.import_service import import_products
        from db import get_db

        self._insert_product(get_db(), "Neither B", ean="6000000000006", brand="OldBrand", synced=False)
        import_products(
            {"products": [{"type": "Snacks", "name": "Neither B", "ean": "6000000000006", "brand": "ImportBrand"}]},
            on_duplicate="merge",
            merge_priority="use_imported",
        )
        row = get_db().execute(
            "SELECT p.brand FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = '6000000000006'"
        ).fetchone()
        assert row["brand"] == "ImportBrand"


class TestRestoreScoreWeights:
    def test_restore_weights(self, app_ctx, db):
        from services.backup_core import _restore_score_weights

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
        from services.backup_core import _restore_score_weights

        cur = db.cursor()
        _restore_score_weights(cur, [{"field": "nonexistent_field"}])
        db.commit()
        row = db.execute(
            "SELECT weight FROM score_weights WHERE field='nonexistent_field'"
        ).fetchone()
        assert row is None


class TestRestoreCategories:
    def test_restore_categories(self, app_ctx, db, translations_dir):
        from services.backup_core import _restore_categories

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
