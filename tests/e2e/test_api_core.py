"""Tests for core API endpoints: health, products CRUD, translations, and languages.

All tests drive the live Flask server directly via ``urllib.request`` — no
browser required — which makes them fast and deterministic.  The ``page``
fixture is imported in the signature only where needed to satisfy the fixture
dependency chain; pure API tests omit it.
"""

import json
import urllib.error
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get(url: str) -> dict:
    """Issue a GET request and return the parsed JSON body."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _get_products_list(url: str) -> list:
    """GET /api/products and return the product list (unwraps paginated response)."""
    data = _get(url)
    if isinstance(data, dict) and "products" in data:
        return data["products"]
    return data


def _put(url: str, payload: dict) -> dict:
    """Issue a PUT request with a JSON payload and return the parsed JSON body."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _delete(url: str) -> dict:
    """Issue a DELETE request and return the parsed JSON body."""
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_endpoint(live_url):
    """GET /health returns status 'ok' and a numeric product count."""
    data = _get(f"{live_url}/health")

    assert data.get("status") == "ok", (
        f"Expected status 'ok', got {data.get('status')!r}"
    )
    assert "products" in data, f"Response missing 'products' key: {data}"
    assert isinstance(data["products"], int), (
        f"'products' should be an int, got {type(data['products']).__name__}"
    )
    assert data["products"] >= 0, (
        f"'products' count must be non-negative, got {data['products']}"
    )


# ---------------------------------------------------------------------------
# Products list
# ---------------------------------------------------------------------------


def test_products_api_list(live_url, api_create_product):
    """GET /api/products returns a list that includes freshly created products."""
    api_create_product(name="ListApiProduct1")
    api_create_product(name="ListApiProduct2")

    products = _get_products_list(f"{live_url}/api/products")

    assert isinstance(products, list), f"Expected a list, got {type(products).__name__}"
    names = {p["name"] for p in products}
    assert "ListApiProduct1" in names, (
        f"'ListApiProduct1' not found in response names: {names}"
    )
    assert "ListApiProduct2" in names, (
        f"'ListApiProduct2' not found in response names: {names}"
    )


# ---------------------------------------------------------------------------
# Products search
# ---------------------------------------------------------------------------


def test_products_api_search(live_url, api_create_product):
    """GET /api/products?search= returns only products whose name matches."""
    api_create_product(name="UniqueNameXYZAlpha")
    api_create_product(name="TotallyDifferentBeta")

    products = _get_products_list(f"{live_url}/api/products?search=UniqueNameXYZ")

    assert isinstance(products, list), f"Expected a list, got {type(products).__name__}"
    names = [p["name"] for p in products]
    assert all("UniqueNameXYZ" in n for n in names), (
        f"Search results contain non-matching products: {names}"
    )
    assert "TotallyDifferentBeta" not in names, (
        "'TotallyDifferentBeta' should not appear in search results for 'UniqueNameXYZ'"
    )


# ---------------------------------------------------------------------------
# Products type filter
# ---------------------------------------------------------------------------


def test_products_api_type_filter(live_url, api_create_product):
    """GET /api/products?type=Snacks returns only products in that category."""
    api_create_product(name="TypeFilterSnack1", category="Snacks")
    api_create_product(name="TypeFilterSnack2", category="Snacks")

    products = _get_products_list(f"{live_url}/api/products?type=Snacks")

    assert isinstance(products, list), f"Expected a list, got {type(products).__name__}"
    assert len(products) >= 2, (
        f"Expected at least 2 Snacks products, got {len(products)}"
    )
    for product in products:
        assert product.get("type") == "Snacks", (
            f"Product {product.get('name')!r} has type {product.get('type')!r}, "
            f"expected 'Snacks'"
        )


# ---------------------------------------------------------------------------
# Products update
# ---------------------------------------------------------------------------


def test_products_api_update(live_url, api_create_product):
    """PUT /api/products/<id> updates the product name and the change is visible."""
    created = api_create_product(name="UpdateOriginalName")
    pid = created["id"]

    result = _put(
        f"{live_url}/api/products/{pid}",
        {
            "name": "UpdatedNameAfterPut",
        },
    )

    assert result.get("ok") is True, (
        f"PUT did not return ok=True: {result}"
    )

    all_products = _get_products_list(f"{live_url}/api/products")
    names = {p["name"] for p in all_products}
    assert "UpdatedNameAfterPut" in names, (
        f"Updated name not found in product list: {names}"
    )
    assert "UpdateOriginalName" not in names, (
        f"Old name still present after update: {names}"
    )


