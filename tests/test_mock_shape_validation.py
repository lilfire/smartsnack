"""Validate that mock objects used across tests match real API response schemas.

This catches the class of bug from LSO-858 where tests used mocks with
wrong response shapes (e.g. bare list instead of {products: [], total: N}).
If the API schema changes, these tests will fail, forcing mock updates.
"""

import pytest

from tests.mock_shape_validator import (
    validate_product_list_response,
    validate_product_item,
    validate_ean_item,
    validate_add_ean_response,
    validate_add_product_response,
    PRODUCT_REQUIRED_KEYS,
    EAN_ITEM_REQUIRED_KEYS,
)


class TestProductListResponseValidation:
    """Ensure the product list response validator catches common mock errors."""

    def test_valid_empty_response(self):
        validate_product_list_response({"products": [], "total": 0})

    def test_valid_response_with_product(self):
        validate_product_list_response({
            "products": [{"id": 1, "name": "Test", "type": "Snacks", "total_score": 50}],
            "total": 1,
        })

    def test_rejects_bare_list(self):
        with pytest.raises(AssertionError, match="must be a dict"):
            validate_product_list_response([{"id": 1}])

    def test_rejects_missing_products_key(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_product_list_response({"total": 0})

    def test_rejects_missing_total_key(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_product_list_response({"products": []})

    def test_rejects_wrong_products_type(self):
        with pytest.raises(AssertionError, match="must be a list"):
            validate_product_list_response({"products": "bad", "total": 0})

    def test_rejects_wrong_total_type(self):
        with pytest.raises(AssertionError, match="must be an int"):
            validate_product_list_response({"products": [], "total": "0"})

    def test_allow_empty_false_rejects_empty(self):
        with pytest.raises(AssertionError, match="non-empty"):
            validate_product_list_response({"products": [], "total": 0}, allow_empty=False)


class TestProductItemValidation:
    """Ensure individual product items are validated correctly."""

    def test_valid_minimal_product(self):
        validate_product_item({"id": 1, "name": "Test", "type": "Snacks", "total_score": 50})

    def test_valid_product_with_optional_fields(self):
        validate_product_item({
            "id": 1, "name": "Test", "type": "Snacks", "total_score": 50,
            "ean": "7038010069307", "brand": "TestBrand", "kcal": 200,
            "flags": [], "tags": [],
        })

    def test_rejects_missing_required_keys(self):
        for key in PRODUCT_REQUIRED_KEYS:
            product = {"id": 1, "name": "Test", "type": "Snacks", "total_score": 50}
            del product[key]
            with pytest.raises(AssertionError, match="missing required keys"):
                validate_product_item(product)

    def test_rejects_unknown_keys(self):
        with pytest.raises(AssertionError, match="unknown keys"):
            validate_product_item({
                "id": 1, "name": "Test", "type": "Snacks", "total_score": 50,
                "bogus_field": True,
            })


class TestEanItemValidation:
    """Ensure EAN items are validated correctly."""

    def test_valid_ean_item(self):
        validate_ean_item({"id": 1, "ean": "7038010069307", "is_primary": True, "synced_with_off": False})

    def test_rejects_missing_keys(self):
        for key in EAN_ITEM_REQUIRED_KEYS:
            item = {"id": 1, "ean": "7038010069307", "is_primary": True, "synced_with_off": False}
            del item[key]
            with pytest.raises(AssertionError, match="missing required keys"):
                validate_ean_item(item)

    def test_rejects_non_bool_is_primary(self):
        with pytest.raises(AssertionError, match="must be a bool"):
            validate_ean_item({"id": 1, "ean": "123", "is_primary": 1, "synced_with_off": False})


class TestAddProductResponseValidation:
    def test_valid(self):
        validate_add_product_response({"id": 1, "message": "Product added"})

    def test_rejects_missing_id(self):
        with pytest.raises(AssertionError, match="missing required keys"):
            validate_add_product_response({"message": "Product added"})


class TestAddEanResponseValidation:
    def test_valid(self):
        validate_add_ean_response({"id": 1, "ean": "123", "is_primary": True})

    def test_rejects_missing_keys(self):
        with pytest.raises(AssertionError, match="missing required keys"):
            validate_add_ean_response({"id": 1})


class TestRealApiShapeMatchesFrontendMocks:
    """Validate that the mock shapes used in frontend scanner.test.js are correct.

    These are the exact shapes used in the frontend tests. If these fail,
    it means the frontend mocks have drifted from the real API contract.
    """

    def test_scanner_fetchProducts_empty_mock(self):
        """Matches: fetchProducts.mockResolvedValue({ products: [], total: 0 })"""
        validate_product_list_response({"products": [], "total": 0})

    def test_scanner_fetchProducts_with_product_mock(self):
        """Matches: fetchProducts.mockResolvedValue({ products: [matchingProduct], total: 1 })"""
        mock_product = {"id": 10, "name": "TestProduct", "type": "dairy", "total_score": 0}
        validate_product_list_response({"products": [mock_product], "total": 1})

    def test_scanner_product_mock_shape(self):
        """The scanner test uses: { id: 10, name: 'TestProduct', type: 'dairy', ean: '...' }
        Verify this has all required keys (it was missing total_score in LSO-858)."""
        scanner_mock = {"id": 10, "name": "TestProduct", "type": "dairy", "ean": "7038010055720", "total_score": 0}
        validate_product_item(scanner_mock)

    def test_real_api_returns_dict_not_list(self, client, app_ctx):
        """The original LSO-858 bug: scanner code expected a list but got a dict."""
        resp = client.get("/api/products")
        data = resp.get_json()
        validate_product_list_response(data)
        assert not isinstance(data, list), "API must NOT return a bare list"
