"""QA integration tests for Gemini image format conversion (LSO-299).

Tests the full dispatch_ocr → _convert_for_gemini → Gemini API pipeline
with various image formats, verifying:
- Unsupported formats (BMP, TIFF, GIF, SVG) are transparently converted to PNG
- Supported formats (JPEG, PNG, WebP) pass through unchanged
- Conversion logging works correctly
- No regression through the blueprint endpoint
"""

import base64
import io
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _make_image(fmt, size=(100, 50)):
    """Create a minimal valid image in the given PIL format."""
    from PIL import Image

    img = Image.new("RGB", size, color="white")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_webp():
    return _make_image("WEBP")


def _make_svg():
    return b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="white"/></svg>'


def _b64(raw_bytes):
    return base64.b64encode(raw_bytes).decode()


def _data_uri(raw_bytes, mime="image/png"):
    return f"data:{mime};base64,{_b64(raw_bytes)}"


def _mock_genai_modules(mock_client):
    """Patch sys.modules for google.genai with a mock client."""
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_google = MagicMock()
    mock_google.genai = mock_genai
    return patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai})


def _make_gemini_response(text="sukker, mel, vann"):
    mock_response = MagicMock()
    mock_response.text = text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# dispatch_ocr integration: unsupported formats converted
# ---------------------------------------------------------------------------

class TestDispatchOcrFormatConversion:
    """Integration tests: dispatch_ocr with gemini backend and various formats.

    These test the full user-facing path: dispatch_ocr → _convert_for_gemini
    → Gemini API, verifying that the conversion is transparent.
    """

    def _setup_gemini_setting(self):
        """Patch settings_service to return 'gemini' as selected backend."""
        return patch("services.settings_service.get_ocr_backend", return_value="gemini")

    @pytest.mark.parametrize("fmt,expected_mime", [
        ("BMP", "image/png"),
        ("TIFF", "image/png"),
        ("GIF", "image/png"),
    ])
    def test_unsupported_format_converted_and_ocr_succeeds(self, fmt, expected_mime):
        """Unsupported format should be converted to PNG; OCR returns text."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("ingredienser")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    result = dispatch_ocr(_b64(image_bytes))

        assert result["text"] == "ingredienser"
        # Verify the API was called with PNG mime type
        call_kwargs = mock_client.models.generate_content.call_args
        parts = call_kwargs[1]["contents"][0]["parts"]
        assert parts[0]["inline_data"]["mime_type"] == expected_mime

    def test_svg_converted_and_ocr_succeeds(self):
        """SVG should be converted to PNG via cairosvg; OCR returns text."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("ingredienser fra svg")
        genai_patch = _mock_genai_modules(mock_client)

        svg_bytes = _make_svg()
        fake_png = _make_image("PNG")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with patch("services.ocr_service._svg_to_png", return_value=fake_png):
                        result = dispatch_ocr(_b64(svg_bytes))

        assert result["text"] == "ingredienser fra svg"
        call_kwargs = mock_client.models.generate_content.call_args
        parts = call_kwargs[1]["contents"][0]["parts"]
        assert parts[0]["inline_data"]["mime_type"] == "image/png"

    @pytest.mark.parametrize("fmt,expected_mime", [
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
    ])
    def test_supported_format_passes_through(self, fmt, expected_mime):
        """Supported formats should pass through with original mime type."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("sukker")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    result = dispatch_ocr(_b64(image_bytes))

        assert result["text"] == "sukker"
        call_kwargs = mock_client.models.generate_content.call_args
        parts = call_kwargs[1]["contents"][0]["parts"]
        assert parts[0]["inline_data"]["mime_type"] == expected_mime

    def test_webp_passes_through(self):
        """WebP should pass through as image/webp (Gemini-supported)."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("mel")
        genai_patch = _mock_genai_modules(mock_client)

        webp_bytes = _make_webp()

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    result = dispatch_ocr(_b64(webp_bytes))

        assert result["text"] == "mel"
        call_kwargs = mock_client.models.generate_content.call_args
        parts = call_kwargs[1]["contents"][0]["parts"]
        assert parts[0]["inline_data"]["mime_type"] == "image/webp"

    def test_dispatch_ocr_returns_provider_name(self):
        """dispatch_ocr should include the provider name in the result."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("test")
        genai_patch = _mock_genai_modules(mock_client)

        png_bytes = _make_image("PNG")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    result = dispatch_ocr(_b64(png_bytes))

        assert "provider" in result
        assert result["fallback"] is False

    def test_data_uri_with_bmp_works(self):
        """BMP sent as data URI should still be converted correctly."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("data uri test")
        genai_patch = _mock_genai_modules(mock_client)

        bmp_bytes = _make_image("BMP")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    result = dispatch_ocr(_data_uri(bmp_bytes, mime="image/bmp"))

        assert result["text"] == "data uri test"
        call_kwargs = mock_client.models.generate_content.call_args
        parts = call_kwargs[1]["contents"][0]["parts"]
        assert parts[0]["inline_data"]["mime_type"] == "image/png"


