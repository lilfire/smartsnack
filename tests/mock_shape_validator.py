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


# ---------------------------------------------------------------------------
# OCR dispatch result: {"text": str, "provider": str, "fallback": bool}
# ---------------------------------------------------------------------------

OCR_DISPATCH_RESULT_REQUIRED_KEYS = {"text", "provider", "fallback"}


def validate_ocr_dispatch_result(data):
    """Validate the dict returned by dispatch_ocr / dispatch_ocr_bytes."""
    assert isinstance(data, dict), (
        f"OCR dispatch result must be a dict, got {type(data).__name__}"
    )
    missing = OCR_DISPATCH_RESULT_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"OCR dispatch result missing keys: {missing}"
    assert isinstance(data["text"], str), "'text' must be a str"
    assert isinstance(data["provider"], str), "'provider' must be a str"
    assert isinstance(data["fallback"], bool), "'fallback' must be a bool"


# ---------------------------------------------------------------------------
# OpenAI-compatible API response shapes
# (used by OpenAI, Groq, OpenRouter backends)
# ---------------------------------------------------------------------------

# Dict form of the OpenAI chat completion response.
# Real shape: {"choices": [{"message": {"content": str}, ...}], ...}
OPENAI_RESPONSE_REQUIRED_KEYS = {"choices"}
OPENAI_CHOICE_REQUIRED_KEYS = {"message"}
OPENAI_MESSAGE_REQUIRED_KEYS = {"content"}


def validate_openai_response_shape(data):
    """Validate an OpenAI-compatible chat completion response dict.

    If a test mock returns a dict representation, call this to confirm it
    matches the documented OpenAI API shape.
    """
    assert isinstance(data, dict), (
        f"OpenAI response must be a dict, got {type(data).__name__}"
    )
    missing = OPENAI_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"OpenAI response missing keys: {missing}"
    assert isinstance(data["choices"], list), "'choices' must be a list"
    assert len(data["choices"]) > 0, "Non-empty 'choices' expected in non-error response"
    choice = data["choices"][0]
    assert isinstance(choice, dict), f"choice must be a dict, got {type(choice).__name__}"
    missing_choice = OPENAI_CHOICE_REQUIRED_KEYS - set(choice.keys())
    assert not missing_choice, f"OpenAI choice missing keys: {missing_choice}"
    message = choice["message"]
    assert isinstance(message, dict), f"message must be a dict, got {type(message).__name__}"
    missing_msg = OPENAI_MESSAGE_REQUIRED_KEYS - set(message.keys())
    assert not missing_msg, f"OpenAI message missing keys: {missing_msg}"
    assert isinstance(message["content"], str), "'content' must be a str"


# ---------------------------------------------------------------------------
# Gemini (google.genai) API response shapes
# Real shape: response.text (str attribute, not a dict key)
# Canonical dict form for shape-validation purposes: {"text": str}
# ---------------------------------------------------------------------------

GEMINI_RESPONSE_REQUIRED_KEYS = {"text"}


def validate_gemini_response_shape(data):
    """Validate a Gemini response dict (canonical dict form).

    The real Gemini SDK response is an object with a .text attribute.
    For shape-validation purposes we use {"text": str} as the canonical dict.
    """
    assert isinstance(data, dict), (
        f"Gemini response must be a dict, got {type(data).__name__}"
    )
    missing = GEMINI_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Gemini response missing keys: {missing}"
    assert isinstance(data["text"], str), "'text' must be a str"


# ---------------------------------------------------------------------------
# Claude (anthropic) API response shapes
# Real shape: message.content = [ContentBlock(text=str)]
# Canonical dict form: {"content": [{"text": str}]}
# ---------------------------------------------------------------------------

CLAUDE_RESPONSE_REQUIRED_KEYS = {"content"}
CLAUDE_CONTENT_BLOCK_REQUIRED_KEYS = {"text"}


