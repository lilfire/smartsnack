"""Regression tests for OCR ingredient upload (LSO-309).

Covers:
- JSON base64 upload path (current server behavior)
- Multipart/form-data upload path (documents that server rejects it — no support yet)
- Negative tests: corrupt data, empty body, missing image field

The server endpoint (blueprints/ocr.py) currently uses _require_json() and only
accepts JSON with a base64 data URI in the "image" field. Multipart/form-data is
NOT supported server-side yet (PR #224 not merged). Tests for the multipart path
verify the server correctly rejects non-JSON content types with 400.
"""

import base64
import io
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Minimal synthetic image bytes (no external fixture files)
# ---------------------------------------------------------------------------

def _minimal_png_bytes():
    """Return a minimal valid 1x1 pixel PNG as bytes."""
    # 1x1 red pixel PNG
    return (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _minimal_jpeg_bytes():
    """Return minimal valid JPEG bytes (SOI + APP0 + EOI)."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
        b"\x00\x01\x00\x00\xff\xd9"
    )


def _png_data_uri():
    """Return a base64 data URI for a minimal PNG."""
    encoded = base64.b64encode(_minimal_png_bytes()).decode()
    return f"data:image/png;base64,{encoded}"


def _jpeg_data_uri():
    """Return a base64 data URI for a minimal JPEG."""
    encoded = base64.b64encode(_minimal_jpeg_bytes()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def _ocr_result(text="Sukker, mel, vann", provider="Tesseract (Local)", fallback=False):
    """Helper to build a dispatch_ocr return value."""
    return {"text": text, "provider": provider, "fallback": fallback}


@pytest.fixture()
def client(app):
    """Flask test client with CSRF header."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


# ===========================================================================
# JSON base64 upload tests (current server behavior)
# ===========================================================================


class TestJsonBase64Upload:
    """POST JSON with base64 data URI — the currently supported path."""

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_png_base64_returns_200(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": _png_data_uri()},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"
        assert "provider" in data

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_jpeg_base64_returns_200(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": _jpeg_data_uri()},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Sukker, mel, vann"

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_webp_base64_returns_200(self, mock_dispatch, client):
        """WebP base64 data URI should also be accepted."""
        encoded = base64.b64encode(b"RIFF\x00\x00\x00\x00WEBP").decode()
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": f"data:image/webp;base64,{encoded}"},
        )
        assert resp.status_code == 200

    @patch("services.ocr_service.dispatch_ocr", return_value=_ocr_result())
    def test_dispatch_receives_image_data(self, mock_dispatch, client):
        """Verify the image value is passed through to dispatch_ocr."""
        uri = _png_data_uri()
        client.post("/api/ocr/ingredients", json={"image": uri})
        mock_dispatch.assert_called_once_with(uri)


# ===========================================================================
# Multipart/form-data upload tests (server does NOT support this yet)
# ===========================================================================


class TestMultipartUploadNotSupported:
    """Multipart/form-data is NOT supported by the server yet.

    The frontend (LSO-306) switched to multipart uploads, but the server
    endpoint still requires JSON via _require_json(). These tests document
    that the server rejects multipart requests with 400.

    When server-side multipart support is added (PR #224 or equivalent),
    these tests should be updated to expect 200 instead of 400.
    """

    def test_multipart_png_rejected(self, client):
        """Server rejects multipart/form-data with 400 (no multipart support)."""
        data = {"image": (io.BytesIO(_minimal_png_bytes()), "test.png", "image/png")}
        resp = client.post(
            "/api/ocr/ingredients",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_multipart_jpeg_rejected(self, client):
        """Server rejects JPEG multipart upload with 400."""
        data = {"image": (io.BytesIO(_minimal_jpeg_bytes()), "test.jpg", "image/jpeg")}
        resp = client.post(
            "/api/ocr/ingredients",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_multipart_webp_rejected(self, client):
        """Server rejects WebP multipart upload with 400."""
        webp_bytes = b"RIFF\x00\x00\x00\x00WEBP"
        data = {"image": (io.BytesIO(webp_bytes), "test.webp", "image/webp")}
        resp = client.post(
            "/api/ocr/ingredients",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ===========================================================================
# Negative tests
# ===========================================================================


class TestNegativeOcrUpload:
    """Negative test cases: corrupt data, empty body, missing fields."""

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=OSError("cannot identify image file"),
    )
    def test_corrupt_image_returns_400_invalid_image(self, mock_dispatch, client):
        """Corrupt/unreadable image data should return 400 with error_type=invalid_image."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,AAAA"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "invalid_image"

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=OSError("cannot identify image file"),
    )
    def test_corrupt_jpeg_returns_invalid_image(self, mock_dispatch, client):
        """Corrupt JPEG returns 400 with error_type=invalid_image."""
        encoded = base64.b64encode(b"\xff\xd8garbage").decode()
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": f"data:image/jpeg;base64,{encoded}"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "invalid_image"

    def test_empty_body_returns_400(self, client):
        """POST with completely empty body should return 400."""
        resp = client.post(
            "/api/ocr/ingredients",
            data=b"",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client):
        """POST with empty JSON object {} should return 400 (no image field)."""
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "image" in data["error"].lower() or "no image" in data["error"].lower()

    def test_empty_image_field_returns_400(self, client):
        """POST with image="" should return 400."""
        resp = client.post("/api/ocr/ingredients", json={"image": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "No image provided"

    def test_plain_text_body_returns_400(self, client):
        """POST with text/plain content type should return 400."""
        resp = client.post(
            "/api/ocr/ingredients",
            data="just some text",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=ValueError("Invalid base64 data"),
    )
    def test_invalid_base64_returns_400(self, mock_dispatch, client):
        """Invalid base64 string should return 400."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "not-a-valid-data-uri"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    from PIL import UnidentifiedImageError

    @patch(
        "services.ocr_service.dispatch_ocr",
        side_effect=UnidentifiedImageError("cannot identify image file"),
    )
    def test_unidentified_image_returns_invalid_image(self, mock_dispatch, client):
        """PIL UnidentifiedImageError should map to error_type=invalid_image."""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": _png_data_uri()},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "invalid_image"
