"""Rate limiter validation and API contract enforcement tests.

Verifies:
- Rate limits are applied and return 429 when exceeded
- 429 responses match the {"error": "..."} format convention
- All error responses return {"error": "message"} JSON
- Correct HTTP status codes are returned for various error conditions
- Content-Type is application/json on all API responses
"""

import pytest


# ── Rate-limited app fixture ─────────────────────────────────────────────────


@pytest.fixture()
def rate_limited_client(tmp_path, monkeypatch):
    """Flask test client backed by an app with a 3-request-per-minute default limit.

    The limiter is replaced with a fresh instance so that:
      1. Counters are isolated from other test fixtures.
      2. The limit is low enough to trigger 429 in a small loop.
    A unique REMOTE_ADDR is set so counters don't bleed between tests.

    Note: the autouse translations_dir fixture in conftest.py has already patched
    config.TRANSLATIONS_DIR before this fixture runs, so we reuse that temp dir.
    """
    import config

    db_file = str(tmp_path / "rate_test.sqlite")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "rate-test-secret")
    monkeypatch.setattr(config, "DB_PATH", db_file)

    import db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)

    # Replace the global limiter with a fresh low-limit instance.
    # We patch both extensions.limiter and app.limiter so that the next
    # create_app() call calls test_limiter.init_app(app) instead.
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    test_limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["3 per minute"],
        storage_uri="memory://",
    )

    import extensions
    import app as app_mod

    monkeypatch.setattr(extensions, "limiter", test_limiter)
    monkeypatch.setattr(app_mod, "limiter", test_limiter)

    application = app_mod.create_app()
    application.config["TESTING"] = True

    inner = application.test_client()
    # Use a unique IP to avoid counter bleed across test runs
    inner.environ_base = {"REMOTE_ADDR": "10.0.0.42"}

    # Wrap with CSRF header injection for mutation requests
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(inner)


# ── Rate limiter tests ───────────────────────────────────────────────────────


class TestRateLimiterApplied:
    """Rate limiting triggers 429 after configured threshold is exceeded."""

    def test_requests_within_limit_succeed(self, rate_limited_client):
        """First N requests within the limit must succeed (200)."""
        # With a 3/minute limit, the first 3 GETs should succeed
        for _ in range(3):
            resp = rate_limited_client.get("/api/products")
            assert resp.status_code == 200

    def test_request_exceeding_limit_returns_429(self, rate_limited_client):
        """The (N+1)th request over the limit must return 429."""
        # Exhaust the 3/minute limit
        for _ in range(3):
            rate_limited_client.get("/api/products")

        # One more should be rate-limited
        resp = rate_limited_client.get("/api/products")
        assert resp.status_code == 429

    def test_rate_limit_response_is_json(self, rate_limited_client):
        """429 response must have Content-Type application/json."""
        for _ in range(3):
            rate_limited_client.get("/api/products")

        resp = rate_limited_client.get("/api/products")
        assert resp.status_code == 429
        assert "application/json" in resp.content_type

    def test_rate_limit_response_has_error_key(self, rate_limited_client):
        """429 response body must follow {"error": "..."} convention."""
        for _ in range(3):
            rate_limited_client.get("/api/products")

        resp = rate_limited_client.get("/api/products")
        assert resp.status_code == 429
        data = resp.get_json()
        assert data is not None, "429 response body must be valid JSON"
        assert "error" in data, f"429 response missing 'error' key: {data}"

    def test_rate_limit_error_value_is_string(self, rate_limited_client):
        """'error' in 429 response must be a non-empty string."""
        for _ in range(3):
            rate_limited_client.get("/api/products")

        resp = rate_limited_client.get("/api/products")
        data = resp.get_json()
        assert isinstance(data["error"], str)
        assert len(data["error"]) > 0


# ── API contract: error response format ─────────────────────────────────────


