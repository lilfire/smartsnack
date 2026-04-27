"""Tests for OCR service — multi-provider OCR backends."""

import base64
import io
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiny_png():
    """Create a minimal valid PNG image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_tiny_jpeg():
    """Create a minimal valid JPEG image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_tiny_bmp():
    """Create a minimal valid BMP image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def _make_tiny_tiff():
    """Create a minimal valid TIFF image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    return buf.getvalue()


def _make_tiny_gif():
    """Create a minimal valid GIF image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


def _make_minimal_svg():
    """Return a minimal SVG file as bytes."""
    return b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="white"/></svg>'


def _b64(raw_bytes):
    return base64.b64encode(raw_bytes).decode()


def _data_uri(raw_bytes, mime="image/png"):
    return f"data:{mime};base64,{_b64(raw_bytes)}"


def _make_tesseract_data(texts, confs, lefts=None, tops=None, widths=None, heights=None):
    """Build a pytesseract-style output dict."""
    n = len(texts)
    return {
        "left": lefts or [i * 50 for i in range(n)],
        "top": tops or [10] * n,
        "width": widths or [40] * n,
        "height": heights or [20] * n,
        "text": texts,
        "conf": confs,
    }


# ---------------------------------------------------------------------------
# extract_text — input validation (backend-agnostic)
# ---------------------------------------------------------------------------

class TestExtractTextValidation:
    """Input validation should work regardless of backend."""

    def test_none_input_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text(None)

    def test_empty_string_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text("")

    def test_non_string_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text(123)

    def test_invalid_data_uri_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="Invalid data URI"):
            extract_text("data:text/plain;base64,abc")

    def test_invalid_base64_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="Invalid base64"):
            extract_text("!!!not-base64!!!")

    def test_image_too_large_raises(self):
        from services.ocr_service import extract_text

        huge = base64.b64encode(b"\x00" * (6 * 1024 * 1024)).decode()
        with pytest.raises(ValueError, match="too large"):
            extract_text(huge)


# ---------------------------------------------------------------------------
# Tesseract backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True)
class TestTesseractBackend:
    """Tests for the pytesseract-based OCR backend."""

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_extract_text_calls_pytesseract(self, mock_output, mock_itd, _mock_backend):
        """extract_text should call pytesseract.image_to_data with correct params."""
        from services.ocr_service import extract_text

        mock_itd.return_value = _make_tesseract_data(
            texts=["Sukker", "mel"],
            confs=[90, 85],
            lefts=[10, 60],
            tops=[10, 10],
        )

        png_bytes = _make_tiny_png()
        result = extract_text(_b64(png_bytes))

        assert mock_itd.called
        assert "Sukker" in result
        assert "mel" in result

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_extract_text_with_data_uri(self, mock_output, mock_itd, _mock_backend):
        """Should handle data URI format input."""
        from services.ocr_service import extract_text

        mock_itd.return_value = _make_tesseract_data(
            texts=["ingredienser"],
            confs=[92],
        )

        png_bytes = _make_tiny_png()
        result = extract_text(_data_uri(png_bytes))

        assert result == "ingredienser"

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_filters_low_confidence(self, mock_output, mock_itd, _mock_backend):
        """Words with confidence < 30 should be dropped."""
        from services.ocr_service import extract_text

        mock_itd.return_value = _make_tesseract_data(
            texts=["good", "noise"],
            confs=[80, 10],
            lefts=[10, 60],
        )

        png_bytes = _make_tiny_png()
        result = extract_text(_b64(png_bytes))

        assert "good" in result
        assert "noise" not in result

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_empty_ocr_returns_empty_string(self, mock_output, mock_itd, _mock_backend):
        """When OCR produces no text, return empty string."""
        from services.ocr_service import extract_text

        mock_itd.return_value = _make_tesseract_data(texts=[], confs=[])

        png_bytes = _make_tiny_png()
        result = extract_text(_b64(png_bytes))

        assert result == ""

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_multi_variant_picks_best(self, mock_output, mock_itd, _mock_backend):
        """Should try multiple image variants and pick highest confidence."""
        from services.ocr_service import extract_text

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_tesseract_data(texts=["blurry"], confs=[40])
            else:
                return _make_tesseract_data(texts=["sharp"], confs=[95])

        mock_itd.side_effect = side_effect

        png_bytes = _make_tiny_png()
        result = extract_text(_b64(png_bytes))

        assert "sharp" in result
        assert mock_itd.call_count == 2


# ---------------------------------------------------------------------------
# Claude Vision backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True)
class TestClaudeVisionBackend:
    """Tests for the Claude Vision OCR backend."""

    def test_extract_text_calls_claude_vision(self, _mock_backend):
        """When backend=claude_vision, should use Claude Vision."""
        from services.ocr_service import extract_text

        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="sukker, hvetemel, vann, salt")])

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert mock_cls.return_value.messages.create.called
                assert result == "sukker, hvetemel, vann, salt"

    def test_claude_vision_with_data_uri(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="ingredients list")])

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                png_bytes = _make_tiny_png()
                result = extract_text(_data_uri(png_bytes))

                assert result == "ingredients list"

    def test_missing_api_key_raises(self, _mock_backend):
        """Should raise ValueError when no API key is available."""
        from services.ocr_service import extract_text

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self, _mock_backend):
        """Should use LLM_API_KEY when ANTHROPIC_API_KEY is not set."""
        from services.ocr_service import extract_text

        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="ingredients here")])

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="fallback-key")
                assert result == "ingredients here"

    def test_empty_response(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_msg = types.SimpleNamespace(content=[])

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True)
class TestGeminiBackend:
    """Tests for the Gemini Vision OCR backend."""

    def _patch_genai(self, mock_client):
        """Create sys.modules patches for google.genai with mock_client."""
        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)
        return patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}), mock_genai

    def test_extract_text_calls_gemini(self, _mock_backend):
        """Should call google.genai.Client with correct API shape."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="sukker, mel, vann")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        # For this test we need to assert Client was called with api_key,
        # so we use a tracking wrapper instead of a plain lambda.
        calls = []

        def make_client(**kw):
            calls.append(kw)
            return mock_client

        mock_genai = types.SimpleNamespace(Client=make_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert calls == [{"api_key": "test-gemini-key"}]
                mock_client.models.generate_content.assert_called_once()
                call_kwargs = mock_client.models.generate_content.call_args
                assert call_kwargs[1]["model"] == "gemini-2.0-flash"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self, _mock_backend):
        from services.ocr_service import extract_text

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="ingredients")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        calls = []

        def make_client(**kw):
            calls.append(kw)
            return mock_client

        mock_genai = types.SimpleNamespace(Client=make_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                assert calls == [{"api_key": "fallback-key"}]

    def test_empty_response(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == ""

    def test_bmp_converted_before_gemini_call(self, _mock_backend):
        """BMP image should be converted to PNG before calling Gemini API."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="sukker, mel")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                bmp_bytes = _make_tiny_bmp()
                result = extract_text(_b64(bmp_bytes))

                assert result == "sukker, mel"
                call_kwargs = mock_client.models.generate_content.call_args
                parts = call_kwargs[1]["contents"][0]["parts"]
                mime_type = parts[0]["inline_data"]["mime_type"]
                assert mime_type == "image/png"

    def test_tiff_converted_before_gemini_call(self, _mock_backend):
        """TIFF image should be converted to PNG before calling Gemini API."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="ingredients")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                tiff_bytes = _make_tiny_tiff()
                result = extract_text(_b64(tiff_bytes))

                assert result == "ingredients"
                call_kwargs = mock_client.models.generate_content.call_args
                parts = call_kwargs[1]["contents"][0]["parts"]
                mime_type = parts[0]["inline_data"]["mime_type"]
                assert mime_type == "image/png"

    def test_gif_converted_before_gemini_call(self, _mock_backend):
        """GIF image should be converted to PNG before calling Gemini API."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="ingredients")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                gif_bytes = _make_tiny_gif()
                result = extract_text(_b64(gif_bytes))

                assert result == "ingredients"
                call_kwargs = mock_client.models.generate_content.call_args
                parts = call_kwargs[1]["contents"][0]["parts"]
                mime_type = parts[0]["inline_data"]["mime_type"]
                assert mime_type == "image/png"

    def test_jpeg_passthrough_with_correct_mime_type(self, _mock_backend):
        """JPEG should pass through with image/jpeg mime type."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="sukker")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                jpeg_bytes = _make_tiny_jpeg()
                result = extract_text(_b64(jpeg_bytes))

                assert result == "sukker"
                call_kwargs = mock_client.models.generate_content.call_args
                parts = call_kwargs[1]["contents"][0]["parts"]
                mime_type = parts[0]["inline_data"]["mime_type"]
                assert mime_type == "image/jpeg"

    def test_png_passthrough_with_correct_mime_type(self, _mock_backend):
        """PNG should pass through with image/png mime type."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="mel")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == "mel"
                call_kwargs = mock_client.models.generate_content.call_args
                parts = call_kwargs[1]["contents"][0]["parts"]
                mime_type = parts[0]["inline_data"]["mime_type"]
                assert mime_type == "image/png"

    def test_svg_converted_before_gemini_call(self, _mock_backend):
        """SVG image should be converted to PNG before calling Gemini API."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="ingredients")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        fake_png = _make_tiny_png()

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                with patch("services.ocr_backends.gemini._svg_to_png", return_value=fake_png, autospec=True) as mock_svg:
                    svg_bytes = _make_minimal_svg()
                    result = extract_text(_b64(svg_bytes))

                    assert result == "ingredients"
                    mock_svg.assert_called_once_with(svg_bytes)
                    call_kwargs = mock_client.models.generate_content.call_args
                    parts = call_kwargs[1]["contents"][0]["parts"]
                    mime_type = parts[0]["inline_data"]["mime_type"]
                    assert mime_type == "image/png"


# ---------------------------------------------------------------------------
# _convert_for_gemini unit tests
# ---------------------------------------------------------------------------

class TestConvertForGemini:
    """Unit tests for the _convert_for_gemini helper."""

    def test_png_returns_unchanged_bytes_and_mime(self):
        from services.ocr_service import _convert_for_gemini

        png_bytes = _make_tiny_png()
        out_bytes, mime = _convert_for_gemini(png_bytes)

        assert mime == "image/png"
        assert out_bytes == png_bytes

    def test_jpeg_returns_unchanged_bytes_and_mime(self):
        from services.ocr_service import _convert_for_gemini

        jpeg_bytes = _make_tiny_jpeg()
        out_bytes, mime = _convert_for_gemini(jpeg_bytes)

        assert mime == "image/jpeg"
        assert out_bytes == jpeg_bytes

    def test_bmp_converts_to_png(self):
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        bmp_bytes = _make_tiny_bmp()
        out_bytes, mime = _convert_for_gemini(bmp_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"

    def test_tiff_converts_to_png(self):
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        tiff_bytes = _make_tiny_tiff()
        out_bytes, mime = _convert_for_gemini(tiff_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"

    def test_gif_converts_to_png(self):
        from PIL import Image
        from services.ocr_service import _convert_for_gemini

        gif_bytes = _make_tiny_gif()
        out_bytes, mime = _convert_for_gemini(gif_bytes)

        assert mime == "image/png"
        img = Image.open(io.BytesIO(out_bytes))
        assert img.format == "PNG"

    def test_bmp_conversion_logs_message(self, caplog):
        import logging
        from services.ocr_service import _convert_for_gemini

        bmp_bytes = _make_tiny_bmp()
        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
            _convert_for_gemini(bmp_bytes)

        assert any("OCR: converted bmp → image/png for Gemini" in r.message for r in caplog.records)

    def test_tiff_conversion_logs_message(self, caplog):
        import logging
        from services.ocr_service import _convert_for_gemini

        tiff_bytes = _make_tiny_tiff()
        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
            _convert_for_gemini(tiff_bytes)

        assert any("OCR: converted tiff → image/png for Gemini" in r.message for r in caplog.records)

    def test_gif_conversion_logs_message(self, caplog):
        import logging
        from services.ocr_service import _convert_for_gemini

        gif_bytes = _make_tiny_gif()
        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
            _convert_for_gemini(gif_bytes)

        assert any("OCR: converted gif → image/png for Gemini" in r.message for r in caplog.records)

    def test_png_no_conversion_log(self, caplog):
        import logging
        from services.ocr_service import _convert_for_gemini

        png_bytes = _make_tiny_png()
        with caplog.at_level(logging.INFO, logger="services.ocr_service"):
            _convert_for_gemini(png_bytes)

        assert not any("OCR: converted" in r.message for r in caplog.records)

    def test_svg_calls_svg_to_png(self):
        from services.ocr_service import _convert_for_gemini

        svg_bytes = _make_minimal_svg()
        fake_png = _make_tiny_png()

        with patch("services.ocr_backends.gemini._svg_to_png", return_value=fake_png, autospec=True) as mock_svg:
            out_bytes, mime = _convert_for_gemini(svg_bytes)

        mock_svg.assert_called_once_with(svg_bytes)
        assert mime == "image/png"
        assert out_bytes == fake_png

    def test_svg_conversion_logs_message(self, caplog):
        import logging
        from services.ocr_service import _convert_for_gemini

        svg_bytes = _make_minimal_svg()
        fake_png = _make_tiny_png()

        with patch("services.ocr_backends.gemini._svg_to_png", return_value=fake_png, autospec=True):
            with caplog.at_level(logging.INFO, logger="services.ocr_service"):
                _convert_for_gemini(svg_bytes)

        assert any("OCR: converted svg → image/png for Gemini" in r.message for r in caplog.records)

    def test_svg_with_xml_declaration(self):
        """SVG with XML declaration should also be detected and converted."""
        from services.ocr_service import _convert_for_gemini

        svg_bytes = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        fake_png = _make_tiny_png()

        with patch("services.ocr_backends.gemini._svg_to_png", return_value=fake_png, autospec=True) as mock_svg:
            out_bytes, mime = _convert_for_gemini(svg_bytes)

        mock_svg.assert_called_once()
        assert mime == "image/png"


# ---------------------------------------------------------------------------
# _svg_to_png unit tests
# ---------------------------------------------------------------------------

class TestSvgToPng:
    """Unit tests for the _svg_to_png helper."""

    def test_uses_cairosvg_when_available(self):
        from services.ocr_service import _svg_to_png

        svg_bytes = _make_minimal_svg()
        fake_png = _make_tiny_png()

        mock_cairosvg = types.SimpleNamespace(svg2png=MagicMock(return_value=fake_png))

        with patch.dict("sys.modules", {"cairosvg": mock_cairosvg}):
            result = _svg_to_png(svg_bytes)

        mock_cairosvg.svg2png.assert_called_once_with(bytestring=svg_bytes)
        assert result == fake_png

    def test_raises_value_error_when_cairosvg_missing(self):
        from services.ocr_service import _svg_to_png

        svg_bytes = _make_minimal_svg()

        with patch.dict("sys.modules", {"cairosvg": None}):
            with pytest.raises((ValueError, ImportError)):
                _svg_to_png(svg_bytes)


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="openai", autospec=True)
class TestOpenAIBackend:
    """Tests for the OpenAI Vision OCR backend."""

    def test_extract_text_calls_openai(self, _mock_backend):
        """Should call openai.OpenAI with correct API shape."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="sukker, mel, vann"))]
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="test-openai-key")
                mock_cls.return_value.chat.completions.create.assert_called_once()
                call_kwargs = mock_cls.return_value.chat.completions.create.call_args
                assert call_kwargs[1]["model"] == "gpt-4o"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self, _mock_backend):
        from services.ocr_service import extract_text

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredients"))]
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="fallback-key")

    def test_empty_response(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=""))]
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# OpenRouter backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="openrouter", autospec=True)
class TestOpenRouterBackend:
    """Tests for the OpenRouter Vision OCR backend."""

    def test_extract_text_calls_openrouter(self, _mock_backend):
        """Should call openai.OpenAI with base_url for OpenRouter and correct API key."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="sukker, mel, vann"))]
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-openrouter-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(
                    api_key="test-openrouter-key",
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={"HTTP-Referer": "https://smartsnack.app"},
                )
                mock_cls.return_value.chat.completions.create.assert_called_once()
                call_kwargs = mock_cls.return_value.chat.completions.create.call_args
                assert call_kwargs[1]["model"] == "google/gemini-2.0-flash-001"
                # Verify system prompt is included in messages
                messages = call_kwargs[1]["messages"]
                assert messages[0]["role"] == "system"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self, _mock_backend):
        """When both OPENROUTER_API_KEY and LLM_API_KEY are absent, raise ValueError."""
        from services.ocr_service import extract_text

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENROUTER_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self, _mock_backend):
        """When OPENROUTER_API_KEY absent but LLM_API_KEY set, use LLM_API_KEY."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredients"))]
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("OPENROUTER_API_KEY", None)
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(
                    api_key="fallback-key",
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={"HTTP-Referer": "https://smartsnack.app"},
                )

    def test_custom_model_override(self, _mock_backend):
        """When OPENROUTER_MODEL env var is set, use that model instead of default."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="mel"))]
        )

        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "anthropic/claude-3.5-sonnet",
        }, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                call_kwargs = mock_cls.return_value.chat.completions.create.call_args
                assert call_kwargs[1]["model"] == "anthropic/claude-3.5-sonnet"

    def test_empty_response(self, _mock_backend):
        """When response content is empty string, extract_text() returns empty string."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=""))]
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# Groq backend
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="groq", autospec=True)
class TestGroqBackend:
    """Tests for the Groq Vision OCR backend."""

    def test_extract_text_calls_groq(self, _mock_backend):
        """Should call groq.Groq with correct API shape."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="sukker, mel, vann"))]
        )

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-groq-key"}, clear=False):
            with patch("groq.Groq") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="test-groq-key")
                mock_cls.return_value.chat.completions.create.assert_called_once()
                call_kwargs = mock_cls.return_value.chat.completions.create.call_args
                assert call_kwargs[1]["model"] == "meta-llama/llama-4-scout-17b-16e-instruct"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self, _mock_backend):
        from services.ocr_service import extract_text

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredients"))]
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("GROQ_API_KEY", None)
            with patch("groq.Groq") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="fallback-key")

    def test_empty_response(self, _mock_backend):
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=""))]
        )

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            with patch("groq.Groq") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="llm", autospec=True)
class TestBackwardCompatibility:
    """Verify backend=llm still routes to Claude Vision."""

    def test_llm_routes_to_claude_vision(self, _mock_backend):
        """backend=llm should use the Claude Vision provider (anthropic SDK)."""
        from services.ocr_service import extract_text

        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="sukker, mel")])

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                png_bytes = _make_tiny_png()
                result = extract_text(_b64(png_bytes))

                assert mock_cls.return_value.messages.create.called
                assert result == "sukker, mel"

    def test_llm_alias_in_providers_registry(self, _mock_backend):
        """The _PROVIDERS dict should map 'llm' to claude_vision handler."""
        import services.ocr_service as mod

        assert "llm" in mod._PROVIDERS
        assert mod._PROVIDERS["llm"] == mod._PROVIDERS["claude_vision"]


