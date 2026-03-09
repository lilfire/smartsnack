"""Tests for db.py — database connection management and schema init."""

import sqlite3
import pytest


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
        from db import close_db
        # Should not raise
        close_db()


class TestInitDb:
    def test_tables_created(self, db):
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
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
        row = db.execute("SELECT value FROM user_settings WHERE key='language'").fetchone()
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
        row = db.execute("SELECT name FROM products WHERE name='Classic Popcorn'").fetchone()
        assert row is not None

    def test_demo_product_has_image(self, db):
        row = db.execute("SELECT image FROM products WHERE name='Classic Popcorn'").fetchone()
        assert row["image"].startswith("data:image/png")
