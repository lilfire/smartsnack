"""E2E tests for `@limiter.limit(...)` decorators on rate-limited endpoints.

Verifies each rate-limited endpoint returns **429** after the documented
per-minute threshold is exceeded.

Endpoints covered:
- POST /api/restore           (5 per minute, auth-protected)
- POST /api/import            (5 per minute, auth-protected)
- POST /api/ocr/ingredients   (10 per minute)
- POST /api/ocr/nutrition     (10 per minute)
- GET  /api/proxy-image       (300 per minute)

Limits are read from ``blueprints/*.py`` decorators; if any production
limit changes, update the parametrize list below to match.

These tests use a dedicated Flask app fixture with rate-limiting enabled
and ``SMARTSNACK_API_KEY`` configured. They do NOT touch the session-wide
``app_server`` fixture in conftest.py.

The shared ``flask_limiter`` storage is reset between tests so each test
sees a fresh per-endpoint counter.
"""

import os

import pytest


_TEST_API_KEY = "rate-limit-test-key"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rate_app(tmp_path_factory):
    """Boot an isolated Flask app with rate-limiting enabled.

    ``SMARTSNACK_API_KEY`` is configured so that the auth-protected
    endpoints (restore, import) pass the auth check and reach the
    rate-limit wrapper — otherwise auth would deny before the limit
    counter is exercised. (Note: the limiter wrapper actually runs
    *before* the view function — and therefore before the auth check
    inside the view body — but we still need valid auth so the view
    body doesn't deny while we're verifying the *429* behaviour.)
    """
    db_file = str(tmp_path_factory.mktemp("rate_db") / "rate_e2e.sqlite")
    os.environ["DB_PATH"] = db_file
    os.environ["SMARTSNACK_SECRET_KEY"] = "rate-e2e-secret-key"
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
    # Explicit — rate limiting must be on for these tests.
    application.config["RATELIMIT_ENABLED"] = True

    # The session-scoped ``app_server`` fixture in conftest.py forces
    # ``limiter.enabled = False`` so the live e2e server isn't subject to
    # rate limits. That sets a module-level attribute on the shared
    # ``Limiter`` singleton, which would also disable limiting in this
    # app. Re-enable it for the duration of these tests and restore on
    # teardown so we don't leak state to other test files.
    from extensions import limiter as _limiter

    saved_limiter_enabled = _limiter.enabled
    _limiter.enabled = True

    yield application

    _limiter.enabled = saved_limiter_enabled
    helpers._API_KEY = saved_api_key


@pytest.fixture(autouse=True)
def _reset_limiter(rate_app):
    """Clear the shared limiter storage before each test in this module.

    The ``flask_limiter`` ``Limiter`` instance is a module-level singleton
    in ``extensions.py`` with memory storage. Without a reset, counters
    leak between tests in the same run, causing the second test to start
    near or past its limit and fail spuriously.
    """
    from extensions import limiter

    with rate_app.app_context():
        limiter.reset()
    yield
    with rate_app.app_context():
        limiter.reset()


@pytest.fixture()
def rate_client(rate_app):
    """Return a Flask test client tied to the rate-limited app."""
    return rate_app.test_client()


def _csrf_headers(extra: dict | None = None) -> dict:
    headers = {"X-Requested-With": "SmartSnack"}
    if extra:
        headers.update(extra)
    return headers


# ---------------------------------------------------------------------------
# Parametrised rate-limit verification
# ---------------------------------------------------------------------------

# Each tuple: (label, method, path, limit_per_minute, body_kwargs_factory)
#
# body_kwargs_factory returns kwargs for the test client call. Using a
# factory (callable) rather than a plain dict avoids parametrize ids
# stringifying dict contents in failure messages.
def _restore_kwargs():
    return {"json": {"version": 1, "products": []}}


def _import_kwargs():
    return {"json": {"products": []}}


def _ocr_kwargs():
    # Empty image triggers the early 400 path *inside* the view body,
    # which is fine — the limiter wrapper still increments the counter
    # before the view runs. We never need a real image.
    return {"json": {"image": ""}}