# ---------------------------------------------------------------------------
# Unknown backend
# ---------------------------------------------------------------------------

class TestUnknownBackend:
    """Verify clear error message for invalid backend values."""

    @patch("services.settings_service.get_ocr_backend", return_value="invalid_provider", autospec=True)
    def test_unknown_backend_raises_value_error(self, _mock_backend):
        from services.ocr_service import extract_text

        png_bytes = _make_tiny_png()
        with pytest.raises(ValueError, match="Unknown OCR backend"):
            extract_text(_b64(png_bytes))

    @patch("services.settings_service.get_ocr_backend", return_value="banana_vision", autospec=True)
    def test_error_message_includes_backend_name(self, _mock_backend):
        from services.ocr_service import extract_text

        png_bytes = _make_tiny_png()
        with pytest.raises(ValueError, match="banana_vision"):
            extract_text(_b64(png_bytes))


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    """Verify provider registry contains all expected backends."""

    def test_all_providers_in_registry(self):
        """All valid backend names should be in the _PROVIDERS dict."""
        import services.ocr_service as mod
        expected = {"tesseract", "claude_vision", "gemini", "openai", "openrouter", "groq", "llm"}
        assert expected == set(mod._PROVIDERS.keys())


# ---------------------------------------------------------------------------
# _sort_and_join (tesseract format)
# ---------------------------------------------------------------------------

