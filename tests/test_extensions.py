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


def test_rate_limit_triggers_429_on_201st_request(app):
    """After 200 requests the 201st to any endpoint should return HTTP 429."""
    with app.test_client() as c:
        for i in range(200):
            resp = c.get("/api/products")
            assert resp.status_code != 429, f"Rate limited prematurely at request {i + 1}"
        resp = c.get("/api/products")
        assert resp.status_code == 429
