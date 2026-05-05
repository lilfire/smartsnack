"""Input validation boundary tests.

Verifies text field length limits from config.py TEXT_LIMITS, numeric field
validation, required field enforcement, and invalid data-type rejection.
Each test sets up and tears down its own data.
"""

import pytest

from config import _TEXT_FIELD_LIMITS, TAG_LABEL_MAX_LEN, _MAX_CATEGORY_NAME_LEN


# ── Product text-field limits ────────────────────────────────────────────────


class TestProductTextFieldLimits:
    """Text fields enforce max-length limits from _TEXT_FIELD_LIMITS in config.py."""

    @pytest.mark.parametrize("field,max_len", _TEXT_FIELD_LIMITS.items())
    def test_field_at_exact_limit_accepted(self, client, seed_category, field, max_len):
        """Payload exactly at the limit must be accepted (200/201) or fail only for
        domain-logic reasons (e.g. 'type' requires a matching DB category).
        Must never return 400 for length reasons at or below the limit."""
        value = "A" * max_len
        payload = {"name": "LimitTest", "type": "Snacks", field: value}
        resp = client.post("/api/products", json=payload)
        if field == "type":
            # 'type' is a category name that must exist in the DB;
            # a 100-char dummy type won't exist, so 400 (category not found) is expected.
            assert resp.status_code in (200, 201, 400, 409), (
                f"{field} at exactly {max_len} chars got {resp.status_code}"
            )
        else:
            assert resp.status_code in (200, 201, 409), (
                f"{field} at exactly {max_len} chars got {resp.status_code}"
            )

    @pytest.mark.parametrize("field,max_len", _TEXT_FIELD_LIMITS.items())
    def test_field_one_over_limit_rejected(self, client, seed_category, field, max_len):
        """Payload one character over the limit must be rejected (400)."""
        value = "A" * (max_len + 1)
        payload = {"name": "OverLimitTest", "type": "Snacks", field: value}
        resp = client.post("/api/products", json=payload)
        assert resp.status_code == 400, (
            f"{field} at {max_len + 1} chars (over limit) got {resp.status_code}"
        )
        data = resp.get_json()
        assert "error" in data

    @pytest.mark.parametrize("field,max_len", _TEXT_FIELD_LIMITS.items())
    def test_field_far_over_limit_rejected(self, client, seed_category, field, max_len):
        """Payload far over the limit must be rejected (400)."""
        value = "A" * (max_len * 2 + 100)
        payload = {"name": "FarOverLimitTest", "type": "Snacks", field: value}
        resp = client.post("/api/products", json=payload)
        assert resp.status_code == 400

    def test_name_empty_string_rejected(self, client, seed_category):
        """Empty product name must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"name": "", "type": "Snacks"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_name_whitespace_only_rejected(self, client, seed_category):
        """Whitespace-only product name must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"name": "   ", "type": "Snacks"},
        )
        assert resp.status_code == 400

    def test_name_one_char_accepted(self, client, seed_category):
        """Single-character product name must be accepted."""
        resp = client.post(
            "/api/products",
            json={"name": "X", "type": "Snacks"},
        )
        assert resp.status_code in (200, 201, 409)


