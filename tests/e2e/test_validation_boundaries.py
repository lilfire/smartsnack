"""E2E tests: validation edge cases, boundary tests, and EAN duplicate detection."""

import json
import urllib.error
import urllib.request


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _put(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


# ── Complex Validation Scenarios ──────────────────────────────────────


class TestNumericFieldValidation:
    """Invalid data types and non-finite values for numeric fields."""

    def test_non_numeric_kcal_rejected(self, live_url, api_create_product):
        """String value for a numeric field returns 400."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "BadKcal", "kcal": "not_a_number",
        })
        assert status == 400
        assert "error" in body

    def test_non_numeric_fat_rejected(self, live_url, api_create_product):
        """Non-numeric fat value returns 400."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "BadFat", "fat": "abc",
        })
        assert status == 400
        assert "error" in body

    def test_infinity_rejected(self, live_url, api_create_product):
        """Infinity is not a valid numeric value."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "InfProduct", "kcal": float("inf"),
        })
        assert status == 400
        assert "error" in body

    def test_nan_rejected(self, live_url, api_create_product):
        """NaN is not a valid numeric value."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "NaNProduct", "protein": float("nan"),
        })
        assert status == 400
        assert "error" in body

    def test_negative_nutrition_accepted(self, live_url, api_create_product):
        """Negative values are accepted (no lower-bound validation in service)."""
        product = api_create_product(name="NegativeValues", kcal=-10, fat=-5)
        assert "id" in product

    def test_zero_nutrition_accepted(self, live_url, api_create_product):
        """Zero values are valid for nutrition fields."""
        product = api_create_product(name="ZeroNutrition", kcal=0, fat=0,
                                      protein=0, sugar=0)
        assert "id" in product

    def test_very_large_numeric_accepted(self, live_url, api_create_product):
        """Very large (but finite) numeric values are accepted."""
        product = api_create_product(name="HugeKcal", kcal=999999999)
        assert "id" in product

    def test_update_with_non_numeric_rejected(self, live_url, api_create_product):
        """Updating a numeric field with a string returns 400."""
        product = api_create_product(name="UpdateBadNum")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {
            "protein": "xyz",
        })
        assert status == 400
        assert "error" in body


# ── Text Length Limits ────────────────────────────────────────────────


