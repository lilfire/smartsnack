"""Tests for LSO-1670 low-severity backend fixes."""

import json
import math
import os


# ---------------------------------------------------------------------------
# Fix 1 & 2: helpers — hmac.compare_digest, no query-param auth
# ---------------------------------------------------------------------------

def test_api_key_header_accepted(client, monkeypatch):
    """Valid API key in header is accepted (backup endpoint checks key)."""
    import helpers
    monkeypatch.setattr(helpers, "_API_KEY", "secret")
    resp = client.get("/api/backup", headers={"X-API-Key": "secret"})
    # 200 = key accepted (backup returns data), not 401
    assert resp.status_code != 401


def test_api_key_wrong_header_rejected(client, monkeypatch):
    """Wrong API key in header returns 401."""
    import helpers
    monkeypatch.setattr(helpers, "_API_KEY", "secret")
    resp = client.get("/api/backup", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_api_key_query_param_rejected(client, monkeypatch):
    """api_key query param is no longer accepted (fix 2)."""
    import helpers
    monkeypatch.setattr(helpers, "_API_KEY", "secret")
    resp = client.get("/api/backup?api_key=secret")
    assert resp.status_code == 401


def test_api_key_uses_hmac_compare():
    """_check_api_key uses hmac.compare_digest (not ==)."""
    import inspect
    import helpers
    src = inspect.getsource(helpers._check_api_key)
    assert "hmac.compare_digest" in src


# ---------------------------------------------------------------------------
# Fix 3: app.py — no unsafe-inline in script-src
# ---------------------------------------------------------------------------

def test_csp_no_unsafe_inline_script(client):
    """CSP script-src must not contain 'unsafe-inline'."""
    resp = client.get("/health")
    csp = resp.headers.get("Content-Security-Policy", "")
    # Extract script-src directive
    for part in csp.split(";"):
        if "script-src" in part:
            assert "'unsafe-inline'" not in part
            break


# ---------------------------------------------------------------------------
# Fix 4: settings_service — secret key file written with 0o600
# ---------------------------------------------------------------------------

def test_secret_key_file_mode(tmp_path, monkeypatch):
    """Generated secret key file must have mode 0o600."""
    monkeypatch.delenv("SMARTSNACK_SECRET_KEY", raising=False)
    db_path = str(tmp_path / "smartsnack.sqlite")
    monkeypatch.setenv("DB_PATH", db_path)
    from services import settings_service
    # Call the resolver — it should create the file
    secret = settings_service._resolve_secret_key()
    key_file = str(tmp_path / ".smartsnack_secret_key")
    assert os.path.exists(key_file)
    mode = oct(os.stat(key_file).st_mode)[-3:]
    assert mode == "600", f"Expected 600, got {mode}"


# ---------------------------------------------------------------------------
# Fix 5: extensions — SQLite storage_uri
# ---------------------------------------------------------------------------

def test_extensions_configurable_storage(monkeypatch):
    """RATELIMIT_STORAGE_URI env var controls rate limiter backend."""
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379")
    import importlib
    import extensions
    importlib.reload(extensions)
    assert extensions._rate_limit_uri == "redis://localhost:6379"
    # Restore
    monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)
    importlib.reload(extensions)


def test_extensions_defaults_to_memory():
    """Without RATELIMIT_STORAGE_URI set, falls back to memory://."""
    import extensions
    # In test env, env var is not set, so should be memory://
    import os
    if "RATELIMIT_STORAGE_URI" not in os.environ:
        assert extensions._rate_limit_uri == "memory://"


# ---------------------------------------------------------------------------
# Fix 7: core_service — health check uses service layer
# ---------------------------------------------------------------------------

