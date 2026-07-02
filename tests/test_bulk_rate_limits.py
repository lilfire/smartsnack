"""Tests for per-route rate limits on expensive bulk endpoints (LSO-1689).

Verifies that POST /api/bulk/refresh-off, /api/bulk/refresh-off/start, and
POST /api/bulk/estimate-pq return 429 when the per-route limit is exceeded.

Uses a test limiter with a 2/minute global limit (lower than the 5/minute
per-route limit) so we can trigger 429 quickly without replicating the
full rate-limiter infrastructure.
"""

import pytest
from unittest.mock import patch


@pytest.fixture()
def rate_limited_bulk_client(tmp_path, monkeypatch):
    """Flask test client with a 2/minute global rate limit.

    The very low limit (2/min) lets us trigger 429 in 3 quick requests,
    proving that the bulk endpoints are subject to rate limiting.
    A unique REMOTE_ADDR prevents counter bleed between tests.
    """
    import config

    db_file = str(tmp_path / "bulk_rate_test.sqlite")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "bulk-rate-test-secret")
    monkeypatch.setattr(config, "DB_PATH", db_file)

    import db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)

    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    test_limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["2 per minute"],
        storage_uri="memory://",
    )

    import extensions
    import app as app_mod

    monkeypatch.setattr(extensions, "limiter", test_limiter)
    monkeypatch.setattr(app_mod, "limiter", test_limiter)

    application = app_mod.create_app()
    application.config["TESTING"] = True

    inner = application.test_client()
    inner.environ_base = {"REMOTE_ADDR": "10.1.0.1"}

    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(inner)


class TestBulkRefreshOffRateLimit:
    """POST /api/bulk/refresh-off is rate limited."""

    def test_returns_429_after_limit_exceeded(self, rate_limited_bulk_client):
        with patch("services.bulk_service.refresh_from_off", return_value={"updated": 0}):
            for _ in range(2):
                rate_limited_bulk_client.post("/api/bulk/refresh-off")
            resp = rate_limited_bulk_client.post("/api/bulk/refresh-off")
        assert resp.status_code == 429

    def test_429_response_has_error_key(self, rate_limited_bulk_client):
        with patch("services.bulk_service.refresh_from_off", return_value={"updated": 0}):
            for _ in range(2):
                rate_limited_bulk_client.post("/api/bulk/refresh-off")
            resp = rate_limited_bulk_client.post("/api/bulk/refresh-off")
        data = resp.get_json()
        assert data is not None
        assert "error" in data


class TestBulkRefreshOffStartRateLimit:
    """POST /api/bulk/refresh-off/start is rate limited."""

    def test_returns_429_after_limit_exceeded(self, rate_limited_bulk_client):
        with patch(
            "services.bulk_service.start_refresh_from_off", return_value=True
        ):
            for _ in range(2):
                rate_limited_bulk_client.post(
                    "/api/bulk/refresh-off/start", json={}
                )
            resp = rate_limited_bulk_client.post(
                "/api/bulk/refresh-off/start", json={}
            )
        assert resp.status_code == 429


class TestBulkEstimatePqRateLimit:
    """POST /api/bulk/estimate-pq is rate limited."""

    def test_returns_429_after_limit_exceeded(self, rate_limited_bulk_client):
        with patch(
            "services.bulk_service.estimate_all_pq",
            return_value={"total": 0, "updated": 0, "skipped": 0},
        ):
            for _ in range(2):
                rate_limited_bulk_client.post("/api/bulk/estimate-pq")
            resp = rate_limited_bulk_client.post("/api/bulk/estimate-pq")
        assert resp.status_code == 429
