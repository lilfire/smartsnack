"""End-to-end tests for POST /api/ocr/nutrition.

Tests the full request lifecycle through the live Flask server with a mocked
nutrition OCR dispatcher. Covers happy path, error responses, edge cases,
and both JSON (base64) and multipart upload paths.

Mirrors the structure of ``test_e2e_ocr_ingredients.py`` (15 server-level
tests) but exercises the nutrition endpoint and its shared error taxonomy
via ``_handle_ocr_exception`` in ``blueprints/ocr.py``.

LSO-1288 / LSO-1285 — gap report on LSO-1282 flagged this endpoint as only
covered by Playwright route-mocks. These tests hit the real Flask handler.
"""

import base64
import json
import os
import urllib.error
import urllib.request

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid 1x1 PNG image
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
    b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
_MINIMAL_PNG_B64 = base64.b64encode(_MINIMAL_PNG).decode()
_MINIMAL_PNG_DATA_URI = f"data:image/png;base64,{_MINIMAL_PNG_B64}"


def _post_json(url, payload, timeout=5):
    """POST JSON request returning (status, parsed_json)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post_multipart(url, image_bytes, filename="label.png", timeout=5):
    """POST multipart/form-data with an image file field."""
    boundary = "----WebKitFormBoundaryE2ENutrition"
    body = (
        f"------WebKitFormBoundaryE2ENutrition\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + image_bytes + b"\r\n------WebKitFormBoundaryE2ENutrition--\r\n"

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _make_nutrition_result(values=None, provider="Claude Vision", fallback=False, text="{}"):
    """Build a dict matching the real ``dispatch_nutrition_ocr_bytes`` shape."""
    if values is None:
        values = {"kcal": 250.0, "fat": 12.5, "protein": 8.0}
    return {
        "values": values,
        "text": text,
        "provider": provider,
        "fallback": fallback,
    }


@pytest.fixture(autouse=True)
def _clean_ocr_env(app_server):
    """Clear OCR API key env vars before each test so provider list is deterministic."""
    keys = [
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "LLM_API_KEY",
    ]
    saved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@pytest.fixture()
def patch_dispatch():
    """Yield a helper that swaps ``services.ocr_service.dispatch_nutrition_ocr_bytes``
    with a callable while preserving the real symbol for restoration.

    Uses ``create_autospec`` (Rule 8) so the mock shape matches the real
    interface. The live Flask server runs in another thread of the same
    process, so module-level attribute patching is observed by the handler.
    """
    from unittest.mock import create_autospec
    from services import ocr_service

    original = ocr_service.dispatch_nutrition_ocr_bytes

    def _apply(side_effect=None, return_value=None):
        mock = create_autospec(original, spec_set=False)
        if side_effect is not None:
            mock.side_effect = side_effect
        elif return_value is not None:
            mock.return_value = return_value
        else:
            mock.return_value = _make_nutrition_result()
        ocr_service.dispatch_nutrition_ocr_bytes = mock
        return mock

    yield _apply
    ocr_service.dispatch_nutrition_ocr_bytes = original


# ===========================================================================
# Happy path: JSON body with base64 image
# ===========================================================================


class TestOcrNutritionHappyPath:
    """POST /api/ocr/nutrition with a valid image returns extracted values."""

    def test_json_body_returns_values(self, live_url, patch_dispatch):
        """Valid base64 image via JSON body should return 200 with values."""
        mock = patch_dispatch(return_value=_make_nutrition_result(
            values={"kcal": 250.0, "fat": 12.5, "protein": 8.0},
            provider="Claude Vision",
        ))

        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 200
        assert data["values"] == {"kcal": 250.0, "fat": 12.5, "protein": 8.0}
        assert data["count"] == 3
        assert data["provider"] == "Claude Vision"
        assert data["fallback"] is False
        # Verify the dispatcher was actually invoked (no coverage theater)
        assert mock.call_count == 1
        called_with = mock.call_args[0][0]
        assert isinstance(called_with, (bytes, bytearray))

    def test_data_uri_body_returns_values(self, live_url, patch_dispatch):
        """A data: URI in the JSON body should be decoded and dispatched."""
        patch_dispatch(return_value=_make_nutrition_result())
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_DATA_URI},
        )
        assert status == 200
        assert "values" in data
        assert data["count"] == len(data["values"])

    def test_response_shape(self, live_url, patch_dispatch):
        """Response must include values, count, provider, and fallback keys."""
        patch_dispatch(return_value=_make_nutrition_result(
            values={"kcal": 100.0},
            provider="Gemini Vision",
        ))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 200
        assert set(data.keys()) >= {"values", "count", "provider", "fallback"}
        assert isinstance(data["values"], dict)
        assert isinstance(data["count"], int)
        assert isinstance(data["provider"], str)
        assert isinstance(data["fallback"], bool)

    def test_multipart_upload_returns_values(self, live_url, patch_dispatch):
        """POST /api/ocr/nutrition with multipart/form-data image upload."""
        patch_dispatch(return_value=_make_nutrition_result(
            values={"kcal": 180.0, "salt": 0.5},
            provider="Tesseract (Local)",
        ))
        status, data = _post_multipart(
            f"{live_url}/api/ocr/nutrition",
            _MINIMAL_PNG,
        )
        assert status == 200
        assert data["values"] == {"kcal": 180.0, "salt": 0.5}
        assert data["count"] == 2
        assert data["provider"] == "Tesseract (Local)"

    def test_fallback_true_propagates(self, live_url, patch_dispatch):
        """When the dispatcher reports fallback=True, the API surfaces it."""
        patch_dispatch(return_value=_make_nutrition_result(
            values={"kcal": 200.0},
            provider="Tesseract (Local)",
            fallback=True,
        ))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 200
        assert data["fallback"] is True
        assert data["provider"] == "Tesseract (Local)"


# ===========================================================================
# Edge case: empty values dict from provider
# ===========================================================================


class TestOcrNutritionEmptyResult:
    """When the OCR provider returns no values, endpoint surfaces no_values."""

    def test_empty_values_returns_no_values_error(self, live_url, patch_dispatch):
        patch_dispatch(return_value=_make_nutrition_result(
            values={},
            provider="Gemini Vision",
        ))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 200
        assert data["values"] == {}
        assert data["count"] == 0
        assert data["error_type"] == "no_values"
        assert "error" in data
        assert data["provider"] == "Gemini Vision"


# ===========================================================================
# Validation errors: bad / missing input — handler short-circuits before dispatch
# ===========================================================================


class TestOcrNutritionValidationErrors:
    """POST /api/ocr/nutrition with invalid input returns 400 with error_type."""

    def test_missing_image_field_returns_400(self, live_url):
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition", {}
        )
        assert status == 400
        assert "error" in data
        # Validation rejections use _error_response without explicit error_type,
        # which defaults to "generic" for non-token-limit messages.
        assert data["error_type"] == "generic"

    def test_empty_image_string_returns_400(self, live_url):
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": ""},
        )
        assert status == 400
        assert "error" in data
        assert data["error_type"] == "generic"

    def test_invalid_data_uri_returns_400(self, live_url):
        """A malformed data: URI must be rejected with 400 before any dispatch."""
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": "data:garbage,not-base64"},
        )
        assert status == 400
        assert "error" in data
        # Error message contains an explanatory string for the frontend toast.
        assert data["error"]

    def test_invalid_base64_returns_400(self, live_url):
        """Non-base64 characters in the image field must be rejected with 400.

        Note: ``base64.b64decode`` is lenient by default and accepts many
        odd strings without raising, so we send a literal that cannot be
        decoded (binary bytes that can't be base64) wrapped as a string.
        The handler protects against decoded-empty / decode-error paths.
        """
        # Use raw control-character noise that base64 rejects (validate=True
        # is not used by the handler, so we rely on either decode failure or
        # empty result). Either path produces a 400 with an error key.
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": "!@#$%^&*()"},  # decodes to b'' in lenient mode
        )
        assert status == 400
        assert "error" in data

    def test_non_string_image_returns_400(self, live_url):
        """Numeric / null image values must be rejected with 400."""
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": 12345},
        )
        assert status == 400
        assert "error" in data
        assert data["error_type"] == "generic"


# ===========================================================================
# Provider exception mapping — exercises blueprints.ocr._handle_ocr_exception
# ===========================================================================


class TestOcrNutritionProviderErrors:
    """Provider exceptions should map to structured error responses."""

    def test_value_error_returns_400(self, live_url, patch_dispatch):
        patch_dispatch(side_effect=ValueError("Bad image data"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 400
        assert "error" in data
        # Generic ValueError without token-limit keywords -> default "generic"
        assert data["error_type"] == "generic"

    def test_token_limit_value_error_returns_400_with_token_type(
        self, live_url, patch_dispatch
    ):
        """ValueError whose message mentions a token/quota limit must be
        surfaced with error_type ``token_limit_exceeded`` (frontend toast)."""
        patch_dispatch(side_effect=ValueError("Token limit exceeded for vision call"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 400
        assert data["error_type"] == "token_limit_exceeded"
        assert "Token limit" in data["error"]

    def test_timeout_returns_503(self, live_url, patch_dispatch):
        patch_dispatch(side_effect=TimeoutError("Provider timed out"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 503
        assert data["error_type"] == "provider_timeout"

    def test_connection_error_returns_503(self, live_url, patch_dispatch):
        patch_dispatch(side_effect=ConnectionError("Connection refused"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 503
        assert data["error_type"] == "provider_timeout"

    def test_unidentified_image_returns_400(self, live_url, patch_dispatch):
        from PIL import UnidentifiedImageError

        patch_dispatch(side_effect=UnidentifiedImageError("cannot identify image"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 400
        assert data["error_type"] == "invalid_image"

    def test_quota_error_by_status_code_returns_429(self, live_url, patch_dispatch):
        """Exceptions exposing ``status_code == 429`` map to provider_quota."""
        class QuotaError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        patch_dispatch(side_effect=QuotaError("too many requests", 429))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 429
        assert data["error_type"] == "provider_quota"

    def test_quota_error_by_message_returns_429(self, live_url, patch_dispatch):
        """Exceptions whose message matches quota keywords map to provider_quota."""
        patch_dispatch(side_effect=Exception("quota exceeded for this month"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 429
        assert data["error_type"] == "provider_quota"

    def test_provider_4xx_error_returns_same_status(self, live_url, patch_dispatch):
        """Non-quota 4xx provider errors propagate the upstream status code."""
        class ProviderError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        patch_dispatch(side_effect=ProviderError("image too large", 413))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 413
        assert data["error_type"] == "provider_error"
        assert "image too large" in data["error"]

    def test_generic_exception_returns_500(self, live_url, patch_dispatch):
        patch_dispatch(side_effect=RuntimeError("Unexpected failure"))
        status, data = _post_json(
            f"{live_url}/api/ocr/nutrition",
            {"image": _MINIMAL_PNG_B64},
        )
        assert status == 500
        assert "error" in data
        assert data["error_type"] == "generic"


# ===========================================================================
# Multipart edge case: empty upload
# ===========================================================================


class TestOcrNutritionMultipartEdgeCases:
    """Multipart-specific failure modes."""

    def test_multipart_empty_image_returns_400(self, live_url):
        """A multipart upload with an empty image field must 400."""
        status, data = _post_multipart(
            f"{live_url}/api/ocr/nutrition",
            b"",
        )
        assert status == 400
        assert "error" in data
        assert data["error_type"] == "generic"
