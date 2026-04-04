"""Tests for migrations.py — database migration system."""

import sqlite3


import contextlib


@contextlib.contextmanager
def _make_conn():
    """Yield an in-memory SQLite connection and close it when done."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _setup_minimal_schema(conn):
    """Create the minimal schema needed before running tag system migration."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


class TestTagSystemMigration:
    """Tests for 009_tag_system_reimplementation migration."""

    def test_old_schema_migrates_data(self):
        """Old product_tags(tag TEXT) data is migrated to tags + product_tags(tag_id)."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("INSERT INTO products (id, type, name) VALUES (1, 'Snacks', 'Test')")
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag TEXT NOT NULL COLLATE NOCASE,
                    PRIMARY KEY (product_id, tag)
                )
            """)
            conn.execute("INSERT INTO product_tags VALUES (1, 'Organic')")
            conn.execute("INSERT INTO product_tags VALUES (1, 'Vegan')")
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            tags = {r[0] for r in conn.execute("SELECT label FROM tags").fetchall()}
            assert "organic" in tags
            assert "vegan" in tags

            cols = {r[1] for r in conn.execute("PRAGMA table_info(product_tags)").fetchall()}
            assert "tag_id" in cols
            assert "tag" not in cols

            rows = conn.execute(
                "SELECT pt.product_id, t.label FROM product_tags pt JOIN tags t ON t.id = pt.tag_id"
            ).fetchall()
            linked = {(r[0], r[1]) for r in rows}
            assert (1, "organic") in linked
            assert (1, "vegan") in linked

    def test_old_schema_drops_temp_table(self):
        """product_tags_old is cleaned up after migration."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (product_id, tag)
                )
            """)
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "product_tags_old" not in tables

    def test_new_schema_noop(self):
        """Fresh install with new product_tags schema is a no-op (no rename, no data loss)."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("""
                CREATE TABLE tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL UNIQUE COLLATE NOCASE
                )
            """)
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (product_id, tag_id)
                )
            """)
            conn.execute("INSERT INTO tags (label) VALUES ('healthy')")
            conn.execute("INSERT INTO products (id, type, name) VALUES (1, 'Snacks', 'Test')")
            conn.execute("INSERT INTO product_tags VALUES (1, 1)")
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            count = conn.execute("SELECT COUNT(*) FROM product_tags").fetchone()[0]
            assert count == 1
            cols = {r[1] for r in conn.execute("PRAGMA table_info(product_tags)").fetchall()}
            assert "tag_id" in cols
            assert "tag" not in cols

    def test_old_schema_whitespace_and_case_normalised(self):
        """Tags with leading/trailing whitespace and mixed case are normalised."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (product_id, tag)
                )
            """)
            conn.execute("INSERT INTO products (id, type, name) VALUES (1, 'S', 'P')")
            conn.execute("INSERT INTO product_tags VALUES (1, '  Organic  ')")
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            labels = [r[0] for r in conn.execute("SELECT label FROM tags").fetchall()]
            assert labels == ["organic"]

    def test_old_schema_empty_tags_skipped(self):
        """Blank/whitespace-only tags in old schema are not inserted into tags table."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (product_id, tag)
                )
            """)
            conn.execute("INSERT INTO products (id, type, name) VALUES (1, 'S', 'P')")
            conn.execute("INSERT INTO product_tags VALUES (1, '   ')")
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            count = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
            assert count == 0

    def test_indexes_created(self):
        """Migration creates the expected indexes on product_tags and tags."""
        from migrations import _migrate_008_tag_system

        with _make_conn() as conn:
            _setup_minimal_schema(conn)
            conn.execute("""
                CREATE TABLE product_tags (
                    product_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (product_id, tag)
                )
            """)
            conn.commit()

            cur = conn.cursor()
            _migrate_008_tag_system(cur)
            conn.commit()

            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
            assert "idx_product_tags_product_id" in indexes
            assert "idx_product_tags_tag_id" in indexes
            assert "idx_tags_label" in indexes


class TestRunMigrations:
    def test_creates_schema_migrations_table(self, db):
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchall()
        ]
        assert "schema_migrations" in tables

    def test_migrations_tracked(self, db):
        from migrations import MIGRATIONS

        applied = {
            r[0] for r in db.execute("SELECT name FROM schema_migrations").fetchall()
        }
        for name, _ in MIGRATIONS:
            assert name in applied

    def test_idempotent_rerun(self, db):
        from migrations import run_migrations

        cur = db.cursor()
        # Running again should not raise
        run_migrations(cur)
        db.commit()
        applied = db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        from migrations import MIGRATIONS

        assert applied == len(MIGRATIONS)

    def test_volume_migration_applied(self, db):
        row = db.execute(
            "SELECT formula, formula_min, formula_max FROM score_weights WHERE field='volume'"
        ).fetchone()
        assert row["formula"] == "direct"
        assert row["formula_min"] == 1
        assert row["formula_max"] == 3
