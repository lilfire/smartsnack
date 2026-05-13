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
        with patch("openai.OpenAI") as mock_cls:
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
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            _extract_openai(img, _b64(img), "image/png")
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
            # system is msgs[0], user is msgs[1]
            url = msgs[1]["content"][0]["image_url"]["url"]
            assert url.startswith("data:image/png;base64,")

    def test_system_message_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_openai(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT

    def test_empty_choices_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(choices=[])
        with patch("openai.OpenAI") as mock_cls:
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
        with patch("openai.OpenAI") as mock_cls:
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
        with patch("openai.OpenAI") as mock_cls:
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
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            assert _extract_openrouter(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.openrouter import _extract_openrouter
        with pytest.raises(ValueError, match="API key required"):
            _extract_openrouter(b"data", "b64")

    def test_system_message_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_openrouter(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in msgs[0]["content"]


# ── Groq ──────────────────────────────────────────────────────────────────────


class TestGroq:
    def test_success_returns_text(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="groq result"))]
        )
        with patch("groq.Groq") as mock_cls:
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
        with patch("groq.Groq") as mock_cls:
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
        with patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            assert _extract_groq(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.groq import _extract_groq
        with pytest.raises(ValueError, match="API key required"):
            _extract_groq(b"data", "b64")

    def test_system_message_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="text"))]
        )
        with patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_groq(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT


# ── Claude ────────────────────────────────────────────────────────────────────


class TestClaude:
    def test_success_returns_text(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="  claude result  ")]
        )
        with patch("anthropic.Anthropic") as mock_cls:
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
        with patch("anthropic.Anthropic") as mock_cls:
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
        with patch("anthropic.Anthropic") as mock_cls:
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
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            assert _extract_claude_vision(img, _b64(img)) == ""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends.claude import _extract_claude_vision
        with pytest.raises(ValueError, match="API key required"):
            _extract_claude_vision(b"data", "b64")

    def test_system_prompt_is_sent(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="ok")]
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_claude_vision(img, _b64(img))
            call_kwargs = mock_cls.return_value.messages.create.call_args
            system_param = call_kwargs[1].get("system", "")
        assert system_param == _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in system_param
        assert "INTERNAL STEP 2" in system_param


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

    def test_system_instruction_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(text="text")
        with patch("google.genai.Client", autospec=True) as mock_cls:
            mock_cls.return_value.models.generate_content.return_value = mock_response
            from services.ocr_backends.gemini import _extract_gemini
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_gemini(img, _b64(img))
            call_kwargs = mock_cls.return_value.models.generate_content.call_args
            config = call_kwargs[1].get("config", {})
        assert config.get("system_instruction") == _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in config["system_instruction"]
        assert "INTERNAL STEP 2" in config["system_instruction"]


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


# ── looks_like_llm_refusal ────────────────────────────────────────────────────


class TestLooksLikeLlmRefusal:
    """The conversational-response detector that protects users from vision
    LLMs ignoring the prompt's empty-string rule for unreadable labels."""

    def test_real_claude_refusal_is_detected(self):
        """The exact response that triggered the original bug report."""
        from services.ocr_backends import looks_like_llm_refusal
        text = (
            "I'm happy to help, but I don't see an image of a food label. "
            "Please provide the image, and I'll extract the ingredient list "
            "and translate it into Norwegian (Bokmål) according to the rules."
        )
        assert looks_like_llm_refusal(text) is True

    @pytest.mark.parametrize("text", [
        "I'm happy to help, but I need a clearer image.",
        "I'd be happy to help once you share the photo.",
        "Sorry, I can't see the ingredients in this image.",
        "I'm sorry, the image is too blurry to read.",
        "Unfortunately, the image is unreadable.",
        "I'm unable to read the ingredient list from this image.",
        "I cannot see any text on this label.",
        "Please provide a clearer image of the label.",
        "Could you share a higher-resolution photo?",
        "I don't see an ingredient list in this image.",
        "No ingredient list is visible in the picture.",
        "The image appears to be blurry.",
        "This appears to be a photo of something else.",
    ])
    def test_conversational_responses_detected(self, text):
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal(text) is True

    def test_mixed_case_marker_is_detected(self):
        """Detection is case-insensitive."""
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal("I'M HAPPY TO HELP, BUT...") is True

    @pytest.mark.parametrize("text", [
        "Sukker, mel, vann, salt, gjær",
        "Hvetemel, sukker (15%), vann, palmeolje, salt",
        "Salt",
        "Vann, sukker, sitronsyre (E330), naturlige aromaer",
        "Wheat flour, water, yeast, salt",
        "Mjölk, socker, kakao, vaniljarom",
    ])
    def test_real_ingredient_lists_pass_through(self, text):
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal(text) is False

    @pytest.mark.parametrize("text", ["", "   ", "\n\n"])
    def test_empty_or_whitespace_returns_false(self, text):
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal(text) is False

    def test_none_returns_false(self):
        """Defensive: provider wrappers may pass through None on edge cases."""
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal(None) is False  # type: ignore[arg-type]