class TestSortAndJoin:
    """Test spatial sorting of tesseract OCR results."""

    def test_empty_items(self):
        from services.ocr_service import _sort_and_join
        assert _sort_and_join([]) == ""

    def test_single_line(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 100, "top": 10, "width": 40, "height": 20, "text": "world"},
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "hello"},
        ]
        result = _sort_and_join(items)
        assert result == "hello world"

    def test_multi_line(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 10, "top": 50, "width": 40, "height": 20, "text": "line2"},
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "line1"},
        ]
        result = _sort_and_join(items)
        assert result == "line1 line2"

    def test_whitespace_only_text_skipped(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "  "},
            {"left": 60, "top": 10, "width": 40, "height": 20, "text": "valid"},
        ]
        result = _sort_and_join(items)
        assert result == "valid"


# ---------------------------------------------------------------------------
# _prepare_images
# ---------------------------------------------------------------------------

class TestPrepareImages:
    """Test image preprocessing pipeline."""

    def test_returns_two_variants(self):
        from services.ocr_service import _prepare_images

        png_bytes = _make_tiny_png()
        variants = _prepare_images(png_bytes)
        assert len(variants) == 2

    def test_upscales_small_images(self):
        from PIL import Image
        from services.ocr_service import _prepare_images

        # Create a small 50x50 image
        img = Image.new("RGB", (50, 50), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        variants = _prepare_images(buf.getvalue())
        # First variant should be a PIL image that's been upscaled
        first = variants[0]
        assert isinstance(first, Image.Image)
        assert max(first.size) >= 1500

    def test_large_image_not_upscaled(self):
        from PIL import Image
        from services.ocr_service import _prepare_images

        img = Image.new("RGB", (2000, 1500), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        variants = _prepare_images(buf.getvalue())
        first = variants[0]
        assert isinstance(first, Image.Image)
        # Should keep original size
        assert first.size == (2000, 1500)


# ---------------------------------------------------------------------------
# _avg_confidence_tesseract
# ---------------------------------------------------------------------------

class TestAvgConfidenceTesseract:
    """Test confidence averaging."""

    def test_empty_data(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [], "text": []}
        assert _avg_confidence_tesseract(data) == 0.0

    def test_filters_low_confidence(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [90, 10, 80], "text": ["a", "b", "c"]}
        # Only 90 and 80 pass (>= 30), avg = 85
        assert _avg_confidence_tesseract(data) == 85.0

    def test_filters_empty_text(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [90, 80], "text": ["word", "  "]}
        # Only first passes (text is non-empty after strip)
        assert _avg_confidence_tesseract(data) == 90.0


# ---------------------------------------------------------------------------
# Blueprint integration (endpoint contract)
# ---------------------------------------------------------------------------

class TestOCRBlueprint:
    """Test the /api/ocr/ingredients endpoint contract is preserved."""

    @patch("services.ocr_service.dispatch_ocr", autospec=True)
    def test_post_returns_text(self, mock_dispatch, client):
        mock_dispatch.return_value = {
            "text": "sukker, mel",
            "provider": "Tesseract (Local)",
            "fallback": False,
        }
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "sukker, mel"

    def test_post_no_image_returns_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    @patch("services.ocr_service.dispatch_ocr", autospec=True)
    def test_post_empty_result(self, mock_dispatch, client):
        mock_dispatch.return_value = {
            "text": "",
            "provider": "Tesseract (Local)",
            "fallback": False,
        }
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == ""
        assert "error" in data  # "No text found in image"

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("bad input"), autospec=True)
    def test_post_value_error_returns_400(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "bad"},
        )
        assert resp.status_code == 400

    @patch("services.ocr_service.dispatch_ocr", side_effect=RuntimeError("boom"), autospec=True)
    def test_post_runtime_error_returns_500(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 500


# MIME type extraction and propagation
# ---------------------------------------------------------------------------


class TestMimeTypeExtraction:
    """dispatch_ocr() should extract and propagate MIME type to providers."""

    def test_jpeg_data_uri_passes_correct_mime_to_gemini(self):
        """Gemini should receive image/jpeg when the data URI declares JPEG."""
        mock_response = types.SimpleNamespace(text="sukker")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        jpeg_bytes = _make_tiny_jpeg()
        jpeg_uri = f"data:image/jpeg;base64,{_b64(jpeg_bytes)}"

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                with patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(jpeg_uri)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        inline_data = contents[0]["parts"][0]["inline_data"]
        assert inline_data["mime_type"] == "image/jpeg"

    def test_png_data_uri_passes_correct_mime_to_gemini(self):
        """Gemini should receive image/png when the data URI declares PNG."""
        mock_response = types.SimpleNamespace(text="mel")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        png_bytes = _make_tiny_png()
        png_uri = f"data:image/png;base64,{_b64(png_bytes)}"

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                with patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(png_uri)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        inline_data = contents[0]["parts"][0]["inline_data"]
        assert inline_data["mime_type"] == "image/png"

    def test_jpeg_data_uri_passes_correct_mime_to_openai(self):
        """OpenAI data URI should contain image/jpeg when input is JPEG."""
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredienser"))]
        )

        jpeg_bytes = _make_tiny_jpeg()
        jpeg_uri = f"data:image/jpeg;base64,{_b64(jpeg_bytes)}"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                with patch("services.settings_service.get_ocr_backend", return_value="openai", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(jpeg_uri)

        call_args = mock_cls.return_value.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        image_url = messages[0]["content"][0]["image_url"]["url"]
        assert image_url.startswith("data:image/jpeg;base64,")

    def test_png_data_uri_passes_correct_mime_to_openai(self):
        """OpenAI data URI should contain image/png when input is PNG."""
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredienser"))]
        )

        png_bytes = _make_tiny_png()
        png_uri = f"data:image/png;base64,{_b64(png_bytes)}"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                with patch("services.settings_service.get_ocr_backend", return_value="openai", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(png_uri)

        call_args = mock_cls.return_value.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        image_url = messages[0]["content"][0]["image_url"]["url"]
        assert image_url.startswith("data:image/png;base64,")

    def test_jpeg_data_uri_passes_correct_media_type_to_claude(self):
        """Claude Vision should receive media_type=image/jpeg when input is JPEG."""
        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="sukker")])

        jpeg_bytes = _make_tiny_jpeg()
        jpeg_uri = f"data:image/jpeg;base64,{_b64(jpeg_bytes)}"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(jpeg_uri)

        call_args = mock_cls.return_value.messages.create.call_args
        messages = call_args[1]["messages"]
        source = messages[0]["content"][0]["source"]
        assert source["media_type"] == "image/jpeg"

    def test_png_data_uri_passes_correct_media_type_to_claude(self):
        """Claude Vision should receive media_type=image/png when input is PNG."""
        mock_msg = types.SimpleNamespace(content=[types.SimpleNamespace(text="mel")])

        png_bytes = _make_tiny_png()
        png_uri = f"data:image/png;base64,{_b64(png_bytes)}"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_msg
                with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(png_uri)

        call_args = mock_cls.return_value.messages.create.call_args
        messages = call_args[1]["messages"]
        source = messages[0]["content"][0]["source"]
        assert source["media_type"] == "image/png"


