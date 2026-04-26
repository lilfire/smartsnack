"""Tests for extensions.py — rate limiter configuration and behaviour."""
import pytest
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def test_limiter_is_limiter_instance():
    from extensions import limiter
    assert isinstance(limiter, Limiter)


def test_limiter_key_func_is_get_remote_address():
    from extensions import limiter
    assert limiter._key_func is get_remote_address


def test_limiter_storage_uri_is_memory():
    from extensions import limiter
    assert limiter._storage_uri == "memory://"


def test_limiter_default_limits_contains_200_per_minute():
    from extensions import limiter
    raw_defaults = limiter.limit_manager._default_limits
    assert len(raw_defaults) == 1
    limit_str = raw_defaults[0].limit_provider
    assert limit_str == "200 per minute"


def test_limiter_initialized_in_app(app):
    from extensions import limiter
    assert limiter._storage is not None


def test_rate_limit_triggers_429_on_201st_request(tmp_path, monkeypatch):
    """After 200 requests the 201st to any endpoint should return HTTP 429."""
    from extensions import limiter
    import config
    import os

    # Ensure limiter is enabled BEFORE create_app calls limiter.init_app.
    # E2e tests may have disabled it at session scope on an earlier app.
    limiter.enabled = True

    db_file = str(tmp_path / "ratelimit_test.sqlite")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "test-secret")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    try:
        import db as db_mod
        monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    except ImportError:
        pass

    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    # Explicitly enable rate limiting on this app instance
    application.config["RATELIMIT_ENABLED"] = True

    with application.app_context():
        limiter.reset()

    with application.test_client() as c:
        for i in range(200):
            resp = c.get("/api/products")
            assert resp.status_code != 429, f"Rate limited prematurely at request {i + 1}"
        resp = c.get("/api/products")
        assert resp.status_code == 429
