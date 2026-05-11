"""Integration tests for OCR MIME type detection through the full endpoint flow.

Verifies that POST /api/ocr/ingredients correctly detects MIME types from
image bytes and passes them through to the OCR provider — NOT hardcoded
as image/png. Tests exercise: endpoint → service → provider call with the
provider mocked only at the boundary.
"""

import base64
import io
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import _CsrfTestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes():
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes():
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def client(app):
    return _CsrfTestClient(app.test_client())


# ---------------------------------------------------------------------------
# Integration: multipart/form-data upload (dispatch_ocr_bytes path)
# ---------------------------------------------------------------------------

class TestOcrMimeTypeIntegrationMultipart:
    """Full endpoint integration: POST /api/ocr/ingredients with multipart upload.

    Mocks only the provider function at the boundary to capture the mime_type
    argument. Everything else (blueprint, service routing, MIME detection) runs
    for real.
    """

    @patch("services.settings_service.get_ocr_backend", return_value="tesseract")
    def test_jpeg_upload_passes_image_jpeg_to_provider(self, _mock_backend, client):
        """JPEG image bytes must result in mime_type='image/jpeg' at the provider."""
        jpeg = _make_jpeg_bytes()
        provider_fn = MagicMock(return_value="Sukker, mel, vann")

        with patch.dict(
            "services.ocr_service._PROVIDERS", {"tesseract": provider_fn}
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                data={"image": (io.BytesIO(jpeg), "test.jpg", "image/jpeg")},
                content_type="multipart/form-data",
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

        # The provider must have been called with mime_type='image/jpeg'
        provider_fn.assert_called_once()
        _, _, mime_arg = provider_fn.call_args[0]
        assert mime_arg == "image/jpeg", (
            f"Expected provider to receive 'image/jpeg', got '{mime_arg}'"
        )

    @patch("services.settings_service.get_ocr_backend", return_value="tesseract")
    def test_png_upload_passes_image_png_to_provider(self, _mock_backend, client):
        """PNG image bytes must result in mime_type='image/png' at the provider."""
        png = _make_png_bytes()
        provider_fn = MagicMock(return_value="Mel, sukker")

        with patch.dict(
            "services.ocr_service._PROVIDERS", {"tesseract": provider_fn}
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                data={"image": (io.BytesIO(png), "test.png", "image/png")},
                content_type="multipart/form-data",
            )

        assert resp.status_code == 200
        provider_fn.assert_called_once()
        _, _, mime_arg = provider_fn.call_args[0]
        assert mime_arg == "image/png", (
            f"Expected provider to receive 'image/png', got '{mime_arg}'"
        )


# ---------------------------------------------------------------------------
# Integration: JSON base64 upload (dispatch_ocr path)
# ---------------------------------------------------------------------------

class TestOcrMimeTypeIntegrationJson:
    """Full endpoint integration: POST /api/ocr/ingredients with JSON base64.

    Ensures dispatch_ocr also detects and passes the correct MIME type.
    """

    @patch("services.settings_service.get_ocr_backend", return_value="tesseract")
    def test_jpeg_base64_passes_image_jpeg_to_provider(self, _mock_backend, client):
        """JPEG bytes encoded as base64 must yield mime_type='image/jpeg'."""
        jpeg = _make_jpeg_bytes()
        b64 = base64.b64encode(jpeg).decode()
        provider_fn = MagicMock(return_value="Sukker, vann")

        with patch.dict(
            "services.ocr_service._PROVIDERS", {"tesseract": provider_fn}
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": b64},
            )

        assert resp.status_code == 200
        provider_fn.assert_called_once()
        _, _, mime_arg = provider_fn.call_args[0]
        assert mime_arg == "image/jpeg", (
            f"Expected provider to receive 'image/jpeg', got '{mime_arg}'"
        )

    @patch("services.settings_service.get_ocr_backend", return_value="tesseract")
    def test_jpeg_data_uri_passes_image_jpeg_to_provider(self, _mock_backend, client):
        """JPEG data URI must preserve the declared MIME type."""
        jpeg = _make_jpeg_bytes()
        b64 = base64.b64encode(jpeg).decode()
        data_uri = f"data:image/jpeg;base64,{b64}"
        provider_fn = MagicMock(return_value="Mel, salt")

        with patch.dict(
            "services.ocr_service._PROVIDERS", {"tesseract": provider_fn}
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": data_uri},
            )

        assert resp.status_code == 200
        provider_fn.assert_called_once()
        _, _, mime_arg = provider_fn.call_args[0]
        assert mime_arg == "image/jpeg", (
            f"Expected provider to receive 'image/jpeg', got '{mime_arg}'"
        )

    @patch("services.settings_service.get_ocr_backend", return_value="tesseract")
    def test_png_base64_passes_image_png_to_provider(self, _mock_backend, client):
        """PNG bytes encoded as base64 must yield mime_type='image/png'."""
        png = _make_png_bytes()
        b64 = base64.b64encode(png).decode()
        provider_fn = MagicMock(return_value="Hvetemel")

        with patch.dict(
            "services.ocr_service._PROVIDERS", {"tesseract": provider_fn}
        ):
            resp = client.post(
                "/api/ocr/ingredients",
                json={"image": b64},
            )

        assert resp.status_code == 200
        provider_fn.assert_called_once()
        _, _, mime_arg = provider_fn.call_args[0]
        assert mime_arg == "image/png", (
            f"Expected provider to receive 'image/png', got '{mime_arg}'"
        )
