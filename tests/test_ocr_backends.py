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
"""Tests for services.ocr_backends — prompt builder, system prompt, and backends.

Strategy:
- Stub classes below document the minimal interface of each third-party SDK.
  create_autospec() enforces shape conformance on mocks (Rule 8).
- All SDK imports inside backend functions are lazy, so we inject fakes via
  sys.modules before calling extract(); monkeypatch restores state afterward.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, create_autospec

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# SDK interface stubs — must track the real SDK signatures (Rule 8)
# ─────────────────────────────────────────────────────────────────────────────


class _AnthropicMessages:
    """Matches anthropic.resources.Messages.create() call signature."""

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list,
    ) -> object: ...


class _AnthropicClientStub:
    """Matches anthropic.Anthropic() instance interface."""

    messages = _AnthropicMessages()  # instance attr so create_autospec picks it up


class _ChatCompletionMessage:
    def __init__(self):
        self.content = ""


class _ChatCompletionChoice:
    def __init__(self):
        self.message = _ChatCompletionMessage()


class _ChatCompletionResult:
    def __init__(self):
        self.choices = [_ChatCompletionChoice()]


class _OpenAICompletions:
    """Matches openai.resources.chat.Completions.create() call signature."""

    def create(
        self,
        *,
        model: str,
        messages: list,
        max_tokens: int,
    ) -> _ChatCompletionResult: ...


class _OpenAIChat:
    completions = _OpenAICompletions()  # instance attr so create_autospec picks it up


class _OpenAIClientStub:
    """Matches openai.OpenAI() instance interface."""

    chat = _OpenAIChat()  # instance attr so create_autospec picks it up


class _GeminiGenerateContentResult:
    def __init__(self):
        self.text = ""


class _GeminiModelStub:
    """Matches google.generativeai.GenerativeModel instance interface."""

    def generate_content(self, contents: list) -> _GeminiGenerateContentResult: ...


class _GroqClientStub:
    """Matches groq.Groq() instance interface (same shape as OpenAI)."""

    chat = _OpenAIChat()  # instance attr so create_autospec picks it up


# ─────────────────────────────────────────────────────────────────────────────
# Factory helpers — build fake SDK modules with predictable responses
# ─────────────────────────────────────────────────────────────────────────────


def _make_anthropic_module(response_text: str):
    """Return (fake_module, mock_client) with autospec-shaped mock."""
    mock_client = create_autospec(_AnthropicClientStub, instance=True)
    msg = MagicMock()
    block = MagicMock()
    block.text = response_text
    msg.content = [block]
    mock_client.messages.create.return_value = msg

    fake = ModuleType("anthropic")
    fake.Anthropic = MagicMock(return_value=mock_client)
    return fake, mock_client


def _make_openai_module(response_text: str, module_name: str = "openai"):
    """Return (fake_module, mock_client) with autospec-shaped mock."""
    mock_client = create_autospec(_OpenAIClientStub, instance=True)
    choice = MagicMock()
    choice.message.content = response_text
    mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    fake = ModuleType(module_name)
    fake.OpenAI = MagicMock(return_value=mock_client)
    return fake, mock_client


def _make_gemini_modules(response_text: str):
    """Return (fake_genai_module, mock_model) with autospec-shaped mock."""
    mock_model = create_autospec(_GeminiModelStub, instance=True)
    mock_model.generate_content.return_value = MagicMock(text=response_text)

    fake_genai = ModuleType("google.generativeai")
    fake_genai.GenerativeModel = MagicMock(return_value=mock_model)

    fake_google = ModuleType("google")
    fake_google.generativeai = fake_genai
    return fake_genai, fake_google, mock_model


def _make_groq_module(response_text: str):
    """Return (fake_module, mock_client) with autospec-shaped mock."""
    mock_client = create_autospec(_GroqClientStub, instance=True)
    choice = MagicMock()
    choice.message.content = response_text
    mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    fake = ModuleType("groq")
    fake.Groq = MagicMock(return_value=mock_client)
    return fake, mock_client


# ─────────────────────────────────────────────────────────────────────────────
# Tests — build_ingredient_prompt
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildIngredientPrompt:
    def test_norwegian_language_field(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Language: Norwegian" in build_ingredient_prompt("no")

    def test_english_language_field(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Language: English" in build_ingredient_prompt("en")

    def test_swedish_language_field(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Language: Swedish" in build_ingredient_prompt("se")

    @pytest.mark.parametrize("term", ["MELK", "EGG", "HVETE", "GLUTEN", "SOYA", "SESAM", "FISK"])
    def test_norwegian_allergen_terms_all_caps(self, term):
        from services.ocr_backends import build_ingredient_prompt

        assert term in build_ingredient_prompt("no"), f"Expected {term!r} in Norwegian prompt"

    @pytest.mark.parametrize("term", ["MILK", "EGGS", "WHEAT", "GLUTEN", "SOY", "SESAME", "FISH"])
    def test_english_allergen_terms_all_caps(self, term):
        from services.ocr_backends import build_ingredient_prompt

        assert term in build_ingredient_prompt("en"), f"Expected {term!r} in English prompt"

    @pytest.mark.parametrize("term", ["MJÖLK", "ÄGG", "VETE", "GLUTEN", "SOJA", "SESAM", "FISK"])
    def test_swedish_allergen_terms_all_caps(self, term):
        from services.ocr_backends import build_ingredient_prompt

        assert term in build_ingredient_prompt("se"), f"Expected {term!r} in Swedish prompt"

    def test_norwegian_decimal_separator_comma(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Decimal separator: ," in build_ingredient_prompt("no")

    def test_english_decimal_separator_period(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Decimal separator: ." in build_ingredient_prompt("en")

    def test_swedish_decimal_separator_comma(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Decimal separator: ," in build_ingredient_prompt("se")

    def test_norwegian_trace_notice_template(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Kan inneholde spor av {items}." in build_ingredient_prompt("no")

    def test_english_trace_notice_template(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "May contain traces of {items}." in build_ingredient_prompt("en")

    def test_swedish_trace_notice_template(self):
        from services.ocr_backends import build_ingredient_prompt

        assert "Kan innehålla spår av {items}." in build_ingredient_prompt("se")

    def test_unsupported_language_raises_value_error(self):
        from services.ocr_backends import build_ingredient_prompt

        with pytest.raises(ValueError, match="Unsupported language"):
            build_ingredient_prompt("de")

    def test_empty_string_language_raises_value_error(self):
        from services.ocr_backends import build_ingredient_prompt

        with pytest.raises(ValueError, match="Unsupported language"):
            build_ingredient_prompt("")

    def test_none_language_raises(self):
        from services.ocr_backends import build_ingredient_prompt

        with pytest.raises((ValueError, TypeError, AttributeError)):
            build_ingredient_prompt(None)  # type: ignore[arg-type]

    def test_all_languages_return_nonempty_string(self):
        from services.ocr_backends import build_ingredient_prompt

        for lang in ("no", "en", "se"):
            result = build_ingredient_prompt(lang)
            assert isinstance(result, str) and len(result) > 0

    def test_each_language_prompt_is_distinct(self):
        from services.ocr_backends import build_ingredient_prompt

        prompts = {lang: build_ingredient_prompt(lang) for lang in ("no", "en", "se")}
        assert len(set(prompts.values())) == 3, "All language prompts must be unique"


# ─────────────────────────────────────────────────────────────────────────────
# Tests — _HARDENED_SYSTEM_PROMPT language-agnosticism
# ─────────────────────────────────────────────────────────────────────────────


class TestHardenedSystemPrompt:
    def test_no_hardcoded_language_names(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        for name in ("Norwegian", "English", "Swedish"):
            assert name not in _HARDENED_SYSTEM_PROMPT, (
                f"System prompt must be language-agnostic — found hardcoded {name!r}"
            )

    def test_no_hardcoded_allergen_vocabulary(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        for term in ("MELK", "MJÖLK", "MILK", "HVETE", "VETE", "WHEAT"):
            assert term not in _HARDENED_SYSTEM_PROMPT, (
                f"System prompt must not hardcode allergen vocab — found {term!r}"
            )

    def test_has_four_step_structure(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        for step in ("Step 1", "Step 2", "Step 3", "Step 4"):
            assert step in _HARDENED_SYSTEM_PROMPT, f"Missing {step!r} in system prompt"

    def test_is_nonempty_string(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        assert isinstance(_HARDENED_SYSTEM_PROMPT, str)
        assert len(_HARDENED_SYSTEM_PROMPT) > 100


# ─────────────────────────────────────────────────────────────────────────────
# Tests — backward-compat alias
# ─────────────────────────────────────────────────────────────────────────────


class TestIngredientPromptAlias:
    def test_alias_exists_and_is_string(self):
        from services.ocr_backends import _INGREDIENT_PROMPT

        assert isinstance(_INGREDIENT_PROMPT, str) and len(_INGREDIENT_PROMPT) > 0

    def test_alias_equals_norwegian_prompt(self):
        from services.ocr_backends import _INGREDIENT_PROMPT, build_ingredient_prompt

        assert _INGREDIENT_PROMPT == build_ingredient_prompt("no")


# ─────────────────────────────────────────────────────────────────────────────
# Tests — Claude backend
# ─────────────────────────────────────────────────────────────────────────────


class TestClaudeBackend:
    def test_passes_system_prompt_as_system_param(self, monkeypatch):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        fake, mock_client = _make_anthropic_module("mel, sukker")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        extract("dGVzdA==", "no")

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["system"] == _HARDENED_SYSTEM_PROMPT

    def test_user_message_contains_language_prompt(self, monkeypatch):
        from services.ocr_backends import build_ingredient_prompt

        fake, mock_client = _make_anthropic_module("mel, sukker")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        extract("dGVzdA==", "no")

        kwargs = mock_client.messages.create.call_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        texts = [c["text"] for c in user_content if c.get("type") == "text"]
        expected = build_ingredient_prompt("no")
        assert any(expected in t for t in texts)

    def test_user_message_contains_image_block(self, monkeypatch):
        fake, mock_client = _make_anthropic_module("mel")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.messages.create.call_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        image_blocks = [c for c in user_content if c.get("type") == "image"]
        assert len(image_blocks) == 1

    def test_returns_stripped_text(self, monkeypatch):
        fake, _ = _make_anthropic_module("  mel, sukker  ")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        assert extract("dGVzdA==", "no") == "mel, sukker"

    def test_different_language_in_user_message(self, monkeypatch):
        from services.ocr_backends import build_ingredient_prompt

        fake, mock_client = _make_anthropic_module("milk, sugar")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.messages.create.call_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        texts = [c["text"] for c in user_content if c.get("type") == "text"]
        assert any("Language: English" in t for t in texts)

    def test_sdk_not_installed_raises_runtime_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)

        from services.ocr_backends.claude import extract

        with pytest.raises((RuntimeError, ImportError)):
            extract("dGVzdA==", "no")

    def test_data_uri_input_parsed_correctly(self, monkeypatch):
        fake, mock_client = _make_anthropic_module("mel")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends.claude import extract

        extract("data:image/png;base64,dGVzdA==", "no")

        kwargs = mock_client.messages.create.call_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        image_blocks = [c for c in user_content if c.get("type") == "image"]
        assert image_blocks[0]["source"]["media_type"] == "image/png"
        assert image_blocks[0]["source"]["data"] == "dGVzdA=="


# ─────────────────────────────────────────────────────────────────────────────
# Tests — OpenAI backend
# ─────────────────────────────────────────────────────────────────────────────


class TestOpenAIBackend:
    def test_passes_system_role_message(self, monkeypatch):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        fake, mock_client = _make_openai_module("flour, milk")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openai import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        system_msgs = [m for m in kwargs["messages"] if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT

    def test_user_content_has_image_url_and_text(self, monkeypatch):
        fake, mock_client = _make_openai_module("flour")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openai import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msgs = [m for m in kwargs["messages"] if m.get("role") == "user"]
        content_types = {c["type"] for c in user_msgs[0]["content"]}
        assert "image_url" in content_types
        assert "text" in content_types

    def test_returns_stripped_text(self, monkeypatch):
        fake, _ = _make_openai_module("  flour, milk  ")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openai import extract

        assert extract("dGVzdA==", "en") == "flour, milk"

    def test_user_text_contains_language_prompt(self, monkeypatch):
        from services.ocr_backends import build_ingredient_prompt

        fake, mock_client = _make_openai_module("flour")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openai import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msgs = [m for m in kwargs["messages"] if m.get("role") == "user"]
        texts = [c["text"] for c in user_msgs[0]["content"] if c.get("type") == "text"]
        expected = build_ingredient_prompt("en")
        assert any(expected in t for t in texts)

    def test_sdk_not_installed_raises_runtime_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "openai", None)

        from services.ocr_backends.openai import extract

        with pytest.raises((RuntimeError, ImportError)):
            extract("dGVzdA==", "en")


# ─────────────────────────────────────────────────────────────────────────────
# Tests — Gemini backend
# ─────────────────────────────────────────────────────────────────────────────


class TestGeminiBackend:
    def _inject(self, monkeypatch, response_text: str):
        fake_genai, fake_google, mock_model = _make_gemini_modules(response_text)
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)
        return fake_genai, mock_model

    def test_system_instruction_passed_to_model(self, monkeypatch):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        fake_genai, mock_model = self._inject(monkeypatch, "mjöl, socker")

        from services.ocr_backends.gemini import extract

        extract("dGVzdA==", "se")

        fake_genai.GenerativeModel.assert_called_once()
        call_kwargs = fake_genai.GenerativeModel.call_args.kwargs
        assert call_kwargs.get("system_instruction") == _HARDENED_SYSTEM_PROMPT

    def test_generate_content_called_with_image_and_text(self, monkeypatch):
        fake_genai, mock_model = self._inject(monkeypatch, "mjöl")

        from services.ocr_backends.gemini import extract

        extract("dGVzdA==", "se")

        mock_model.generate_content.assert_called_once()
        contents = mock_model.generate_content.call_args.args[0]
        assert len(contents) >= 2

    def test_returns_stripped_text(self, monkeypatch):
        fake_genai, _ = self._inject(monkeypatch, "  mjöl, socker  ")

        from services.ocr_backends.gemini import extract

        assert extract("dGVzdA==", "se") == "mjöl, socker"

    def test_sdk_not_installed_raises_runtime_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "google", None)
        monkeypatch.setitem(sys.modules, "google.generativeai", None)

        from services.ocr_backends.gemini import extract

        with pytest.raises((RuntimeError, ImportError)):
            extract("dGVzdA==", "se")


# ─────────────────────────────────────────────────────────────────────────────
# Tests — Groq backend
# ─────────────────────────────────────────────────────────────────────────────


class TestGroqBackend:
    def test_passes_system_role_message(self, monkeypatch):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        fake, mock_client = _make_groq_module("mel, mjölk")
        monkeypatch.setitem(sys.modules, "groq", fake)

        from services.ocr_backends.groq import extract

        extract("dGVzdA==", "no")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        system_msgs = [m for m in kwargs["messages"] if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT

    def test_user_content_has_image_url_and_text(self, monkeypatch):
        fake, mock_client = _make_groq_module("mel")
        monkeypatch.setitem(sys.modules, "groq", fake)

        from services.ocr_backends.groq import extract

        extract("dGVzdA==", "no")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msgs = [m for m in kwargs["messages"] if m.get("role") == "user"]
        content_types = {c["type"] for c in user_msgs[0]["content"]}
        assert "image_url" in content_types
        assert "text" in content_types

    def test_returns_stripped_text(self, monkeypatch):
        fake, _ = _make_groq_module("  mel, sukker  ")
        monkeypatch.setitem(sys.modules, "groq", fake)

        from services.ocr_backends.groq import extract

        assert extract("dGVzdA==", "no") == "mel, sukker"

    def test_sdk_not_installed_raises_runtime_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "groq", None)

        from services.ocr_backends.groq import extract

        with pytest.raises((RuntimeError, ImportError)):
            extract("dGVzdA==", "no")


# ─────────────────────────────────────────────────────────────────────────────
# Tests — OpenRouter backend
# ─────────────────────────────────────────────────────────────────────────────


class TestOpenRouterBackend:
    def test_passes_system_role_message(self, monkeypatch):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT

        fake, mock_client = _make_openai_module("flour, sugar")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openrouter import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        system_msgs = [m for m in kwargs["messages"] if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == _HARDENED_SYSTEM_PROMPT

    def test_uses_openrouter_base_url(self, monkeypatch):
        fake, _ = _make_openai_module("flour")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openrouter import extract

        extract("dGVzdA==", "en")

        init_kwargs = fake.OpenAI.call_args.kwargs
        assert "openrouter" in init_kwargs.get("base_url", "").lower()

    def test_returns_stripped_text(self, monkeypatch):
        fake, _ = _make_openai_module("  flour, sugar  ")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openrouter import extract

        assert extract("dGVzdA==", "en") == "flour, sugar"

    def test_user_content_has_image_url_and_text(self, monkeypatch):
        fake, mock_client = _make_openai_module("flour")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends.openrouter import extract

        extract("dGVzdA==", "en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msgs = [m for m in kwargs["messages"] if m.get("role") == "user"]
        content_types = {c["type"] for c in user_msgs[0]["content"]}
        assert "image_url" in content_types
        assert "text" in content_types


# ─────────────────────────────────────────────────────────────────────────────
# Tests — dispatch_ocr (integration)
# ─────────────────────────────────────────────────────────────────────────────


class TestDispatchOcr:
    def test_unknown_backend_raises_value_error(self):
        from services.ocr_backends import dispatch_ocr

        with pytest.raises(ValueError, match="Unknown OCR backend"):
            dispatch_ocr("dGVzdA==", backend="nonexistent", language="no")

    def test_empty_backend_raises_value_error(self):
        from services.ocr_backends import dispatch_ocr

        with pytest.raises(ValueError, match="Unknown OCR backend"):
            dispatch_ocr("dGVzdA==", backend="", language="no")

    def test_unsupported_language_raises_for_claude(self, monkeypatch):
        fake, _ = _make_anthropic_module("text")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends import dispatch_ocr

        with pytest.raises(ValueError, match="Unsupported language"):
            dispatch_ocr("dGVzdA==", backend="claude", language="de")

    def test_unsupported_language_raises_for_openai(self, monkeypatch):
        fake, _ = _make_openai_module("text")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends import dispatch_ocr

        with pytest.raises(ValueError, match="Unsupported language"):
            dispatch_ocr("dGVzdA==", backend="openai", language="fr")

    def test_dispatches_claude_and_returns_result(self, monkeypatch):
        fake, mock_client = _make_anthropic_module("mel, sukker")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="claude", language="no")

        assert result == "mel, sukker"
        mock_client.messages.create.assert_called_once()

    def test_dispatches_openai_and_returns_result(self, monkeypatch):
        fake, mock_client = _make_openai_module("flour, milk")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="openai", language="en")

        assert result == "flour, milk"
        mock_client.chat.completions.create.assert_called_once()

    def test_dispatches_groq_and_returns_result(self, monkeypatch):
        fake, mock_client = _make_groq_module("mel")
        monkeypatch.setitem(sys.modules, "groq", fake)

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="groq", language="no")

        assert result == "mel"
        mock_client.chat.completions.create.assert_called_once()

    def test_dispatches_openrouter_and_returns_result(self, monkeypatch):
        fake, mock_client = _make_openai_module("flour, sugar")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="openrouter", language="en")

        assert result == "flour, sugar"
        mock_client.chat.completions.create.assert_called_once()

    def test_dispatches_gemini_and_returns_result(self, monkeypatch):
        fake_genai, fake_google, mock_model = _make_gemini_modules("mjöl, socker")
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="gemini", language="se")

        assert result == "mjöl, socker"
        mock_model.generate_content.assert_called_once()

    def test_tesseract_ignores_language_and_returns_result(self, monkeypatch):
        monkeypatch.setattr("services.ocr_service.extract_text", lambda _: "mel, sukker")

        from services.ocr_backends import dispatch_ocr

        result = dispatch_ocr("dGVzdA==", backend="tesseract", language="no")
        assert result == "mel, sukker"

    def test_default_backend_is_tesseract(self, monkeypatch):
        monkeypatch.setattr("services.ocr_service.extract_text", lambda _: "mel")

        from services.ocr_backends import dispatch_ocr

        assert dispatch_ocr("dGVzdA==") == "mel"

    def test_language_param_flows_through_to_claude_user_message(self, monkeypatch):
        """Integration: dispatch_ocr passes language through to build_ingredient_prompt."""
        from services.ocr_backends import build_ingredient_prompt

        fake, mock_client = _make_anthropic_module("mjöl")
        monkeypatch.setitem(sys.modules, "anthropic", fake)

        from services.ocr_backends import dispatch_ocr

        dispatch_ocr("dGVzdA==", backend="claude", language="se")

        kwargs = mock_client.messages.create.call_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        texts = [c["text"] for c in user_content if c.get("type") == "text"]
        expected = build_ingredient_prompt("se")
        assert any(expected in t for t in texts), (
            "dispatch_ocr must pass language='se' through to the user message"
        )

    def test_language_param_flows_through_to_openai_user_message(self, monkeypatch):
        """Integration: dispatch_ocr passes language through to OpenAI backend."""
        from services.ocr_backends import build_ingredient_prompt

        fake, mock_client = _make_openai_module("flour")
        monkeypatch.setitem(sys.modules, "openai", fake)

        from services.ocr_backends import dispatch_ocr

        dispatch_ocr("dGVzdA==", backend="openai", language="en")

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msgs = [m for m in kwargs["messages"] if m.get("role") == "user"]
        texts = [c["text"] for c in user_msgs[0]["content"] if c.get("type") == "text"]
        expected = build_ingredient_prompt("en")
        assert any(expected in t for t in texts), (
            "dispatch_ocr must pass language='en' through to the user message"
        )
