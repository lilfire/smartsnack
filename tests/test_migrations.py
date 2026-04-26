"""Tests for migrations.py — database migration system."""


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

    def test_008_category_score_weights_table_exists(self, db):
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='category_score_weights'"
            ).fetchall()
        ]
        assert "category_score_weights" in tables

    def test_008_category_score_weights_has_correct_pk(self, db):
        info = db.execute("PRAGMA table_info(category_score_weights)").fetchall()
        pk_cols = [r["name"] for r in info if r["pk"] > 0]
        assert "category" in pk_cols
        assert "field" in pk_cols

    def test_008_category_score_weights_idempotent(self, db):
        from migrations import run_migrations

        cur = db.cursor()
        run_migrations(cur)
        db.commit()
        row = db.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE name='008_category_score_weights'"
        ).fetchone()
        assert row[0] == 1
