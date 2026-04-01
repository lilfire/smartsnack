"""Tests for OCR API response structure — toast notification contract.

These tests validate the expected response structure for the OCR toast
notification system as specified in LSO-228 / LSO-264. The API should return:
- Success: {"text": "...", "provider": "Tesseract"}
- Error (invalid image): {"error": "...", "error_type": "invalid_image"}
- Error (provider timeout): {"error": "...", "error_type": "provider_timeout"}
- Error (no text): {"error_type": "no_text"} on empty OCR result
- Error (token limit): {"error": "...", "error_type": "token_limit_exceeded"}
- Error (generic): {"error": "...", "error_type": "generic", "error_detail": "..."}
- Backwards compat: "text" and "error" fields always present where expected
"""

import json
from unittest.mock import patch

import pytest
from PIL import UnidentifiedImageError

_VALID_IMAGE = "data:image/png;base64,iVBORw0KGgo="
_DISPATCH = "services.ocr_service.dispatch_ocr"


def _post_ocr(client, image=_VALID_IMAGE):
    return client.post(
        "/api/ocr/ingredients",
        data=json.dumps({"image": image}),
        content_type="application/json",
    )


class TestOcrSuccessResponse:
    """Test that successful OCR responses include provider info."""

    def test_success_returns_text(self, client):
        """Baseline: successful OCR returns text field."""
        with patch(_DISPATCH, return_value={"text": "sukker, mel", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["text"] == "sukker, mel"

    def test_success_includes_provider_field(self, client):
        """Success response must include provider field."""
        with patch(_DISPATCH, return_value={"text": "sukker, mel", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert "provider" in data, "Success response must include 'provider' field"
        assert data["provider"] == "Tesseract"

    def test_no_text_still_has_text_field(self, client):
        """When OCR finds no text, response still has 'text' field (empty string)."""
        with patch(_DISPATCH, return_value={"text": "", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert "text" in data
        assert data["text"] == ""


class TestOcrErrorClassification:
    """Test that each OCR failure mode produces a distinct error_type (LSO-264)."""

    def test_invalid_image_error_type(self, client):
        """PIL UnidentifiedImageError returns error_type='invalid_image'."""
        with patch(_DISPATCH, side_effect=UnidentifiedImageError("cannot identify image file")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["error_type"] == "invalid_image"
        assert "error" in data

    def test_corrupt_image_error_type(self, client):
        """OSError from corrupt image data returns error_type='invalid_image'."""
        with patch(_DISPATCH, side_effect=OSError("image file is truncated")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["error_type"] == "invalid_image"

    def test_timeout_error_type(self, client):
        """TimeoutError returns error_type='provider_timeout'."""
        with patch(_DISPATCH, side_effect=TimeoutError("Connection timed out")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 503
        assert data["error_type"] == "provider_timeout"
        assert "error" in data

    def test_connection_error_type(self, client):
        """ConnectionError returns error_type='provider_timeout'."""
        with patch(_DISPATCH, side_effect=ConnectionError("Failed to connect")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 503
        assert data["error_type"] == "provider_timeout"

    def test_no_text_includes_error_type(self, client):
        """When OCR returns no text, response includes error_type='no_text'."""
        with patch(_DISPATCH, return_value={"text": "", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["error_type"] == "no_text"

    def test_generic_error_includes_class_name(self, client):
        """Unexpected exceptions return error_type='generic' with class name in error_detail."""
        with patch(_DISPATCH, side_effect=RuntimeError("something broke")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 500
        assert data["error_type"] == "generic"
        assert "RuntimeError" in data["error_detail"]

    def test_generic_error_does_not_expose_traceback(self, client):
        """Generic error messages must not contain raw tracebacks."""
        with patch(_DISPATCH, side_effect=RuntimeError("internal details here")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert "Traceback" not in data.get("error", "")
        assert "internal details here" not in data.get("error", "")


class TestOcrErrorResponse:
    """Test that error responses include structured error fields."""

    def test_value_error_returns_error_field(self, client):
        """ValueError from service returns error field (backwards compat)."""
        with patch(_DISPATCH, side_effect=ValueError("Invalid base64 data")):
            resp = _post_ocr(client, image="bad-data")
        data = resp.get_json()
        assert resp.status_code == 400
        assert "error" in data

    def test_generic_error_includes_error_type(self, client):
        """Generic errors must include error_type='generic' and error_detail."""
        with patch(_DISPATCH, side_effect=RuntimeError("network timeout")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 500
        assert "error" in data, "Error response must include 'error' field"
        assert "error_type" in data, "Error response must include 'error_type' field"
        assert data["error_type"] == "generic"
        assert "error_detail" in data, "Generic error must include 'error_detail'"

    def test_token_limit_error_type(self, client):
        """Token limit exceeded must return error_type='token_limit_exceeded'."""
        with patch(_DISPATCH, side_effect=ValueError("token_limit_exceeded")):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert "error" in data
        assert "error_type" in data, "Token limit error must include 'error_type'"
        assert data["error_type"] == "token_limit_exceeded"


class TestOcrBackwardsCompat:
    """Backwards compatibility: existing text/error fields still present."""

    def test_success_has_text_field(self, client):
        """Success response always includes 'text' field."""
        with patch(_DISPATCH, return_value={"text": "mel", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert "text" in data

    def test_no_text_has_error_field(self, client):
        """When no text found, response includes both 'text' and 'error' fields."""
        with patch(_DISPATCH, return_value={"text": "", "provider": "Tesseract", "fallback": False}):
            resp = _post_ocr(client)
        data = resp.get_json()
        assert resp.status_code == 200
        assert "text" in data
        assert "error" in data

    def test_missing_image_returns_error(self, client):
        """Missing image returns 400 with error field."""
        resp = _post_ocr(client, image="")
        data = resp.get_json()
        assert resp.status_code == 400
        assert "error" in data

    def test_no_json_body_returns_error(self, client):
        """Missing JSON body returns 400 with error field."""
        resp = client.post(
            "/api/ocr/ingredients",
            data="not json",
            content_type="text/plain",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert "error" in data
