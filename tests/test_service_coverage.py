"""Additional tests for proxy_service and bulk_service to reach 75%+ coverage."""

import json
from unittest.mock import patch, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — off_search
# ─────────────────────────────────────────────────────────────────────────────


class TestOffSearch:
    def test_query_too_short_raises(self):
        from services.proxy_service import off_search

        with pytest.raises(ValueError, match="too short"):
            off_search("")

    def test_query_single_char_raises(self):
        from services.proxy_service import off_search

        with pytest.raises(ValueError, match="too short"):
            off_search("a")

    def test_combines_results_from_both_backends(self):
        from services.proxy_service import off_search

        products_a = [
            {"code": "111", "product_name": "Chips A", "completeness": 0.9},
        ]
        products_c = [
            {"code": "222", "product_name": "Chips B", "completeness": 0.8},
        ]
        with patch("services.proxy_service._off_search_a_licious", return_value={"products": products_a}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": products_c}):
            result = off_search("Chips")

        assert result["count"] == 2
        codes = [p["code"] for p in result["products"]]
        assert "111" in codes
        assert "222" in codes

    def test_deduplicates_by_code(self):
        from services.proxy_service import off_search

        products_a = [{"code": "111", "product_name": "Chips", "completeness": 0.9}]
        products_c = [{"code": "111", "product_name": "Chips", "completeness": 0.9}]
        with patch("services.proxy_service._off_search_a_licious", return_value={"products": products_a}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": products_c}):
            result = off_search("Chips")

        assert result["count"] == 1

    def test_handles_a_licious_failure(self):
        from services.proxy_service import off_search

        products_c = [{"code": "222", "product_name": "Chips", "completeness": 0.8}]
        with patch("services.proxy_service._off_search_a_licious", side_effect=RuntimeError("down")), \
             patch("services.proxy_service._off_search_classic", return_value={"products": products_c}):
            result = off_search("Chips")

        assert result["count"] == 1

    def test_handles_classic_failure(self):
        from services.proxy_service import off_search

        products_a = [{"code": "111", "product_name": "Chips", "completeness": 0.9}]
        with patch("services.proxy_service._off_search_a_licious", return_value={"products": products_a}), \
             patch("services.proxy_service._off_search_classic", side_effect=RuntimeError("down")):
            result = off_search("Chips")

        assert result["count"] == 1

    def test_handles_both_failures(self):
        from services.proxy_service import off_search

        with patch("services.proxy_service._off_search_a_licious", side_effect=RuntimeError("down")), \
             patch("services.proxy_service._off_search_classic", side_effect=RuntimeError("down")):
            result = off_search("Chips")

        assert result["count"] == 0

    def test_non_list_products_ignored(self):
        from services.proxy_service import off_search

        with patch("services.proxy_service._off_search_a_licious", return_value={"products": "bad"}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": None}):
            result = off_search("Chips")

        assert result["count"] == 0

    def test_non_dict_items_skipped(self):
        from services.proxy_service import off_search

        products_a = [{"code": "111", "product_name": "Chips"}, "not_a_dict", 42]
        with patch("services.proxy_service._off_search_a_licious", return_value={"products": products_a}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": []}):
            result = off_search("Chips")

        assert result["count"] == 1

    def test_with_nutrition_param(self):
        from services.proxy_service import off_search

        product = {
            "code": "111",
            "product_name": "Protein Bar",
            "nutriments": {"proteins_100g": 20},
            "completeness": 0.9,
        }
        with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": []}):
            result = off_search("Protein Bar", nutrition={"protein": 20})

        assert result["count"] == 1
        assert "certainty" in result["products"][0]

    def test_a_licious_returns_hits_key(self):
        from services.proxy_service import off_search

        with patch("services.proxy_service._off_search_a_licious", return_value={"hits": [{"code": "111", "product_name": "X"}]}), \
             patch("services.proxy_service._off_search_classic", return_value={"products": []}):
            result = off_search("test query")

        assert result["count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — off_product
# ─────────────────────────────────────────────────────────────────────────────


class TestOffProduct:
    def test_invalid_code_raises(self):
        from services.proxy_service import off_product

        with pytest.raises(ValueError, match="Invalid"):
            off_product("")

    def test_non_digit_code_raises(self):
        from services.proxy_service import off_product

        with pytest.raises(ValueError, match="Invalid"):
            off_product("abc123")

    def test_valid_code_returns_data(self):
        from services.proxy_service import off_product

        mock_data = {"product": {"code": "1234567890123"}, "status": 1}
        with patch("services.proxy_service._off_get_json", return_value=mock_data):
            result = off_product("1234567890123")

        assert result["status"] == 1

    def test_runtime_error_returns_not_found(self):
        from services.proxy_service import off_product

        with patch("services.proxy_service._off_get_json", side_effect=RuntimeError("404")):
            result = off_product("1234567890123")

        assert result["status"] == 0
        assert "not found" in result["status_verbose"]


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _off_get_json
# ─────────────────────────────────────────────────────────────────────────────


class TestOffGetJson:
    def test_success(self):
        from services.proxy_service import _off_get_json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _off_get_json("https://example.com/api")

        assert result["ok"] is True

    def test_failure_raises_runtime_error(self):
        from services.proxy_service import _off_get_json

        with patch("urllib.request.urlopen", side_effect=Exception("network")):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                _off_get_json("https://example.com/api")


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _off_search_a_licious
# ─────────────────────────────────────────────────────────────────────────────


class TestOffSearchALicious:
    def test_normalizes_hits_to_products(self):
        from services.proxy_service import _off_search_a_licious

        api_response = {"hits": [{"code": "123", "product_name": "Test"}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(api_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _off_search_a_licious("test")

        assert "products" in result
        assert len(result["products"]) == 1

    def test_nested_es_format(self):
        from services.proxy_service import _off_search_a_licious

        api_response = {
            "hits": {
                "total": 1,
                "hits": [{"_source": {"code": "123", "product_name": "Test"}}],
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(api_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _off_search_a_licious("test")

        assert result["products"][0]["code"] == "123"

    def test_error_raises_runtime_error(self):
        from services.proxy_service import _off_search_a_licious

        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            with pytest.raises(RuntimeError, match="search-a-licious"):
                _off_search_a_licious("test")

    def test_products_key_already_present(self):
        from services.proxy_service import _off_search_a_licious

        api_response = {"products": [{"code": "123"}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(api_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _off_search_a_licious("test")

        assert len(result["products"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _off_search_classic
# ─────────────────────────────────────────────────────────────────────────────


class TestOffSearchClassic:
    def test_calls_off_get_json(self):
        from services.proxy_service import _off_search_classic

        with patch("services.proxy_service._off_get_json", return_value={"products": []}) as mock_get:
            result = _off_search_classic("chips")

        assert result == {"products": []}
        mock_get.assert_called_once()
        assert "chips" in mock_get.call_args[0][0]


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _compute_certainty with category
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeCertaintyWithCategory:
    def test_category_boost_with_lang(self):
        from services.proxy_service import _compute_certainty

        product = {
            "product_name": "Snacks Chips",
            "brands": "",
            "lang": "no",
        }
        with_cat = _compute_certainty("Chips", product, category="Snacks")
        without_cat = _compute_certainty("Chips", product)
        assert with_cat >= without_cat

    def test_category_no_lang_field(self):
        from services.proxy_service import _compute_certainty

        product = {"product_name": "Snacks Chips", "brands": ""}
        score = _compute_certainty("Chips", product, category="Snacks")
        assert score > 0


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _compute_nutrition_similarity edge cases
# ─────────────────────────────────────────────────────────────────────────────


class TestNutritionSimilarityEdgeCases:
    def test_off_val_none_treated_as_mismatch(self):
        from services.proxy_service import _compute_nutrition_similarity

        nutrition = {"kcal": 100}
        product = {"nutriments": {"energy-kcal_100g": None}}
        result = _compute_nutrition_similarity(nutrition, product)
        assert result < 0

    def test_non_numeric_values_skipped(self):
        from services.proxy_service import _compute_nutrition_similarity

        nutrition = {"kcal": "not-a-number"}
        product = {"nutriments": {"energy-kcal_100g": "also-not"}}
        result = _compute_nutrition_similarity(nutrition, product)
        assert result == 0

    def test_no_product_nutriments_key(self):
        from services.proxy_service import _compute_nutrition_similarity

        result = _compute_nutrition_similarity({"kcal": 100}, {})
        assert result == 0


# ─────────────────────────────────────────────────────────────────────────────
# proxy_service — _NoRedirectHandler
# ─────────────────────────────────────────────────────────────────────────────


class TestNoRedirectHandler:
    def test_redirect_raises(self):
        import urllib.error
        from services.proxy_service import _NoRedirectHandler

        handler = _NoRedirectHandler()
        with pytest.raises(urllib.error.HTTPError):
            handler.redirect_request(
                MagicMock(full_url="https://example.com"),
                None, 302, "Found", {}, "https://other.com",
            )


# ─────────────────────────────────────────────────────────────────────────────
# bulk_service — _set_off_sync_flag
# ─────────────────────────────────────────────────────────────────────────────


class TestSetOffSyncFlag:
    def test_inserts_flag(self, app_ctx, db):
        from services.bulk_service import _set_off_sync_flag

        row = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        pid = row["id"]

        _set_off_sync_flag(db, pid)

        flag = db.execute(
            "SELECT * FROM product_flags WHERE product_id = ? AND flag = ?",
            (pid, "is_synced_with_off"),
        ).fetchone()
        assert flag is not None

    def test_ignores_duplicate(self, app_ctx, db):
        from services.bulk_service import _set_off_sync_flag

        row = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        pid = row["id"]

        _set_off_sync_flag(db, pid)
        _set_off_sync_flag(db, pid)

        count = db.execute(
            "SELECT COUNT(*) FROM product_flags WHERE product_id = ? AND flag = ?",
            (pid, "is_synced_with_off"),
        ).fetchone()[0]
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# bulk_service — refresh_from_off
# ─────────────────────────────────────────────────────────────────────────────


class TestRefreshFromOff:
    def test_no_products_with_ean(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute("UPDATE products SET ean = ''")
        db.commit()

        with patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["total"] == 0
        assert result["updated"] == 0

    def test_product_found_and_updated(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Test EAN Product", "9999999999999", ""),
        )
        db.commit()

        off_product_data = {
            "product": {
                "product_name": "Updated Name",
                "brands": "TestBrand",
                "nutriments": {"energy-kcal_100g": 200, "proteins_100g": 10},
            },
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_product_data), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["updated"] >= 1

    def test_product_not_found_skipped(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Missing Product", "0000000000000", ""),
        )
        db.commit()

        with patch("services.bulk_service.proxy_service.off_product", return_value={"status": 0}), \
             patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["skipped"] >= 1

    def test_exception_counted_as_error(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Error Product", "8888888888888", ""),
        )
        db.commit()

        with patch("services.bulk_service.proxy_service.off_product", side_effect=RuntimeError("API down")), \
             patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["errors"] >= 1

    def test_no_new_data_skipped(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, brand, image) VALUES (?, ?, ?, ?, ?)",
            ("Snacks", "Already Up To Date", "7777777777777", "ExistingBrand", ""),
        )
        db.commit()

        off_product_data = {
            "product": {
                "product_name": "",
                "brands": "",
                "nutriments": {},
            },
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_product_data), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["skipped"] >= 1

    def test_image_updated(self, app_ctx, db):
        from services.bulk_service import refresh_from_off

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Image Product", "6666666666666", ""),
        )
        db.commit()

        off_product_data = {
            "product": {
                "nutriments": {},
                "image_front_url": "https://images.openfoodfacts.org/test.jpg",
            },
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_product_data), \
             patch("services.bulk_service.proxy_service.proxy_image", return_value=(b"\xff\xd8\xff", "image/jpeg")), \
             patch("services.bulk_service.time.sleep"):
            result = refresh_from_off()

        assert result["updated"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# bulk_service — _run_refresh (background thread)
# ─────────────────────────────────────────────────────────────────────────────


class TestRunRefresh:
    """Tests for _run_refresh which runs in a background thread with its own
    DB connection via sqlite3.connect(DB_PATH)."""

    def _setup_db(self, db):
        """Clear EAN products, insert one with EAN for phase 1 testing."""
        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Thread Test Product", "1111111111111", ""),
        )
        db.commit()

    def test_phase1_product_updated(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        self._setup_db(db)
        # Point DB_PATH to the test database
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        off_data = {
            "product": {
                "product_name": "New Name",
                "brands": "NewBrand",
                "nutriments": {"energy-kcal_100g": 300},
            },
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_data), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["done"] is True
            assert svc._refresh_job["updated"] >= 1
            # Reset state
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase1_product_not_found_skipped(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        self._setup_db(db)
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        with patch("services.bulk_service.proxy_service.off_product", return_value={"status": 0}), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["skipped"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase1_no_new_data_skipped(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        self._setup_db(db)
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        off_data = {
            "product": {"nutriments": {}, "product_name": "", "brands": ""},
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_data), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["skipped"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase1_error_counted(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        self._setup_db(db)
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        with patch("services.bulk_service.proxy_service.off_product", side_effect=RuntimeError("fail")), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["errors"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase1_with_image(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        self._setup_db(db)
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        off_data = {
            "product": {
                "nutriments": {"energy-kcal_100g": 200},
                "product_name": "Updated",
            },
            "status": 1,
        }
        with patch("services.bulk_service.proxy_service.off_product", return_value=off_data), \
             patch("services.bulk_service._fetch_off_image", return_value="data:image/jpeg;base64,abc"), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["updated"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_search_missing_no_results(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        # No EAN products, one product without EAN for phase 2
        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Search Me", "", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", return_value={"products": []}), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 50, "min_completeness": 50})

        with svc._refresh_lock:
            assert svc._refresh_job["done"] is True
            assert svc._refresh_job["skipped"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_search_missing_below_threshold(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Low Cert Product", "", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        search_result = {
            "products": [
                {"code": "999", "product_name": "Low Cert", "certainty": 10, "completeness": 0.1},
            ]
        }
        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", return_value=search_result), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 90, "min_completeness": 90})

        with svc._refresh_lock:
            assert svc._refresh_job["skipped"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_search_missing_match_found(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Good Match", "", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        search_result = {
            "products": [
                {
                    "code": "5555555555555",
                    "product_name": "Good Match",
                    "certainty": 95,
                    "completeness": 0.9,
                    "brands": "TestBrand",
                    "nutriments": {"energy-kcal_100g": 150},
                },
            ]
        }
        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", return_value=search_result), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 50, "min_completeness": 50})

        with svc._refresh_lock:
            assert svc._refresh_job["updated"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_search_error_counted(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Error Search", "", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", side_effect=RuntimeError("search fail")), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 50, "min_completeness": 50})

        with svc._refresh_lock:
            assert svc._refresh_job["errors"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_crash_sets_done(self, app_ctx, db, monkeypatch, tmp_path):
        import services.bulk_service as svc

        crash_db = str(tmp_path / "crash.sqlite")
        monkeypatch.setattr(svc, "DB_PATH", crash_db)

        # Force a crash inside the try block: let PRAGMA pass but crash on SELECT
        call_count = [0]
        original_execute = None

        with patch("services.bulk_service.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()

            def side_effect_execute(sql, *args):
                call_count[0] += 1
                if call_count[0] <= 1:  # PRAGMA busy_timeout
                    return MagicMock()
                raise RuntimeError("DB crashed on query")

            mock_conn.execute = side_effect_execute
            mock_connect.return_value = mock_conn
            svc._run_refresh()

        with svc._refresh_lock:
            assert svc._refresh_job["done"] is True
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_match_with_image(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "Image Match", "", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        search_result = {
            "products": [
                {
                    "code": "4444444444444",
                    "product_name": "Image Match",
                    "certainty": 95,
                    "completeness": 0.9,
                    "nutriments": {},
                },
            ]
        }
        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", return_value=search_result), \
             patch("services.bulk_service._fetch_off_image", return_value="data:image/png;base64,xyz"), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 50, "min_completeness": 50})

        with svc._refresh_lock:
            assert svc._refresh_job["updated"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)

    def test_phase2_no_new_data_skipped(self, app_ctx, db, monkeypatch):
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, brand, image) VALUES (?, ?, ?, ?, ?)",
            ("Snacks", "No New Data", "", "ExistingBrand", ""),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", db.execute("PRAGMA database_list").fetchone()[2])

        search_result = {
            "products": [
                {
                    "code": "",
                    "product_name": "",
                    "certainty": 95,
                    "completeness": 0.9,
                    "nutriments": {},
                    "brands": "",
                },
            ]
        }
        with patch("services.bulk_service.proxy_service.off_product"), \
             patch("services.bulk_service.proxy_service.off_search", return_value=search_result), \
             patch("services.bulk_service._fetch_off_image", return_value=None), \
             patch("services.bulk_service.time.sleep"):
            svc._run_refresh({"search_missing": True, "min_certainty": 50, "min_completeness": 50})

        with svc._refresh_lock:
            assert svc._refresh_job["skipped"] >= 1
            svc._refresh_job.update(done=False, running=False, updated=0, skipped=0, errors=0)


# ─────────────────────────────────────────────────────────────────────────────
# bulk_service — _fetch_off_image (PIL branch and fallbacks)
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchOffImage:
    def test_no_url_returns_none(self):
        from services.bulk_service import _fetch_off_image

        assert _fetch_off_image({}) is None
        assert _fetch_off_image({"image_front_url": ""}) is None

    def test_proxy_image_exception_returns_none(self):
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/test.jpg"}
        with patch("services.bulk_service.proxy_service.proxy_image", side_effect=Exception("no")):
            assert _fetch_off_image(product) is None

    def test_valid_image_produces_data_uri(self):
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/test.jpg"}
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(b"\xff\xd8\xff\xe0" + b"\x00" * 50, "image/jpeg"),
        ):
            result = _fetch_off_image(product)

        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_oversized_returns_none(self):
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/test.jpg"}
        big = b"x" * (3 * 1024 * 1024)
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(big, "image/jpeg"),
        ):
            result = _fetch_off_image(product)

        assert result is None

    def test_image_url_fallback(self):
        from services.bulk_service import _fetch_off_image

        product = {"image_url": "https://images.openfoodfacts.org/fallback.jpg"}
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(b"\x89PNG\r\n" + b"\x00" * 30, "image/png"),
        ) as mock_proxy:
            result = _fetch_off_image(product)

        assert result is not None
        assert "fallback.jpg" in mock_proxy.call_args[0][0]

    def test_content_type_with_params(self):
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/test.jpg"}
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(b"\xff\xd8\xff" + b"\x00" * 30, "image/jpeg; charset=utf-8"),
        ):
            result = _fetch_off_image(product)

        assert result is not None
        assert "data:image/jpeg;base64," in result

    def test_pil_resize_jpeg_path(self):
        import sys
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/large.jpg"}
        small_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 40
        resized_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20

        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600

        def fake_save(buf, format, quality=None):
            buf.write(resized_bytes)

        mock_img.save = fake_save
        mock_img.thumbnail = MagicMock()

        mock_pil_image = MagicMock()
        mock_pil_image.open.return_value = mock_img
        mock_pil_image.LANCZOS = MagicMock()
        fake_pil = MagicMock()
        fake_pil.Image = mock_pil_image

        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(small_bytes, "image/jpeg"),
        ), patch.dict(sys.modules, {"PIL": fake_pil, "PIL.Image": mock_pil_image}):
            result = _fetch_off_image(product)

        mock_img.thumbnail.assert_called_once()
        assert result is not None

    def test_pil_resize_png_path(self):
        import sys
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/img.png"}
        small_bytes = b"\x89PNG\r\n" + b"\x00" * 40
        png_bytes = b"\x89PNG\r\n" + b"\x00" * 10

        mock_img = MagicMock()
        mock_img.width = 500
        mock_img.height = 500

        def fake_save(buf, format, quality=None):
            buf.write(png_bytes)

        mock_img.save = fake_save
        mock_img.thumbnail = MagicMock()

        mock_pil_image = MagicMock()
        mock_pil_image.open.return_value = mock_img
        mock_pil_image.LANCZOS = MagicMock()
        fake_pil = MagicMock()
        fake_pil.Image = mock_pil_image

        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(small_bytes, "image/png"),
        ), patch.dict(sys.modules, {"PIL": fake_pil, "PIL.Image": mock_pil_image}):
            result = _fetch_off_image(product)

        mock_img.thumbnail.assert_called_once()
        assert result is not None

    def test_pil_not_installed_uses_original(self):
        import sys
        from services.bulk_service import _fetch_off_image

        product = {"image_front_url": "https://images.openfoodfacts.org/test.jpg"}
        raw_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 30

        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(raw_bytes, "image/jpeg"),
        ), patch.dict(sys.modules, {"PIL": None}):
            result = _fetch_off_image(product)

        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

