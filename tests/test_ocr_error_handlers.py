"""Tests for specific OCR error handlers (LSO-258).

Covers:
- Invalid/corrupt image → error_type: "invalid_image", HTTP 400
- OCR provider timeout/network error → error_type: "provider_timeout", HTTP 503
- No text found → error_type: "no_text" in response
- Generic catch-all → error_type: "generic" with exception class name
- Translation keys exist for new error types
"""

import json
import os
from unittest.mock import patch

import pytest
from PIL import UnidentifiedImageError


@pytest.fixture()
def client(app):
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


VALID_IMAGE_PAYLOAD = {"image": "data:image/png;base64,iVBORw0KGgo="}


class TestInvalidImageError:
    """Invalid/corrupt image should return error_type=invalid_image, HTTP 400."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=UnidentifiedImageError("cannot identify image file"),
    )
    def test_invalid_image_returns_400(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 400

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=UnidentifiedImageError("cannot identify image file"),
    )
    def test_invalid_image_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert data["error_type"] == "invalid_image"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=UnidentifiedImageError("cannot identify image file"),
    )
    def test_invalid_image_has_error_detail(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert "error" in data
        assert "error_detail" in data

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=OSError("truncated image"),
    )
    def test_os_error_from_image_returns_invalid_image(self, mock_dispatch, client):
        """OSError from PIL (corrupt image) should also map to invalid_image."""
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "invalid_image"


class TestProviderTimeoutError:
    """OCR provider timeout/network errors should return error_type=provider_timeout, HTTP 503."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=TimeoutError("Connection timed out"),
    )
    def test_timeout_error_returns_503(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 503

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=TimeoutError("Connection timed out"),
    )
    def test_timeout_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert data["error_type"] == "provider_timeout"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ConnectionError("Connection refused"),
    )
    def test_connection_error_returns_503(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 503

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ConnectionError("Connection refused"),
    )
    def test_connection_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert data["error_type"] == "provider_timeout"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=TimeoutError("timed out"),
    )
    def test_timeout_has_error_detail(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert "error" in data
        assert "error_detail" in data


class TestSdkTimeoutDetection:
    """SDK-specific timeout/connection errors (class name heuristic)."""

    def test_sdk_timeout_class_detected(self, client):
        """Exceptions with 'Timeout' in class name should map to provider_timeout."""

        class APITimeoutError(Exception):
            pass

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=APITimeoutError("request timed out"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            assert resp.status_code == 503
            data = resp.get_json()
            assert data["error_type"] == "provider_timeout"

    def test_sdk_connection_class_detected(self, client):
        """Exceptions with 'Connection' in class name should map to provider_timeout."""

        class APIConnectionError(Exception):
            pass

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=APIConnectionError("connection failed"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            assert resp.status_code == 503
            data = resp.get_json()
            assert data["error_type"] == "provider_timeout"


class TestNoTextResponse:
    """Empty OCR result should include error_type=no_text."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        return_value={"text": "", "provider": "Tesseract (Local)", "fallback": False},
    )
    def test_no_text_has_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["error_type"] == "no_text"


class TestGenericCatchAll:
    """Unexpected exceptions should return error_type=generic with class name."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=RuntimeError("something unexpected"),
    )
    def test_generic_error_returns_500(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 500

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=RuntimeError("something unexpected"),
    )
    def test_generic_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert data["error_type"] == "generic"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=RuntimeError("something unexpected"),
    )
    def test_generic_error_includes_class_name(self, mock_dispatch, client):
        """error_detail should include the exception class name."""
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert "RuntimeError" in data["error_detail"]

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=RuntimeError("something unexpected"),
    )
    def test_generic_error_no_stack_trace(self, mock_dispatch, client):
        """Should not expose raw stack traces."""
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        data = resp.get_json()
        assert "Traceback" not in data.get("error", "")
        assert "Traceback" not in data.get("error_detail", "")


class TestExistingErrorsUnchanged:
    """Token limit and ValueError handlers must still work as before."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ValueError("Token limit exceeded"),
    )
    def test_token_limit_still_works(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ValueError("Invalid base64 data"),
    )
    def test_value_error_still_works(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "generic"

    def test_missing_image_still_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={"image": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "generic"


class TestTranslationKeys:
    """New error types must have translation keys in all language files."""

    @pytest.fixture()
    def translations_data(self):
        """Load all translation files."""
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "translations",
        )
        data = {}
        for lang in ("no", "en", "se"):
            path = os.path.join(base, f"{lang}.json")
            with open(path) as f:
                data[lang] = json.load(f)
        return data

    def test_norwegian_has_invalid_image_key(self, translations_data):
        assert "toast_ocr_invalid_image" in translations_data["no"]

    def test_norwegian_has_provider_timeout_key(self, translations_data):
        assert "toast_ocr_provider_timeout" in translations_data["no"]

    def test_english_has_invalid_image_key(self, translations_data):
        assert "toast_ocr_invalid_image" in translations_data["en"]

    def test_english_has_provider_timeout_key(self, translations_data):
        assert "toast_ocr_provider_timeout" in translations_data["en"]

    def test_swedish_has_invalid_image_key(self, translations_data):
        assert "toast_ocr_invalid_image" in translations_data["se"]

    def test_swedish_has_provider_timeout_key(self, translations_data):
        assert "toast_ocr_provider_timeout" in translations_data["se"]

    def test_norwegian_has_provider_quota_key(self, translations_data):
        assert "toast_ocr_provider_quota" in translations_data["no"]

    def test_english_has_provider_quota_key(self, translations_data):
        assert "toast_ocr_provider_quota" in translations_data["en"]

    def test_swedish_has_provider_quota_key(self, translations_data):
        assert "toast_ocr_provider_quota" in translations_data["se"]


class TestProviderQuotaError:
    """429 / RESOURCE_EXHAUSTED errors should return error_type=provider_quota."""

    def test_http_429_returns_provider_quota(self, client):
        """Exception with status_code=429 should map to provider_quota."""

        class APIRateLimitError(Exception):
            status_code = 429

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=APIRateLimitError("Too Many Requests"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            assert resp.status_code == 429
            data = resp.get_json()
            assert data["error_type"] == "provider_quota"

    def test_resource_exhausted_message_returns_provider_quota(self, client):
        """Exception message containing 'RESOURCE_EXHAUSTED' maps to provider_quota."""
        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            assert resp.status_code == 429
            data = resp.get_json()
            assert data["error_type"] == "provider_quota"

    def test_rate_limit_message_returns_provider_quota(self, client):
        """Exception message containing 'rate limit' maps to provider_quota."""
        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=RuntimeError("rate limit exceeded"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            assert resp.status_code == 429
            data = resp.get_json()
            assert data["error_type"] == "provider_quota"

    def test_quota_error_has_error_detail(self, client):
        """provider_quota response should include error_detail."""

        class APIRateLimitError(Exception):
            status_code = 429

        with patch(
            "services.ocr_service.dispatch_ocr",
            side_effect=APIRateLimitError("Too Many Requests"),
        ):
            resp = client.post("/api/ocr/ingredients", json=VALID_IMAGE_PAYLOAD)
            data = resp.get_json()
            assert "error_detail" in data
