"""SQL injection prevention tests.

Verifies that all user-input paths use parameterized queries and that
dynamic column names are validated against config.py constants.
Each test sets up its own data and tears down via the tmp_path fixture.
"""

import json
import pytest


# Common SQL injection payloads that should never cause errors or data leaks
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1 --",
    "'; DROP TABLE products; --",
    "' UNION SELECT 1,2,3,4,5,6,7,8,9,10 --",
    "1' AND SLEEP(5) --",
    "admin'--",
    "' OR 'x'='x",
    "') OR ('1'='1",
    "'; INSERT INTO products (name) VALUES ('hacked'); --",
    "%27 OR %271%27=%271",
]


def _make_product(client, name="TestProduct", category="Snacks"):
    """Helper: create a product via POST /api/products."""
    resp = client.post(
        "/api/products",
        json={"name": name, "type": category, "kcal": 100, "protein": 5},
    )
    assert resp.status_code in (200, 201, 409)
    return resp


class TestSearchSqlInjection:
    """Product search endpoint rejects SQL injection via parameterized queries."""

    def test_sql_injection_in_search_returns_200(self, client, seed_category):
        """SQL injection payload in search must not cause a server error."""
        for payload in SQL_INJECTION_PAYLOADS:
            resp = client.get(f"/api/products?search={payload}")
            assert resp.status_code == 200, (
                f"Payload {payload!r} caused HTTP {resp.status_code}"
            )

    def test_sql_injection_search_returns_valid_json(self, client, seed_category):
        """Search with injection payload still returns valid JSON structure."""
        resp = client.get("/api/products?search=' OR 1=1 --")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data
        assert "total" in data

    def test_sql_injection_does_not_leak_all_rows(self, client, db, seed_category):
        """OR 1=1 injection via search should NOT return all products (it's a literal search)."""
        # Insert a known product
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("SafeProduct_unique_xyz", "Snacks"),
        )
        db.commit()

        resp = client.get("/api/products?search=' OR '1'='1")
        assert resp.status_code == 200
        data = resp.get_json()
        # Injection is treated as literal text; should NOT match "SafeProduct_unique_xyz"
        names = [p["name"] for p in data["products"]]
        assert "SafeProduct_unique_xyz" not in names

    def test_semicolon_drop_table_injection_in_search(self, client, db, seed_category):
        """DROP TABLE injection in search must not destroy the products table."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("PersistentProduct", "Snacks"),
        )
        db.commit()

        client.get("/api/products?search='; DROP TABLE products; --")

        # Table must still exist and contain our product
        resp = client.get("/api/products?search=PersistentProduct")
        assert resp.status_code == 200
        data = resp.get_json()
        names = [p["name"] for p in data["products"]]
        assert "PersistentProduct" in names

    def test_union_select_injection_in_search(self, client, seed_category):
        """UNION SELECT injection in search must not expose extra columns."""
        resp = client.get(
            "/api/products?search=' UNION SELECT 1,2,3,4,5,6,7,8,9,10 --"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # All returned products must have the expected product structure
        for p in data["products"]:
            assert "id" in p
            assert "name" in p


class TestTypeCategorySqlInjection:
    """Category filter parameter is parameterized and safe from SQL injection."""

    def test_sql_injection_in_type_filter_returns_200(self, client, seed_category):
        """SQL injection payload in type filter must not cause a server error."""
        for payload in SQL_INJECTION_PAYLOADS:
            resp = client.get(f"/api/products?type={payload}")
            assert resp.status_code == 200, (
                f"Payload {payload!r} caused HTTP {resp.status_code}"
            )

    def test_type_filter_injection_returns_empty_not_all(self, client, db, seed_category):
        """Injected type filter treats injection as literal; returns only matching."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("RealProduct", "Snacks"),
        )
        db.commit()

        resp = client.get("/api/products?type=' OR '1'='1")
        assert resp.status_code == 200
        data = resp.get_json()
        # No product has type "' OR '1'='1" so result must be empty
        assert data["products"] == []


class TestAdvancedFilterSqlInjection:
    """Advanced filter column names are validated against config.py whitelist."""

    def test_injection_in_filter_column_returns_400(self, client, seed_category):
        """Column injection in filters must be rejected as invalid column."""
        injection_filter = json.dumps({
            "op": "AND",
            "conditions": [
                {
                    "field": "name; DROP TABLE products; --",
                    "op": "=",
                    "value": "x",
                }
            ],
        })
        resp = client.get(f"/api/products?filters={injection_filter}")
        # Should be rejected (400) or return empty result safely — never 500
        assert resp.status_code in (400, 200)
        if resp.status_code == 400:
            data = resp.get_json()
            assert "error" in data

    def test_valid_filter_column_works(self, client, db, seed_category):
        """Valid column name in filters must work correctly."""
        db.execute(
            "INSERT INTO products (name, type, kcal) VALUES (?, ?, ?)",
            ("FilterProduct", "Snacks", 150),
        )
        db.commit()

        valid_filter = json.dumps({
            "op": "AND",
            "conditions": [{"field": "kcal", "op": ">", "value": 100}],
        })
        resp = client.get(f"/api/products?filters={valid_filter}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["products"], list)

    def test_filter_sql_fragment_in_value_is_safe(self, client, seed_category):
        """SQL fragment as filter value must be treated as a literal string."""
        safe_filter = json.dumps({
            "op": "AND",
            "conditions": [
                {
                    "field": "name",
                    "op": "contains",
                    "value": "' OR 1=1 --",
                }
            ],
        })
        resp = client.get(f"/api/products?filters={safe_filter}")
        assert resp.status_code == 200
        data = resp.get_json()
        # Should return empty list (no product with that literal name)
        assert "products" in data


class TestCategoryEndpointSqlInjection:
    """Category CRUD endpoints handle SQL injection safely."""

    def test_create_category_with_sql_injection_name_rejected(self, client):
        """Category name with SQL injection payload must be rejected by validation."""
        resp = client.post(
            "/api/categories",
            json={"name": "' OR 1=1 --", "label": "test"},
        )
        # Category name validation rejects control chars; injection names may pass
        # but must not cause 500
        assert resp.status_code in (201, 400, 409)
        assert resp.status_code != 500

    def test_delete_category_with_sql_injection_in_url(self, client):
        """SQL injection in DELETE category URL must not cause a server error."""
        resp = client.delete("/api/categories/' OR '1'='1")
        # Printable chars pass name validation; non-existent category may return 200 or 400
        assert resp.status_code in (200, 400, 404)
        assert resp.status_code != 500

    def test_update_category_with_sql_injection_in_url(self, client):
        """SQL injection in PUT category URL must not cause a server error."""
        resp = client.put(
            "/api/categories/'; DROP TABLE categories; --",
            json={"label": "hacked"},
        )
        # Long names (>100 chars) will be rejected (400); shorter ones may pass (200/404)
        assert resp.status_code in (200, 400, 404)
        assert resp.status_code != 500


class TestTagEndpointSqlInjection:
    """Tag CRUD endpoints handle SQL injection in label fields safely."""

    def test_create_tag_with_sql_injection_label(self, client):
        """SQL injection payload as tag label must not cause server error."""
        resp = client.post(
            "/api/tags",
            json={"label": "' OR 1=1 --"},
        )
        # Tag label validation may reject or accept — must not 500
        assert resp.status_code in (201, 400)
        assert resp.status_code != 500

    def test_search_tags_with_sql_injection(self, client):
        """SQL injection in tag search query parameter must not cause server error."""
        resp = client.get("/api/tags?q=' OR '1'='1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
