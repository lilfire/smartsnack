"""Tests for db.py — database connection management and schema init."""

import sqlite3


class TestGetDb:
    def test_returns_connection(self, app_ctx):
        from db import get_db

        conn = get_db()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

    def test_returns_same_connection(self, app_ctx):
        from db import get_db

        conn1 = get_db()
        conn2 = get_db()
        assert conn1 is conn2

    def test_row_factory_set(self, app_ctx):
        from db import get_db

        conn = get_db()
        row = conn.execute("SELECT 1 as val").fetchone()
        assert row["val"] == 1


class TestCloseDb:
    def test_close_removes_from_g(self, app_ctx):
        from db import get_db, close_db
        from flask import g

        get_db()
        assert "db" in g
        close_db()
        assert "db" not in g

    def test_close_without_db(self, app_ctx):
        from db import close_db, get_db
        from flask import g

        close_db()
        assert "db" not in g  # still absent: close with no DB open is a silent no-op
        db = get_db()
        assert db is not None  # normal DB access still works after the no-op close


class TestInitDb:
    def test_tables_created(self, db):
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "products" in tables
        assert "categories" in tables
        assert "score_weights" in tables
        assert "protein_quality" in tables
        assert "user_settings" in tables
        assert "schema_migrations" in tables

    def test_default_category_seeded(self, db):
        row = db.execute("SELECT name FROM categories WHERE name='Snacks'").fetchone()
        assert row is not None

    def test_default_language_seeded(self, db):
        row = db.execute(
            "SELECT value FROM user_settings WHERE key='language'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "no"

    def test_score_weights_seeded(self, db):
        count = db.execute("SELECT COUNT(*) FROM score_weights").fetchone()[0]
        from config import SCORE_CONFIG

        assert count == len(SCORE_CONFIG)

    def test_protein_quality_seeded(self, db):
        count = db.execute("SELECT COUNT(*) FROM protein_quality").fetchone()[0]
        from config import PQ_SEED

        assert count == len(PQ_SEED)


class TestSeedProducts:
    def test_demo_product_exists(self, db):
        row = db.execute(
            "SELECT name FROM products WHERE name='Classic Popcorn'"
        ).fetchone()
        assert row is not None

    def test_demo_product_has_image(self, db):
        row = db.execute(
            "SELECT image FROM products WHERE name='Classic Popcorn'"
        ).fetchone()
        assert row["image"].startswith("data:image/png")


class TestEanSyncTriggers:
    """Verify that the SQLite triggers keep products.ean in sync with product_eans."""

    def _insert_product(self, db, name, ean=""):
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES ('Snacks', ?, ?, '')",
            (name, ean),
        )
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_insert_primary_ean_syncs_products_ean(self, db):
        pid = self._insert_product(db, "TriggerInsert")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '12345678', 1)",
            (pid,),
        )
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "12345678"

    def test_insert_non_primary_ean_does_not_change_products_ean(self, db):
        pid = self._insert_product(db, "TriggerNonPrimary", "11111111")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '11111111', 1)",
            (pid,),
        )
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '22222222', 0)",
            (pid,),
        )
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "11111111"

    def test_update_primary_ean_value_syncs_products_ean(self, db):
        pid = self._insert_product(db, "TriggerUpdateValue")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '11111111', 1)",
            (pid,),
        )
        db.execute(
            "UPDATE product_eans SET ean = '99999999' WHERE product_id = ? AND is_primary = 1",
            (pid,),
        )
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "99999999"

    def test_demote_primary_clears_products_ean(self, db):
        pid = self._insert_product(db, "TriggerDemote")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '11111111', 1)",
            (pid,),
        )
        db.execute(
            "UPDATE product_eans SET is_primary = 0 WHERE product_id = ?", (pid,)
        )
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == ""

    def test_delete_primary_row_clears_products_ean(self, db):
        pid = self._insert_product(db, "TriggerDeletePrimary")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '11111111', 1)",
            (pid,),
        )
        db.execute("DELETE FROM product_eans WHERE product_id = ?", (pid,))
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == ""

    def test_delete_secondary_row_does_not_change_products_ean(self, db):
        pid = self._insert_product(db, "TriggerDeleteSecondary")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '11111111', 1)",
            (pid,),
        )
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '22222222', 0)",
            (pid,),
        )
        sec_id = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = '22222222'", (pid,)
        ).fetchone()[0]
        db.execute("DELETE FROM product_eans WHERE id = ?", (sec_id,))
        db.commit()
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "11111111"

    def test_triggers_exist_in_schema(self, db):
        triggers = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
        assert "trg_ean_insert_sync" in triggers
        assert "trg_ean_update_sync" in triggers
        assert "trg_ean_delete_sync" in triggers


class TestRepairEanMismatches:
    """Verify startup repair of pre-existing products.ean mismatches."""

    def _insert_product(self, db, name, ean=""):
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES ('Snacks', ?, ?, '')",
            (name, ean),
        )
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_repairs_mismatch(self, db):
        from db import _repair_ean_mismatches

        pid = self._insert_product(db, "RepairTest")
        db.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, '12345678', 1)",
            (pid,),
        )
        # Artificially introduce mismatch by directly updating products.ean
        db.execute("UPDATE products SET ean = 'wrongean' WHERE id = ?", (pid,))
        db.commit()

        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "wrongean"

        count = _repair_ean_mismatches(db.cursor())
        db.commit()

        assert count >= 1
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == "12345678"

    def test_no_mismatches_returns_zero(self, db):
        from db import _repair_ean_mismatches

        count = _repair_ean_mismatches(db.cursor())
        assert count == 0

    def test_clears_ean_when_no_primary_row_exists(self, db):
        from db import _repair_ean_mismatches

        pid = self._insert_product(db, "OrphanEan", "orphanvalue")
        # No product_eans row — products.ean should be cleared
        db.commit()

        count = _repair_ean_mismatches(db.cursor())
        db.commit()

        assert count >= 1
        row = db.execute("SELECT ean FROM products WHERE id = ?", (pid,)).fetchone()
        assert row["ean"] == ""