def validate_claude_response_shape(data):
    """Validate a Claude messages.create response dict (canonical dict form).

    Real SDK shape: message.content[0].text (object with attributes).
    Canonical dict form: {"content": [{"text": str}]}.
    """
    assert isinstance(data, dict), (
        f"Claude response must be a dict, got {type(data).__name__}"
    )
    missing = CLAUDE_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Claude response missing keys: {missing}"
    assert isinstance(data["content"], list), "'content' must be a list"
    assert len(data["content"]) > 0, "Non-empty 'content' expected in non-error response"
    block = data["content"][0]
    assert isinstance(block, dict), f"content block must be a dict, got {type(block).__name__}"
    missing_block = CLAUDE_CONTENT_BLOCK_REQUIRED_KEYS - set(block.keys())
    assert not missing_block, f"Claude content block missing keys: {missing_block}"
    assert isinstance(block["text"], str), "'text' must be a str"


# ---------------------------------------------------------------------------
# OFF (Open Food Facts) API response shapes
# ---------------------------------------------------------------------------

OFF_ADD_PRODUCT_RESPONSE_REQUIRED_KEYS = {"status"}
OFF_UPLOAD_IMAGE_RESPONSE_REQUIRED_KEYS = {"status", "imagefield"}


def validate_off_add_product_response(data):
    """Validate an OFF add-product API response dict."""
    assert isinstance(data, dict), (
        f"OFF add-product response must be a dict, got {type(data).__name__}"
    )
    missing = OFF_ADD_PRODUCT_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"OFF add-product response missing keys: {missing}"
    assert isinstance(data["status"], int), "'status' must be an int (1=ok)"


def validate_off_upload_image_response(data):
    """Validate an OFF upload-image API response dict."""
    assert isinstance(data, dict), (
        f"OFF upload-image response must be a dict, got {type(data).__name__}"
    )
    missing = OFF_UPLOAD_IMAGE_RESPONSE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"OFF upload-image response missing keys: {missing}"
    assert isinstance(data["status"], str), "'status' must be a str"
    assert isinstance(data["imagefield"], str), "'imagefield' must be a str"


# ---------------------------------------------------------------------------
# Proxy service response shape: (bytes, content_type_str)
# ---------------------------------------------------------------------------

PROXY_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def validate_proxy_response(data, content_type):
    """Validate the (bytes, content_type) tuple returned by proxy_image."""
    assert isinstance(data, bytes), f"Proxy data must be bytes, got {type(data).__name__}"
    assert len(data) > 0, "Proxy response must not be empty"
    assert isinstance(content_type, str), (
        f"Content-type must be a str, got {type(content_type).__name__}"
    )
    assert content_type in PROXY_ALLOWED_CONTENT_TYPES, (
        f"Unexpected content-type '{content_type}', "
        f"expected one of {PROXY_ALLOWED_CONTENT_TYPES}"
    )


# ---------------------------------------------------------------------------
# Bulk service response shapes
# ---------------------------------------------------------------------------

REFRESH_STATUS_REQUIRED_KEYS = {"running", "done", "current", "total", "updated", "skipped", "errors"}
PQ_ESTIMATION_REQUIRED_KEYS = {"total", "updated", "skipped"}


def validate_refresh_status_response(data):
    """Validate the dict returned by get_refresh_status."""
    assert isinstance(data, dict), (
        f"Refresh status must be a dict, got {type(data).__name__}"
    )
    missing = REFRESH_STATUS_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"Refresh status missing keys: {missing}"
    assert isinstance(data["running"], bool), "'running' must be a bool"
    assert isinstance(data["done"], bool), "'done' must be a bool"


def validate_pq_estimation_response(data):
    """Validate the dict returned by estimate_all_pq."""
    assert isinstance(data, dict), (
        f"PQ estimation result must be a dict, got {type(data).__name__}"
    )
    missing = PQ_ESTIMATION_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"PQ estimation result missing keys: {missing}"
    assert isinstance(data["total"], int), "'total' must be an int"
    assert isinstance(data["updated"], int), "'updated' must be an int"
    assert isinstance(data["skipped"], int), "'skipped' must be an int"
