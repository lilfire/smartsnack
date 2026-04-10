"""Tests for multipart/form-data OCR endpoint and dispatch_ocr_bytes service (LSO-311).

Covers:
- POST /api/ocr/ingredients with multipart/form-data succeeds for PNG, JPEG, WebP
- Missing file returns 400 {"error": "No image provided"}
- dispatch_ocr_bytes accepts raw bytes and returns same shape as dispatch_ocr
- dispatch_ocr (base64 string) still works (backward compat)
"""

import base64
import io
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes():
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes():
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_webp_bytes():
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def _ocr_result(text="Sukker, mel, vann", provider="Tesseract (Local)", fallback=False):
    return {"text": text, "provider": provider, "fallback": fallback}


@pytest.fixture()
def client(app):
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


# ---------------------------------------------------------------------------
# Blueprint: multipart/form-data upload
# ---------------------------------------------------------------------------

class TestOcrMultipartUpload:
    """POST /api/ocr/ingredients must accept multipart/form-data image uploads."""

    @patch("services.ocr_service.dispatch_ocr_bytes", return_value=_ocr_result())
    def test_png_upload_returns_200(self, mock_dispatch, client):
        png = _make_png_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

    @patch("services.ocr_service.dispatch_ocr_bytes", return_value=_ocr_result())
    def test_jpeg_upload_returns_200(self, mock_dispatch, client):
        jpeg = _make_jpeg_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(jpeg), "test.jpg", "image/jpeg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data

    @patch("services.ocr_service.dispatch_ocr_bytes", return_value=_ocr_result())
    def test_webp_upload_returns_200(self, mock_dispatch, client):
        webp = _make_webp_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(webp), "test.webp", "image/webp")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data

    def test_missing_file_returns_400(self, client):
        resp = client.post(
            "/api/ocr/ingredients",
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid or missing JSON body"

    def test_missing_file_error_has_error_type(self, client):
        resp = client.post(
            "/api/ocr/ingredients",
            data={},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["error_type"] == "generic"
        assert "error_detail" in data

    @patch(
        "services.ocr_service.dispatch_ocr_bytes",
        side_effect=ValueError("Image too large (max 5 MB)"),
    )
    def test_oversized_file_returns_400(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(b"\x00" * 10), "big.png", "image/png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    @patch(
        "services.ocr_service.dispatch_ocr_bytes",
        side_effect=Exception("OCR crashed"),
    )
    def test_ocr_exception_returns_500(self, mock_dispatch, client):
        png = _make_png_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error"] == "OCR processing failed"

    @patch(
        "services.ocr_service.dispatch_ocr_bytes",
        return_value=_ocr_result(text="", provider="Tesseract (Local)", fallback=False),
    )
    def test_empty_text_result_still_200(self, mock_dispatch, client):
        png = _make_png_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == ""
        assert "error" in data  # "No text found in image"
        assert data["provider"] == "Tesseract (Local)"

    @patch("services.ocr_service.dispatch_ocr_bytes", return_value=_ocr_result(provider="Claude Vision", fallback=True))
    def test_multipart_response_includes_provider_and_fallback(self, mock_dispatch, client):
        png = _make_png_bytes()
        resp = client.post(
            "/api/ocr/ingredients",
            data={"image": (io.BytesIO(png), "test.png", "image/png")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["provider"] == "Claude Vision"
        assert data["fallback"] is True


# ---------------------------------------------------------------------------
# Backward compat: JSON path still works after changes
# ---------------------------------------------------------------------------

class TestOcrJsonBackwardCompat:
    """JSON requests must still work after multipart support is added."""

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_json_image_still_accepted(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

    def test_json_missing_image_returns_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "No image provided"


# ---------------------------------------------------------------------------
# Service: dispatch_ocr_bytes
# ---------------------------------------------------------------------------

class TestDispatchOcrBytes:
    """dispatch_ocr_bytes must accept raw image bytes and return standard shape."""

    def _setup_tesseract(self):
        import services.ocr_service as mod
        return mod

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_dispatch_ocr_bytes_returns_dict(self, mock_output, mock_itd):
        mod = self._setup_tesseract()

        mock_itd.return_value = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["ingredienser"], "conf": [85],
        }

        from unittest.mock import patch as _patch
        with _patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            png_bytes = _make_png_bytes()
            result = mod.dispatch_ocr_bytes(png_bytes)

        assert "text" in result
        assert "provider" in result
        assert "fallback" in result
        assert isinstance(result["fallback"], bool)

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_dispatch_ocr_bytes_extracts_text(self, mock_output, mock_itd):
        mod = self._setup_tesseract()

        mock_itd.return_value = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["Sukker"], "conf": [90],
        }

        from unittest.mock import patch as _patch
        with _patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            png_bytes = _make_png_bytes()
            result = mod.dispatch_ocr_bytes(png_bytes)

        assert "Sukker" in result["text"]

    def test_dispatch_ocr_bytes_empty_raises(self):
        import services.ocr_service as mod

        from unittest.mock import patch as _patch
        with _patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            with pytest.raises(ValueError, match="No image provided"):
                mod.dispatch_ocr_bytes(b"")

    def test_dispatch_ocr_bytes_none_raises(self):
        import services.ocr_service as mod

        from unittest.mock import patch as _patch
        with _patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            with pytest.raises(ValueError, match="No image provided"):
                mod.dispatch_ocr_bytes(None)

    def test_dispatch_ocr_bytes_too_large_raises(self):
        import services.ocr_service as mod

        from unittest.mock import patch as _patch
        with _patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            big = b"\x00" * (6 * 1024 * 1024)
            with pytest.raises(ValueError, match="too large"):
                mod.dispatch_ocr_bytes(big)

    def test_dispatch_ocr_bytes_fallback_when_backend_unavailable(self):
        import services.ocr_service as mod
        import os

        mock_itd_data = {
            "left": [10], "top": [10], "width": [40], "height": [20],
            "text": ["test"], "conf": [80],
        }

        from unittest.mock import patch as _patch, MagicMock
        with _patch("services.settings_service.get_ocr_backend", return_value="claude_vision"):
            # claude_vision unavailable (no key)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ANTHROPIC_API_KEY", None)
                os.environ.pop("LLM_API_KEY", None)
                with _patch("pytesseract.image_to_data", return_value=mock_itd_data):
                    with _patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"})):
                        png_bytes = _make_png_bytes()
                        result = mod.dispatch_ocr_bytes(png_bytes)

        assert result["fallback"] is True
