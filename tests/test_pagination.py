"""Tests for pagination (limit/offset) on the product list API and service."""

import pytest


def _add_products(db, n, category="Snacks"):
    """Insert n products into the database and return their ids."""
    ids = []
    for i in range(n):
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            (f"Pagination Product {i:03d}", category),
        )
        ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    db.commit()
    return ids


class TestListProductsServicePagination:
    """Service-level tests for list_products with limit/offset."""

    def test_default_page_size_is_50(self, app_ctx):
        from config import DEFAULT_PAGE_SIZE

        assert DEFAULT_PAGE_SIZE == 50

    def test_returns_dict_with_products_and_total(self, app_ctx):
        from services.product_service import list_products

        result = list_products(None, None)
        assert isinstance(result, dict)
        assert "products" in result
        assert "total" in result
        assert isinstance(result["products"], list)
        assert isinstance(result["total"], int)

    def test_limit_restricts_returned_products(self, db, app_ctx):
        _add_products(db, 10)
        from services.product_service import list_products

        result = list_products(None, None, limit=3)
        assert len(result["products"]) == 3
        assert result["total"] >= 10

    def test_offset_skips_products(self, db, app_ctx):
        _add_products(db, 10)
        from services.product_service import list_products

        all_result = list_products(None, None, limit=100)
        offset_result = list_products(None, None, limit=100, offset=5)
        assert len(offset_result["products"]) == len(all_result["products"]) - 5

    def test_limit_and_offset_together(self, db, app_ctx):
        _add_products(db, 20)
        from services.product_service import list_products

        page1 = list_products(None, None, limit=5, offset=0)
        page2 = list_products(None, None, limit=5, offset=5)
        ids_page1 = {p["id"] for p in page1["products"]}
        ids_page2 = {p["id"] for p in page2["products"]}
        assert len(ids_page1) == 5
        assert len(ids_page2) == 5
        assert ids_page1.isdisjoint(ids_page2), "Pages should not overlap"

    def test_total_reflects_full_count_not_page_size(self, db, app_ctx):
        _add_products(db, 15)
        from services.product_service import list_products

        result = list_products(None, None, limit=3)
        assert result["total"] >= 15
        assert len(result["products"]) == 3

    def test_total_with_search_filter(self, db, app_ctx):
        _add_products(db, 10, category="Snacks")
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("Unique Searched Item", "Snacks"),
        )
        db.commit()
        from services.product_service import list_products

        result = list_products("Unique Searched Item", None, limit=50)
        assert result["total"] >= 1
        assert any("Unique Searched" in p["name"] for p in result["products"])

    def test_total_with_type_filter(self, db, app_ctx):
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("Filtered Type Product", "Drikke"),
        )
        db.commit()
        from services.product_service import list_products

        result = list_products(None, "Drikke", limit=50)
        assert result["total"] >= 1
        assert all(p["type"] == "Drikke" for p in result["products"])

    def test_offset_beyond_total_returns_empty(self, db, app_ctx):
        from services.product_service import list_products

        result = list_products(None, None, limit=10, offset=99999)
        assert result["products"] == []
        assert result["total"] >= 0

    def test_zero_limit_returns_empty(self, db, app_ctx):
        _add_products(db, 5)
        from services.product_service import list_products

        result = list_products(None, None, limit=0)
        assert result["products"] == []
        assert result["total"] >= 5


class TestProductsBlueprintPagination:
    """Blueprint-level tests for GET /api/products with limit/offset params."""

    def test_default_response_shape(self, client):
        resp = client.get("/api/products")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data
        assert "total" in data

    def test_limit_param(self, client, db):
        _add_products(db, 10)
        resp = client.get("/api/products?limit=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["products"]) == 3
        assert data["total"] >= 10

    def test_offset_param(self, client, db):
        _add_products(db, 10)
        resp_all = client.get("/api/products?limit=100")
        resp_offset = client.get("/api/products?limit=100&offset=5")
        all_data = resp_all.get_json()
        offset_data = resp_offset.get_json()
        assert len(offset_data["products"]) == len(all_data["products"]) - 5
        assert offset_data["total"] == all_data["total"]

    def test_limit_and_offset_pagination(self, client, db):
        _add_products(db, 20)
        resp1 = client.get("/api/products?limit=5&offset=0")
        resp2 = client.get("/api/products?limit=5&offset=5")
        data1 = resp1.get_json()
        data2 = resp2.get_json()
        ids1 = {p["id"] for p in data1["products"]}
        ids2 = {p["id"] for p in data2["products"]}
        assert ids1.isdisjoint(ids2)

    def test_invalid_limit_returns_400(self, client):
        resp = client.get("/api/products?limit=abc")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_invalid_offset_returns_400(self, client):
        resp = client.get("/api/products?offset=xyz")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_offset_beyond_total_returns_empty_list(self, client):
        resp = client.get("/api/products?offset=99999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["products"] == []

    def test_total_reflects_filtered_count(self, client, db):
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("Pagination Filter Test", "Drikke"),
        )
        db.commit()
        resp = client.get("/api/products?type=Drikke&limit=1")
        data = resp.get_json()
        assert data["total"] >= 1
        assert len(data["products"]) <= 1

    def test_search_with_pagination(self, client, db):
        for i in range(5):
            db.execute(
                "INSERT INTO products (name, type) VALUES (?, ?)",
                (f"SearchPagTest {i}", "Snacks"),
            )
        db.commit()
        resp = client.get("/api/products?search=SearchPagTest&limit=2&offset=0")
        data = resp.get_json()
        assert data["total"] >= 5
        assert len(data["products"]) == 2


class TestProxyRateLimit:
    """Verify the proxy-image rate limit was raised to 300/min."""

    def test_proxy_image_not_rate_limited_at_30(self, app):
        with app.test_client() as c:
            # Make 31 requests — should NOT be rate limited at the old 30/min
            for i in range(31):
                resp = c.get("/api/proxy-image?url=https://images.openfoodfacts.org/test.jpg")
                # 400 (no valid url) or 403 (domain check) is fine; 429 is not
                assert resp.status_code != 429, (
                    f"Rate limited at request {i + 1} — old 30/min limit may still be in effect"
                )
