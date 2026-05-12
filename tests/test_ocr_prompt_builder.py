"""Tests for the build_ingredient_prompt function and language passing through dispatch."""
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
        assert "Phase 1" in _HARDENED_SYSTEM_PROMPT

    def test_contains_phase_2(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "Phase 2" in _HARDENED_SYSTEM_PROMPT

    def test_contains_header_strip_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "INGREDIENSER" in _HARDENED_SYSTEM_PROMPT
        assert "INGREDIENTS" in _HARDENED_SYSTEM_PROMPT
        assert "ZUTATEN" in _HARDENED_SYSTEM_PROMPT

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


# ---------------------------------------------------------------------------
# build_ingredient_prompt — new structured user message format
# ---------------------------------------------------------------------------


class TestBuildIngredientPrompt:
    def test_no_language_returns_norwegian_by_default(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        assert "Language: Norwegian" in prompt

    def test_none_language_returns_norwegian(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(None)
        assert "Language: Norwegian" in prompt

    def test_none_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt(None) == build_ingredient_prompt()

    def test_unknown_language_falls_back_to_norwegian(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("xx")
        assert "Language: Norwegian" in prompt

    def test_empty_string_falls_back_to_norwegian(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("")
        assert "Language: Norwegian" in prompt

    def test_empty_string_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt("") == build_ingredient_prompt()

    def test_norwegian_prompt_contains_language_header(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Language: Norwegian" in prompt

    def test_norwegian_prompt_contains_melk_allergen(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "MELK" in prompt

    def test_norwegian_prompt_contains_trace_template(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Kan inneholde spor av" in prompt

    def test_norwegian_prompt_contains_comma_decimal(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "comma" in prompt

    def test_norwegian_prompt_contains_allergen_terms_line(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Allergen terms:" in prompt

    def test_norwegian_prompt_contains_decimal_separator_line(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Decimal separator:" in prompt

    def test_norwegian_prompt_contains_trace_notice_template_line(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Trace notice template:" in prompt

    def test_english_prompt_contains_language_header(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("en")
        assert "Language: English" in prompt

    def test_english_prompt_contains_milk_allergen(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("en")
        assert "MILK" in prompt

    def test_english_prompt_contains_trace_template(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("en")
        assert "May contain traces of" in prompt

    def test_english_prompt_uses_dot_decimal(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("en")
        assert "dot" in prompt

    def test_swedish_prompt_contains_language_header(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("se")
        assert "Language: Swedish" in prompt

    def test_swedish_prompt_contains_trace_template(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("se")
        assert "Kan innehålla spår av" in prompt

    def test_swedish_prompt_uses_comma_decimal(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("se")
        assert "comma" in prompt

    def test_no_prompt_does_not_contain_translate_directive(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        for name in ("Norwegian", "English", "Swedish"):
            assert f"translate every ingredient into {name}" not in prompt
            assert f"Always output in {name}" not in prompt

    def test_all_prompts_contain_allergen_terms_line(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "Allergen terms:" in prompt, f"missing 'Allergen terms:' for lang={lang!r}"

    def test_all_prompts_contain_decimal_separator_line(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "Decimal separator:" in prompt, f"missing 'Decimal separator:' for lang={lang!r}"

    def test_all_prompts_contain_trace_notice_template_line(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "Trace notice template:" in prompt, f"missing 'Trace notice template:' for lang={lang!r}"

    @pytest.mark.parametrize("lang", [None, "no", "en", "se"])
    def test_all_prompts_start_with_language_line(self, lang):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert prompt.startswith("Language:"), f"prompt does not start with Language: for lang={lang!r}"

    @pytest.mark.parametrize("lang", [None, "no", "en", "se"])
    def test_all_prompts_do_not_contain_extract_only(self, lang):
        """System prompt now handles extraction instructions; user message must not
        duplicate them."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert "Extract ONLY" not in prompt

    def test_no_translation_prompt_task_header_does_not_include_translate(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        first_line = prompt.split("\n")[0]
        assert "translate" not in first_line.lower()

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_translation_prompt_task_header_does_not_say_extract_only(self, lang):
        """The language-specific user message must not say 'Extract ONLY' — that
        belongs in the system prompt."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        first_line = prompt.split("\n")[0]
        assert "Extract ONLY" not in first_line

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
        assert "INGREDIENSER" in _HARDENED_SYSTEM_PROMPT
        assert "INGREDIENTS" in _HARDENED_SYSTEM_PROMPT
        assert "ZUTATEN" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_contains_empty_string_rule(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "empty string" in _HARDENED_SYSTEM_PROMPT

    def test_system_prompt_phase1_and_phase2(self):
        from services.ocr_backends import _HARDENED_SYSTEM_PROMPT
        assert "Phase 1" in _HARDENED_SYSTEM_PROMPT
        assert "Phase 2" in _HARDENED_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# ensure_trailing_period
# ---------------------------------------------------------------------------


class TestEnsureTrailingPeriod:
    """Safety-net helper that aligns OCR output with the DB convention of a
    trailing period on every ingredient string."""

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
        """Empty must remain empty so the no-text error path still fires."""
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("") == ""

    def test_whitespace_only_returns_empty(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period("   \n\t") == ""

    def test_none_returns_empty(self):
        from services.ocr_backends import ensure_trailing_period
        assert ensure_trailing_period(None) == ""  # type: ignore[arg-type]

    def test_preserves_trace_warning_period(self):
        from services.ocr_backends import ensure_trailing_period
        text = "Sukker, mel. Kan inneholde spor av HVETE, RUG og BYGG."
        assert ensure_trailing_period(text) == text


# ---------------------------------------------------------------------------
# Backend functions accept and use language parameter
# ---------------------------------------------------------------------------


class TestClaudeLanguageParam:
    def test_language_none_uses_norwegian_prompt(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        img = _tiny_png_bytes()
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="sugar")]
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            from services.ocr_backends.claude import _extract_claude_vision
            _extract_claude_vision(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.messages.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[0]["content"][1]["text"]
        # Norwegian is the default fallback; user message says "Language: Norwegian"
        assert "Language: Norwegian" in text_content
        assert "translate it to" not in text_content.lower()

    def test_language_en_uses_english_prompt(self, monkeypatch):
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
        assert "Language: English" in text_content

    def test_system_prompt_is_sent(self, monkeypatch):
        """Claude must send _HARDENED_SYSTEM_PROMPT as the system parameter."""
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
        assert "Phase 1" in system_param
        assert "Phase 2" in system_param


class TestGroqLanguageParam:
    def test_language_no_uses_norwegian_prompt(self, monkeypatch):
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
            # system is msgs[0], user is msgs[1]
            text_content = msgs[1]["content"][1]["text"]
        assert "Norwegian" in text_content

    def test_language_none_uses_norwegian_prompt(self, monkeypatch):
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
            _extract_groq(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[1]["content"][1]["text"]
        assert "Language: Norwegian" in text_content
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
    def test_language_se_uses_swedish_prompt(self, monkeypatch):
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
            # system is msgs[0], user is msgs[1]
            text_content = msgs[1]["content"][1]["text"]
        assert "Swedish" in text_content

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
    def test_language_en_uses_english_prompt(self, monkeypatch):
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
            # User message is msgs[1], system is msgs[0]
            user_content = msgs[1]["content"]
            text_part = next(p for p in user_content if p.get("type") == "text")
        assert "English" in text_part["text"]

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
        assert "Phase 1" in system_msg["content"]


class TestGeminiLanguageParam:
    def test_language_no_uses_norwegian_prompt(self, monkeypatch):
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
        assert "Norwegian" in text_part["text"]

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
        assert "Phase 1" in config["system_instruction"]


# ---------------------------------------------------------------------------
# dispatch_ocr passes language to LLM backend
# ---------------------------------------------------------------------------


class TestDispatchOcrPassesLanguage:
    def test_dispatch_ocr_passes_language_to_claude(self):
        """dispatch_ocr should pass the user's language to the Claude provider."""
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
        assert "English" in text_content

    def test_dispatch_ocr_tesseract_does_not_pass_language(self):
        """dispatch_ocr with tesseract should not pass language (tesseract ignores it)."""
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
        """If get_language() raises RuntimeError, dispatch_ocr falls back to Norwegian."""
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

        # Vision backend output gets a trailing period applied by the
        # dispatch layer to match the SmartSnack DB convention.
        assert result["text"] == "sugar."
        call_kwargs = mock_cls.return_value.messages.create.call_args
        msgs = call_kwargs[1]["messages"]
        text_content = msgs[0]["content"][1]["text"]
        # Norwegian is the fallback when language lookup fails
        assert "Language: Norwegian" in text_content


# ---------------------------------------------------------------------------
# dispatch_ocr_bytes passes language to LLM backend
# ---------------------------------------------------------------------------


class TestDispatchOcrBytesPassesLanguage:
    def test_dispatch_ocr_bytes_passes_language_to_groq(self):
        """dispatch_ocr_bytes should pass the user's language to the Groq provider."""
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
        # system is msgs[0], user is msgs[1]
        text_content = msgs[1]["content"][1]["text"]
        assert "Norwegian" in text_content

    def test_dispatch_ocr_bytes_tesseract_no_language(self):
        """dispatch_ocr_bytes with tesseract does not pass language."""
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
    """When a vision LLM ignores the empty-string rule and replies with prose
    (e.g. "I'm happy to help, but I don't see an image..."), the dispatch
    layer must convert the response into empty text so the blueprint surfaces
    error_type='no_text' and the frontend shows the no-text toast."""

    _REFUSAL_TEXT = (
        "I'm happy to help, but I don't see an image of a food label. "
        "Please provide the image, and I'll extract the ingredient list "
        "and translate it into Norwegian (Bokmål) according to the rules."
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
        """Sanity check: ingredient lists must not be mistaken for refusals.
        The dispatch layer adds a trailing period to match the SmartSnack
        DB convention but otherwise leaves the text alone."""
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
        """Tesseract returns raw OCR text and must not be filtered, even if
        the OCR happens to contain a marker phrase."""
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
    """The conversational-response detector that protects users from vision
    LLMs ignoring the empty-string rule for unreadable labels."""

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