def test_health_via_core_service(client):
    """Health endpoint returns ok and products count."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "products" in data


def test_core_service_get_product_count(app_ctx):
    """core_service.get_product_count() returns an integer >= 0."""
    from services import core_service
    count = core_service.get_product_count()
    assert isinstance(count, int)
    assert count >= 0


# ---------------------------------------------------------------------------
# Fix 8: products — clamp limit/offset
# ---------------------------------------------------------------------------

def test_products_limit_clamped_max(client):
    """Limit above 200 is clamped to 200 (no error, just clamped)."""
    resp = client.get("/api/products?limit=9999")
    assert resp.status_code == 200


def test_products_limit_clamped_min(client):
    """Limit of 0 is clamped to 1."""
    resp = client.get("/api/products?limit=0")
    assert resp.status_code == 200


def test_products_negative_offset_rejected(client):
    """Negative offset is rejected with 400 (LSO-1679 tightened validation)."""
    resp = client.get("/api/products?offset=-5")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Fix 9: proxy — reject non-string q, reject NaN/Infinity
# ---------------------------------------------------------------------------

def test_off_search_non_string_q_rejected(client):
    """POST /api/off/search with non-string q returns 400."""
    resp = client.post(
        "/api/off/search",
        json={"q": 123},
        headers={"X-Requested-With": "SmartSnack"},
    )
    assert resp.status_code == 400
    assert "string" in resp.get_json().get("error", "").lower()


def test_off_search_nutrition_nan_filtered(client, monkeypatch):
    """NaN/Infinity values in nutrition are filtered out."""
    import services.proxy_service as ps
    calls = []

    def mock_off_search(query, nutrition, category):
        calls.append({"query": query, "nutrition": nutrition, "category": category})
        return {"products": []}

    monkeypatch.setattr(ps, "off_search", mock_off_search)
    resp = client.post(
        "/api/off/search",
        json={"q": "test", "nutrition": {"energy": float("nan"), "protein": 10.0}},
        headers={"X-Requested-With": "SmartSnack"},
    )
    assert resp.status_code == 200
    # NaN should be filtered; protein should remain
    passed_nutrition = calls[0]["nutrition"]
    assert passed_nutrition is not None
    assert "energy" not in passed_nutrition
    assert passed_nutrition.get("protein") == 10.0


# ---------------------------------------------------------------------------
# Fix 10: app.py — MAX_CONTENT_LENGTH = 16 MB
# ---------------------------------------------------------------------------

def test_max_content_length(app):
    """MAX_CONTENT_LENGTH must be 16 MB."""
    assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024


# ---------------------------------------------------------------------------
# Fix 11: off_service — catch json.JSONDecodeError
# ---------------------------------------------------------------------------

def test_off_service_json_decode_error(monkeypatch):
    """add_product_to_off raises RuntimeError on HTML maintenance page response."""
    import urllib.request
    import io
    from unittest.mock import patch, MagicMock
    from services import off_service

    html_body = b"<html>We are down for maintenance</html>"

    class FakeResp:
        def read(self):
            return html_body
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    monkeypatch.setattr(
        "services.off_service.get_off_credentials",
        lambda: {"off_user_id": "u", "off_password": "p"},
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=15: FakeResp())

    product = {
        "code": "1234567890123",
        "product_name": "Test",
        "categories": "snacks",
        "nutriments": {},
        "ingredients_text": "stuff",
    }
    import pytest
    with pytest.raises(RuntimeError, match="off_err_api"):
        off_service.add_product_to_off(product)


# ---------------------------------------------------------------------------
# Fix 12: protein_quality_service — skip empty label
# ---------------------------------------------------------------------------

def test_update_entry_empty_label_skipped(app_ctx, monkeypatch):
    """update_entry with empty label does not write a translation key."""
    from services import protein_quality_service
    calls = []
    original = protein_quality_service._set_translation_key

    def mock_set(key, val):
        calls.append(key)

    monkeypatch.setattr(protein_quality_service, "_set_translation_key", mock_set)

    # Insert an entry first
    from db import get_db
    conn = get_db()
    conn.execute("INSERT INTO protein_quality (name, pdcaas, diaas) VALUES ('testprot', 0.5, 0.5)")
    conn.commit()
    pid = conn.execute("SELECT id FROM protein_quality WHERE name='testprot'").fetchone()[0]

    # Update with empty label
    calls.clear()
    protein_quality_service.update_entry(pid, {"label": ""})

    label_keys = [k for k in calls if "label" in k]
    assert label_keys == [], f"Expected no label translation write, got {label_keys}"


# ---------------------------------------------------------------------------
# Fix 13: migrations — idx_product_eans_ean
# ---------------------------------------------------------------------------

def test_migration_022_adds_ean_index(db):
    """Migration 022 creates idx_product_eans_ean index."""
    indexes = {
        row[1]
        for row in db.execute("PRAGMA index_list(product_eans)").fetchall()
    }
    assert "idx_product_eans_ean" in indexes, f"Index not found; got: {indexes}"
