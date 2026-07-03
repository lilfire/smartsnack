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


# ---------------------------------------------------------------------------
# Pagination edge cases
# ---------------------------------------------------------------------------


class TestPaginationEdgeCases:
    """Edge cases for pagination: boundary offsets, empty result sets, filter interaction."""

    def test_offset_at_exact_total_count_returns_empty(self, db, app_ctx):
        """When offset equals the total product count, no products are returned."""
        ids = _add_products(db, 5)
        from services.product_service import list_products

        full = list_products(None, None, limit=1000)
        total = full["total"]

        result = list_products(None, None, limit=10, offset=total)
        assert result["products"] == [], (
            f"offset={total} (= total) should return empty list, got {len(result['products'])}"
        )
        assert result["total"] == total

    def test_offset_one_past_last_item_returns_empty(self, db, app_ctx):
        """offset = total + 1 should still return empty (not wrap around)."""
        _add_products(db, 3)
        from services.product_service import list_products

        full = list_products(None, None, limit=1000)
        total = full["total"]

        result = list_products(None, None, limit=10, offset=total + 1)
        assert result["products"] == []

    def test_search_with_no_match_returns_empty_and_zero_total(self, app_ctx):
        """A search query that matches nothing returns empty products and total=0."""
        from services.product_service import list_products

        result = list_products("ZZZNOTEXISTINGPRODUCTXYZ12345", None, limit=50)
        assert result["products"] == []
        assert result["total"] == 0

    def test_type_filter_with_no_match_returns_empty(self, app_ctx):
        """A type filter that matches nothing returns empty products and total=0."""
        from services.product_service import list_products

        result = list_products(None, "NonExistentCategoryZZZ", limit=50)
        assert result["products"] == []
        assert result["total"] == 0

    def test_filter_and_pagination_combined(self, db, app_ctx):
        """Filter by type then paginate: total reflects filtered count, not all products."""
        for i in range(8):
            db.execute(
                "INSERT INTO products (name, type) VALUES (?, ?)",
                (f"Filtered Drink {i}", "Drikke"),
            )
        db.execute("INSERT INTO products (name, type) VALUES (?, ?)", ("Snack", "Snacks"))
        db.commit()

        from services.product_service import list_products

        page1 = list_products(None, "Drikke", limit=3, offset=0)
        page2 = list_products(None, "Drikke", limit=3, offset=3)

        assert page1["total"] >= 8
        assert page2["total"] == page1["total"]
        ids_p1 = {p["id"] for p in page1["products"]}
        ids_p2 = {p["id"] for p in page2["products"]}
        assert ids_p1.isdisjoint(ids_p2), "Paginated pages must not overlap"
        assert all(p["type"] == "Drikke" for p in page1["products"])
        assert all(p["type"] == "Drikke" for p in page2["products"])

    def test_blueprint_offset_equals_total_returns_empty(self, client, db):
        """HTTP endpoint: offset at exact total count returns [] and correct total."""
        _add_products(db, 5, "Snacks")
        resp = client.get("/api/products?limit=1000")
        total = resp.get_json()["total"]

        resp2 = client.get(f"/api/products?offset={total}&limit=10")
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["products"] == []
        assert data["total"] == total

    def test_search_and_offset_interaction(self, db, app_ctx):
        """Search filter + pagination: first page has items, second page when beyond total is empty."""
        for i in range(3):
            db.execute(
                "INSERT INTO products (name, type) VALUES (?, ?)",
                (f"PaginationEdge SpecialItem {i}", "Snacks"),
            )
        db.commit()

        from services.product_service import list_products

        result_all = list_products("PaginationEdge SpecialItem", None, limit=100)
        assert result_all["total"] >= 3

        # Offset beyond the filtered total
        result_beyond = list_products(
            "PaginationEdge SpecialItem", None, limit=10, offset=result_all["total"]
        )
        assert result_beyond["products"] == []
        assert result_beyond["total"] == result_all["total"]


