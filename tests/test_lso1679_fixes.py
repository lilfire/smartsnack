"""Tests for LSO-1679: low-severity backend fixes."""

import json
import os
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# Fix 1 & 2: API key constant-time compare + query-string removed
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    def test_header_key_accepted(self, app, monkeypatch):
        monkeypatch.setenv("SMARTSNACK_API_KEY", "secret123")
        import helpers
        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_client() as c:
            resp = c.get(
                "/api/backup",
                headers={"X-API-Key": "secret123", "X-Requested-With": "SmartSnack"},
            )
            assert resp.status_code != 401

    def test_missing_header_rejected(self, app, monkeypatch):
        monkeypatch.setenv("SMARTSNACK_API_KEY", "secret123")
        import helpers
        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_client() as c:
            resp = c.get("/api/backup")
            assert resp.status_code == 401

    def test_query_string_api_key_rejected(self, app, monkeypatch):
        """API key via ?api_key= must NOT be accepted (logged in access logs)."""
        monkeypatch.setenv("SMARTSNACK_API_KEY", "secret123")
        import helpers
        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_client() as c:
            resp = c.get("/api/backup?api_key=secret123")
            assert resp.status_code == 401

    def test_wrong_key_rejected(self, app, monkeypatch):
        monkeypatch.setenv("SMARTSNACK_API_KEY", "secret123")
        import helpers
        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_client() as c:
            resp = c.get("/api/backup", headers={"X-API-Key": "wrong"})
            assert resp.status_code == 401

    def test_check_api_key_uses_constant_time_compare(self, app, monkeypatch):
        """_check_api_key must use hmac.compare_digest, not == or !=."""
        import hmac as hmac_mod
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "mysecret")
        calls = []
        original = hmac_mod.compare_digest

        def spy(a, b):
            calls.append((a, b))
            return original(a, b)

        with app.test_request_context(headers={"X-API-Key": "mysecret"}):
            with mock.patch("hmac.compare_digest", side_effect=spy):
                helpers._check_api_key()
        assert len(calls) >= 1, "hmac.compare_digest was not called"


# ---------------------------------------------------------------------------
# Fix 3: Rate limiter storage URI env var
# ---------------------------------------------------------------------------


class TestRateLimiterStorage:
    def test_default_is_memory(self):
        import importlib
        import sys

        orig = os.environ.pop("RATELIMIT_STORAGE_URI", None)
        try:
            if "extensions" in sys.modules:
                del sys.modules["extensions"]
            import extensions
            assert extensions._rate_limit_uri == "memory://"
        finally:
            if orig is not None:
                os.environ["RATELIMIT_STORAGE_URI"] = orig
            if "extensions" in sys.modules:
                del sys.modules["extensions"]

    def test_env_var_overrides_storage(self, monkeypatch):
        import sys

        monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
        if "extensions" in sys.modules:
            del sys.modules["extensions"]
        try:
            import extensions
            assert extensions._rate_limit_uri == "redis://localhost:6379/0"
        finally:
            if "extensions" in sys.modules:
                del sys.modules["extensions"]


# ---------------------------------------------------------------------------
# Fix 4: MAX_CONTENT_LENGTH reduced (16 MB)
# ---------------------------------------------------------------------------


class TestMaxContentLength:
    def test_global_limit_is_16mb(self, app):
        assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024


# ---------------------------------------------------------------------------
# Fix 5: CSP restricts script sources to self.
# LSO-1783: inline event handlers were migrated to addEventListener, so
# script-src no longer needs (or allows) 'unsafe-inline'.
# ---------------------------------------------------------------------------


class TestCSP:
    def test_script_src_restricted_to_self(self, client):
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "script-src" in csp
        script_src = next(d for d in csp.split(";") if "script-src" in d)
        assert "'self'" in script_src
        # No external script hosts, no unsafe-eval, no unsafe-inline
        assert "http" not in script_src
        assert "'unsafe-eval'" not in script_src
        assert "'unsafe-inline'" not in script_src

    def test_style_src_may_keep_unsafe_inline(self, client):
        """style-src still allows unsafe-inline (for dynamic inline styles)."""
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        for directive in csp.split(";"):
            if "style-src" in directive:
                assert "'unsafe-inline'" in directive


