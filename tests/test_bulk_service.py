"""Tests for services/bulk_service.py — refresh status and PQ estimation."""


class TestGetRefreshStatus:
    def test_returns_dict(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        assert isinstance(result, dict)

    def test_contains_running_key(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        assert "running" in result

    def test_contains_done_key(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        assert "done" in result

    def test_contains_progress_keys(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        assert "current" in result
        assert "total" in result

    def test_contains_counter_keys(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        assert "updated" in result
        assert "skipped" in result
        assert "errors" in result

    def test_idle_state_not_running(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        # At startup the job is not running
        assert result["running"] is False

    def test_idle_state_not_done(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        # Initially done is False (no job has run yet)
        assert result["done"] is False

    def test_report_absent_when_not_done(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        # When not done, report should be absent from the snapshot
        assert "report" not in result

    def test_returns_snapshot_not_reference(self, app_ctx):
        from services.bulk_service import get_refresh_status

        r1 = get_refresh_status()
        r2 = get_refresh_status()
        # Each call returns a fresh dict, not the same object
        assert r1 is not r2


class TestEstimateAllPq:
    def test_returns_dict(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert isinstance(result, dict)

    def test_has_total_key(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert "total" in result

    def test_has_updated_key(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert "updated" in result

    def test_has_skipped_key(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert "skipped" in result

    def test_total_equals_updated_plus_skipped(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert result["total"] == result["updated"] + result["skipped"]

    def test_seed_product_with_known_ingredient_is_updated(
        self, app_ctx, db, translations_dir
    ):
        """Seed product has 'Corn' — if a PQ entry with 'corn' keyword exists, it gets updated."""
        from services.bulk_service import estimate_all_pq
        from translations import _set_translation_key

        # Ensure the 'corn' PQ entry has its keyword registered so the estimator
        # can match against the seed product's ingredients "Corn, sunflower oil, sea salt".
        # The seeded PQ table may or may not have corn; insert one explicitly.
        existing = db.execute(
            "SELECT id FROM protein_quality WHERE name = 'corn'"
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO protein_quality (name, pdcaas, diaas) VALUES (?, ?, ?)",
                ("corn", 0.42, 0.35),
            )
            db.commit()

        _set_translation_key("pq_corn_keywords", {"no": "corn, mais"})

        result = estimate_all_pq()
        assert result["total"] >= 1
        assert result["updated"] >= 1

        # Confirm the DB was written
        row = db.execute(
            "SELECT est_pdcaas, est_diaas FROM products WHERE ingredients != '' LIMIT 1"
        ).fetchone()
        assert row["est_pdcaas"] is not None
        assert row["est_diaas"] is not None

    def test_product_without_ingredients_is_excluded(self, app_ctx, db):
        """Products with no ingredients text are never counted in total."""
        from services.bulk_service import estimate_all_pq

        # Insert a product with empty ingredients
        db.execute(
            "INSERT INTO products (type, name, ingredients, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "No-Ingredient Product", "", ""),
        )
        db.commit()

        result = estimate_all_pq()
        # The no-ingredient product must not appear in the total
        ingredient_count = db.execute(
            "SELECT COUNT(*) FROM products "
            "WHERE ingredients IS NOT NULL AND ingredients != ''"
        ).fetchone()[0]
        assert result["total"] == ingredient_count

    def test_product_with_unrecognised_ingredients_is_skipped(self, app_ctx, db):
        """Products whose ingredients match no PQ entry are skipped, not updated."""
        from services.bulk_service import estimate_all_pq

        db.execute(
            "INSERT INTO products (type, name, ingredients, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Mystery Product", "zzz_unknown_ingredient_xyz", ""),
        )
        db.commit()

        result = estimate_all_pq()

        after = db.execute(
            "SELECT COUNT(*) FROM products "
            "WHERE ingredients IS NOT NULL AND ingredients != '' "
            "AND est_pdcaas IS NULL"
        ).fetchone()[0]

        # The mystery product should remain with NULL pdcaas (skipped)
        assert result["skipped"] >= 1
        assert after >= 1

    def test_counters_are_non_negative_integers(self, app_ctx):
        from services.bulk_service import estimate_all_pq

        result = estimate_all_pq()
        assert isinstance(result["total"], int) and result["total"] >= 0
        assert isinstance(result["updated"], int) and result["updated"] >= 0
        assert isinstance(result["skipped"], int) and result["skipped"] >= 0