class TestComputedFilterPagination:
    """Computed-field filters (total_score) must apply BEFORE pagination (LSO-1674/LSO-1695).

    Regression: previously the SQL query paginated first (ORDER BY name LIMIT/OFFSET)
    and post-filters ran on the page slice only, so matches beyond the first
    name-ordered page never appeared and `total` reflected the raw SQL count.
    """

    SCORE_FILTER = '{{"logic": "and", "conditions": [{{"field": "total_score", "op": ">=", "value": {threshold}}}]}}'

    def _seed_products(self, db, n_poor=50, n_good=10):
        """Insert n_poor low-score then n_good high-score products.

        Names are chosen so all poor products sort BEFORE all good products
        by name — the good ones land past the first 50-row page.
        """
        for i in range(n_poor):
            db.execute(
                "INSERT INTO products (name, type) VALUES (?, ?)",
                (f"FilterPageAaa Poor {i:03d}", "Snacks"),
            )
        for i in range(n_good):
            db.execute(
                """INSERT INTO products
                   (name, type, taste_score, kcal, protein, fiber, sugar, salt, saturated_fat, price, weight)
                   VALUES (?, ?, 10, 100, 25, 9, 1, 0.1, 0.5, 20, 100)""",
                (f"FilterPageZzz Good {i:03d}", "Snacks"),
            )
        db.commit()

    def _score_threshold(self, products):
        """Pick a threshold strictly between poor-group and good-group scores."""
        good = [p["total_score"] for p in products if "Zzz" in p["name"]]
        poor = [
            p["total_score"]
            for p in products
            if "Aaa" in p["name"] and p["total_score"] is not None
        ]
        poor_max = max(poor, default=0.0)
        good_min = min(good)
        assert good_min > poor_max, (
            f"Fixture assumption broken: good scores ({good_min}) must exceed "
            f"poor scores ({poor_max})"
        )
        return (good_min + poor_max) / 2

    def test_score_filter_finds_matches_beyond_first_page(self, db, app_ctx):
        """>50 products, matches sorted last by name: page 1 must return them all."""
        self._seed_products(db)
        from services.product_service import list_products

        unfiltered = list_products("FilterPage", None, limit=200)
        assert unfiltered["total"] == 60
        threshold = self._score_threshold(unfiltered["products"])

        filters = self.SCORE_FILTER.format(threshold=threshold)
        page1 = list_products("FilterPage", None, filters, limit=50, offset=0)

        assert page1["total"] == 10
        names = {p["name"] for p in page1["products"]}
        assert names == {f"FilterPageZzz Good {i:03d}" for i in range(10)}

    def test_total_reflects_filtered_count_not_sql_count(self, db, app_ctx):
        self._seed_products(db)
        from services.product_service import list_products

        unfiltered = list_products("FilterPage", None, limit=200)
        threshold = self._score_threshold(unfiltered["products"])

        filters = self.SCORE_FILTER.format(threshold=threshold)
        result = list_products("FilterPage", None, filters, limit=3, offset=0)
        assert result["total"] == 10, "total must count ALL filtered rows, not the SQL count"
        assert len(result["products"]) == 3

    def test_pagination_pages_with_computed_filter(self, db, app_ctx):
        """Pages 1-3 over the filtered set are disjoint, complete, and share the total."""
        self._seed_products(db)
        from services.product_service import list_products

        unfiltered = list_products("FilterPage", None, limit=200)
        threshold = self._score_threshold(unfiltered["products"])
        filters = self.SCORE_FILTER.format(threshold=threshold)

        pages = [
            list_products("FilterPage", None, filters, limit=4, offset=off)
            for off in (0, 4, 8)
        ]
        assert [len(p["products"]) for p in pages] == [4, 4, 2]
        assert all(p["total"] == 10 for p in pages)
        seen = [prod["id"] for page in pages for prod in page["products"]]
        assert len(seen) == len(set(seen)) == 10, "Pages must be disjoint and cover all matches"

    def test_offset_beyond_filtered_total_returns_empty(self, db, app_ctx):
        self._seed_products(db)
        from services.product_service import list_products

        unfiltered = list_products("FilterPage", None, limit=200)
        threshold = self._score_threshold(unfiltered["products"])
        filters = self.SCORE_FILTER.format(threshold=threshold)

        result = list_products("FilterPage", None, filters, limit=10, offset=10)
        assert result["products"] == []
        assert result["total"] == 10

    def test_api_endpoint_score_filter_pagination(self, client, db):
        """Blueprint-level: /api/products?filters=... paginates the filtered set."""
        self._seed_products(db)

        unfiltered = client.get("/api/products?search=FilterPage&limit=200").get_json()
        threshold = self._score_threshold(unfiltered["products"])

        filters = self.SCORE_FILTER.format(threshold=threshold)
        resp = client.get(
            "/api/products",
            query_string={"search": "FilterPage", "filters": filters, "limit": 50},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 10
        assert len(data["products"]) == 10
        assert all("Zzz" in p["name"] for p in data["products"])

    def test_sql_only_filter_path_unchanged(self, db, app_ctx):
        """No computed filter: SQL LIMIT/OFFSET path still paginates and counts correctly."""
        self._seed_products(db)
        from services.product_service import list_products

        filters = '{"logic": "and", "conditions": [{"field": "protein", "op": ">=", "value": 20}]}'
        result = list_products("FilterPage", None, filters, limit=4, offset=0)
        assert result["total"] == 10
        assert len(result["products"]) == 4
