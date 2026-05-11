"""Tests for OCR blueprint enhanced response fields (LSO-231).

Covers:
- Success responses include `provider` and `fallback` fields
- Error responses include `error_type` and `error_detail` fields
- Backwards compatibility (text/error fields unchanged)
- Dynamic provider name from dispatch_ocr result
"""

from unittest.mock import patch

import pytest


@pytest.fixture()
def client(app):
    """Flask test client with CSRF header for OCR tests."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


def _ocr_result(text="Sukker, mel, vann", provider="Tesseract (Local)", fallback=False):
    """Helper to build a dispatch_ocr return value."""
    return {"text": text, "provider": provider, "fallback": fallback}


class TestOcrSuccessResponse:
    """Success responses must include provider and fallback fields."""

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_success_includes_provider(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["provider"] == "Tesseract (Local)"

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_success_includes_fallback_false(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["fallback"] is False

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_success_still_has_text(self, mock_dispatch, client):
        """Backwards compat: text field is still present."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

    @patch(
        "services.ocr_service.dispatch_ocr",
        return_value=_ocr_result(text="", provider="Claude Vision", fallback=False),
    )
    def test_empty_text_includes_provider_and_fallback(self, mock_dispatch, client):
        """Even empty-text responses get provider/fallback."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["text"] == ""
        assert data["provider"] == "Claude Vision"
        assert data["fallback"] is False

    @patch(
        "services.ocr_service.dispatch_ocr",
        return_value=_ocr_result(provider="GPT-4 Vision", fallback=True),
    )
    def test_fallback_true_when_backend_unavailable(self, mock_dispatch, client):
        """Provider shows actual used backend and fallback=true."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["provider"] == "GPT-4 Vision"
        assert data["fallback"] is True


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
        "services.ocr_service.dispatch_ocr",
        side_effect=ValueError("Invalid base64 data"),
    )
    def test_value_error_has_structured_error(self, mock_dispatch, client):
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
        "services.ocr_service.dispatch_ocr",
        side_effect=Exception("something broke"),
    )
    def test_internal_error_has_structured_error(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error"] == "OCR processing failed"
        assert data["error_type"] == "generic"
        assert "OCR processing failed" in data["error_detail"]

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ValueError("Token limit exceeded"),
    )
    def test_token_limit_error_type(self, mock_dispatch, client):
        """Token-limit errors should use error_type=token_limit_exceeded."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"
        assert "Token limit" in data["error_detail"]


class TestClientError4xxMapping:
    """ClientError with 4xx status_code should map to provider_error (LSO-383)."""

    def test_client_error_400_returns_provider_error(self, client):
        """ClientError with status_code=400 → HTTP 400, error_type=provider_error."""

        class ClientError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ClientError("Bad Request", 400),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": "data:image/png;base64,iVBORw0KGgo="},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error_type"] == "provider_error"
            assert "Bad Request" in data["error"]

    def test_client_error_422_returns_provider_error(self, client):
        """ClientError with status_code=422 → HTTP 422, error_type=provider_error."""

        class ClientError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ClientError("Unprocessable Entity", 422),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": "data:image/png;base64,iVBORw0KGgo="},
            )
            assert resp.status_code == 422
            data = resp.get_json()
            assert data["error_type"] == "provider_error"

    def test_server_error_5xx_still_generic(self, client):
        """Exception with status_code=500 should NOT map to provider_error."""

        class ServerError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ServerError("Internal Server Error", 500),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": "data:image/png;base64,iVBORw0KGgo="},
            )
            assert resp.status_code == 500
            data = resp.get_json()
            assert data["error_type"] == "generic"


class TestOcrClientErrorClassification:
    """4xx errors via code attribute (google.genai) must map to provider_error."""

    @patch("services.ocr_service.dispatch_ocr")
    def test_google_genai_code_400_returns_provider_error(self, mock_dispatch, client):
        """google.genai ClientError with code=400 → HTTP 400, error_type=provider_error."""
        err = Exception("Invalid image format")
        err.code = 400
        mock_dispatch.side_effect = err
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "provider_error"

    @patch("services.ocr_service.dispatch_ocr")
    def test_no_status_attribute_still_returns_500_generic(self, mock_dispatch, client):
        """Exceptions without status_code or code still return 500 generic."""
        mock_dispatch.side_effect = Exception("unknown error")
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error_type"] == "generic"


class TestOcrBackwardsCompat:
    """Existing fields must not change shape or status codes."""

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_success_status_200(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200

    def test_no_image_status_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400


class TestProviderError4xxMapping:
    """LSO-383: 4xx provider exceptions must produce error_type=provider_error with actual message."""

    def test_4xx_json_path_returns_provider_error(self, client):
        """JSON path: 4xx exception → error_type=provider_error, actual error message."""

        class ProviderError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=ProviderError("image too large", 413),
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": "data:image/png;base64,iVBORw0KGgo="},
            )
            assert resp.status_code == 413
            data = resp.get_json()
            assert data["error_type"] == "provider_error"
            assert "image too large" in data["error"]
            assert data["error"] != "Invalid or corrupt image"

    def test_4xx_multipart_path_returns_provider_error(self, client):
        """Multipart path: 4xx exception → error_type=provider_error, actual error message."""
        import io

        class ProviderError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_ocr_bytes",
            side_effect=ProviderError("bad image data", 400),
        ):
            data = io.BytesIO(b"\x89PNG\r\n")
            resp = client.post(
                "/api/ocr/ingredients",
                data={"image": (data, "test.png")},
                content_type="multipart/form-data",
            )
            assert resp.status_code == 400
            result = resp.get_json()
            assert result["error_type"] == "provider_error"
            assert "bad image data" in result["error"]
            assert result["error"] != "Invalid or corrupt image"