class TestMagicByteFallback:
    """dispatch_ocr() should detect format from magic bytes when no data URI."""

    def test_raw_jpeg_base64_defaults_to_jpeg(self):
        """Raw JPEG base64 (no data URI) should be detected as image/jpeg."""
        mock_response = types.SimpleNamespace(text="sukker")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        jpeg_bytes = _make_tiny_jpeg()
        raw_b64 = _b64(jpeg_bytes)  # no data URI prefix

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                with patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(raw_b64)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        inline_data = contents[0]["parts"][0]["inline_data"]
        assert inline_data["mime_type"] == "image/jpeg"

    def test_raw_png_base64_detects_png(self):
        """Raw PNG base64 (no data URI) should be detected as image/png."""
        mock_response = types.SimpleNamespace(text="mel")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)

        png_bytes = _make_tiny_png()
        raw_b64 = _b64(png_bytes)  # no data URI prefix

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
                with patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(raw_b64)

        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        inline_data = contents[0]["parts"][0]["inline_data"]
        assert inline_data["mime_type"] == "image/png"

    def test_unknown_magic_bytes_defaults_to_jpeg(self):
        """When magic bytes are unrecognized, _detect_mime_type defaults to image/jpeg.

        Uses OpenAI provider since Gemini overrides MIME type via _convert_for_gemini.
        """
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )

        # Bytes with unknown magic bytes (not JPEG or PNG)
        unknown_bytes = b"\x00\x01\x02\x03" + b"\xff" * 200
        raw_b64 = _b64(unknown_bytes)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI") as mock_cls:
                mock_cls.return_value.chat.completions.create.return_value = mock_response
                with patch("services.settings_service.get_ocr_backend", return_value="openai", autospec=True):
                    from services.ocr_service import dispatch_ocr
                    dispatch_ocr(raw_b64)

        call_args = mock_cls.return_value.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        image_url = messages[0]["content"][0]["image_url"]["url"]
        assert image_url.startswith("data:image/jpeg;base64,")


