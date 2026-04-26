"""Regression tests for OCR MIME type propagation and error_type fixes (LSO-354).

Bug 1 — MIME Type: Vision backends must use the MIME type from the data URI,
         not hardcode image/png.  JPEG, PNG, and WebP data URIs must pass
         through with the correct MIME type to Claude, Gemini, and OpenAI.
         Tesseract must continue to work regardless of MIME type.

Bug 2 — error_type: The backend must return error_type="token_limit_exceeded"
         (not "token_limit") for token-limit errors, and "generic" for other
         failures.
"""

import base64
import io
import os
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(fmt):
    """Create a minimal valid image in the given format and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (80, 40), color="white")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _b64(raw_bytes):
    return base64.b64encode(raw_bytes).decode()


def _data_uri(raw_bytes, mime):
    return f"data:{mime};base64,{_b64(raw_bytes)}"


# ---------------------------------------------------------------------------
# Bug 1 — WebP MIME type propagation (new; JPEG/PNG already tested elsewhere)
# ---------------------------------------------------------------------------

class TestWebpMimeTypePropagation:
    """WebP data URIs must propagate image/webp to all vision backends."""

    def test_webp_data_uri_passes_correct_mime_to_gemini(self):
        """Gemini should receive image/webp when the data URI declares WebP."""
        mock_response = types.SimpleNamespace(text="sukker")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        webp_bytes = _make_image("WEBP")
        webp_uri = _data_uri(webp_bytes, "image/webp")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                with patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(webp_uri)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        inline_data = contents[0]["parts"][0]["inline_data"]
        assert inline_data["mime_type"] == "image/webp"

    def test_webp_data_uri_passes_correct_mime_to_openai(self):
        """OpenAI data URI should contain image/webp when input is WebP."""
        mock_choice = types.SimpleNamespace(message=types.SimpleNamespace(content="ingredienser"))
        mock_response = types.SimpleNamespace(choices=[mock_choice])

        webp_bytes = _make_image("WEBP")
        webp_uri = _data_uri(webp_bytes, "image/webp")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI", autospec=True) as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                with patch("services.settings_service.get_ocr_backend", return_value="openai", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(webp_uri)

                call_args = mock_cls.return_value.chat.completions.create.call_args

        messages = call_args[1]["messages"]
        image_url = messages[0]["content"][0]["image_url"]["url"]
        assert image_url.startswith("data:image/webp;base64,")

    def test_webp_data_uri_passes_correct_media_type_to_claude(self):
        """Claude Vision should receive media_type=image/webp when input is WebP."""
        mock_content_item = types.SimpleNamespace(text="sukker")
        mock_msg = types.SimpleNamespace(content=[mock_content_item])

        webp_bytes = _make_image("WEBP")
        webp_uri = _data_uri(webp_bytes, "image/webp")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic", autospec=True) as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(webp_uri)

                call_args = mock_cls.return_value.messages.create.call_args

        messages = call_args[1]["messages"]
        source = messages[0]["content"][0]["source"]
        assert source["media_type"] == "image/webp"


# ---------------------------------------------------------------------------
# Bug 1 — Tesseract ignores MIME type and works for any valid image
# ---------------------------------------------------------------------------

class TestTesseractMimeTypeAgnostic:
    """Tesseract backend should process images regardless of declared MIME type."""

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_jpeg_data_uri_works_with_tesseract(self, mock_output, mock_itd):
        """Tesseract should process a JPEG data URI without error."""
        mock_itd.return_value = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["ingredienser"], "conf": [90],
        }

        jpeg_bytes = _make_image("JPEG")
        jpeg_uri = _data_uri(jpeg_bytes, "image/jpeg")

        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True):
            from services.ocr_service import dispatch_ocr
            result = dispatch_ocr(jpeg_uri)

        assert "ingredienser" in result["text"]
        assert result["fallback"] is False

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_png_data_uri_works_with_tesseract(self, mock_output, mock_itd):
        """Tesseract should process a PNG data URI without error."""
        mock_itd.return_value = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["sukker"], "conf": [85],
        }

        png_bytes = _make_image("PNG")
        png_uri = _data_uri(png_bytes, "image/png")

        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True):
            from services.ocr_service import dispatch_ocr
            result = dispatch_ocr(png_uri)

        assert "sukker" in result["text"]

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_webp_data_uri_works_with_tesseract(self, mock_output, mock_itd):
        """Tesseract should process a WebP data URI without error."""
        mock_itd.return_value = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["mel"], "conf": [80],
        }

        webp_bytes = _make_image("WEBP")
        webp_uri = _data_uri(webp_bytes, "image/webp")

        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True):
            from services.ocr_service import dispatch_ocr
            result = dispatch_ocr(webp_uri)

        assert "mel" in result["text"]


# ---------------------------------------------------------------------------
# Bug 2 — error_type alignment: backend returns "token_limit_exceeded"
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(app):
    """Flask test client with CSRF header for OCR tests."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


class TestErrorTypeTokenLimitExceeded:
    """Backend must return error_type='token_limit_exceeded', never 'token_limit'."""

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("Token limit exceeded"), autospec=True)
    def test_token_limit_error_returns_token_limit_exceeded(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("token_limit reached"), autospec=True)
    def test_token_limit_keyword_variant(self, mock_dispatch, client):
        """Alternative phrasing containing 'token_limit' still maps correctly."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("usage budget exceeded"), autospec=True)
    def test_usage_budget_keyword(self, mock_dispatch, client):
        """'usage budget' errors also map to token_limit_exceeded."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("quota exceeded"), autospec=True)
    def test_quota_exceeded_keyword(self, mock_dispatch, client):
        """'quota exceeded' errors also map to token_limit_exceeded."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"


class TestErrorTypeGenericFallback:
    """Non-token-limit errors must return error_type='generic'."""

    @patch("services.ocr_service.dispatch_ocr", side_effect=Exception("something broke"), autospec=True)
    def test_unexpected_error_returns_generic(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error_type"] == "generic"

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("Invalid base64 data"), autospec=True)
    def test_value_error_without_token_keyword_returns_generic(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "bad-data"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "generic"


# ---------------------------------------------------------------------------
# Bug 2 — error_type via multipart path matches JSON path
# ---------------------------------------------------------------------------

class TestErrorTypeMultipartPath:
    """Multipart upload path should return the same error_type values."""

    @patch(
        "services.ocr_service.dispatch_ocr_bytes",
        side_effect=ValueError("Token limit exceeded"),
        autospec=True)
    def test_multipart_token_limit_returns_correct_error_type(self, mock_dispatch, client):
        png = _make_image("PNG")
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch(
        "services.ocr_service.dispatch_ocr_bytes",
        side_effect=Exception("OCR crashed"),
        autospec=True)
    def test_multipart_generic_error_returns_generic_type(self, mock_dispatch, client):
        png = _make_image("PNG")
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["error_type"] == "generic"