class TestTextFieldLimits:
    """Text fields exceeding config limits are rejected."""

    def test_name_at_limit(self, live_url, api_create_product):
        """Product name exactly at 200 chars is accepted."""
        name = "A" * 200
        product = api_create_product(name=name)
        assert "id" in product

    def test_name_beyond_limit(self, live_url):
        """Product name exceeding 200 chars is rejected."""
        name = "A" * 201
        status, body = _post(f"{live_url}/api/products", {"name": name})
        assert status == 400
        assert "error" in body
        assert "name" in body["error"].lower() or "max length" in body["error"].lower()

    def test_brand_beyond_limit(self, live_url, api_create_product):
        """Brand exceeding 200 chars is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "BrandTest", "brand": "B" * 201,
        })
        assert status == 400
        assert "error" in body

    def test_stores_beyond_limit(self, live_url, api_create_product):
        """Stores field exceeding 500 chars is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "StoresTest", "stores": "S" * 501,
        })
        assert status == 400
        assert "error" in body

    def test_ingredients_beyond_limit(self, live_url, api_create_product):
        """Ingredients exceeding 10000 chars is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "IngrTest", "ingredients": "I" * 10001,
        })
        assert status == 400
        assert "error" in body

    def test_taste_note_beyond_limit(self, live_url, api_create_product):
        """Taste note exceeding 2000 chars is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "TasteTest", "taste_note": "T" * 2001,
        })
        assert status == 400
        assert "error" in body

    def test_type_beyond_limit(self, live_url, api_create_product):
        """Type field exceeding 100 chars is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "TypeTest", "type": "X" * 101,
        })
        assert status == 400
        assert "error" in body

    def test_update_name_beyond_limit(self, live_url, api_create_product):
        """Updating name beyond 200 chars is rejected."""
        product = api_create_product(name="UpdateNameLimit")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {
            "name": "N" * 201,
        })
        assert status == 400
        assert "error" in body


# ── Empty / Null / Missing Field Edge Cases ───────────────────────────


class TestEmptyNullMissing:
    """Edge cases for empty strings, null, and missing fields."""

    def test_empty_name_rejected(self, live_url):
        """Empty product name is rejected."""
        status, body = _post(f"{live_url}/api/products", {"name": ""})
        assert status == 400
        assert "error" in body

    def test_whitespace_only_name_rejected(self, live_url):
        """Whitespace-only name is rejected."""
        status, body = _post(f"{live_url}/api/products", {"name": "   "})
        assert status == 400
        assert "error" in body

    def test_missing_name_rejected(self, live_url):
        """Missing name field is rejected."""
        status, body = _post(f"{live_url}/api/products", {"kcal": 100})
        assert status == 400
        assert "error" in body

    def test_null_nutrition_accepted(self, live_url, api_create_product):
        """Null nutrition values are accepted (fields are optional)."""
        product = api_create_product(name="NullNutrition", kcal=None, fat=None)
        assert "id" in product

    def test_empty_string_nutrition_accepted(self, live_url, api_create_product):
        """Empty string for nutrition field treated as null."""
        product = api_create_product(name="EmptyStrNutr", kcal="", protein="")
        assert "id" in product

    def test_no_json_body_rejected(self, live_url):
        """POST with no JSON body returns 400."""
        req = urllib.request.Request(
            f"{live_url}/api/products",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "Expected error"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400


# ── Special Characters in Text Fields ─────────────────────────────────


class TestSpecialCharacters:
    """Unicode, emoji, and HTML injection attempts in text fields."""

    def test_unicode_name_accepted(self, live_url, api_create_product):
        """Unicode characters in product name are accepted."""
        product = api_create_product(name="Skogsbær Ørret Ål")
        assert "id" in product

    def test_emoji_in_name_accepted(self, live_url, api_create_product):
        """Emoji characters in product name are accepted."""
        product = api_create_product(name="Healthy Snack 🥗🍎")
        assert "id" in product

    def test_html_in_name_stored_as_text(self, live_url, api_create_product):
        """HTML tags in name are stored as plain text (no XSS)."""
        product = api_create_product(name="<script>alert(1)</script>")
        assert "id" in product

    def test_sql_injection_in_name_safe(self, live_url, api_create_product):
        """SQL injection attempts in name field are safely handled."""
        product = api_create_product(name="'; DROP TABLE products; --")
        assert "id" in product
        # Verify products endpoint still works
        status, body = _get(f"{live_url}/api/products")
        assert status == 200


# ── EAN Validation ────────────────────────────────────────────────────


class TestEanValidation:
    """EAN format validation on product create and update."""

    def test_valid_ean_13(self, live_url, api_create_product):
        """Valid 13-digit EAN is accepted."""
        product = api_create_product(name="Ean13Product", ean="1234567890123")
        assert "id" in product

    def test_valid_ean_8(self, live_url, api_create_product):
        """Valid 8-digit EAN is accepted."""
        product = api_create_product(name="Ean8Product", ean="12345678")
        assert "id" in product

    def test_too_short_ean_rejected(self, live_url):
        """EAN shorter than 8 digits is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "ShortEan", "ean": "1234567",
        })
        assert status == 400
        assert "EAN" in body["error"]

    def test_too_long_ean_rejected(self, live_url):
        """EAN longer than 13 digits is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "LongEan", "ean": "12345678901234",
        })
        assert status == 400
        assert "EAN" in body["error"]

    def test_non_digit_ean_rejected(self, live_url):
        """EAN with letters is rejected."""
        status, body = _post(f"{live_url}/api/products", {
            "name": "AlphaEan", "ean": "12345678abc",
        })
        assert status == 400
        assert "EAN" in body["error"]

    def test_empty_ean_accepted(self, live_url, api_create_product):
        """Empty EAN is accepted (EAN is optional)."""
        product = api_create_product(name="NoEanProduct", ean="")
        assert "id" in product

    def test_update_invalid_ean_rejected(self, live_url, api_create_product):
        """Updating product with invalid EAN format returns 400."""
        product = api_create_product(name="UpdateEanTest")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {
            "ean": "INVALID",
        })
        assert status == 400
        assert "EAN" in body["error"]

    def test_add_ean_invalid_format_rejected(self, live_url, api_create_product):
        """POST /api/products/<id>/eans with bad format returns 400."""
        product = api_create_product(name="EanAddBadFmt")
        pid = product["id"]
        status, body = _post(f"{live_url}/api/products/{pid}/eans", {
            "ean": "abc",
        })
        assert status == 400
        assert "error" in body


# ── EAN Duplicate Detection ──────────────────────────────────────────


class TestEanDuplicateDetection:
    """Cross-product EAN uniqueness enforcement."""

    def test_duplicate_ean_on_create_detected(self, live_url, api_create_product):
        """Creating a product with an EAN matching an existing product returns 409."""
        ean = "9991111111111"
        api_create_product(name="OriginalEanProd", ean=ean)
        status, body = _post(f"{live_url}/api/products", {
            "name": "DuplicateEanProd", "ean": ean,
        })
        assert status == 409
        assert "duplicate" in body
        assert body["duplicate"]["match_type"] == "ean"

    def test_duplicate_ean_add_to_different_product_rejected(
        self, live_url, api_create_product
    ):
        """Adding an EAN that belongs to another product returns 409."""
        ean = "9992222222222"
        api_create_product(name="ProdWithEan1", ean=ean)
        product_b = api_create_product(
            name="ProdWithEan2", ean="9992222222223"
        )
        pid_b = product_b["id"]
        status, body = _post(f"{live_url}/api/products/{pid_b}/eans", {
            "ean": ean,
        })
        assert status == 409
        assert body["error"] == "ean_already_exists"

    def test_same_ean_same_product_idempotent(self, live_url, api_create_product):
        """Adding the same EAN to the same product is idempotent (200)."""
        ean = "9993333333333"
        product = api_create_product(name="IdempotentEan", ean=ean)
        pid = product["id"]
        status, body = _post(f"{live_url}/api/products/{pid}/eans", {
            "ean": ean,
        })
        assert status == 200
        assert body.get("already_exists") is True

    def test_duplicate_ean_on_create_returns_existing_id(
        self, live_url, api_create_product
    ):
        """Duplicate detection returns the existing product's id and name."""
        ean = "9994444444444"
        original = api_create_product(name="OrigProd4", ean=ean)
        status, body = _post(f"{live_url}/api/products", {
            "name": "DupProd4", "ean": ean,
        })
        assert status == 409
        assert body["duplicate"]["id"] == original["id"]

    def test_allow_duplicate_bypasses_ean_check(self, live_url, api_create_product):
        """on_duplicate=allow_duplicate lets a product with the same EAN be created."""
        ean = "9995555555555"
        api_create_product(name="OrigProd5", ean=ean)
        status, body = _post(f"{live_url}/api/products", {
            "name": "DupAllowed5", "ean": ean,
            "on_duplicate": "allow_duplicate",
        })
        assert status == 201
        assert "id" in body

    def test_different_ean_no_duplicate(self, live_url, api_create_product):
        """Products with different EANs do not trigger duplicate detection."""
        api_create_product(name="ProdEanA", ean="9996666666666")
        status, body = _post(f"{live_url}/api/products", {
            "name": "ProdEanB", "ean": "9996666666667",
        })
        assert status == 201
        assert "id" in body


# ── Invalid Field / Nothing to Update ─────────────────────────────────


class TestUpdateValidation:
    """Update endpoint validation edge cases."""

    def test_update_nonexistent_product_404(self, live_url):
        """Updating a product that doesn't exist returns 404."""
        status, body = _put(f"{live_url}/api/products/999999", {
            "name": "Ghost",
        })
        assert status == 404

    def test_update_invalid_field_rejected(self, live_url, api_create_product):
        """Updating with an unknown field name returns 400."""
        product = api_create_product(name="InvalidFieldProd")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {
            "nonexistent_field": "value",
        })
        assert status == 400
        assert "error" in body

    def test_update_empty_body_rejected(self, live_url, api_create_product):
        """Updating with empty payload returns 400 (nothing to update)."""
        product = api_create_product(name="EmptyUpdateProd")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {})
        assert status == 400
        assert "error" in body

    def test_nonexistent_category_rejected(self, live_url, api_create_product):
        """Setting type to a category that doesn't exist returns 400."""
        product = api_create_product(name="BadCatProd")
        pid = product["id"]
        status, body = _put(f"{live_url}/api/products/{pid}", {
            "type": "NonexistentCategory12345",
        })
        assert status == 400
        assert "error" in body
