"""E2E tests for OFF integration: search, product lookup, add product.

External APIs are mocked via unittest.mock to avoid hitting real servers.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import patch


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


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


_MOCK_OFF_PRODUCT = {
    "status": 1,
    "product": {
        "code": "7310865004703",
        "product_name": "Kvarg Naturell",
        "brands": "Lindahls",
        "nutriments": {
            "energy-kcal_100g": 60,
            "fat_100g": 0.2,
            "saturated-fat_100g": 0.1,
            "carbohydrates_100g": 3.5,
            "sugars_100g": 3.5,
            "proteins_100g": 11,
            "fiber_100g": 0,
            "salt_100g": 0.1,
        },
        "completeness": 0.8,
    },
}

_MOCK_OFF_SEARCH = {
    "products": [
        {
            "code": "7310865004703",
            "product_name": "Kvarg Naturell",
            "brands": "Lindahls",
            "completeness": 0.8,
        },
    ],
    "count": 1,
}


def test_off_search_get(live_url):
    """GET /api/off/search?q=<query> proxies to OFF search with mock."""
    with patch("services.proxy_service.off_search") as mock_search:
        mock_search.return_value = _MOCK_OFF_SEARCH
        status, body = _get(f"{live_url}/api/off/search?q=kvarg")

    assert status == 200
    assert "products" in body


def test_off_search_post(live_url):
    """POST /api/off/search with JSON body proxies to OFF search with mock."""
    with patch("services.proxy_service.off_search") as mock_search:
        mock_search.return_value = _MOCK_OFF_SEARCH
        status, body = _post(
            f"{live_url}/api/off/search",
            {"q": "kvarg", "category": "Dairy"},
        )

    assert status == 200
    assert "products" in body


def test_off_search_with_nutrition(live_url):
    """POST /api/off/search with nutrition data passes it through."""
    with patch("services.proxy_service.off_search") as mock_search:
        mock_search.return_value = _MOCK_OFF_SEARCH
        status, body = _post(
            f"{live_url}/api/off/search",
            {
                "q": "kvarg",
                "nutrition": {"kcal": 60, "protein": 11},
            },
        )

    assert status == 200
    assert "products" in body


def test_off_search_short_query(live_url):
    """GET /api/off/search?q=a returns 400 for query too short."""
    with patch("services.proxy_service.off_search") as mock_search:
        mock_search.side_effect = ValueError("Query too short")
        status, body = _get(f"{live_url}/api/off/search?q=a")

    assert status == 400
    assert "error" in body


def test_off_product_lookup(live_url):
    """GET /api/off/product/<code> returns product data with mock."""
    with patch("services.proxy_service.off_product") as mock_product:
        mock_product.return_value = _MOCK_OFF_PRODUCT
        status, body = _get(f"{live_url}/api/off/product/7310865004703")

    assert status == 200
    assert "product" in body or "status" in body


def test_off_product_invalid_code(live_url):
    """GET /api/off/product/abc returns 400 for non-numeric code."""
    with patch("services.proxy_service.off_product") as mock_product:
        mock_product.side_effect = ValueError("Invalid product code")
        status, body = _get(f"{live_url}/api/off/product/abc")

    assert status == 400
    assert "error" in body


def test_off_add_product(live_url):
    """POST /api/off/add-product publishes product to OFF with mock."""
    with patch("services.off_service.add_product_to_off") as mock_add:
        mock_add.return_value = {"status": 1, "status_verbose": "fields saved"}
        status, body = _post(
            f"{live_url}/api/off/add-product",
            {
                "code": "7310865004703",
                "product_name": "Test Product",
            },
        )

    assert status == 200
    assert body.get("ok") is True


def test_off_add_product_no_credentials(live_url):
    """POST /api/off/add-product fails when no credentials configured."""
    with patch("services.off_service.add_product_to_off") as mock_add:
        mock_add.side_effect = ValueError("off_err_no_credentials")
        status, body = _post(
            f"{live_url}/api/off/add-product",
            {"code": "1234567890", "product_name": "Test"},
        )

    assert status == 400
    assert "error" in body


def test_off_add_product_no_ean(live_url):
    """POST /api/off/add-product fails when no EAN provided."""
    with patch("services.off_service.add_product_to_off") as mock_add:
        mock_add.side_effect = ValueError("off_err_no_ean")
        status, body = _post(
            f"{live_url}/api/off/add-product",
            {"product_name": "Test"},
        )

    assert status == 400
    assert "error" in body
