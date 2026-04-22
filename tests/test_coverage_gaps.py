"""Tests to bring coverage to ≥85% for files that were below threshold:
- app.py (79%)
- blueprints/backup.py (78%)
- blueprints/categories.py (80%)
- blueprints/core.py (84%)
- services/backup_service.py (81%)
"""

import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# app.py — missing lines: 20-22 (init_db error), 39 (HTTP error handler),
#   43-44 (generic error handler)
# ─────────────────────────────────────────────────────────────────────────────


class TestAppErrorHandlers:
    def test_http_error_handler_returns_json(self, client):
        """Line 39: HTTP errors return JSON."""
        resp = client.get("/nonexistent-route-xyz")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_unhandled_error_returns_500(self, client):
        """Lines 43-44: unhandled exceptions return 500 JSON."""
        with patch("blueprints.core.get_db", side_effect=RuntimeError("boom")):
            resp = client.get("/health")
            assert resp.status_code == 500
            data = resp.get_json()
            assert "error" in data

    def test_js_cache_headers(self, client):
        """Lines 33-34: JS responses get no-cache headers."""
        # Request a JS file — any static JS file will do
        resp = client.get("/static/js/app.js")
        if resp.status_code == 200 and resp.content_type and "javascript" in resp.content_type:
            assert "no-cache" in resp.headers.get("Cache-Control", "")


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/core.py — missing lines: 22-24 (health check db error)
# ─────────────────────────────────────────────────────────────────────────────