# ---------------------------------------------------------------------------
# Products delete
# ---------------------------------------------------------------------------


def test_products_api_delete(live_url, api_create_product):
    """DELETE /api/products/<id> removes the product from subsequent GET responses."""
    created = api_create_product(name="DeleteMeApiProduct")
    pid = created["id"]

    # Verify it exists before deletion
    before = _get_products_list(f"{live_url}/api/products")
    names_before = {p["name"] for p in before}
    assert "DeleteMeApiProduct" in names_before, (
        "Product was not found before deletion attempt"
    )

    result = _delete(f"{live_url}/api/products/{pid}")

    assert result.get("ok") is True, (
        f"DELETE did not return ok=True: {result}"
    )

    after = _get_products_list(f"{live_url}/api/products")
    names_after = {p["name"] for p in after}
    assert "DeleteMeApiProduct" not in names_after, (
        "Deleted product still appears in GET /api/products response"
    )


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


def test_languages_api(live_url):
    """GET /api/languages returns a list containing 'no', 'en', and 'se' codes."""
    data = _get(f"{live_url}/api/languages")

    assert isinstance(data, list), f"Expected a list, got {type(data).__name__}"
    assert len(data) >= 3, (
        f"Expected at least 3 language entries, got {len(data)}"
    )

    codes = {entry["code"] for entry in data}
    for expected_code in ("no", "en", "se"):
        assert expected_code in codes, (
            f"Language code {expected_code!r} missing from /api/languages response: {codes}"
        )

    # Every entry must carry the three required keys
    for entry in data:
        assert "code" in entry, f"Language entry missing 'code': {entry}"
        assert "label" in entry, f"Language entry missing 'label': {entry}"
        assert "flag" in entry, f"Language entry missing 'flag': {entry}"


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------


def test_translations_api(live_url):
    """GET /api/translations/en returns a non-empty dict of translation keys."""
    data = _get(f"{live_url}/api/translations/en")

    assert isinstance(data, dict), (
        f"Expected a dict for translations, got {type(data).__name__}"
    )
    assert len(data) > 0, "Translation dict is empty"

    # Every value should be a string (translation strings, not nested objects)
    for key, value in data.items():
        assert isinstance(value, str), (
            f"Translation key {key!r} has non-string value: {value!r}"
        )


def test_translations_api_invalid_lang(live_url):
    """GET /api/translations/<unknown> returns a 404 error response."""
    req = urllib.request.Request(
        f"{live_url}/api/translations/zz_unknown",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            # If somehow 200 is returned, it must at least have an error key
            assert "error" in body, (
                f"Expected error for unknown language, got: {body}"
            )
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, (
            f"Expected HTTP 404 for unknown language, got {exc.code}"
        )


# ---------------------------------------------------------------------------
# Language setting
# ---------------------------------------------------------------------------


def test_language_setting_api(live_url):
    """PUT /api/settings/language sets the language; GET confirms the change."""
    # Switch to English
    put_result = _put(f"{live_url}/api/settings/language", {"language": "en"})

    assert put_result.get("ok") is True, (
        f"PUT /api/settings/language did not return ok=True: {put_result}"
    )
    assert put_result.get("language") == "en", (
        f"PUT response language mismatch: {put_result}"
    )

    # Confirm the GET reflects the change
    get_result = _get(f"{live_url}/api/settings/language")

    assert "language" in get_result, (
        f"GET /api/settings/language response missing 'language' key: {get_result}"
    )
    assert get_result["language"] == "en", (
        f"Expected language 'en' after PUT, got {get_result['language']!r}"
    )

    # Reset to Norwegian so other tests are not affected by the changed state
    reset_result = _put(f"{live_url}/api/settings/language", {"language": "no"})
    assert reset_result.get("ok") is True, (
        f"Failed to reset language to 'no': {reset_result}"
    )

    final = _get(f"{live_url}/api/settings/language")
    assert final.get("language") == "no", (
        f"Language was not reset to 'no': {final}"
    )
