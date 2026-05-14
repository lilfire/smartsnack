"""Tests for build_ingredient_prompt and language passing through dispatch.

LSO-1243: all assertions must be language-agnostic — no allergen vocab,
decimal separators, or trace templates may appear in this file.
"""
import base64
import io
import types
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiny_png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# ---------------------------------------------------------------------------
# _HARDENED_SYSTEM_PROMPT
# ---------------------------------------------------------------------------


class TestHardenedSystemPrompt:
    def test_is_non_empty_string(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert isinstance(_HARDENED_SYSTEM_PROMPT, str)
        assert len(_HARDENED_SYSTEM_PROMPT) > 0

    def test_contains_phase_1(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in _HARDENED_SYSTEM_PROMPT

    def test_contains_phase_2(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 2" in _HARDENED_SYSTEM_PROMPT

    def test_contains_header_strip_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "Strip ingredient-section headings" in _HARDENED_SYSTEM_PROMPT

    def test_contains_empty_string_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "empty string" in _HARDENED_SYSTEM_PROMPT

    def test_contains_single_comma_separated_line_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "single comma-separated line" in _HARDENED_SYSTEM_PROMPT

    def test_contains_allergen_all_caps_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "ALL CAPS" in _HARDENED_SYSTEM_PROMPT

    def test_contains_e_number_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "E270" in _HARDENED_SYSTEM_PROMPT

    def test_contains_trailing_period_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "one period" in _HARDENED_SYSTEM_PROMPT

    def test_contains_language_isolation(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "target language" in _HARDENED_SYSTEM_PROMPT.lower()

    def test_uses_model_language_knowledge_for_allergens(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "language knowledge" in _HARDENED_SYSTEM_PROMPT

    def test_decimal_separator_from_target_language(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "standard in the target language" in _HARDENED_SYSTEM_PROMPT

    def test_trace_notice_phrased_naturally_in_target_language(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "phrased naturally in the" in _HARDENED_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# build_ingredient_prompt — language-code-only user message
# ---------------------------------------------------------------------------


class TestBuildIngredientPrompt:
    def test_no_language_returns_default(self):
        from services.ocr_backends import build_ingredient_prompt
        from config import DEFAULT_LANGUAGE
        prompt = build_ingredient_prompt()
        assert DEFAULT_LANGUAGE in prompt

    def test_none_language_returns_default(self):
        from services.ocr_backends import build_ingredient_prompt
        from config import DEFAULT_LANGUAGE
        prompt = build_ingredient_prompt(None)
        assert DEFAULT_LANGUAGE in prompt

    def test_none_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt(None) == build_ingredient_prompt()

    def test_unknown_language_is_passed_through(self):
        """Unknown language codes are passed to the LLM unchanged."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("xx")
        assert "xx" in prompt

    def test_empty_string_falls_back_to_default(self):
        from services.ocr_backends import build_ingredient_prompt
        from config import DEFAULT_LANGUAGE
        prompt = build_ingredient_prompt("")
        assert DEFAULT_LANGUAGE in prompt

    def test_empty_string_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt("") == build_ingredient_prompt()

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_prompt_contains_language_code(self, lang):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert lang in prompt

    @pytest.mark.parametrize("lang", [None, "no", "en", "se"])
    def test_all_prompts_start_with_language_line(self, lang):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert prompt.startswith("Language:"), (
            f"prompt does not start with Language: for lang={lang!r}"
        )

    @pytest.mark.parametrize("lang", [None, "no", "en", "se"])
    def test_all_prompts_do_not_contain_extract_only(self, lang):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert "Extract ONLY" not in prompt

    def test_no_translation_prompt_does_not_include_translate_directive(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        first_line = prompt.split("\n")[0]
        assert "translate" not in first_line.lower()

    def test_backward_compat_alias_is_set(self):
        import services.ocr_backends as mod
        assert hasattr(mod, "_INGREDIENT_PROMPT")
        assert isinstance(mod._INGREDIENT_PROMPT, str)
        assert len(mod._INGREDIENT_PROMPT) > 0

    def test_backward_compat_alias_equals_no_language_call(self):
        import services.ocr_backends as mod
        from services.ocr_backends import build_ingredient_prompt
        assert mod._INGREDIENT_PROMPT == build_ingredient_prompt()

    def test_system_prompt_contains_single_comma_separated_line_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "single comma-separated line" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_allergen_all_caps_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "ALL CAPS" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_e_number_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "E270" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_trailing_period_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "one period" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_header_strip_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "Strip ingredient-section headings" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_empty_string_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "empty string" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_phase1_and_phase2(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 2" in _HARDENED_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# ensure_trailing_period
# ---------------------------------------------------------------------------


class TestEnsureTrailingPeriod:
    def test_appends_period_when_missing(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("Sukker, mel, vann") == "Sukker, mel, vann."

    def test_does_not_double_period(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("Sukker, mel, vann.") == "Sukker, mel, vann."

    @pytest.mark.parametrize("punct", [".", "!", "?"])
    def test_preserves_terminal_punctuation(self, punct):
        from services.ocr_backends import ensure_trailing_period
        text = f"Sukker, mel, vann{punct}"
        assert ensure_trailing_period(text) == text

    def test_strips_trailing_whitespace_before_period(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("Sukker, mel  \n") == "Sukker, mel."

    def test_empty_string_stays_empty(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("") == ""

    def test_whitespace_only_returns_empty(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("   \n\t") == ""

    def test_none_returns_empty(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period(None) == ""  # type: ignore[arg-type]

    def test_preserves_multi_sentence_text(self):
        from services.ocr_backends import ensure_trailing_period
        text = "Sukker, mel. Spor av nøtter."
        assert ensure_trailing_period(text) == text


# ---------------------------------------------------------------------------
# Backend functions accept and use language parameter
# ---------------------------------------------------------------------------


class TestClaudeLanguageParam:
    def test_language_none_uses_default_prompt(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="sugar")]
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            from config import DEFAULT_LANGUAGE
            _extract_claude_vision(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.messages.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[0]["content"][1]["text"]
        assert DEFAULT_LANGUAGE in text_content
        assert "translate it to" not in text_content.lower()

    def test_language_en_uses_en_code(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="sugar")]
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            _extract_claude_vision(img, _b64(img), language="en")
            call_kwargs = mock_cls.return_value.messages.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[0]["content"][1]["text"]
        assert "en" in text_content

    def test_system_prompt_is_sent(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
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


class TestGroqLanguageParam:
    def test_language_no_uses_no_code(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="sukker")
            )]
        )
        with patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            _extract_groq(img, _b64(img), language="no")
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[1]["content"][1]["text"]
        assert "no" in text_content

    def test_language_none_uses_default_prompt(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="sukker")
            )]
        )
        with patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            from config import DEFAULT_LANGUAGE
            _extract_groq(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[1]["content"][1]["text"]
        assert DEFAULT_LANGUAGE in text_content
        assert "translate it to" not in text_content.lower()

    def test_system_message_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="sukker")
            )]
        )
        with patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.groq import _extract_groq
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_groq(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            system_msg = msgs[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == _HARDENED_SYSTEM_PROMPT


class TestOpenAILanguageParam:
    def test_language_se_uses_se_code(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="socker")
            )]
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            _extract_openai(img, _b64(img), language="se")
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[1]["content"][1]["text"]
        assert "se" in text_content

    def test_system_message_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="text")
            )]
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openai import _extract_openai
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_openai(img, _b64(img))
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            system_msg = msgs[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == _HARDENED_SYSTEM_PROMPT


class TestOpenRouterLanguageParam:
    def test_language_en_uses_en_code(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="sugar"))]
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_backends.openrouter import _extract_openrouter
            _extract_openrouter(img, _b64(img), language="en")
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            user_content = msgs[1]["content"]
            text_part = next(p for p in user_content if p.get("type") == "text")
        assert "en" in text_part["text"]

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
            system_msg = msgs[0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in system_msg["content"]


class TestGeminiLanguageParam:
    def test_language_no_uses_no_code(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(text="sukker")
        with patch("google.genai.Client", autospec=True) as mock_cls:
            mock_cls.return_value.models.generate_content.return_value = mock_response
            from services.ocr_backends.gemini import _extract_gemini
            _extract_gemini(img, _b64(img), language="no")
            call_kwargs = mock_cls.return_value.models.generate_content.call_args
            parts = call_kwargs[1]["contents"][0]["parts"]
            text_part = next(p for p in parts if "text" in p)
        assert "no" in text_part["text"]

    def test_system_instruction_contains_hardened_prompt(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(text="sukker")
        with patch("google.genai.Client", autospec=True) as mock_cls:
            mock_cls.return_value.models.generate_content.return_value = mock_response
            from services.ocr_backends.gemini import _extract_gemini
            from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
            _extract_gemini(img, _b64(img))
            call_kwargs = mock_cls.return_value.models.generate_content.call_args
            config = call_kwargs[1].get("config", {})
        assert config.get("system_instruction") == _HARDENED_SYSTEM_PROMPT
        assert "INTERNAL STEP 1" in config["system_instruction"]


# ---------------------------------------------------------------------------
# dispatch_ocr passes language to LLM backend
# ---------------------------------------------------------------------------


class TestDispatchOcrPassesLanguage:
    def test_dispatch_ocr_passes_language_to_claude(self):
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="sugar")]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True), \
             patch("services.settings_service.get_language", return_value="en", autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_core import dispatch_ocr
            dispatch_ocr(_b64(img))

        call_kwargs = mock_cls.return_value.messages.create.call_args
        msgs = call_kwargs[1]["messages"]
        text_content = msgs[0]["content"][1]["text"]
        assert "en" in text_content

    def test_dispatch_ocr_tesseract_does_not_pass_language(self):
        img = _tiny_png_bytes()
        mock_data = {
            "text": ["sukker"], "conf": [90],
            "left": [0], "top": [0], "width": [30], "height": [10],
        }
        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True), \
             patch("pytesseract.image_to_data", return_value=mock_data, autospec=True), \
             patch("pytesseract.Output", new_callable=lambda: type("O", (), {"DICT": "dict"})):
            from services.ocr_core import dispatch_ocr
            result = dispatch_ocr(_b64(img))
        assert result["text"] == "sukker"

    def test_dispatch_ocr_no_language_when_runtime_error(self):
        """If get_language() raises RuntimeError, dispatch_ocr uses the default language."""
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="sugar")]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True), \
             patch("services.settings_service.get_language", side_effect=RuntimeError, autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_core import dispatch_ocr
            result = dispatch_ocr(_b64(img))

        assert result["text"] == "sugar."
        call_kwargs = mock_cls.return_value.messages.create.call_args
        msgs = call_kwargs[1]["messages"]
        text_content = msgs[0]["content"][1]["text"]
        from config import DEFAULT_LANGUAGE
        assert DEFAULT_LANGUAGE in text_content


# ---------------------------------------------------------------------------
# dispatch_ocr_bytes passes language to LLM backend
# ---------------------------------------------------------------------------


class TestDispatchOcrBytesPassesLanguage:
    def test_dispatch_ocr_bytes_passes_language_to_groq(self):
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="sukker")
            )]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="groq", autospec=True), \
             patch("services.settings_service.get_language", return_value="no", autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}), \
             patch("groq.Groq") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = mock_response
            from services.ocr_core import dispatch_ocr_bytes
            dispatch_ocr_bytes(img)

        call_kwargs = mock_cls.return_value.chat.completions.create.call_args
        msgs = call_kwargs[1]["messages"]
        text_content = msgs[1]["content"][1]["text"]
        assert "no" in text_content

    def test_dispatch_ocr_bytes_tesseract_no_language(self):
        img = _tiny_png_bytes()
        mock_data = {
            "text": ["mel"], "conf": [85],
            "left": [0], "top": [0], "width": [30], "height": [10],
        }
        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True), \
             patch("pytesseract.image_to_data", return_value=mock_data, autospec=True), \
             patch("pytesseract.Output", new_callable=lambda: type("O", (), {"DICT": "dict"})):
            from services.ocr_core import dispatch_ocr_bytes
            result = dispatch_ocr_bytes(img)
        assert result["text"] == "mel"


# ---------------------------------------------------------------------------
# dispatch_ocr safety net for conversational LLM responses
# ---------------------------------------------------------------------------


class TestDispatchOcrConversationalGuard:
    """When a vision LLM ignores the empty-string rule and replies with prose,
    the dispatch layer must convert it to empty text."""

    _REFUSAL_TEXT = (
        "I'm happy to help, but I don't see an image of a food label. "
        "Please provide the image, and I'll extract the ingredient list."
    )

    def test_dispatch_ocr_bytes_strips_claude_refusal(self):
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text=self._REFUSAL_TEXT)]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True), \
             patch("services.settings_service.get_language", return_value="no", autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_core import dispatch_ocr_bytes
            result = dispatch_ocr_bytes(img)

        assert result["text"] == ""
        assert result["provider"]
        assert result["fallback"] is False

    def test_dispatch_ocr_strips_claude_refusal(self):
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text=self._REFUSAL_TEXT)]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True), \
             patch("services.settings_service.get_language", return_value="no", autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_core import dispatch_ocr
            result = dispatch_ocr(_b64(img))

        assert result["text"] == ""

    def test_dispatch_ocr_passes_real_ingredient_list_unchanged(self):
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="Sukker, mel, vann, salt")]
        )

        with patch("services.settings_service.get_ocr_backend", return_value="claude_vision", autospec=True), \
             patch("services.settings_service.get_language", return_value="no", autospec=True), \
             patch("services.ocr_settings_service.get_model_for_provider", side_effect=RuntimeError, autospec=True), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_core import dispatch_ocr_bytes
            result = dispatch_ocr_bytes(img)

        assert result["text"] == "Sukker, mel, vann, salt."

    def test_dispatch_ocr_tesseract_skips_refusal_check(self):
        img = _tiny_png_bytes()
        mock_data = {
            "text": ["Please", "provide", "fresh", "milk"],
            "conf": [90, 90, 90, 90],
            "left": [0, 50, 100, 150],
            "top": [0, 0, 0, 0],
            "width": [40, 50, 40, 40],
            "height": [10, 10, 10, 10],
        }
        with patch("services.settings_service.get_ocr_backend", return_value="tesseract", autospec=True), \
             patch("pytesseract.image_to_data", return_value=mock_data, autospec=True), \
             patch("pytesseract.Output", new_callable=lambda: type("O", (), {"DICT": "dict"})):
            from services.ocr_core import dispatch_ocr_bytes
            result = dispatch_ocr_bytes(img)
        assert "Please" in result["text"]
        assert result["text"] != ""


# ---------------------------------------------------------------------------
# looks_like_llm_refusal
# ---------------------------------------------------------------------------


class TestLooksLikeLlmRefusal:
    def test_real_claude_refusal_is_detected(self):
        from services.ocr_backends import looks_like_llm_refusal
        text = (
            "I'm happy to help, but I don't see an image of a food label. "
            "Please provide the image, and I'll extract the ingredient list."
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
        from services.ocr_backends import looks_like_llm_refusal
        assert looks_like_llm_refusal(None) is False  # type: ignore[arg-type]
