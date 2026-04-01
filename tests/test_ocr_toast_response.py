"""Tests for OCR API response structure — toast notification contract.

These tests validate the expected response structure for the OCR toast
notification system as specified in LSO-228. The API should return:
- Success: {"text": "...", "provider": "EasyOCR"}
- Error (token limit): {"error": "...", "error_type": "token_limit_exceeded"}
- Error (generic): {"error": "...", "error_type": "generic", "error_detail": "..."}
- Backwards compat: "text" and "error" fields always present where expected
"""

import json
from unittest.mock import patch

import pytest


class TestOcrSuccessResponse:
    """Test that successful OCR responses include provider info."""

    def test_success_returns_text(self, client):
        """Baseline: successful OCR returns text field."""
        with patch("services.ocr_service.dispatch_ocr", return_value={"text": "sukker, mel", "provider": "EasyOCR", "fallback": False}):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["text"] == "sukker, mel"

    def test_success_includes_provider_field(self, client):
        """Success response must include provider field (value: 'EasyOCR')."""
        with patch("services.ocr_service.dispatch_ocr", return_value={"text": "sukker, mel", "provider": "EasyOCR", "fallback": False}):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "provider" in data, "Success response must include 'provider' field"
        assert data["provider"] == "EasyOCR"

    def test_no_text_still_has_text_field(self, client):
        """When OCR finds no text, response still has 'text' field (empty string)."""
        with patch("services.ocr_service.dispatch_ocr", return_value={"text": "", "provider": "EasyOCR", "fallback": False}):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "text" in data
        assert data["text"] == ""


class TestOcrErrorResponse:
    """Test that error responses include structured error fields."""

    def test_value_error_returns_error_field(self, client):
        """ValueError from service returns error field (backwards compat)."""
        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ValueError("Invalid base64 data"),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "bad-data"}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 400
        assert "error" in data

    def test_generic_error_includes_error_type(self, client):
        """Generic errors must include error_type='generic' and error_detail."""
        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=RuntimeError("network timeout"),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 500
        assert "error" in data, "Error response must include 'error' field"
        assert "error_type" in data, "Error response must include 'error_type' field"
        assert data["error_type"] == "generic"
        assert "error_detail" in data, "Generic error must include 'error_detail'"

    def test_token_limit_error_type(self, client):
        """Token limit exceeded must return error_type='token_limit_exceeded'."""
        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ValueError("token_limit_exceeded"),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert "error" in data
        assert "error_type" in data, "Token limit error must include 'error_type'"
        assert data["error_type"] == "token_limit_exceeded"


class TestOcrBackwardsCompat:
    """Backwards compatibility: existing text/error fields still present."""

    def test_success_has_text_field(self, client):
        """Success response always includes 'text' field."""
        with patch("services.ocr_service.dispatch_ocr", return_value={"text": "mel", "provider": "EasyOCR", "fallback": False}):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert "text" in data

    def test_no_text_has_error_field(self, client):
        """When no text found, response includes both 'text' and 'error' fields."""
        with patch("services.ocr_service.dispatch_ocr", return_value={"text": "", "provider": "EasyOCR", "fallback": False}):
            resp = client.post(
                "/api/ocr/ingredients",
                data=json.dumps({"image": "data:image/png;base64,iVBORw0KGgo="}),
                content_type="application/json",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "text" in data
        assert "error" in data

    def test_missing_image_returns_error(self, client):
        """Missing image returns 400 with error field."""
        resp = client.post(
            "/api/ocr/ingredients",
            data=json.dumps({"image": ""}),
            content_type="application/json",
        )
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
