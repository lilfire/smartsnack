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
# build_ingredient_prompt
# ---------------------------------------------------------------------------


class TestBuildIngredientPrompt:
    def test_no_language_returns_default_task(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        assert "Extract ONLY the ingredient list" in prompt

    def test_none_language_returns_default_task(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(None)
        assert "Extract ONLY the ingredient list" in prompt

    def test_none_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt(None) == build_ingredient_prompt()

    def test_unknown_language_returns_default_task(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("xx")
        assert "Extract ONLY the ingredient list" in prompt

    def test_no_language_task_header_does_not_include_translate(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        # The task header line should not contain a translate instruction
        first_line = prompt.split("\n")[0]
        assert "translate" not in first_line.lower()

    def test_norwegian_includes_language_name(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("no")
        assert "Norwegian (Bokmål)" in prompt
        assert "translate" in prompt.lower()

    def test_english_includes_language_name(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("en")
        assert "English" in prompt
        assert "translate" in prompt.lower()

    def test_swedish_includes_language_name(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("se")
        assert "Swedish" in prompt
        assert "translate" in prompt.lower()

    def test_all_prompts_contain_header_strip_rule(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "INGREDIENSER" in prompt
            assert "INGREDIENTS" in prompt
            assert "ZUTATEN" in prompt

    def test_all_prompts_contain_no_narrative_rule(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "The label reads" in prompt

    def test_all_prompts_contain_empty_string_rule(self):
        from services.ocr_backends import build_ingredient_prompt
        for lang in [None, "no", "en", "se"]:
            prompt = build_ingredient_prompt(lang)
            assert "empty string" in prompt

    # --- Translation vs no-translation prompt content validation ---

    def test_empty_string_language_returns_default_task(self):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt("")
        assert "Extract ONLY the ingredient list" in prompt
        assert "translate" not in prompt.split("\n")[0].lower()

    def test_empty_string_language_equals_no_arg_call(self):
        from services.ocr_backends import build_ingredient_prompt
        assert build_ingredient_prompt("") == build_ingredient_prompt()

    @pytest.mark.parametrize("lang,expected_name", [
        ("no", "Norwegian (Bokmål)"),
        ("en", "English"),
        ("se", "Swedish"),
    ])
    def test_translation_prompt_contains_translate_directive(self, lang, expected_name):
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert f"translate every ingredient into {expected_name}" in prompt.lower() or \
               f"always output in {expected_name}" in prompt

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_translation_prompt_task_header_does_not_say_extract_only(self, lang):
        """When translating, the header should NOT say 'Extract ONLY' — that
        implies verbatim extraction without translation."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        first_line = prompt.split("\n")[0]
        assert "Extract ONLY" not in first_line

    def test_no_translation_prompt_does_not_contain_language_names(self):
        """The default (no-language) prompt must not mention any specific language."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        for name in ("Norwegian", "English", "Swedish"):
            assert name not in prompt

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_translation_prompt_would_catch_conflicting_instructions(self, lang):
        """Regression: the original bug had both 'as it appears' (verbatim) and
        'translate' in the same prompt, creating conflicting instructions.
        When translation is requested, the prompt must contain translation
        directives and must NOT say 'Extract ONLY' or 'as it appears'."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert "translate" in prompt.lower()
        assert "Extract ONLY" not in prompt
        assert "exactly as it appears" not in prompt.lower()

    def test_no_translation_prompt_uses_verbatim_rules(self):
        """Without a language, the prompt must use verbatim extraction rules."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt()
        assert "Extract ONLY the ingredient list" in prompt
        assert "as it appears" in prompt.lower()

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_translation_rules_contain_e_number_exception(self, lang):
        """Translation rules should allow E-numbers to remain untranslated."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert "E-number" in prompt or "E471" in prompt

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_translation_rules_require_full_translation(self, lang):
        """Translation rules should require all ingredients to be translated."""
        from services.ocr_backends import build_ingredient_prompt
        prompt = build_ingredient_prompt(lang)
        assert "Do NOT output any text in the original label language" in prompt

    def test_backward_compat_alias_is_set(self):
        import services.ocr_backends as mod
        assert hasattr(mod, "_INGREDIENT_PROMPT")
        assert isinstance(mod._INGREDIENT_PROMPT, str)
        assert "ingredient" in mod._INGREDIENT_PROMPT.lower()

    def test_backward_compat_alias_equals_no_language_call(self):
        import services.ocr_backends as mod
        from services.ocr_backends import build_ingredient_prompt
        assert mod._INGREDIENT_PROMPT == build_ingredient_prompt()


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
            _extract_claude_vision(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.messages.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[0]["content"][1]["text"]
        assert "Extract ONLY" in text_content
        # Task header should not mention translating to a specific language
        assert "translate it to" not in text_content.lower()

    def test_language_en_uses_translation_prompt(self, monkeypatch):
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
        assert "English" in text_content


class TestGroqLanguageParam:
    def test_language_no_uses_translation_prompt(self, monkeypatch):
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
            text_content = msgs[0]["content"][1]["text"]
        assert "Norwegian" in text_content

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
            _extract_groq(img, _b64(img), language=None)
            call_kwargs = mock_cls.return_value.chat.completions.create.call_args
            msgs = call_kwargs[1]["messages"]
            text_content = msgs[0]["content"][1]["text"]
        # Task header should not mention translating to a specific language
        assert "translate it to" not in text_content.lower()


class TestOpenAILanguageParam:
    def test_language_se_uses_translation_prompt(self, monkeypatch):
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
            text_content = msgs[0]["content"][1]["text"]
        assert "Swedish" in text_content


class TestOpenRouterLanguageParam:
    def test_language_en_uses_translation_prompt(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        img = _tiny_png_bytes()
        mock_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="sugar")
            )]
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


class TestGeminiLanguageParam:
    def test_language_no_uses_translation_prompt(self, monkeypatch):
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
        """If get_language() raises RuntimeError, dispatch_ocr falls back gracefully."""
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

        assert result["text"] == "sugar"
        call_kwargs = mock_cls.return_value.messages.create.call_args
        msgs = call_kwargs[1]["messages"]
        text_content = msgs[0]["content"][1]["text"]
        assert "Extract ONLY" in text_content


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
        text_content = msgs[0]["content"][1]["text"]
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