class TestCoreHealthError:
    def test_health_db_error(self, client):
        """Lines 22-24: health check returns error on DB failure."""
        with patch("blueprints.core.get_db", side_effect=sqlite3.OperationalError("fail")):
            resp = client.get("/health")
            assert resp.status_code == 500
            data = resp.get_json()
            assert data["status"] == "error"


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/backup.py — missing lines: 21 (api key denied), 39 (api key
#   denied restore), 45-47 (restore OSError/RuntimeError), 55 (api key denied
#   import), 67-71 (import errors)
# ─────────────────────────────────────────────────────────────────────────────


class TestBackupBlueprintApiKey:
    def test_backup_denied_without_api_key(self, client, monkeypatch):
        """Line 21: backup returns 401 when api key is required but missing."""
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        resp = client.get("/api/backup")
        assert resp.status_code == 401

    def test_restore_denied_without_api_key(self, client, monkeypatch):
        """Line 39: restore returns 401 when api key is required but missing."""
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        resp = client.post("/api/restore", json={"products": []})
        assert resp.status_code == 401

    def test_import_denied_without_api_key(self, client, monkeypatch):
        """Line 55: import returns 401 when api key is required but missing."""
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        resp = client.post("/api/import", json={"products": []})
        assert resp.status_code == 401


class TestBackupBlueprintErrors:
    def test_restore_oserror_returns_500(self, client):
        """Lines 45-47: OSError during restore returns 500."""
        with patch("services.backup_core.restore_backup", side_effect=OSError("disk fail")):
            resp = client.post("/api/restore", json={"products": []})
            assert resp.status_code == 500
            assert "Restore failed" in resp.get_json()["error"]

    def test_restore_runtime_error_returns_500(self, client):
        """Lines 45-47: RuntimeError during restore returns 500."""
        with patch("services.backup_core.restore_backup", side_effect=RuntimeError("fail")):
            resp = client.post("/api/restore", json={"products": []})
            assert resp.status_code == 500

    def test_restore_value_error_returns_400(self, client):
        """Line 44: ValueError during restore returns 400."""
        resp = client.post("/api/restore", json={})
        assert resp.status_code == 400

    def test_import_oserror_returns_500(self, client):
        """Lines 69-71: OSError during import returns 500."""
        with patch("services.import_service.import_products", side_effect=OSError("disk")):
            resp = client.post("/api/import", json={"products": []})
            assert resp.status_code == 500
            assert "Import failed" in resp.get_json()["error"]

    def test_import_value_error_returns_400(self, client):
        """Line 68: ValueError during import returns 400."""
        resp = client.post("/api/import", json={})
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/categories.py — missing lines: 27-28, 36, 42-43, 51, 55-56, 59-60
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoriesBlueprintEdgeCases:
    @pytest.fixture(autouse=True)
    def _use_temp_translations(self, translations_dir):
        pass

    def test_add_category_conflict(self, client, seed_category):
        """Lines 25-26: ConflictError when adding duplicate category."""
        resp = client.post(
            "/api/categories",
            json={"name": "Snacks", "label": "Snacks"},
        )
        assert resp.status_code == 409

    def test_add_category_missing_name(self, client):
        """Lines 27-28: ValueError when name is missing/invalid."""
        resp = client.post("/api/categories", json={"name": "", "label": ""})
        assert resp.status_code == 400

    def test_update_category_invalid_name(self, client):
        """Line 36: invalid category name returns 400."""
        resp = client.put(
            "/api/categories/" + "x" * 200,
            json={"label": "Test", "emoji": "🍎"},
        )
        assert resp.status_code == 400

    def test_update_category_empty_fields(self, client):
        """Lines 42-43: ValueError when nothing to update."""
        resp = client.put(
            "/api/categories/Snacks",
            json={"label": "", "emoji": ""},
        )
        assert resp.status_code == 400

    def test_delete_category_invalid_name(self, client):
        """Line 51: invalid category name on delete returns 400."""
        resp = client.delete("/api/categories/" + "x" * 200)
        assert resp.status_code == 400

    def test_delete_category_with_move_to(self, client, db, seed_category):
        """Lines 55-56: delete category with move_to parameter."""
        db.execute("INSERT INTO categories (name, emoji) VALUES ('TempCat', '📦')")
        db.commit()
        resp = client.delete(
            "/api/categories/TempCat",
            json={"move_to": "Snacks"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_delete_category_with_products_no_move(self, client, db, seed_product):
        """Lines 59-60: ValueError when deleting category with products but no move_to."""
        resp = client.delete("/api/categories/Snacks")
        assert resp.status_code == 400
        assert "Cannot delete" in resp.get_json()["error"]


# ─────────────────────────────────────────────────────────────────────────────
# services/backup_service.py — target the 69 missing lines
# ─────────────────────────────────────────────────────────────────────────────


class TestOptFloatEdgeCases:
    def test_invalid_string_raises(self):
        """Lines 94-95: non-numeric string raises ValueError."""
        from services.backup_core import _opt_float

        with pytest.raises(ValueError, match="Invalid numeric"):
            _opt_float("not_a_number")

    def test_nan_raises(self):
        """Line 97: NaN raises ValueError."""
        from services.backup_core import _opt_float

        with pytest.raises(ValueError, match="Non-finite"):
            _opt_float(float("nan"))

    def test_inf_raises(self):
        """Line 97: Infinity raises ValueError."""
        from services.backup_core import _opt_float

        with pytest.raises(ValueError, match="Non-finite"):
            _opt_float(float("inf"))


class TestOverwriteProduct:
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
        return pid

    def test_overwrite_all_fields(self, app_ctx, db, seed_category):
        """Lines 112-148: overwrite replaces all fields including flags."""
        from services.import_service import _overwrite_product

        pid = self._insert_product(db, "Overwrite Test", ean="OW123")
        cur = db.cursor()
        _overwrite_product(
            cur, pid,
            {
                "type": "Snacks", "name": "Overwrite Test", "ean": "OW123",
                "brand": "NewBrand", "stores": "", "ingredients": "",
                "taste_note": "", "taste_score": 5, "kcal": 100,
                "energy_kj": 418, "carbs": 10, "sugar": 5, "fat": 3,
                "saturated_fat": 1, "protein": 8, "fiber": 2, "salt": 0.5,
                "volume": None, "price": None, "weight": None, "portion": None,
                "est_pdcaas": None, "est_diaas": None,
                "image": "data:image/png;base64,abc",
                "flags": ["is_synced_with_off"],
            },
        )
        db.commit()
        row = db.execute("SELECT brand, image FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["brand"] == "NewBrand"
        assert row["image"] == "data:image/png;base64,abc"

    def test_overwrite_text_too_long(self, app_ctx, db, seed_category):
        """Line 117: text field exceeding max length raises ValueError."""
        from services.import_service import _overwrite_product

        pid = self._insert_product(db, "Long Text Test")
        cur = db.cursor()
        with pytest.raises(ValueError, match="exceeds max length"):
            _overwrite_product(cur, pid, {"name": "x" * 300})


class TestMergeProduct:
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

    def test_merge_text_too_long(self, app_ctx, db, seed_category):
        """Line 164: merge raises ValueError for too-long text."""
        from services.import_service import _merge_product

        pid = self._insert_product(db, "Merge Long")
        cur = db.cursor()
        with pytest.raises(ValueError, match="exceeds max length"):
            _merge_product(cur, pid, {"name": "x" * 300}, "keep_existing")

    def test_merge_numeric_fields(self, app_ctx, db, seed_category):
        """Lines 197-199: merge handles numeric fields via _opt_float."""
        from services.import_service import _merge_product

        pid = self._insert_product(db, "Merge Numeric", ean="MN001")
        cur = db.cursor()
        _merge_product(
            cur, pid,
            {"kcal": 200, "protein": 15, "flags": []},
            "keep_existing",
        )
        db.commit()
        row = db.execute("SELECT kcal, protein FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["kcal"] == 200
        assert row["protein"] == 15

    def test_merge_image_fill_empty(self, app_ctx, db, seed_category):
        """Lines 214-217: merge fills image when existing is empty."""
        from services.import_service import _merge_product

        pid = self._insert_product(db, "Merge Img")
        cur = db.cursor()
        _merge_product(
            cur, pid,
            {"image": "data:image/png;base64,xyz", "flags": []},
            "keep_existing",
        )
        db.commit()
        row = db.execute("SELECT image FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["image"] == "data:image/png;base64,xyz"

    def test_merge_image_imported_wins(self, app_ctx, db, seed_category):
        """Lines 214-217: merge replaces image when imported wins."""
        from services.import_service import _merge_product

        pid = self._insert_product(db, "Merge Img2", synced=False)
        # Set existing image
        db.execute("UPDATE products SET image = 'old_img' WHERE id = ?", (pid,))
        db.commit()
        cur = db.cursor()
        _merge_product(
            cur, pid,
            {"image": "new_img", "flags": ["is_synced_with_off"]},
            "keep_existing",
        )
        db.commit()
        row = db.execute("SELECT image FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["image"] == "new_img"


class TestRestoreProteinQualityEdgeCases:
    def test_pq_with_label_fallback_name(self, app_ctx, db):
        """Lines 451-455: protein quality entry with no name, using label as fallback."""
        from services.backup_core import _restore_protein_quality

        cur = db.cursor()
        pending = _restore_protein_quality(
            cur,
            [{"label": "Whey Protein", "pdcaas": 1.0, "diaas": 1.0}],
        )
        db.commit()
        row = db.execute(
            "SELECT name FROM protein_quality WHERE name = 'whey_protein'"
        ).fetchone()
        assert row is not None

    def test_pq_with_keywords_fallback_name(self, app_ctx, db):
        """Lines 451-455: protein quality entry with no name/label, using first keyword."""
        from services.backup_core import _restore_protein_quality

        cur = db.cursor()
        _restore_protein_quality(
            cur,
            [{"keywords": ["casein", "milk protein"], "pdcaas": 0.9, "diaas": 0.9}],
        )
        db.commit()
        row = db.execute(
            "SELECT name FROM protein_quality WHERE name = 'casein'"
        ).fetchone()
        assert row is not None

    def test_pq_legacy_flat_label_and_keywords(self, app_ctx, db, translations_dir):
        """Lines 479-491: legacy format with flat label/keywords fields."""
        from services.backup_core import _restore_protein_quality

        cur = db.cursor()
        pending = _restore_protein_quality(
            cur,
            [{
                "name": "legacy_src",
                "pdcaas": 0.8,
                "diaas": 0.75,
                "label": "Legacy Source",
                "keywords": "milk, cheese, yogurt",
            }],
        )
        db.commit()
        # Should produce translation entries for label and keywords
        label_entries = [p for p in pending if "label" in p[0]]
        kw_entries = [p for p in pending if "keywords" in p[0]]
        assert len(label_entries) >= 1
        assert len(kw_entries) >= 1

    def test_pq_legacy_keywords_as_list(self, app_ctx, db, translations_dir):
        """Lines 488-496: legacy keywords as list."""
        from services.backup_core import _restore_protein_quality

        cur = db.cursor()
        pending = _restore_protein_quality(
            cur,
            [{
                "name": "legacy_list",
                "pdcaas": 0.7,
                "diaas": 0.7,
                "keywords": ["egg", "oeuf"],
            }],
        )
        db.commit()
        kw_entries = [p for p in pending if "keywords" in p[0]]
        assert len(kw_entries) >= 1


class TestRestoreFlagDefinitionsEdgeCases:
    def test_empty_name_skipped(self, app_ctx, db, translations_dir):
        """Line 510: flag definition with empty name is skipped."""
        from services.backup_core import _restore_flag_definitions

        cur = db.cursor()
        _restore_flag_definitions(
            cur,
            [{"name": "", "type": "user"}, {"name": "valid_flag", "type": "user"}],
        )
        db.commit()
        rows = db.execute("SELECT name FROM flag_definitions WHERE name = ''").fetchall()
        assert len(rows) == 0

    def test_invalid_type_defaults_to_user(self, app_ctx, db, translations_dir):
        """Line 512: invalid type defaults to 'user'."""
        from services.backup_core import _restore_flag_definitions

        cur = db.cursor()
        _restore_flag_definitions(
            cur,
            [{"name": "typed_flag", "type": "invalid_type"}],
        )
        db.commit()
        row = db.execute(
            "SELECT type FROM flag_definitions WHERE name = 'typed_flag'"
        ).fetchone()
        assert row["type"] == "user"


class TestRestoreBackupRollback:
    def test_restore_rolls_back_on_error(self, app_ctx, db, translations_dir):
        """Lines 561-564: restore rolls back on exception."""
        from services.backup_core import restore_backup
        from db import get_db

        before = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with pytest.raises(Exception):
            restore_backup({
                "products": [
                    {"type": "Snacks", "name": "Good Product"},
                    {"type": "Snacks", "name": "x" * 300},  # will fail
                ],
            })
        after = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert after == before  # rolled back


class TestImportWithCategoriesAndFlags:
    @pytest.fixture(autouse=True)
    def _use_temp_translations(self, translations_dir):
        pass

    def test_import_with_category_translations(self, app_ctx, seed_category):
        """Lines 597-613: import creates categories with translations."""
        from services.import_service import import_products

        import_products({
            "categories": [
                {
                    "name": "ImportedCat",
                    "emoji": "🍎",
                    "translations": {"no": "Importert Kategori", "en": "Imported Category"},
                },
            ],
            "products": [{"type": "ImportedCat", "name": "Cat Product"}],
        })
        from db import get_db

        row = get_db().execute(
            "SELECT emoji FROM categories WHERE name = 'ImportedCat'"
        ).fetchone()
        assert row["emoji"] == "🍎"

    def test_import_with_category_label_legacy(self, app_ctx, seed_category):
        """Lines 604-606: import with legacy label field creates translations for all langs."""
        from services.import_service import import_products

        import_products({
            "categories": [
                {"name": "LegacyCat", "emoji": "📦", "label": "Legacy Label"},
            ],
            "products": [],
        })
        from db import get_db

        row = get_db().execute(
            "SELECT name FROM categories WHERE name = 'LegacyCat'"
        ).fetchone()
        assert row is not None

    def test_import_duplicate_category_ignored(self, app_ctx, seed_category):
        """Line 612: IntegrityError on duplicate category is silently ignored."""
        from services.import_service import import_products

        import_products({
            "categories": [{"name": "Snacks", "emoji": "🍿"}],
            "products": [],
        })
        # Should not raise

    def test_import_with_flag_definitions(self, app_ctx, seed_category):
        """Lines 615-630: import creates flag definitions with translations."""
        from services.import_service import import_products

        import_products({
            "flag_definitions": [
                {
                    "name": "imported_flag",
                    "type": "user",
                    "translations": {"no": "Importert Flagg"},
                },
            ],
            "products": [],
        })
        from db import get_db

        row = get_db().execute(
            "SELECT name FROM flag_definitions WHERE name = 'imported_flag'"
        ).fetchone()
        assert row is not None

    def test_import_duplicate_flag_definition_ignored(self, app_ctx, seed_category):
        """Line 630: IntegrityError on duplicate flag definition is silently ignored."""
        from services.import_service import import_products
        from db import get_db

        # First import
        import_products({
            "flag_definitions": [{"name": "dup_flag", "type": "user"}],
            "products": [],
        })
        # Second import — same flag — should not raise
        import_products({
            "flag_definitions": [{"name": "dup_flag", "type": "user"}],
            "products": [],
        })

    def test_import_flag_definition_invalid_type_skipped(self, app_ctx, seed_category):
        """Line 618: flag definition with invalid type is skipped during import."""
        from services.import_service import import_products
        from db import get_db

        import_products({
            "flag_definitions": [{"name": "bad_type_flag", "type": "invalid"}],
            "products": [],
        })
        row = get_db().execute(
            "SELECT name FROM flag_definitions WHERE name = 'bad_type_flag'"
        ).fetchone()
        assert row is None

    def test_import_auto_creates_category_dedup(self, app_ctx, seed_category):
        """Lines 638-654: auto-create category from product type, with dedup."""
        from services.import_service import import_products
        from db import get_db

        import_products({
            "products": [
                {"type": "AutoCoffee", "name": "Item1"},
                {"type": "AutoCoffee", "name": "Item2"},
            ],
        })
        rows = get_db().execute(
            "SELECT name FROM categories WHERE name = 'AutoCoffee'"
        ).fetchall()
        assert len(rows) == 1


class TestImportRollback:
    @pytest.fixture(autouse=True)
    def _use_temp_translations(self, translations_dir):
        pass

    def test_import_rolls_back_on_error(self, app_ctx, seed_category):
        """Lines 686-689: import rolls back on exception."""
        from services.import_service import import_products
        from db import get_db

        before = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with pytest.raises(Exception):
            import_products({
                "products": [
                    {"type": "Snacks", "name": "Good"},
                    {"type": "Snacks", "name": "x" * 300},  # will fail
                ],
            })
        after = get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert after == before

    def test_import_invalid_merge_priority_defaults(self, app_ctx, seed_category):
        """Line 587: invalid merge_priority falls back to keep_existing."""
        from services.import_service import import_products

        msg = import_products(
            {"products": [{"type": "Snacks", "name": "MP Test"}]},
            merge_priority="invalid",
        )
        assert "Imported 1" in msg