def _proxy_kwargs():
    # Empty/invalid URL → 400 inside the view body. Same reasoning as OCR.
    return {"query_string": {"url": ""}}


_RATE_LIMITED = [
    ("restore_5pm", "POST", "/api/restore", 5, _restore_kwargs),
    ("import_5pm", "POST", "/api/import", 5, _import_kwargs),
    ("ocr_ingredients_10pm", "POST", "/api/ocr/ingredients", 10, _ocr_kwargs),
    ("ocr_nutrition_10pm", "POST", "/api/ocr/nutrition", 10, _ocr_kwargs),
    # /api/proxy-image is 300/min on development. Firing 301 test-client
    # requests is fast (well under one second) so we use the real limit
    # rather than a synthetic override that would diverge from production.
    ("proxy_image_300pm", "GET", "/api/proxy-image", 300, _proxy_kwargs),
]


def _fire(client, method: str, path: str, headers: dict, body_kwargs: dict):
    """Send one request, returning the response."""
    method = method.upper()
    if method == "GET":
        return client.get(path, headers=headers, **body_kwargs)
    if method == "POST":
        return client.post(path, headers=headers, **body_kwargs)
    if method == "PUT":
        return client.put(path, headers=headers, **body_kwargs)
    raise AssertionError(f"Unsupported method {method}")


@pytest.mark.parametrize(
    ("label", "method", "path", "limit", "body_factory"),
    _RATE_LIMITED,
    ids=[r[0] for r in _RATE_LIMITED],
)
def test_endpoint_returns_429_after_threshold(
    rate_client, label, method, path, limit, body_factory
):
    """After `limit` successful (or 4xx-validation) requests, the next is 429."""
    headers = _csrf_headers({"X-API-Key": _TEST_API_KEY})
    body_kwargs = body_factory()

    # Fire `limit` requests — none of these may be 429.
    for i in range(limit):
        resp = _fire(rate_client, method, path, headers, body_kwargs)
        assert (
            resp.status_code != 429
        ), f"{label}: request {i + 1}/{limit} was rate-limited too early ({resp.status_code})"

    # Request `limit + 1` MUST be 429.
    resp = _fire(rate_client, method, path, headers, body_kwargs)
    assert resp.status_code == 429, (
        f"{label}: request {limit + 1} expected 429, got {resp.status_code} "
        f"body={resp.data!r}"
    )

    # Flask-Limiter returns a JSON body via the app's HTTPException handler;
    # the default phrasing is the raw limit string, e.g. "5 per 1 minute".
    # Assert the body mentions the configured limit so we know it's the
    # limiter that fired and not some unrelated 429.
    body = resp.get_json() or {}
    assert "error" in body, f"{label}: 429 body missing 'error': {resp.data!r}"
    err = body["error"].lower()
    assert (
        str(limit) in err and "per" in err and "minute" in err
    ), f"{label}: 429 error text doesn't match flask-limiter format: {body['error']!r}"


# ---------------------------------------------------------------------------
# Sanity checks: rate limit isolation per endpoint
# ---------------------------------------------------------------------------


def test_rate_limit_does_not_block_other_endpoints(rate_client):
    """Hitting one endpoint to its limit must not 429 a different endpoint.

    Each `@limiter.limit("N per minute")` decorator scopes its counter to
    the wrapped view, so exhausting /api/restore should leave /api/import
    available. This guards against accidental shared-key regressions.
    """
    headers = _csrf_headers({"X-API-Key": _TEST_API_KEY})

    # Exhaust /api/restore (5/min).
    for _ in range(5):
        rate_client.post("/api/restore", headers=headers, json={"products": []})
    # 6th must be 429.
    blocked = rate_client.post(
        "/api/restore", headers=headers, json={"products": []}
    )
    assert blocked.status_code == 429

    # /api/import must still be open — first call is NOT rate-limited.
    other = rate_client.post(
        "/api/import", headers=headers, json={"products": []}
    )
    assert other.status_code != 429, (
        f"/api/import was rate-limited despite a fresh counter "
        f"(status={other.status_code}, body={other.data!r})"
    )
