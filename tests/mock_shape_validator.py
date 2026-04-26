"""Mock shape validation utility for SmartSnack API responses.

Validates that mock/fixture objects in tests conform to the real API response
schemas. If a mock drifts from the actual shape, tests using this validator
will fail, catching the class of bug from LSO-858 where mocked responses
hid real API issues.

Usage in tests:
    from tests.mock_shape_validator import validate_product_list_response, validate_ean_response

    def test_my_mock_is_valid():
        mock_response = {"products": [...], "total": 1}
        validate_product_list_response(mock_response)
"""


# -- Product list response: GET /api/products --

PRODUCT_LIST_RESPONSE_REQUIRED_KEYS = {"products", "total"}

PRODUCT_REQUIRED_KEYS = {
    "id", "name", "type", "total_score",
}

PRODUCT_OPTIONAL_KEYS = {
    "ean", "brand", "stores", "ingredients", "taste_note", "taste_score",
    "kcal", "energy_kj", "carbs", "sugar", "fat", "saturated_fat",
    "protein", "fiber", "salt", "volume", "price", "weight", "portion",
    "est_pdcaas", "est_diaas", "has_image", "completeness",
    "flags", "tags", "scores",
    # Computed scoring fields
    "nutri_score", "protein_per_kcal", "fiber_per_kcal",
    "sugar_per_100g_eq", "sat_fat_per_100g_eq",
    # Macro calorie percentage fields
    "pct_protein_cal", "pct_carb_cal", "pct_fat_cal",
    # Completeness fields
    "missing_fields", "has_missing_scores",
}

PRODUCT_ALL_KNOWN_KEYS = PRODUCT_REQUIRED_KEYS | PRODUCT_OPTIONAL_KEYS


# -- EAN response: GET /api/products/<pid>/eans --

EAN_ITEM_REQUIRED_KEYS = {"id", "ean", "is_primary", "synced_with_off"}


# -- Add EAN response: POST /api/products/<pid>/eans --
# Note: add_ean returns {id, ean, is_primary} — synced_with_off is NOT included

ADD_EAN_RESPONSE_REQUIRED_KEYS = {"id", "ean", "is_primary"}


# -- Add product response: POST /api/products --

ADD_PRODUCT_RESPONSE_REQUIRED_KEYS = {"id", "message"}


def validate_product_list_response(data, allow_empty=True):
    """Validate a product list response matches {products: [...], total: N}.

    Raises AssertionError with a descriptive message if the shape is wrong.
    """
    assert isinstance(data, dict), (
        f"Product list response must be a dict, got {type(data).__name__}. "
        "The API returns {{products: [...], total: N}}, not a bare list."
    )
    missing = PRODUCT_LIST_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Product list response missing keys: {missing}"
    assert isinstance(data["products"], list), "'products' must be a list"
    assert isinstance(data["total"], int), "'total' must be an int"
    if not allow_empty:
        assert len(data["products"]) > 0, "Expected non-empty product list"
    for product in data["products"]:
        validate_product_item(product)


def validate_product_item(product):
    """Validate a single product object has the required keys.

    Does NOT require all optional keys — mocks may omit them.
    Flags unknown keys to catch accidental schema drift.
    """
    assert isinstance(product, dict), f"Product must be a dict, got {type(product).__name__}"
    missing = PRODUCT_REQUIRED_KEYS - set(product.keys())
    assert not missing, (
        f"Product mock missing required keys: {missing}. "
        f"Required keys are: {PRODUCT_REQUIRED_KEYS}"
    )
    unknown = set(product.keys()) - PRODUCT_ALL_KNOWN_KEYS
    if unknown:
        raise AssertionError(
            f"Product mock has unknown keys: {unknown}. "
            "If the API schema changed, update PRODUCT_ALL_KNOWN_KEYS in mock_shape_validator.py"
        )


def validate_ean_list_response(data):
    """Validate an EAN list response (list of EAN items)."""
    assert isinstance(data, list), f"EAN list must be a list, got {type(data).__name__}"
    for item in data:
        validate_ean_item(item)


def validate_ean_item(item):
    """Validate a single EAN item has all required keys."""
    assert isinstance(item, dict), f"EAN item must be a dict, got {type(item).__name__}"
    missing = EAN_ITEM_REQUIRED_KEYS - set(item.keys())
    assert not missing, f"EAN item missing required keys: {missing}"
    assert isinstance(item["is_primary"], bool), "'is_primary' must be a bool"
    assert isinstance(item["synced_with_off"], bool), "'synced_with_off' must be a bool"


def validate_add_ean_response(data):
    """Validate an add-EAN response."""
    assert isinstance(data, dict), f"Add EAN response must be a dict, got {type(data).__name__}"
    missing = ADD_EAN_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Add EAN response missing required keys: {missing}"


def validate_add_product_response(data):
    """Validate an add-product response."""
    assert isinstance(data, dict), f"Add product response must be a dict, got {type(data).__name__}"
    missing = ADD_PRODUCT_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Add product response missing required keys: {missing}"
