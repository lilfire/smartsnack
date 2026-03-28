"""Tests for OCR blueprint enhanced response fields (LSO-231).

Covers:
- Success responses include `provider` and `fallback` fields
- Error responses include `error_type` and `error_detail` fields
- Backwards compatibility (text/error fields unchanged)
"""

from unittest.mock import patch

import pytest


@pytest.fixture()
def client(app):
    """Flask test client with CSRF header for OCR tests."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


class TestOcrSuccessResponse:
    """Success responses must include provider and fallback fields."""

    @patch("services.ocr_service.extract_text", return_value="Sukker, mel, vann")
    def test_success_includes_provider(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["provider"] == "EasyOCR"

    @patch("services.ocr_service.extract_text", return_value="Sukker, mel, vann")
    def test_success_includes_fallback_false(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["fallback"] is False

    @patch("services.ocr_service.extract_text", return_value="Sukker, mel, vann")
    def test_success_still_has_text(self, mock_extract, client):
        """Backwards compat: text field is still present."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

    @patch("services.ocr_service.extract_text", return_value="")
    def test_empty_text_includes_provider_and_fallback(self, mock_extract, client):
        """Even empty-text responses get provider/fallback."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["text"] == ""
        assert data["provider"] == "EasyOCR"
        assert data["fallback"] is False


class TestOcrErrorResponse:
    """Error responses must include error_type and error_detail fields."""

    def test_missing_image_error_fields(self, client):
        resp = client.post("/api/ocr/ingredients", json={"image": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "No image provided"
        assert data["error_type"] == "generic"
        assert "error_detail" in data

    def test_missing_json_body_error_fields(self, client):
        resp = client.post(
            "/api/ocr/ingredients",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error_type"] == "generic"
        assert "error_detail" in data

    @patch(
        "services.ocr_service.extract_text",
        side_effect=ValueError("Invalid base64 data"),
    )
    def test_value_error_has_structured_error(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "bad-data"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid base64 data"
        assert data["error_type"] == "generic"
        assert data["error_detail"] == "Invalid base64 data"

    @patch(
        "services.ocr_service.extract_text",
        side_effect=Exception("something broke"),
    )
    def test_internal_error_has_structured_error(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error"] == "OCR processing failed"
        assert data["error_type"] == "generic"
        assert data["error_detail"] == "OCR processing failed"

    @patch(
        "services.ocr_service.extract_text",
        side_effect=ValueError("Token limit exceeded"),
    )
    def test_token_limit_error_type(self, mock_extract, client):
        """Token-limit errors should use error_type=token_limit_exceeded."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"
        assert "Token limit" in data["error_detail"]


class TestOcrBackwardsCompat:
    """Existing fields must not change shape or status codes."""

    @patch("services.ocr_service.extract_text", return_value="Sukker")
    def test_success_status_200(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200

    def test_no_image_status_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
