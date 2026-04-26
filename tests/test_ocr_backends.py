"""Tests for services/ocr_backends/ — all 6 backends with mocked external calls."""
import io
import base64
import types
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from tests.mock_shape_validator import (
    validate_openai_response_shape,
    validate_gemini_response_shape,
    validate_claude_response_shape,
)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _tiny_png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _tiny_jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(100, 100, 100)).save(buf, format="JPEG")
    return buf.getvalue()


def _tiny_bmp_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(50, 50, 50)).save(buf, format="BMP")
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# ── _get_api_key ──────────────────────────────────────────────────────────────


class TestGetApiKey:
    def test_raises_when_no_key_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends import _get_api_key
        with pytest.raises(ValueError, match="API key required"):
            _get_api_key("OPENAI_API_KEY")

    def test_returns_specific_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "my-key")
        from services.ocr_backends import _get_api_key
        assert _get_api_key("OPENAI_API_KEY") == "my-key"

    def test_falls_back_to_llm_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_API_KEY", "fallback-key")
        from services.ocr_backends import _get_api_key
        assert _get_api_key("OPENAI_API_KEY") == "fallback-key"


# ── OpenAI ────────────────────────────────────────────────────────────────────


class TestOpenAI:
    def test_success_returns_extracted_text(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="  sugar, flour  "))]
        )
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            result = _extract_openai(img, _b64(img), "image/png")
        assert result == "sugar, flour"

    def test_image_url_starts_with_data_uri(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            _extract_openai(img, _b64(img), "image/png")
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
            url = msgs[0]["content"][0]["image_url"]["url"]
            assert url.startswith("data:image/png;base64,")

    def test_empty_choices_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(choices=[])
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            result = _extract_openai(img, _b64(img))
        assert result == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.openai import _extract_openai
        with pytest.raises(ValueError, match="API key required"):
            _extract_openai(b"data", "b64data")


# ── OpenRouter ────────────────────────────────────────────────────────────────


class TestOpenRouter:
    def test_success_returns_text(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ingredients"))]
        )
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            result = _extract_openrouter(img, _b64(img))
        assert result == "ingredients"

    def test_default_model_is_gemini_flash(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            _extract_openrouter(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            model = call_kwargs[1].get("model") or call_kwargs[0][0]
            assert model == "google/gemini-2.0-flash-001"

    def test_empty_choices_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(choices=[])
        with patch("openai.OpenAI", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            assert _extract_openrouter(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.openrouter import _extract_openrouter
        with pytest.raises(ValueError, match="API key required"):
            _extract_openrouter(b"data", "b64")


# ── Groq ──────────────────────────────────────────────────────────────────────


class TestGroq:
    def test_success_returns_text(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="groq result"))]
        )
        with patch("groq.Groq", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            result = _extract_groq(img, _b64(img))
        assert result == "groq result"

    def test_model_is_llama(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
        )
        with patch("groq.Groq", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            _extract_groq(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            model = call_kwargs[1].get("model")
            assert "llama" in model

    def test_empty_choices_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(choices=[])
        with patch("groq.Groq", autospec=True) as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            assert _extract_groq(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.groq import _extract_groq
        with pytest.raises(ValueError, match="API key required"):
            _extract_groq(b"data", "b64")


# ── Claude ────────────────────────────────────────────────────────────────────


class TestClaude:
    def test_success_returns_text(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="  claude result  ")]
        )
        with patch("anthropic.Anthropic", autospec=True) as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            result = _extract_claude_vision(img, _b64(img))
        assert result == "claude result"

    def test_model_is_claude_sonnet(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="ok")]
        )
        with patch("anthropic.Anthropic", autospec=True) as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            _extract_claude_vision(img, _b64(img))
            call_kwargs = mock_cls.return_value.messages.create.call_args
            model = call_kwargs[1].get("model")
            assert "claude" in model.lower()

    def test_image_source_type_is_base64(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="ok")]
        )
        with patch("anthropic.Anthropic", autospec=True) as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            _extract_claude_vision(img, _b64(img))
            call_kwargs = mock_cls.return_value.messages.create.call_args
            msgs = call_kwargs[1].get("messages")
            source = msgs[0]["content"][0]["source"]
            assert source["type"] == "base64"

    def test_empty_content_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(content=[])
        with patch("anthropic.Anthropic", autospec=True) as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            assert _extract_claude_vision(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.claude import _extract_claude_vision
        with pytest.raises(ValueError, match="API key required"):
            _extract_claude_vision(b"data", "b64")


# ── Gemini ────────────────────────────────────────────────────────────────────


class TestGemini:
    def test_extract_gemini_returns_text(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(text="  gemini result  ")
        with patch("google.genai.Client", autospec=True) as mock_cls:
            mock_cls.return_value.models.generate_content.return_value = mock_response
            from services.ocr_backends.gemini import _extract_gemini
            result = _extract_gemini(img, _b64(img))
        assert result == "gemini result"

    def test_convert_jpeg_unchanged(self):
        from services.ocr_backends.gemini import _convert_for_gemini
        data = _tiny_jpeg_bytes()
        result_bytes, mime = _convert_for_gemini(data)
        assert mime == "image/jpeg"
        assert result_bytes == data

    def test_convert_png_unchanged(self):
        from services.ocr_backends.gemini import _convert_for_gemini
        data = _tiny_png_bytes()
        result_bytes, mime = _convert_for_gemini(data)
        assert mime == "image/png"
        assert result_bytes == data

    def test_convert_unsupported_converts_to_png(self):
        from services.ocr_backends.gemini import _convert_for_gemini
        data = _tiny_bmp_bytes()
        result_bytes, mime = _convert_for_gemini(data)
        assert mime == "image/png"
        assert result_bytes != data

    def test_svg_to_png_uses_cairosvg(self):
        import sys
        svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'></svg>"
        png_stub = b"\x89PNG\r\n\x1a\n"
        mock_cairosvg = MagicMock(spec=["svg2png"])
        mock_cairosvg.svg2png.return_value = png_stub
        with patch.dict(sys.modules, {"cairosvg": mock_cairosvg}):
            from services.ocr_backends.gemini import _svg_to_png
            result = _svg_to_png(svg)
        mock_cairosvg.svg2png.assert_called_once_with(bytestring=svg)
        assert result == png_stub

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.gemini import _extract_gemini
        with pytest.raises(ValueError, match="API key required"):
            _extract_gemini(b"data", "b64")


# ── Tesseract ─────────────────────────────────────────────────────────────────


class TestTesseract:
    def test_prepare_images_returns_two_variants(self):
        from services.ocr_backends.tesseract import _prepare_images
        variants = _prepare_images(_tiny_png_bytes())
        assert len(variants) == 2

    def test_prepare_images_are_pil_images(self):
        from services.ocr_backends.tesseract import _prepare_images
        variants = _prepare_images(_tiny_png_bytes())
        for v in variants:
            assert isinstance(v, Image.Image)

    def test_sort_and_join_orders_top_to_bottom(self):
        from services.ocr_backends.tesseract import _sort_and_join
        items = [
            {"left": 0, "top": 50, "width": 30, "height": 10, "text": "second"},
            {"left": 0, "top": 10, "width": 30, "height": 10, "text": "first"},
        ]
        result = _sort_and_join(items)
        assert result.index("first") < result.index("second")

    def test_sort_and_join_empty_returns_empty_string(self):
        from services.ocr_backends.tesseract import _sort_and_join
        assert _sort_and_join([]) == ""

    def test_extract_tesseract_uses_high_confidence_words(self, monkeypatch):
        from services.ocr_backends.tesseract import _extract_tesseract
        mock_data = {
            "text": ["sugar", "flour", "lowconf"],
            "conf": [90, 85, 10],
            "left": [0, 40, 80],
            "top": [0, 0, 0],
            "width": [30, 30, 30],
            "height": [10, 10, 10],
        }
        with patch("pytesseract.image_to_data", return_value=mock_data, autospec=True):
            result = _extract_tesseract(_tiny_png_bytes(), "b64")
        assert "sugar" in result
        assert "flour" in result
        assert "lowconf" not in result

    def test_extract_tesseract_empty_when_all_low_confidence(self, monkeypatch):
        from services.ocr_backends.tesseract import _extract_tesseract
        mock_data = {
            "text": ["bad", "words"],
            "conf": [5, 10],
            "left": [0, 40],
            "top": [0, 0],
            "width": [30, 30],
            "height": [10, 10],
        }
        with patch("pytesseract.image_to_data", return_value=mock_data, autospec=True):
            result = _extract_tesseract(_tiny_png_bytes(), "b64")
        assert result == ""


# ── Mock shape validation: canonical dict forms ────────────────────────────────


class TestOcrApiMockShapes:
    """Validate that the canonical dict forms of external API responses match their real shapes.

    If the real API changes its response structure, update these canonical dicts
    AND the corresponding validators in mock_shape_validator.py — these tests will
    fail to remind you to keep them in sync.
    """

    def test_openai_canonical_response_shape(self):
        canonical = {
            "choices": [
                {"message": {"role": "assistant", "content": "sugar, flour"}}
            ]
        }
        validate_openai_response_shape(canonical)

    def test_groq_canonical_response_shape(self):
        """Groq uses the OpenAI-compatible API format."""
        canonical = {
            "choices": [
                {"message": {"role": "assistant", "content": "ingredienser"}}
            ]
        }
        validate_openai_response_shape(canonical)

    def test_openrouter_canonical_response_shape(self):
        """OpenRouter uses the OpenAI-compatible API format."""
        canonical = {
            "choices": [
                {"message": {"role": "assistant", "content": "ingredients list"}}
            ]
        }
        validate_openai_response_shape(canonical)

    def test_gemini_canonical_response_shape(self):
        canonical = {"text": "sukker, mel, vann"}
        validate_gemini_response_shape(canonical)

    def test_claude_canonical_response_shape(self):
        canonical = {
            "content": [{"type": "text", "text": "ingredienser"}]
        }
        validate_claude_response_shape(canonical)

    def test_openai_rejects_missing_choices(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_openai_response_shape({"id": "chatcmpl-123"})

    def test_openai_rejects_empty_choices(self):
        with pytest.raises(AssertionError, match="Non-empty"):
            validate_openai_response_shape({"choices": []})

    def test_gemini_rejects_missing_text(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_gemini_response_shape({"candidates": []})

    def test_claude_rejects_empty_content(self):
        with pytest.raises(AssertionError, match="Non-empty"):
            validate_claude_response_shape({"content": []})