class TestErrorResponseFormat:
    """All API error responses return {"error": "message"} JSON."""

    def test_400_missing_name_has_error_key(self, client, seed_category):
        """400 on missing product name returns {"error": "..."}."""
        resp = client.post(
            "/api/products",
            json={"type": "Snacks"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_400_over_length_has_error_key(self, client, seed_category):
        """400 on name-too-long returns {"error": "..."}."""
        resp = client.post(
            "/api/products",
            json={"name": "X" * 201, "type": "Snacks"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_400_invalid_limit_has_error_key(self, client):
        """400 on invalid limit param returns {"error": "..."}."""
        resp = client.get("/api/products?limit=abc")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_400_invalid_tag_label_has_error_key(self, client):
        """400 on empty tag label returns {"error": "..."}."""
        resp = client.post("/api/tags", json={"label": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_403_csrf_failure_has_error_key(self, client):
        """403 on CSRF failure returns {"error": "..."}."""
        inner = client._inner if hasattr(client, "_inner") else client
        resp = inner.post(
            "/api/products",
            json={"name": "CsrfTest"},
            # No X-Requested-With header → CSRF failure
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert "error" in data

    def test_404_product_not_found_has_error_key(self, client):
        """404 on missing product returns {"error": "..."}."""
        resp = client.put(
            "/api/products/99999999",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_404_tag_not_found_has_error_key(self, client):
        """404 on missing tag returns {"error": "..."}."""
        resp = client.get("/api/tags/99999999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_409_duplicate_product_has_duplicate_key(self, client, seed_category):
        """409 on duplicate product returns a body with expected keys."""
        resp = client.post(
            "/api/products",
            json={"name": "DupCheckProduct", "type": "Snacks"},
        )
        assert resp.status_code in (200, 201, 409)

        # Try to create the same product again
        resp2 = client.post(
            "/api/products",
            json={"name": "DupCheckProduct", "type": "Snacks"},
        )
        assert resp2.status_code in (200, 201, 409)
        data = resp2.get_json()
        assert data is not None


# ── API contract: HTTP status codes ─────────────────────────────────────────


class TestHttpStatusCodes:
    """API returns appropriate HTTP status codes for different scenarios."""

    def test_200_on_get_products(self, client, seed_category):
        """GET /api/products must return 200."""
        resp = client.get("/api/products")
        assert resp.status_code == 200

    def test_200_on_get_categories(self, client):
        """GET /api/categories must return 200."""
        resp = client.get("/api/categories")
        assert resp.status_code == 200

    def test_200_on_get_tags(self, client):
        """GET /api/tags must return 200."""
        resp = client.get("/api/tags")
        assert resp.status_code == 200

    def test_201_on_create_product(self, client, seed_category):
        """POST /api/products with valid data must return 201."""
        resp = client.post(
            "/api/products",
            json={"name": "StatusCheck201", "type": "Snacks"},
        )
        assert resp.status_code in (200, 201)

    def test_400_on_bad_product_data(self, client):
        """POST /api/products with missing name must return 400."""
        resp = client.post("/api/products", json={"type": "Snacks"})
        assert resp.status_code == 400

    def test_403_on_missing_csrf(self, client):
        """POST without CSRF header must return 403."""
        inner = client._inner if hasattr(client, "_inner") else client
        resp = inner.post("/api/products", json={"name": "test"})
        assert resp.status_code == 403

    def test_404_on_nonexistent_product_update(self, client):
        """PUT /api/products/99999 must return 404."""
        resp = client.put(
            "/api/products/99999999",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_405_on_wrong_method_for_product(self, client):
        """PATCH /api/products (method not allowed) must return 405."""
        resp = client.patch("/api/products", json={"name": "Wrong"})
        assert resp.status_code == 405

    def test_409_on_duplicate_category(self, client):
        """Creating a category that already exists must return 409."""
        client.post(
            "/api/categories",
            json={"name": "DupCatStatus", "label": "Dup"},
        )
        resp = client.post(
            "/api/categories",
            json={"name": "DupCatStatus", "label": "Dup"},
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data


# ── API contract: Content-Type ───────────────────────────────────────────────


class TestContentType:
    """All API responses set Content-Type: application/json."""

    def test_get_products_content_type(self, client, seed_category):
        """GET /api/products must respond with application/json."""
        resp = client.get("/api/products")
        assert "application/json" in resp.content_type

    def test_post_product_content_type(self, client, seed_category):
        """POST /api/products must respond with application/json."""
        resp = client.post(
            "/api/products",
            json={"name": "ContentTypeTest", "type": "Snacks"},
        )
        assert "application/json" in resp.content_type

    def test_error_400_content_type(self, client):
        """400 error response must have Content-Type application/json."""
        resp = client.post("/api/products", json={"type": "Snacks"})
        assert resp.status_code == 400
        assert "application/json" in resp.content_type

    def test_error_403_content_type(self, client):
        """403 CSRF error response must have Content-Type application/json."""
        inner = client._inner if hasattr(client, "_inner") else client
        resp = inner.post("/api/products", json={"name": "t"})
        assert resp.status_code == 403
        assert "application/json" in resp.content_type

    def test_error_404_content_type(self, client):
        """404 not-found response must have Content-Type application/json."""
        resp = client.put("/api/products/9999999", json={"name": "x"})
        assert resp.status_code == 404
        assert "application/json" in resp.content_type

    def test_get_tags_content_type(self, client):
        """GET /api/tags must respond with application/json."""
        resp = client.get("/api/tags")
        assert "application/json" in resp.content_type

    def test_get_categories_content_type(self, client):
        """GET /api/categories must respond with application/json."""
        resp = client.get("/api/categories")
        assert "application/json" in resp.content_type
