"""E2E tests for X-API-Key authentication on protected endpoints.

Verifies the `_check_api_key()` guard on all 5 protected endpoints rejects
requests with a wrong key, missing header, or empty header, and accepts
requests with the correct key.

Also verifies that authentication runs BEFORE payload validation: sending
a deliberately invalid body with a wrong key returns the auth-deny status,
not 400.

These tests use an isolated Flask app fixture that boots a fresh
`create_app()` with `SMARTSNACK_API_KEY` configured. They do NOT touch the
session-wide `app_server` fixture in conftest.py — that fixture leaves
`SMARTSNACK_API_KEY` unset so its protected-endpoint cases would skip the
guard entirely.

Note on status code: the production guard returns **401** (see
`helpers._check_api_key`), so these tests assert 401 even though the
task description mentioned 403. The intent is the same — assert the
auth-deny code rather than the validation code (400).
"""

import os

import pytest


_TEST_API_KEY = "e2e-api-key-test-secret"
_WRONG_API_KEY = "definitely-not-the-right-key"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def auth_app(tmp_path_factory):
    """Boot an isolated Flask app with ``SMARTSNACK_API_KEY`` configured.

    Rate limiting is disabled so deny-path tests can fire repeatedly without
    tripping the 5/min cap on /api/backup, /api/restore, /api/import. The
    session-scoped ``app_server`` fixture in conftest.py is not requested,
    so we don't perturb the live e2e server.
    """
    db_file = str(tmp_path_factory.mktemp("auth_db") / "auth_e2e.sqlite")
    os.environ["DB_PATH"] = db_file
    os.environ["SMARTSNACK_SECRET_KEY"] = "auth-e2e-secret-key"
    os.environ["SMARTSNACK_API_KEY"] = _TEST_API_KEY

    import config

    config.DB_PATH = db_file

    import db as db_mod

    db_mod.DB_PATH = db_file

    import helpers

    saved_api_key = helpers._API_KEY
    helpers._API_KEY = _TEST_API_KEY

    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    application.config["RATELIMIT_ENABLED"] = False

    yield application

    helpers._API_KEY = saved_api_key


@pytest.fixture()
def auth_client(auth_app):
    """Return a Flask test client for the auth-enabled app."""
    return auth_app.test_client()


def _csrf_headers(extra: dict | None = None) -> dict:
    """Build a header dict that includes the CSRF marker non-GET routes expect."""
    headers = {"X-Requested-With": "SmartSnack"}
    if extra:
        headers.update(extra)
    return headers


def _count_products(auth_app) -> int:
    """Count rows in the products table — used to assert no side-effect on deny."""
    with auth_app.app_context():
        from db import get_db

        return get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0]


# Valid bodies that *would* succeed if auth passes; used by the
# correct-key tests. Restore/import use a minimal-but-valid payload to
# exercise the happy path (200) rather than a service-level error.
_VALID_RESTORE_BODY = {"version": 1, "products": []}
_VALID_IMPORT_BODY = {"products": []}
_VALID_OFF_PUT_BODY = {"off_user_id": "test_user", "off_password": "test_pw"}


# ---------------------------------------------------------------------------
# Parametrised deny-path tests
# ---------------------------------------------------------------------------

# (label, method, path, kwargs-for-correct-key-call)
_PROTECTED_ENDPOINTS = [
    ("backup_export", "GET", "/api/backup", {}),
    (
        "restore",
        "POST",
        "/api/restore",
        {"json": _VALID_RESTORE_BODY},
    ),
    (
        "import_products",
        "POST",
        "/api/import",
        {"json": _VALID_IMPORT_BODY},
    ),
    ("get_off_credentials", "GET", "/api/settings/off-credentials", {}),
    (
        "put_off_credentials",
        "PUT",
        "/api/settings/off-credentials",
        {"json": _VALID_OFF_PUT_BODY},
    ),
]


def _call(client, method: str, path: str, headers: dict, body_kwargs: dict | None = None):
    """Invoke the Flask test client for any method, attaching CSRF headers."""
    body_kwargs = dict(body_kwargs or {})
    method = method.upper()
    headers = _csrf_headers(headers)
    if method == "GET":
        return client.get(path, headers=headers)
    if method == "POST":
        return client.post(path, headers=headers, **body_kwargs)
    if method == "PUT":
        return client.put(path, headers=headers, **body_kwargs)
    raise AssertionError(f"Unsupported method {method}")


@pytest.mark.parametrize(
    ("label", "method", "path", "valid_kwargs"),
    _PROTECTED_ENDPOINTS,
    ids=[e[0] for e in _PROTECTED_ENDPOINTS],
)
def test_wrong_key_is_denied(auth_client, auth_app, label, method, path, valid_kwargs):
    """A request with a wrong X-API-Key value must be denied (401)."""
    before = _count_products(auth_app)
    resp = _call(
        auth_client,
        method,
        path,
        headers={"X-API-Key": _WRONG_API_KEY},
        body_kwargs=valid_kwargs,
    )
    assert resp.status_code == 401, f"{label}: expected 401, got {resp.status_code}"
    body = resp.get_json() or {}
    assert "error" in body, f"{label}: error message missing in body: {resp.data!r}"
    assert "api key" in body["error"].lower() or "unauthorized" in body["error"].lower()
    # No side-effect on the products table.
    assert _count_products(auth_app) == before, f"{label}: products table changed on deny"