# ---------------------------------------------------------------------------
# Fix 6: Secret key file written with mode 0o600
# ---------------------------------------------------------------------------


class TestSecretKeyFilePermissions:
    def test_key_file_written_as_owner_only(self, tmp_path, monkeypatch):
        key_file = str(tmp_path / ".smartsnack_secret_key")
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite"))
        monkeypatch.delenv("SMARTSNACK_SECRET_KEY", raising=False)

        import services.settings_service as svc
        svc._resolve_secret_key()

        mode = oct(os.stat(key_file).st_mode)[-3:]
        assert mode == "600", f"Key file should be 0o600, got {mode}"


# ---------------------------------------------------------------------------
# Fix 7: /health uses service layer (not raw SQL in blueprint)
# ---------------------------------------------------------------------------


class TestHealthService:
    def test_health_endpoint_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "products" in data

    def test_health_calls_core_service(self, app):
        """Blueprint must delegate to core_service.get_product_count, not raw SQL."""
        import blueprints.core as core_bp
        import services.core_service as svc
        import inspect

        src = inspect.getsource(core_bp)
        assert "core_service" in src, "blueprint must use core_service"
        assert "get_product_count" in inspect.getsource(svc)

    def test_core_service_returns_int(self, app_ctx):
        from services.core_service import get_product_count
        result = get_product_count()
        assert isinstance(result, int)
        assert result >= 0


# ---------------------------------------------------------------------------
# Fix 8: SSE stream has bounded lifetime (deadline constant exists)
# ---------------------------------------------------------------------------


class TestSSETimeout:
    def test_sse_stream_has_deadline(self):
        import blueprints.bulk as bulk_bp
        assert hasattr(bulk_bp, "_SSE_STREAM_TIMEOUT"), (
            "_SSE_STREAM_TIMEOUT constant must exist in blueprints/bulk.py"
        )
        assert bulk_bp._SSE_STREAM_TIMEOUT > 0

    def test_sse_stream_terminates_when_not_running(self, client):
        """When the job is not running, the SSE stream must terminate quickly."""
        resp = client.get("/api/bulk/refresh-off/stream")
        assert resp.status_code == 200
        data = resp.data.decode("utf-8")
        assert "data:" in data
        assert "running" in data


# ---------------------------------------------------------------------------
# Fix 9: Proxy search validates q is a string; nutrition rejects NaN/Infinity
# ---------------------------------------------------------------------------


class TestProxyInputValidation:
    def test_non_string_q_returns_400(self, client):
        resp = client.post(
            "/api/off/search",
            json={"q": 12345},
        )
        assert resp.status_code == 400
        assert "string" in resp.get_json()["error"].lower()

    def test_dict_q_returns_400(self, client):
        resp = client.post(
            "/api/off/search",
            json={"q": {"nested": "obj"}},
        )
        assert resp.status_code == 400

    def test_string_q_passes_validation(self, client, monkeypatch):
        import services.proxy_service as ps
        monkeypatch.setattr(ps, "off_search", lambda q, n, c: {"products": []})
        resp = client.post("/api/off/search", json={"q": "chicken"})
        assert resp.status_code == 200

    def test_nutrition_nan_is_ignored(self, client, monkeypatch):
        """NaN/Infinity values in nutrition dict must be silently dropped."""
        import math
        import services.proxy_service as ps

        received = {}

        def capture(q, nutrition, category):
            received["nutrition"] = nutrition
            return {"products": []}

        monkeypatch.setattr(ps, "off_search", capture)
        resp = client.post(
            "/api/off/search",
            json={"q": "test", "nutrition": {"protein": "NaN", "fat": 10.0}},
        )
        assert resp.status_code == 200
        nutrition = received.get("nutrition")
        if nutrition:
            for v in nutrition.values():
                assert math.isfinite(v), f"Non-finite value slipped through: {v}"