# ---------------------------------------------------------------------------
# _convert_for_gemini — WebP passthrough (gap in existing tests)
# ---------------------------------------------------------------------------

class TestConvertForGeminiWebP:
    """WebP passthrough was missing from existing unit tests."""

    def test_webp_returns_unchanged_bytes_and_mime(self):
        from services.ocr_service import _convert_for_gemini

        webp_bytes = _make_webp()
        out_bytes, mime = _convert_for_gemini(webp_bytes)

        assert mime == "image/webp"
        assert out_bytes == webp_bytes

    def test_webp_no_conversion_log(self, caplog):
        from services.ocr_service import _convert_for_gemini

        webp_bytes = _make_webp()
        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
            _convert_for_gemini(webp_bytes)

        assert not any("OCR: converted" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _convert_for_gemini — edge cases
# ---------------------------------------------------------------------------

class TestConvertForGeminiEdgeCases:
    """Edge cases for format conversion."""

    def test_unrecognizable_bytes_returns_detected_mime(self):
        """Corrupt/unknown bytes should fall back to _detect_mime_type result (image/jpeg by default)."""
        from services.ocr_service import _convert_for_gemini, _detect_mime_type

        garbage = b"\x00\x01\x02\x03\x04\x05"
        out_bytes, mime = _convert_for_gemini(garbage)

        # Should return original bytes with mime type detected from magic bytes
        assert mime == _detect_mime_type(garbage)
        assert out_bytes == garbage

    def test_converted_bmp_is_valid_png(self):
        """BMP conversion should produce valid PNG bytes."""
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        bmp_bytes = _make_image("BMP")
        out_bytes, mime = _convert_for_gemini(bmp_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"
        assert img.size == (100, 50)

    def test_converted_tiff_is_valid_png(self):
        """TIFF conversion should produce valid PNG bytes."""
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        tiff_bytes = _make_image("TIFF")
        out_bytes, mime = _convert_for_gemini(tiff_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"

    def test_converted_gif_is_valid_png(self):
        """GIF conversion should produce valid PNG bytes."""
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        gif_bytes = _make_image("GIF")
        out_bytes, mime = _convert_for_gemini(gif_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"


# ---------------------------------------------------------------------------
# Logging verification through dispatch_ocr
# ---------------------------------------------------------------------------

class TestFormatConversionLogging:
    """Verify conversion logging through the full dispatch_ocr path."""

    def _setup_gemini_setting(self):
        return patch("services.settings_service.get_ocr_backend", return_value="gemini")

    @pytest.mark.parametrize("fmt,expected_log_fragment", [
        ("BMP", "OCR: converted bmp"),
        ("TIFF", "OCR: converted tiff"),
        ("GIF", "OCR: converted gif"),
    ])
    def test_unsupported_format_logs_conversion(self, fmt, expected_log_fragment, caplog):
        """dispatch_ocr should log when converting unsupported formats."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("text")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with caplog.at_level(logging.INFO, logger="services.ocr_service"):
                        dispatch_ocr(_b64(image_bytes))

        assert any(expected_log_fragment in r.message for r in caplog.records)

    def test_svg_logs_conversion(self, caplog):
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("text")
        genai_patch = _mock_genai_modules(mock_client)

        svg_bytes = _make_svg()
        fake_png = _make_image("PNG")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with patch("services.ocr_service._svg_to_png", return_value=fake_png):
                        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
                            dispatch_ocr(_b64(svg_bytes))

        assert any("OCR: converted svg" in r.message for r in caplog.records)

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
    def test_supported_format_no_conversion_log(self, fmt, caplog):
        """Supported formats should NOT produce conversion logs."""
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("text")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with caplog.at_level(logging.INFO, logger="services.ocr_service"):
                        dispatch_ocr(_b64(image_bytes))

        assert not any("OCR: converted" in r.message for r in caplog.records)

    def test_webp_no_conversion_log_via_dispatch(self, caplog):
        from services.ocr_service import dispatch_ocr

        mock_client = _make_gemini_response("text")
        genai_patch = _mock_genai_modules(mock_client)

        webp_bytes = _make_webp()

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with caplog.at_level(logging.INFO, logger="services.ocr_service"):
                        dispatch_ocr(_b64(webp_bytes))

        assert not any("OCR: converted" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Blueprint endpoint integration with format conversion
# ---------------------------------------------------------------------------

class TestBlueprintFormatConversion:
    """Test the /api/ocr/ingredients endpoint with various image formats.

    Verifies the full stack: HTTP request → blueprint → dispatch_ocr →
    _convert_for_gemini → Gemini API mock → HTTP response.
    """

    def _setup_gemini_setting(self):
        return patch("services.settings_service.get_ocr_backend", return_value="gemini")

    @pytest.mark.parametrize("fmt,label", [
        ("BMP", "bmp"),
        ("TIFF", "tiff"),
        ("GIF", "gif"),
    ])
    def test_endpoint_with_unsupported_format_returns_200(self, fmt, label, client):
        """Posting an unsupported image format should succeed (200) after conversion."""
        mock_client = _make_gemini_response(f"ingredients from {label}")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    resp = client.post(
                        "/api/ocr/ingredients",
                        json={"image": _b64(image_bytes)},
                    )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == f"ingredients from {label}"
        assert "provider" in data

    def test_endpoint_with_svg_returns_200(self, client):
        mock_client = _make_gemini_response("svg ingredients")
        genai_patch = _mock_genai_modules(mock_client)

        svg_bytes = _make_svg()
        fake_png = _make_image("PNG")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    with patch("services.ocr_service._svg_to_png", return_value=fake_png):
                        resp = client.post(
                            "/api/ocr/ingredients",
                            json={"image": _b64(svg_bytes)},
                        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "svg ingredients"

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
    def test_endpoint_with_supported_format_returns_200(self, fmt, client):
        """Supported formats should work without any conversion."""
        mock_client = _make_gemini_response("normal ingredients")
        genai_patch = _mock_genai_modules(mock_client)

        image_bytes = _make_image(fmt)

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    resp = client.post(
                        "/api/ocr/ingredients",
                        json={"image": _b64(image_bytes)},
                    )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "normal ingredients"

    def test_endpoint_with_webp_returns_200(self, client):
        mock_client = _make_gemini_response("webp ingredients")
        genai_patch = _mock_genai_modules(mock_client)

        webp_bytes = _make_webp()

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    resp = client.post(
                        "/api/ocr/ingredients",
                        json={"image": _b64(webp_bytes)},
                    )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "webp ingredients"

    def test_endpoint_no_ui_change_unsupported_format(self, client):
        """Response shape for unsupported formats should match supported ones."""
        mock_client = _make_gemini_response("bmp text")
        genai_patch = _mock_genai_modules(mock_client)

        bmp_bytes = _make_image("BMP")

        with self._setup_gemini_setting():
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with genai_patch:
                    resp = client.post(
                        "/api/ocr/ingredients",
                        json={"image": _b64(bmp_bytes)},
                    )

        data = resp.get_json()
        # Same response shape as any other format — no extra fields
        assert set(data.keys()) == {"text", "provider", "fallback"}