# ── LSO-1234: translate-fallback contract (paths A / B / C) ───────────────────
#
# The hardened system prompt (LSO-1232 / LSO-1234, PR #424) introduced a
# three-path output contract:
#
#   (A) extract — when the target-language section is present
#   (B) translate — when no target-language section is present but a readable
#       ingredient list exists in another language
#   (C) empty string — only when no readable ingredient list exists anywhere
#
# The original Chinese-label bug (LSO-1232) occurred because the LLM took
# path (C) when path (B) was correct AND leaked the reasoning prose
# "I will output an empty string" into the response. These tests lock the
# contract in: the prompt itself must drive the model toward (B) for any
# readable foreign-language list, and the dispatch layer must not tolerate
# reasoning-text leaks if the model misbehaves.


class TestTranslateFallbackPromptContract:
    """LSO-1234 §1: static assertions on the system prompt and per-language
    user-message closing line. No LLM call. These tests are intentionally
    paranoid about wording — they exist to fail loudly if a future edit
    removes the (A)/(B)/(C) contract or re-introduces hardcoded language
    names that violate the language-agnostic rule."""

    # The full set of language-name and language-vocab tokens that must NEVER
    # appear in the system prompt. These are the kinds of strings that, in
    # earlier prompt revisions (LSO-1227), biased the model toward specific
    # languages and caused regressions for any label whose script wasn't
    # represented in the hardcoded list.
    FORBIDDEN_LANGUAGE_TOKENS = (
        # Language names
        "Norwegian", "English", "Swedish", "German", "Italian",
        "Polish", "French", "Dutch", "Spanish",
        # Hardcoded foreign-language ingredient vocab
        "ZUCKER", "WEIZENMEHL", "INGREDIENSER", "INGREDIENTI",
        "ZUTATEN", "SKLADNIKI",
    )

    # Markers that must appear in the system prompt — the (A)/(B)/(C) contract
    # labels and the words that describe the translate path.
    REQUIRED_PROMPT_MARKERS = (
        "(A)", "(B)", "(C)", "translate", "target language",
    )

    @pytest.mark.parametrize("token", FORBIDDEN_LANGUAGE_TOKENS)
    def test_system_prompt_does_not_contain_language_specific_tokens(self, token):
        """LSO-1234: the system prompt must be language-agnostic. Hardcoded
        language names or foreign-language vocab in the system prompt biased
        the model toward those languages and broke labels in other scripts.
        The user message carries the target language, not the system prompt."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert token not in _HARDENED_SYSTEM_PROMPT, (
            f"Language-specific token {token!r} leaked into _HARDENED_SYSTEM_PROMPT — "
            "the system prompt must remain language-agnostic (LSO-1234)."
        )

    @pytest.mark.parametrize("marker", REQUIRED_PROMPT_MARKERS)
    def test_system_prompt_contains_required_markers(self, marker):
        """The (A)/(B)/(C) contract labels and translate/target-language
        wording must remain in the system prompt — they are how the model
        learns to take path B for foreign-language labels instead of path C."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert marker in _HARDENED_SYSTEM_PROMPT, (
            f"Required marker {marker!r} missing from _HARDENED_SYSTEM_PROMPT."
        )

    def test_per_language_user_messages_share_identical_closing_line(self):
        """LSO-1234: the closing instruction in build_ingredient_prompt must
        be the same language-agnostic line for every supported language. If
        a language-specific closing slips in, the per-language prompts will
        diverge and the contract will weaken for that language."""
        from services.ocr_backends import build_ingredient_prompt

        no_prompt = build_ingredient_prompt("no")
        en_prompt = build_ingredient_prompt("en")
        se_prompt = build_ingredient_prompt("se")

        # The closing line is the last non-empty line of each prompt.
        def _closing_line(prompt: str) -> str:
            return [ln for ln in prompt.splitlines() if ln.strip()][-1]

        no_close = _closing_line(no_prompt)
        en_close = _closing_line(en_prompt)
        se_close = _closing_line(se_prompt)

        assert no_close == en_close == se_close, (
            "Per-language prompts must end with the identical language-agnostic "
            f"closing line.\nno: {no_close!r}\nen: {en_close!r}\nse: {se_close!r}"
        )

    def test_closing_line_describes_translate_fallback(self):
        """The shared closing line must spell out the (A) extract / (B)
        translate / (C) empty contract in plain prose so the model has the
        instruction reinforced in the user message too."""
        from services.ocr_backends import build_ingredient_prompt

        prompt = build_ingredient_prompt("no")
        closing = [ln for ln in prompt.splitlines() if ln.strip()][-1].lower()
        assert "extracted if that language is present" in closing
        assert "translated from another language if not" in closing
        assert "empty string only if no readable ingredient list" in closing