class TestBlueprintErrorMessages:
    """OCR blueprint should include provider name in error responses."""

    @patch("services.ocr_service.dispatch_ocr", side_effect=ValueError("No image provided"), autospec=True)
    def test_value_error_returns_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json={"image": "bad"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "error_type" in data

    @patch("services.ocr_service.dispatch_ocr", side_effect=RuntimeError("provider failed"), autospec=True)
    def test_runtime_error_returns_500_with_error_detail(self, mock_dispatch, client):
        resp = client.post("/api/ocr/ingredients", json={"image": "dGVzdA=="})
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data
        assert "error_type" in data


# ---------------------------------------------------------------------------
# Fix 2: dispatch_ocr() must honor ocr_fallback_to_tesseract setting
# ---------------------------------------------------------------------------

class TestDispatchOcrFallbackSetting:
    """dispatch_ocr() should respect ocr_fallback_to_tesseract user preference."""

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_fallback_allowed_when_setting_enabled(self, mock_output, mock_itd, app_ctx):
        """When fallback is enabled and provider unavailable, fall back to tesseract."""
        from services.ocr_settings_service import save_ocr_settings

        # Select claude_vision but no API key → unavailable; enable fallback
        save_ocr_settings("claude_vision", fallback_to_tesseract=True)

        mock_itd.return_value = _make_tesseract_data(
            texts=["sukker"], confs=[90]
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            from services.ocr_service import dispatch_ocr

            png_bytes = _make_tiny_png()
            result = dispatch_ocr(_b64(png_bytes))

            assert result["fallback"] is True
            assert "sukker" in result["text"]

    def test_fallback_blocked_when_setting_disabled(self, app_ctx):
        """When fallback is disabled and provider unavailable, raise ValueError."""
        from services.ocr_settings_service import save_ocr_settings

        # Select claude_vision but no API key → unavailable; disable fallback
        save_ocr_settings("claude_vision", fallback_to_tesseract=False)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            from services.ocr_service import dispatch_ocr

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="unavailable"):
                dispatch_ocr(_b64(png_bytes))

    @patch("pytesseract.image_to_data", autospec=True)
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_no_fallback_when_provider_available(self, mock_output, mock_itd, app_ctx):
        """When selected provider is available (tesseract), no fallback occurs."""
        from services.ocr_settings_service import save_ocr_settings

        save_ocr_settings("tesseract", fallback_to_tesseract=False)

        mock_itd.return_value = _make_tesseract_data(
            texts=["mel"], confs=[85]
        )

        from services.ocr_service import dispatch_ocr

        png_bytes = _make_tiny_png()
        result = dispatch_ocr(_b64(png_bytes))

        assert result["fallback"] is False


# ---------------------------------------------------------------------------
# Fix 3: _OCR_BACKEND module-level env var should be removed
# ---------------------------------------------------------------------------

class TestLegacyEnvVarRemoved:
    """The unused _OCR_BACKEND module-level variable should no longer exist."""

    def test_ocr_backend_module_var_removed(self):
        """services.ocr_service should not have _OCR_BACKEND attribute."""
        import services.ocr_service as mod

        assert not hasattr(mod, "_OCR_BACKEND"), (
            "_OCR_BACKEND module-level variable should be removed"
        )


# ---------------------------------------------------------------------------
# LSO-383: _extract_gemini must pass raw bytes to inline_data.data
# ---------------------------------------------------------------------------

@patch("services.settings_service.get_ocr_backend", return_value="gemini", autospec=True)
class TestGeminiRawBytesPassthrough:
    """_extract_gemini must pass raw image_bytes (not a base64 string) to inline_data.data."""

    def _patch_genai(self, mock_client):
        mock_genai = types.SimpleNamespace(Client=lambda **kw: mock_client)
        mock_google = types.SimpleNamespace(genai=mock_genai)
        return patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}), mock_genai

    def test_inline_data_receives_bytes_not_string(self, _mock_backend):
        """inline_data.data must be bytes, not a base64-encoded string."""
        from services.ocr_service import extract_text

        mock_response = types.SimpleNamespace(text="sukker, mel")

        mock_client = MagicMock(spec=["models"])
        mock_client.models.generate_content.return_value = mock_response

        patcher, _mock_genai = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                png_bytes = _make_tiny_png()
                extract_text(_b64(png_bytes))

                call_kwargs = mock_client.models.generate_content.call_args
                contents = call_kwargs[1]["contents"]
                inline_data = contents[0]["parts"][0]["inline_data"]
                assert isinstance(inline_data["data"], bytes), (
                    "inline_data.data must be raw bytes, not a string — "
                    "passing a base64 string causes double-encoding (LSO-383)"
                )