@pytest.mark.parametrize(
    ("label", "method", "path", "valid_kwargs"),
    _PROTECTED_ENDPOINTS,
    ids=[e[0] for e in _PROTECTED_ENDPOINTS],
)
def test_missing_header_is_denied(
    auth_client, auth_app, label, method, path, valid_kwargs
):
    """A request without an X-API-Key header at all must be denied (401)."""
    before = _count_products(auth_app)
    resp = _call(
        auth_client,
        method,
        path,
        headers={},
        body_kwargs=valid_kwargs,
    )
    assert resp.status_code == 401, f"{label}: expected 401, got {resp.status_code}"
    body = resp.get_json() or {}
    assert "error" in body
    assert "api key" in body["error"].lower() or "unauthorized" in body["error"].lower()
    assert _count_products(auth_app) == before


@pytest.mark.parametrize(
    ("label", "method", "path", "valid_kwargs"),
    _PROTECTED_ENDPOINTS,
    ids=[e[0] for e in _PROTECTED_ENDPOINTS],
)
def test_empty_string_key_is_denied(
    auth_client, auth_app, label, method, path, valid_kwargs
):
    """An empty-string X-API-Key header must be denied (401)."""
    before = _count_products(auth_app)
    resp = _call(
        auth_client,
        method,
        path,
        headers={"X-API-Key": ""},
        body_kwargs=valid_kwargs,
    )
    assert resp.status_code == 401, f"{label}: expected 401, got {resp.status_code}"
    body = resp.get_json() or {}
    assert "error" in body
    assert "api key" in body["error"].lower() or "unauthorized" in body["error"].lower()
    assert _count_products(auth_app) == before


# ---------------------------------------------------------------------------
# Correct-key success cases (one per endpoint, asserts the real shape)
# ---------------------------------------------------------------------------


def test_correct_key_allows_backup(auth_client):
    """GET /api/backup with the correct key returns 200 + a JSON snapshot."""
    resp = auth_client.get(
        "/api/backup",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body, dict)
    # Snapshot must contain at least the products list (per backup_service.create_backup).
    assert "products" in body and isinstance(body["products"], list)


def test_correct_key_allows_restore(auth_client):
    """POST /api/restore with the correct key + valid body returns 200 ok."""
    resp = auth_client.post(
        "/api/restore",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
        json=_VALID_RESTORE_BODY,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    assert "message" in body


def test_correct_key_allows_import(auth_client):
    """POST /api/import with the correct key + valid body returns 200 ok."""
    resp = auth_client.post(
        "/api/import",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
        json=_VALID_IMPORT_BODY,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True
    assert "message" in body


def test_correct_key_allows_get_off_credentials(auth_client):
    """GET /api/settings/off-credentials with the correct key returns the masked creds."""
    resp = auth_client.get(
        "/api/settings/off-credentials",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "off_user_id" in body
    assert "has_password" in body
    assert isinstance(body["has_password"], bool)


def test_correct_key_allows_put_off_credentials(auth_client):
    """PUT /api/settings/off-credentials with the correct key + body returns 200 ok."""
    resp = auth_client.put(
        "/api/settings/off-credentials",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
        json=_VALID_OFF_PUT_BODY,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("ok") is True


# ---------------------------------------------------------------------------
# Auth-before-validation ordering tests (acceptance criterion)
# ---------------------------------------------------------------------------


def test_restore_auth_runs_before_validation(auth_client):
    """Wrong key + empty body must return 401 (auth deny), not 400 (validation)."""
    resp = auth_client.post(
        "/api/restore",
        headers=_csrf_headers({"X-API-Key": _WRONG_API_KEY}),
        data=b"",
        content_type="application/json",
    )
    assert resp.status_code == 401
    body = resp.get_json() or {}
    assert "api key" in body.get("error", "").lower() or "unauthorized" in body.get(
        "error", ""
    ).lower()


def test_import_auth_runs_before_validation(auth_client):
    """Wrong key + body missing 'products' key must return 401, not 400."""
    resp = auth_client.post(
        "/api/import",
        headers=_csrf_headers({"X-API-Key": _WRONG_API_KEY}),
        json={"match_criteria": "ean"},  # 'products' intentionally missing
    )
    assert resp.status_code == 401
    body = resp.get_json() or {}
    assert "api key" in body.get("error", "").lower() or "unauthorized" in body.get(
        "error", ""
    ).lower()


def test_put_off_credentials_auth_runs_before_validation(auth_client):
    """Wrong key + over-length password must return 401, not 400."""
    huge_password = "x" * 10_000  # well over _MAX_PASSWORD_LEN (500)
    resp = auth_client.put(
        "/api/settings/off-credentials",
        headers=_csrf_headers({"X-API-Key": _WRONG_API_KEY}),
        json={"off_user_id": "u", "off_password": huge_password},
    )
    assert resp.status_code == 401
    body = resp.get_json() or {}
    assert "api key" in body.get("error", "").lower() or "unauthorized" in body.get(
        "error", ""
    ).lower()


def test_put_off_credentials_password_too_long_with_correct_key(auth_client):
    """Correct key + over-length password must return 400 (validation runs AFTER auth)."""
    huge_password = "x" * 10_000
    resp = auth_client.put(
        "/api/settings/off-credentials",
        headers=_csrf_headers({"X-API-Key": _TEST_API_KEY}),
        json={"off_user_id": "u", "off_password": huge_password},
    )
    assert resp.status_code == 400
    body = resp.get_json() or {}
    assert "password" in body.get("error", "").lower()