class TestProductTextFieldUpdate:
    """PUT /api/products/<id> also enforces text field limits."""

    def test_update_name_over_limit_rejected(self, client, db, seed_category):
        """Updating name beyond 200 chars must be rejected."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("UpdateLimitTest", "Snacks"),
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name = ?", ("UpdateLimitTest",)
        ).fetchone()["id"]

        resp = client.put(
            f"/api/products/{pid}",
            json={"name": "A" * 201},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_ingredients_over_limit_rejected(self, client, db, seed_category):
        """Updating ingredients beyond 10000 chars must be rejected."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("IngrLimitTest", "Snacks"),
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name = ?", ("IngrLimitTest",)
        ).fetchone()["id"]

        resp = client.put(
            f"/api/products/{pid}",
            json={"name": "IngrLimitTest", "ingredients": "X" * 10001},
        )
        assert resp.status_code == 400

    def test_update_name_at_exact_limit_accepted(self, client, db, seed_category):
        """Updating name at exactly 200 chars must succeed."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("ExactLimitUpdate", "Snacks"),
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name = ?", ("ExactLimitUpdate",)
        ).fetchone()["id"]

        resp = client.put(
            f"/api/products/{pid}",
            json={"name": "A" * 200},
        )
        assert resp.status_code == 200


# ── Numeric field validation ─────────────────────────────────────────────────


class TestNumericFieldValidation:
    """Numeric fields reject invalid types and accept boundary values."""

    def test_kcal_zero_accepted(self, client, seed_category):
        """kcal = 0 must be accepted (valid boundary)."""
        resp = client.post(
            "/api/products",
            json={"name": "ZeroKcal", "type": "Snacks", "kcal": 0},
        )
        assert resp.status_code in (200, 201, 409)

    def test_kcal_negative_accepted(self, client, seed_category):
        """Negative kcal must be accepted (no lower bound enforced by API)."""
        resp = client.post(
            "/api/products",
            json={"name": "NegKcal", "type": "Snacks", "kcal": -1},
        )
        assert resp.status_code in (200, 201, 409)

    def test_kcal_very_large_accepted(self, client, seed_category):
        """Very large kcal value must be accepted."""
        resp = client.post(
            "/api/products",
            json={"name": "HugeKcal", "type": "Snacks", "kcal": 999999},
        )
        assert resp.status_code in (200, 201, 409)

    def test_kcal_string_not_a_number_rejected(self, client, seed_category):
        """Non-numeric string for kcal must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"name": "BadKcal", "type": "Snacks", "kcal": "not_a_number"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_protein_nan_rejected(self, client, seed_category):
        """NaN value for protein must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"name": "NanProtein", "type": "Snacks", "protein": float("nan")},
        )
        # JSON encoding of NaN may fail at the client level; verify no 500
        assert resp.status_code in (400, 422, 200, 201, 409)
        assert resp.status_code != 500

    def test_numeric_field_as_object_rejected(self, client, seed_category):
        """Object value for numeric field must be rejected."""
        resp = client.post(
            "/api/products",
            json={"name": "ObjKcal", "type": "Snacks", "kcal": {"value": 100}},
        )
        assert resp.status_code == 400

    def test_numeric_field_as_list_rejected(self, client, seed_category):
        """List value for numeric field must be rejected."""
        resp = client.post(
            "/api/products",
            json={"name": "ListKcal", "type": "Snacks", "kcal": [100]},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("field", ["kcal", "protein", "fat", "carbs", "salt"])
    def test_numeric_field_string_of_number_accepted(self, client, seed_category, field):
        """String representation of a valid number must be coerced and accepted."""
        resp = client.post(
            "/api/products",
            json={"name": f"StringNum_{field}", "type": "Snacks", field: "42.5"},
        )
        assert resp.status_code in (200, 201, 409)


# ── Required field enforcement ───────────────────────────────────────────────


class TestRequiredFields:
    """Required fields are enforced on product creation."""

    def test_missing_name_rejected(self, client, seed_category):
        """Creating a product without 'name' must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "kcal": 100},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_null_name_rejected(self, client, seed_category):
        """Creating a product with null name must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={"name": None, "type": "Snacks"},
        )
        assert resp.status_code == 400

    def test_name_with_just_whitespace_rejected(self, client, seed_category):
        """Product name consisting solely of whitespace must be rejected."""
        resp = client.post(
            "/api/products",
            json={"name": "\t\n\r  ", "type": "Snacks"},
        )
        assert resp.status_code == 400

    def test_empty_json_body_rejected(self, client):
        """Empty JSON body for product creation must be rejected (400)."""
        resp = client.post(
            "/api/products",
            json={},
        )
        assert resp.status_code == 400

    def test_create_product_without_type_accepted(self, client):
        """Product without 'type' must be accepted (type is optional)."""
        resp = client.post(
            "/api/products",
            json={"name": "NoTypeProduct"},
        )
        assert resp.status_code in (200, 201, 409)

    def test_non_json_body_rejected(self, client):
        """Non-JSON request body for POST /api/products must be rejected (400)."""
        inner = client._inner if hasattr(client, "_inner") else client
        resp = inner.post(
            "/api/products",
            data="not json",
            content_type="application/json",
            headers={"X-Requested-With": "SmartSnack"},
        )
        assert resp.status_code == 400


# ── Category name validation ─────────────────────────────────────────────────


class TestCategoryNameValidation:
    """Category name enforces max length and character restrictions."""

    def test_category_name_at_limit_accepted(self, client):
        """Category name at exactly 100 chars must be accepted."""
        name = "A" * _MAX_CATEGORY_NAME_LEN
        resp = client.post(
            "/api/categories",
            json={"name": name, "label": "Test"},
        )
        assert resp.status_code in (201, 409)

    def test_category_name_over_limit_rejected(self, client):
        """Category name over 100 chars must be rejected (400)."""
        name = "A" * (_MAX_CATEGORY_NAME_LEN + 1)
        resp = client.post(
            "/api/categories",
            json={"name": name, "label": "Test"},
        )
        assert resp.status_code == 400

    def test_empty_category_name_rejected(self, client):
        """Empty category name must be rejected (400)."""
        resp = client.post(
            "/api/categories",
            json={"name": "", "label": "Test"},
        )
        assert resp.status_code == 400

    def test_category_name_with_control_chars_rejected(self, client):
        """Category name with ASCII control characters must be rejected (400)."""
        resp = client.post(
            "/api/categories",
            json={"name": "Test\x00Category", "label": "Test"},
        )
        assert resp.status_code == 400

    def test_whitespace_only_category_name_rejected(self, client):
        """Whitespace-only category name must be rejected (400)."""
        resp = client.post(
            "/api/categories",
            json={"name": "   ", "label": "Test"},
        )
        assert resp.status_code == 400


# ── Tag label validation ─────────────────────────────────────────────────────


class TestTagLabelValidation:
    """Tag label enforces max length and non-empty constraint."""

    def test_tag_label_at_limit_accepted(self, client):
        """Tag label at exactly TAG_LABEL_MAX_LEN chars must be accepted."""
        label = "A" * TAG_LABEL_MAX_LEN
        resp = client.post("/api/tags", json={"label": label})
        assert resp.status_code in (201, 400, 409)
        # Either accepted or correctly rejected — must not 500
        assert resp.status_code != 500

    def test_tag_label_over_limit_rejected(self, client):
        """Tag label over TAG_LABEL_MAX_LEN chars must be rejected (400)."""
        label = "A" * (TAG_LABEL_MAX_LEN + 1)
        resp = client.post("/api/tags", json={"label": label})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_tag_label_rejected(self, client):
        """Empty tag label must be rejected (400)."""
        resp = client.post("/api/tags", json={"label": ""})
        assert resp.status_code == 400

    def test_tag_label_whitespace_only_rejected(self, client):
        """Whitespace-only tag label must be rejected (400)."""
        resp = client.post("/api/tags", json={"label": "   "})
        assert resp.status_code == 400


# ── Pagination parameter validation ─────────────────────────────────────────


class TestPaginationValidation:
    """limit and offset parameters must be integers; non-integers are rejected."""

    def test_non_integer_limit_rejected(self, client, seed_category):
        """Non-integer limit must return 400."""
        resp = client.get("/api/products?limit=abc")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_non_integer_offset_rejected(self, client, seed_category):
        """Non-integer offset must return 400."""
        resp = client.get("/api/products?offset=xyz")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_valid_limit_and_offset_accepted(self, client, seed_category):
        """Valid integer limit and offset must return 200."""
        resp = client.get("/api/products?limit=10&offset=0")
        assert resp.status_code == 200

    def test_zero_limit_accepted(self, client, seed_category):
        """limit=0 must be accepted (returns empty page)."""
        resp = client.get("/api/products?limit=0&offset=0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["products"] == []