# ---------------------------------------------------------------------------
# Fix 10: Products limit/offset clamping
# ---------------------------------------------------------------------------


class TestProductsLimitOffset:
    def test_negative_limit_returns_400(self, client):
        resp = client.get("/api/products?limit=-1")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "limit" in data["error"].lower()

    def test_zero_limit_clamped_to_one(self, client):
        resp = client.get("/api/products?limit=0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["products"]) <= 1

    def test_limit_above_max_clamped(self, client, db):
        """limit is clamped to MAX_PAGE_SIZE (200); oversized requests still succeed."""
        from config import MAX_PAGE_SIZE

        for i in range(MAX_PAGE_SIZE + 5):
            db.execute(
                "INSERT INTO products (name, type) VALUES (?, ?)",
                (f"ClampTest Product {i}", "Snacks"),
            )
        db.commit()
        resp = client.get("/api/products?limit=9999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["products"]) <= MAX_PAGE_SIZE

    def test_negative_offset_returns_400(self, client):
        resp = client.get("/api/products?offset=-1")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "offset" in data["error"].lower()


# ---------------------------------------------------------------------------
# Fix 11: OFF service catches JSONDecodeError
# ---------------------------------------------------------------------------


class TestOFFJsonDecodeError:
    def test_html_maintenance_page_raises_runtime_error(self, app_ctx, monkeypatch):
        """When OFF returns HTML (e.g. maintenance page), RuntimeError is raised."""
        import urllib.request
        import services.off_service as off_svc

        html_body = b"<html><body>Site under maintenance</body></html>"

        class FakeResponse:
            def read(self):
                return html_body
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())
        # Patch where off_service imported the function from
        monkeypatch.setattr(off_svc, "get_off_credentials", lambda: {
            "off_user_id": "testuser", "off_password": "testpass"
        })

        with pytest.raises(RuntimeError, match="off_err_api"):
            off_svc.add_product_to_off({
                "code": "1234567890123",
                "product_name": "Test Product",
            })


# ---------------------------------------------------------------------------
# Fix 12: Protein quality entry — string keywords don't get first char as name
# ---------------------------------------------------------------------------


class TestProteinQualityEmptyLabel:
    def test_string_keywords_uses_first_word_not_first_char(self, app_ctx):
        """When keywords is a comma-separated string and label is empty,
        name should be derived from the first keyword word, not the first character."""
        from services.protein_quality_service import add_entry

        result = add_entry({
            "keywords": "chicken, beef",
            "pdcaas": 0.95,
            "diaas": 1.0,
            "label": "",
        })
        assert result["ok"] is True
        # name must be the first keyword, not just the first character "c"
        assert result["name"] == "chicken", (
            f"Expected 'chicken', got '{result['name']}' — "
            "bug: string indexing on keyword string gives first char"
        )

    def test_list_keywords_uses_first_element(self, app_ctx):
        from services.protein_quality_service import add_entry

        result = add_entry({
            "keywords": ["salmon", "fish"],
            "pdcaas": 0.92,
            "diaas": 1.0,
            "label": "",
        })
        assert result["name"] == "salmon"

    def test_label_takes_priority_over_keywords(self, app_ctx):
        from services.protein_quality_service import add_entry

        result = add_entry({
            "keywords": ["quinoa"],
            "pdcaas": 0.84,
            "diaas": 0.91,
            "label": "Quinoa Protein",
        })
        assert result["name"] == "quinoa_protein"


# ---------------------------------------------------------------------------
# Fix 13: product_eans(ean) index exists in migrations
# ---------------------------------------------------------------------------


class TestProductEansIndex:
    def test_migration_adds_ean_index(self, app_ctx):
        from db import get_db
        conn = get_db()
        indexes = {
            row[1]
            for row in conn.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='product_eans'"
            ).fetchall()
        }
        assert "idx_product_eans_ean" in indexes, (
            "idx_product_eans_ean must exist on product_eans table"
        )

    def test_migration_022_in_list(self):
        from migrations import MIGRATIONS
        names = [m[0] for m in MIGRATIONS]
        assert "022_add_product_eans_ean_index" in names