class TestChineseLabelRegression:
    """LSO-1234 §2: regression for the Chinese-only label bug (LSO-1232).

    The original bug: the model took path (C) when path (B) was correct AND
    leaked reasoning prose into the response (e.g. "I will output an empty
    string"). Two complementary checks:

    * Snapshot/golden assertion: the system prompt explicitly forbids empty
      output when a readable ingredient list exists in any language.
    * Backend test: when the model misbehaves and emits reasoning prose, the
      dispatch layer's safety net converts it to empty so users see the
      no-text toast rather than the leaked reasoning text.
    """

    def test_system_prompt_forbids_empty_when_readable_list_exists(self):
        """Snapshot check: the prompt must explicitly route any readable
        foreign-language list to path (B), not path (C). This is the heart
        of the Chinese-label fix."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        # Collapse all internal whitespace runs into single spaces so the
        # assertions are stable against future re-indentation of the prompt.
        normalised = " ".join(_HARDENED_SYSTEM_PROMPT.split())

        # The prompt must spell out that empty (path C) is only for the
        # complete absence of a readable list — not for "list exists but is
        # in an unfamiliar language".
        assert "no readable ingredient list exists anywhere" in normalised
        # Path (B) must be described as a translation into the target language
        # (the wording that drives the Chinese case to translate, not empty).
        assert "translate it into the target language" in normalised
        # The "in another language" / "in any other language" wording is the
        # blanket fallback that covers Chinese, Arabic, Japanese, etc.
        assert (
            "list is readable in another language" in normalised
            or "list in any other language" in normalised
        ), (
            "Path (B) must describe the fallback in language-agnostic terms "
            "(e.g. 'in another language' / 'any other language') so any "
            "non-target-language readable list — Chinese, Arabic, Japanese, "
            "etc. — routes to translate, not empty."
        )

    def test_backend_does_not_pass_through_chinese_label_refusal(self, monkeypatch):
        """If a misbehaving model emits a conversational refusal about a
        Chinese-only label (the LSO-1232 bug shape), the dispatch safety
        net (looks_like_llm_refusal) must convert it to empty so the leaked
        reasoning never reaches the user. The safety net is a backstop —
        the real fix is the hardened prompt that drives path (B), but if
        the model misbehaves we still must not surface reasoning prose."""
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        # Variants of the LSO-1232 bug shape: the model refuses or apologises
        # about the Chinese-only label rather than translating it. Each
        # variant matches at least one marker in _CONVERSATIONAL_MARKERS so
        # the safety net catches it; if a future edit weakens the markers,
        # this test fires.
        leak_variants = [
            "Sorry, I cannot read the Chinese characters on this label.",
            "I'm unable to translate the Chinese ingredient list.",
            "I'm sorry, I don't see a Norwegian ingredient list — only Chinese.",
            "Unfortunately, the Chinese label is unreadable to me.",
            "I cannot see any ingredients I recognise on this label.",
        ]

        for leak in leak_variants:
            mock_message = types.SimpleNamespace(
                content=[types.SimpleNamespace(text=leak)]
            )
            with patch.multiple(
                "services.settings_service",
                get_ocr_backend=MagicMock(return_value="claude_vision"),
                get_language=MagicMock(return_value="no"),
            ), patch(
                "services.ocr_settings_service.get_model_for_provider",
                side_effect=RuntimeError,
            ), patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_message
                result = dispatch_ocr_bytes(_tiny_png_bytes())

            # The user must NEVER see the reasoning prose verbatim.
            assert result["text"] == "", (
                f"Refusal leak {leak!r} survived dispatch as {result['text']!r} — "
                "looks_like_llm_refusal safety net failed."
            )


class TestTranslateFallbackPromptEdgeCases:
    """LSO-1234 §3: edge cases for the (A)/(B)/(C) contract.

    These are assertions on the prompt text — we cannot drive a real vision
    model in CI, but we can prove the prompt language unambiguously routes
    each scenario to the correct path."""

    def test_arabic_only_label_routes_to_translate_path(self):
        """An Arabic-only label has no target-language (no/en/se) section
        but a readable ingredient list — the prompt must say path (B)
        applies, not path (C). The wording is generic ('any other language')
        rather than language-specific so Arabic is covered without listing
        it explicitly."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        normalised = " ".join(_HARDENED_SYSTEM_PROMPT.split())

        # The fallback rule must apply to "any other language" / "another
        # language" — that is what generalises to Arabic, Japanese, etc.
        assert (
            "any other language" in normalised
            or "in another language" in normalised
        )
        # And it must explicitly direct the model to translate, not return
        # empty.
        assert "translate it into the target language" in normalised
        # Path (C) — empty — is reserved for the no-readable-list case only.
        # The prompt must NOT say path (C) applies for foreign-language lists.
        # We assert the text describing path (C) only mentions absence/blank.
        path_c_block = _HARDENED_SYSTEM_PROMPT.split("(C)")[1].split("══")[0]
        assert "no readable ingredient list" in path_c_block

    def test_japanese_only_label_routes_to_translate_path(self):
        """Same generalisation as Arabic — the 'any other language' wording
        of path (B) covers Japanese-only labels too."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        # Path (B) must describe the language-agnostic translate behaviour.
        path_b_block = _HARDENED_SYSTEM_PROMPT.split("(B)")[1].split("(C)")[0]
        assert "translate" in path_b_block.lower()
        assert "target language" in path_b_block.lower()
        # Must NOT enumerate specific languages — that would silently exclude
        # Japanese (or any other language not on the list).
        for lang in (
            "Norwegian", "English", "Swedish", "German", "Italian",
            "Polish", "French", "Dutch", "Spanish", "Japanese", "Arabic",
            "Chinese",
        ):
            assert lang not in path_b_block, (
                f"Path (B) block enumerates specific language {lang!r} — "
                "it must remain language-agnostic."
            )

    def test_blank_label_routes_to_empty_path(self):
        """A blank or unreadable label has no readable list anywhere — the
        prompt must route this to path (C) and only path (C)."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        # Path (C) block must mention the unreadable / blank / non-food
        # cases, and must instruct an empty string.
        path_c_block = _HARDENED_SYSTEM_PROMPT.split("(C)")[1].split("══")[0]
        assert "empty string" in path_c_block.lower()
        assert "no readable ingredient list exists anywhere" in path_c_block
        # Examples in path (C) should cover the blank-label case.
        assert "blank" in path_c_block.lower() or "unreadable" in path_c_block.lower()
        # And the FINAL CHECK at the end of the prompt must reinforce that
        # path (C) means literally zero characters.
        final_check = _HARDENED_SYSTEM_PROMPT.split("FINAL CHECK")[1]
        assert "Path C" in final_check
        assert "Zero characters" in final_check or "ZERO characters" in final_check or (
            "zero characters" in final_check.lower()
        )

    def test_multilingual_label_with_target_section_routes_to_extract_path(self):
        """When the target-language ingredient section IS present in a
        multilingual label, path (A) — extract — must apply, not path (B).
        Translating an existing target-language section would be wasteful
        and risk losing fidelity."""
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        # Path (A) block must describe extract-when-present behaviour.
        path_a_block = _HARDENED_SYSTEM_PROMPT.split("(A)")[1].split("(B)")[0]
        path_a_normalised = " ".join(path_a_block.split()).lower()
        assert (
            "target-language" in path_a_normalised
            or "target language" in path_a_normalised
        )
        assert "extract" in path_a_normalised
        # Path (B) must be conditioned on "no target-language section" —
        # i.e. the model only translates when the target section is absent.
        path_b_block = _HARDENED_SYSTEM_PROMPT.split("(B)")[1].split("(C)")[0]
        path_b_normalised = " ".join(path_b_block.split()).lower()
        assert (
            "no target-language section" in path_b_normalised
            or "no target language section" in path_b_normalised
        )
        # And INTERNAL STEP 1 must describe the search order: target
        # language first, fall back to any other language only if absent.
        step1_block = _HARDENED_SYSTEM_PROMPT.split("INTERNAL STEP 1")[1].split(
            "INTERNAL STEP 2"
        )[0]
        assert "search for the target-language ingredient section" in step1_block
        # Fallback wording must come AFTER the target-language search.
        target_idx = step1_block.find("search for the target-language")
        fallback_idx = step1_block.find("search for an ingredient list in any")
        assert 0 <= target_idx < fallback_idx, (
            "INTERNAL STEP 1 must search for the target-language section "
            "BEFORE falling back to other languages."
        )
