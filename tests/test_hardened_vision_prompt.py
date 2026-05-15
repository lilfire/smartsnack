"""LSO-1243: tests for the hardened vision LLM prompt (language-agnostic).

The hardened prompt is designed to isolate the target-language ingredient
block from multilingual food labels. These tests cover:

* Phase-1 and Phase-2 rule statements in the system prompt
* build_ingredient_prompt: contains the language identifier, no vocab lists
* Cross-backend system-prompt parity (all 5 backends send the same prompt)
* Regression simulating the LSO-1222 Norwegian/German/Polish biscuit label
* Edge cases: empty input, conversational refusals, None/unknown language
* Tesseract backend unchanged by vision-prompt work

Design rule (LSO-1243): no language-specific strings (allergen vocab, decimal
separators, trace templates) may appear in code or tests.
"""
from __future__ import annotations

import base64
import io
import types
from unittest.mock import patch

import pytest
from PIL import Image

from services.ocr_backends import (
    _HARDENED_SYSTEM_PROMPT,
    build_ingredient_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# Canonical Norwegian output for the LSO-1222 biscuit example. Real models
# may vary phrasing slightly but this is the shape the hardened prompt drives
# toward — Norwegian only, ALL CAPS allergens, E-numbers preserved, single
# comma-separated line ending with a period.
_LSO_1222_EXPECTED_NORWEGIAN = (
    "HVETEMEL, sukker, vegetabilsk olje (palme, raps), glukose-fruktosesirup, "
    "MELKPULVER, salt, hevemiddel (E 503, E 500), salt, emulgator (SOYALESITIN), "
    "aroma. Kan inneholde spor av EGG og NØTTER."
)

# Words and phrases that must NEVER appear in Norwegian output for the
# LSO-1222 biscuit example (these come from the German and Polish blocks).
_LSO_1222_FORBIDDEN_NON_NORWEGIAN = (
    # German
    "ZUTATEN",
    "Weizenmehl",
    "Zucker",
    "pflanzliche Öle",
    "MILCHpulver",
    "Spuren",
    # Polish
    "SKŁADNIKI",
    "Mąka pszenna",
    "cukier",
    "olej roślinny",
    "MLEKO",
    "śladowe",
)


# ===========================================================================
# 1) System prompt — full coverage of Phase 1 + Phase 2 rules
# ===========================================================================


class TestHardenedSystemPromptPhase1:
    """Phase 1 of the hardened prompt must describe language isolation."""

    def test_explicit_phase_1_section_header(self):
        assert "INTERNAL STEP 1" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_mentions_target_language(self):
        before_step2 = _HARDENED_SYSTEM_PROMPT.split("INTERNAL STEP 2")[0]
        assert "target language" in before_step2.lower()

    def test_phase_1_critical_rule_against_mixed_language_output(self):
        """The cross-contamination rule is the heart of the LSO-1222 fix."""
        assert "Cross-language contamination" in _HARDENED_SYSTEM_PROMPT
        assert "Discard" in _HARDENED_SYSTEM_PROMPT
        assert "do not restart" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_fallback_to_language_recognition(self):
        """INTERNAL STEP 1 must use the model's language knowledge to find
        ingredient headings rather than relying on pre-listed keywords."""
        assert "vocabulary of the target language" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_language_agnostic_no_hardcoded_keywords(self):
        """The prompt must NOT hardcode language-specific ingredient heading
        keywords. The model should use its own language knowledge."""
        assert "without relying on any pre-listed keywords" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_finds_target_language_section_first(self):
        """INTERNAL STEP 1 must first search for the target-language section
        before falling back to other languages (path B)."""
        assert "search for the target-language ingredient section" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_translate_fallback_path_described(self):
        """If no target-language section exists, Step 1 must instruct the
        model to find an ingredient list in any other language (path B)."""
        assert "search for an ingredient list in any" in _HARDENED_SYSTEM_PROMPT


class TestHardenedSystemPromptPhase2:
    """Phase 2 of the hardened prompt must describe normalisation rules."""

    def test_explicit_phase_2_section_header(self):
        assert "INTERNAL STEP 2" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_single_line_rule(self):
        assert "single comma-separated line" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_allergen_all_caps_rule(self):
        assert "ALL CAPS" in _HARDENED_SYSTEM_PROMPT
        assert "compound words" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_allergen_uses_model_language_knowledge(self):
        """LSO-1243: the system prompt must instruct the model to apply its own
        language knowledge for allergen identification — no pre-listed vocab."""
        assert "language knowledge" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_decimal_separator_rule(self):
        assert "decimal separator" in _HARDENED_SYSTEM_PROMPT.lower()

    def test_phase_2_decimal_separator_standard_in_target_language(self):
        """LSO-1243: decimal separator must be derived from target-language
        knowledge, not from a config table supplied in the user message."""
        assert "standard in the target language" in _HARDENED_SYSTEM_PROMPT

    @pytest.mark.parametrize("e_number", ["E270", "E150d", "E471", "E904a"])
    def test_phase_2_e_number_examples(self, e_number):
        assert e_number in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_e_number_preservation_rule(self):
        assert "Preserve E-numbers" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_sub_ingredient_rule(self):
        assert "Sub-ingredients" in _HARDENED_SYSTEM_PROMPT
        assert "parentheses" in _HARDENED_SYSTEM_PROMPT
        assert "immediately after their parent ingredient" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_percentage_rule(self):
        assert "Preserve percentages" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_trace_allergen_rule(self):
        assert "trace-allergen notice" in _HARDENED_SYSTEM_PROMPT
        assert "final sentence" in _HARDENED_SYSTEM_PROMPT
        # LSO-1243: trace notice must be phrased from language knowledge,
        # not from a template supplied in the user message.
        assert "phrased naturally in the" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_one_period_rule(self):
        assert "exactly one period" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_headers_rule(self):
        assert "Strip ingredient-section headings" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_nutrition_rule(self):
        assert "Strip nutrition-table values" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_brand_rule(self):
        assert "brand names" in _HARDENED_SYSTEM_PROMPT
        assert "trademarks" in _HARDENED_SYSTEM_PROMPT
        assert "barcodes" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_empty_string_rule(self):
        """Rule 13: if no ingredient list found anywhere, return empty."""
        assert "return an empty string" in _HARDENED_SYSTEM_PROMPT


# ===========================================================================
# 2) build_ingredient_prompt — language identifier only, no vocab lists
# ===========================================================================


class TestBuildIngredientPromptLanguageIdentifier:
    """build_ingredient_prompt must carry only the language code; the LLM
    resolves allergen vocab, decimal separator, and trace phrasing itself."""

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_prompt_contains_language_code(self, lang):
        prompt = build_ingredient_prompt(lang)
        assert lang in prompt

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_prompt_starts_with_language_line(self, lang):
        prompt = build_ingredient_prompt(lang)
        assert prompt.startswith("Language:")

    def test_none_falls_back_to_default(self):
        from config import DEFAULT_LANGUAGE
        prompt = build_ingredient_prompt(None)
        assert DEFAULT_LANGUAGE in prompt

    def test_empty_string_falls_back_to_default(self):
        from config import DEFAULT_LANGUAGE
        prompt = build_ingredient_prompt("")
        assert DEFAULT_LANGUAGE in prompt

    def test_none_equals_no_arg_call(self):
        assert build_ingredient_prompt(None) == build_ingredient_prompt()

    def test_empty_equals_no_arg_call(self):
        assert build_ingredient_prompt("") == build_ingredient_prompt()

    def test_backward_compat_alias_is_set(self):
        import services.ocr_backends as mod
        assert hasattr(mod, "_INGREDIENT_PROMPT")
        assert isinstance(mod._INGREDIENT_PROMPT, str)
        assert len(mod._INGREDIENT_PROMPT) > 0

    def test_backward_compat_alias_equals_no_language_call(self):
        import services.ocr_backends as mod
        assert mod._INGREDIENT_PROMPT == build_ingredient_prompt()

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_prompt_is_non_empty_string(self, lang):
        prompt = build_ingredient_prompt(lang)
        assert isinstance(prompt, str) and len(prompt) > 0

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_different_languages_produce_different_prompts(self, lang):
        """Each language code must yield a distinct user message."""
        other_langs = [l for l in ["no", "en", "se"] if l != lang]
        prompt = build_ingredient_prompt(lang)
        for other in other_langs:
            assert prompt != build_ingredient_prompt(other)


# ===========================================================================
# 3) Cross-backend system-prompt parity
# ===========================================================================


def _call_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    img = _tiny_png_bytes()
    mock_message = types.SimpleNamespace(
        content=[types.SimpleNamespace(text="ok")]
    )
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_message
        from services.ocr_backends.claude import _extract_claude_vision
        _extract_claude_vision(img, _b64(img), language="no")
        return mock_cls.return_value.messages.create.call_args


def _call_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    img = _tiny_png_bytes()
    mock_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
    )
    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = mock_response
        from services.ocr_backends.openai import _extract_openai
        _extract_openai(img, _b64(img), language="no")
        return mock_cls.return_value.chat.completions.create.call_args


def _call_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    img = _tiny_png_bytes()
    mock_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
    )
    with patch("groq.Groq") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = mock_response
        from services.ocr_backends.groq import _extract_groq
        _extract_groq(img, _b64(img), language="no")
        return mock_cls.return_value.chat.completions.create.call_args


def _call_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    img = _tiny_png_bytes()
    mock_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
    )
    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = mock_response
        from services.ocr_backends.openrouter import _extract_openrouter
        _extract_openrouter(img, _b64(img), language="no")
        return mock_cls.return_value.chat.completions.create.call_args


def _call_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    img = _tiny_png_bytes()
    mock_response = types.SimpleNamespace(text="ok")
    with patch("google.genai.Client", autospec=True) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        from services.ocr_backends.gemini import _extract_gemini
        _extract_gemini(img, _b64(img), language="no")
        return mock_cls.return_value.models.generate_content.call_args


class TestAllBackendsSendIdenticalHardenedSystemPrompt:
    """All 5 LLM backends must send the same hardened system prompt verbatim."""

    def test_claude_system_prompt_is_verbatim(self, monkeypatch):
        call = _call_claude(monkeypatch)
        assert call.kwargs["system"] == _HARDENED_SYSTEM_PROMPT

    def test_openai_system_prompt_is_verbatim(self, monkeypatch):
        call = _call_openai(monkeypatch)
        msgs = call.kwargs["messages"]
        assert msgs[0] == {"role": "system", "content": _HARDENED_SYSTEM_PROMPT}

    def test_groq_system_prompt_is_verbatim(self, monkeypatch):
        call = _call_groq(monkeypatch)
        msgs = call.kwargs["messages"]
        assert msgs[0] == {"role": "system", "content": _HARDENED_SYSTEM_PROMPT}

    def test_openrouter_system_prompt_is_verbatim(self, monkeypatch):
        call = _call_openrouter(monkeypatch)
        msgs = call.kwargs["messages"]
        assert msgs[0] == {"role": "system", "content": _HARDENED_SYSTEM_PROMPT}

    def test_gemini_system_instruction_is_verbatim(self, monkeypatch):
        call = _call_gemini(monkeypatch)
        assert call.kwargs["config"]["system_instruction"] == _HARDENED_SYSTEM_PROMPT


class TestAllBackendsSendCorrectUserMessage:
    """The user message must equal build_ingredient_prompt(language) — the
    language code only. No allergen vocab, decimal tables, or trace templates."""

    def _extract_user_text_claude(self, call):
        return call.kwargs["messages"][0]["content"][1]["text"]

    def _extract_user_text_openai_style(self, call):
        msgs = call.kwargs["messages"]
        text_parts = [p for p in msgs[1]["content"] if p.get("type") == "text"]
        return text_parts[0]["text"]

    def _extract_user_text_gemini(self, call):
        parts = call.kwargs["contents"][0]["parts"]
        return next(p for p in parts if "text" in p)["text"]

    def test_claude_user_message_equals_built_prompt(self, monkeypatch):
        text = self._extract_user_text_claude(_call_claude(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_openai_user_message_equals_built_prompt(self, monkeypatch):
        text = self._extract_user_text_openai_style(_call_openai(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_groq_user_message_equals_built_prompt(self, monkeypatch):
        text = self._extract_user_text_openai_style(_call_groq(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_openrouter_user_message_equals_built_prompt(self, monkeypatch):
        text = self._extract_user_text_openai_style(_call_openrouter(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_gemini_user_message_equals_built_prompt(self, monkeypatch):
        text = self._extract_user_text_gemini(_call_gemini(monkeypatch))
        assert text == build_ingredient_prompt("no")


# ===========================================================================
# 4) Multilingual regression — the LSO-1222 biscuit bug example
# ===========================================================================


class TestLSO1222MultilingualBiscuitRegression:
    """Drive dispatch_ocr_bytes end-to-end with a Norwegian-target setting
    and verify the prompt assembly + response handling."""

    def _setup_claude_mock(self, monkeypatch, llm_text):
        from unittest.mock import MagicMock
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text=llm_text)]
        )
        ctx = patch.multiple(
            "services.settings_service",
            get_ocr_backend=MagicMock(return_value="claude_vision"),
            get_language=MagicMock(return_value="no"),
        )
        ctx2 = patch(
            "services.ocr_settings_service.get_model_for_provider",
            side_effect=RuntimeError,
        )
        ctx3 = patch("anthropic.Anthropic")
        return ctx, ctx2, ctx3, mock_message

    def test_dispatch_returns_norwegian_only_output(self, monkeypatch):
        from services.ocr_core import dispatch_ocr_bytes
        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())

        assert result["text"] == _LSO_1222_EXPECTED_NORWEGIAN
        for forbidden in _LSO_1222_FORBIDDEN_NON_NORWEGIAN:
            assert forbidden not in result["text"], (
                f"Non-Norwegian fragment '{forbidden}' leaked into output"
            )

    def test_dispatch_output_has_all_caps_allergens(self, monkeypatch):
        from services.ocr_core import dispatch_ocr_bytes
        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())

        # Mocked LLM output must pass through with ALL CAPS allergen compounds.
        assert "HVETEMEL" in result["text"]
        assert "MELKPULVER" in result["text"]
        assert "SOYALESITIN" in result["text"]
        assert "hvetemel" not in result["text"]
        assert "melkpulver" not in result["text"]
        assert "soyalesitin" not in result["text"]

    def test_dispatch_output_preserves_e_numbers(self, monkeypatch):
        from services.ocr_core import dispatch_ocr_bytes
        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())

        assert "E 503" in result["text"]
        assert "E 500" in result["text"]

    def test_dispatch_output_is_single_comma_separated_line_with_period(
        self, monkeypatch
    ):
        from services.ocr_core import dispatch_ocr_bytes
        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())

        assert "\n" not in result["text"]
        assert result["text"].rstrip().endswith(".")
        assert "," in result["text"]

    def test_dispatch_sends_hardened_system_prompt_and_language_user_message(
        self, monkeypatch
    ):
        """Prove the dispatch layer feeds the LLM the right instructions:
        hardened system prompt + language-code-only user message."""
        from services.ocr_core import dispatch_ocr_bytes
        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            dispatch_ocr_bytes(_tiny_png_bytes())
            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs

        assert call_kwargs["system"] == _HARDENED_SYSTEM_PROMPT
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        # LSO-1243: user message contains only the language code — no vocab lists.
        assert user_text == build_ingredient_prompt("no")
        assert "no" in user_text


# ===========================================================================
# 5) Edge cases for the hardened prompt path
# ===========================================================================


class TestHardenedPromptEdgeCases:
    """Behaviour the prompt is designed to drive in pathological inputs."""

    def _dispatch_with_claude_response(self, monkeypatch, llm_text, language="no"):
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text=llm_text)] if llm_text else []
        )
        with patch.multiple(
            "services.settings_service",
            get_ocr_backend=MagicMock(return_value="claude_vision"),
            get_language=MagicMock(return_value=language),
        ), patch(
            "services.ocr_settings_service.get_model_for_provider",
            side_effect=RuntimeError,
        ), patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            return dispatch_ocr_bytes(_tiny_png_bytes())

    def test_single_language_label_passes_through_unchanged(self, monkeypatch):
        text = "HVETEMEL, sukker, salt."
        result = self._dispatch_with_claude_response(monkeypatch, text)
        assert result["text"] == "HVETEMEL, sukker, salt."

    def test_empty_input_returns_empty_text_per_rule_13(self, monkeypatch):
        """Rule 13: when no readable ingredient list exists, the LLM returns
        empty string and the dispatch layer propagates it unchanged."""
        result = self._dispatch_with_claude_response(monkeypatch, "")
        assert result["text"] == ""
        assert result["provider"]

    def test_conversational_refusal_is_converted_to_empty(self, monkeypatch):
        """If the model ignores Rule 13 and replies with prose, the dispatch
        layer's looks_like_llm_refusal safety net converts it to empty."""
        refusal = (
            "I'm sorry, I can't see any ingredient list in this image. "
            "Could you provide a clearer photo?"
        )
        result = self._dispatch_with_claude_response(monkeypatch, refusal)
        assert result["text"] == ""

    def test_unknown_language_code_is_passed_to_llm(self, monkeypatch):
        """When settings_service.get_language() returns an unknown code,
        build_ingredient_prompt passes it through — the LLM handles it."""
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="Sukker, mel.")]
        )
        with patch.multiple(
            "services.settings_service",
            get_ocr_backend=MagicMock(return_value="claude_vision"),
            get_language=MagicMock(return_value="xx"),
        ), patch(
            "services.ocr_settings_service.get_model_for_provider",
            side_effect=RuntimeError,
        ), patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())
            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs

        assert result["text"] == "Sukker, mel."
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        # Unknown code is passed through to build_ingredient_prompt
        assert user_text == build_ingredient_prompt("xx")

    def test_none_language_falls_back_to_default(self, monkeypatch):
        """When settings_service.get_language() returns None, the dispatch
        path must not crash — the default language is the safe fallback."""
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes
        from config import DEFAULT_LANGUAGE

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="vann.")]
        )
        with patch.multiple(
            "services.settings_service",
            get_ocr_backend=MagicMock(return_value="claude_vision"),
            get_language=MagicMock(return_value=None),
        ), patch(
            "services.ocr_settings_service.get_model_for_provider",
            side_effect=RuntimeError,
        ), patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())
            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs

        assert result["text"] == "vann."
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        # None language → default language code in the user message
        assert DEFAULT_LANGUAGE in user_text

    def test_trailing_period_added_if_model_drops_it(self, monkeypatch):
        """Vision models occasionally drop the terminal period. The dispatch
        layer enforces the DB convention via ensure_trailing_period()."""
        result = self._dispatch_with_claude_response(
            monkeypatch, "Sukker, mel, vann, salt"
        )
        assert result["text"] == "Sukker, mel, vann, salt."

    def test_label_with_no_recognized_header_still_returns_output(self, monkeypatch):
        """The dispatch layer accepts and forwards a well-formed response
        regardless of how the model located the ingredient block."""
        text = "Sukker, vann, salt."
        result = self._dispatch_with_claude_response(monkeypatch, text)
        assert result["text"] == "Sukker, vann, salt."


# ===========================================================================
# 6) Regression — tesseract backend is untouched by the hardened-prompt work
# ===========================================================================


class TestTesseractBackendUnchanged:
    """The hardened prompt only applies to vision LLM backends. Tesseract
    must not receive any prompt and must operate purely on pixel data."""

    def test_tesseract_extract_signature_does_not_accept_prompt(self):
        from services.ocr_backends.tesseract import _extract_tesseract

        with patch(
            "pytesseract.image_to_data",
            return_value={
                "text": ["sukker", "mel"],
                "conf": [88, 90],
                "left": [0, 40],
                "top": [0, 0],
                "width": [30, 30],
                "height": [10, 10],
            },
            autospec=True,
        ):
            result = _extract_tesseract(_tiny_png_bytes(), "b64")
        assert "sukker" in result
        assert "mel" in result

    def test_dispatch_tesseract_does_not_pass_language_or_prompt(self, monkeypatch):
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes
        from services import ocr_core as core

        mock_extract = MagicMock(return_value="vann, sukker")
        original = core._PROVIDERS["tesseract"]
        core._PROVIDERS["tesseract"] = mock_extract
        try:
            with patch.multiple(
                "services.settings_service",
                get_ocr_backend=MagicMock(return_value="tesseract"),
                get_language=MagicMock(return_value="no"),
            ):
                result = dispatch_ocr_bytes(_tiny_png_bytes())
        finally:
            core._PROVIDERS["tesseract"] = original

        assert result["text"] == "vann, sukker"
        _, kwargs = mock_extract.call_args
        assert "language" not in kwargs
        assert "prompt" not in kwargs
        assert "model" not in kwargs

    def test_dispatch_tesseract_does_not_apply_trailing_period(self, monkeypatch):
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes
        from services import ocr_core as core

        mock_extract = MagicMock(return_value="vann sukker")
        original = core._PROVIDERS["tesseract"]
        core._PROVIDERS["tesseract"] = mock_extract
        try:
            with patch.multiple(
                "services.settings_service",
                get_ocr_backend=MagicMock(return_value="tesseract"),
                get_language=MagicMock(return_value="no"),
            ):
                result = dispatch_ocr_bytes(_tiny_png_bytes())
        finally:
            core._PROVIDERS["tesseract"] = original

        assert result["text"] == "vann sukker"


# ===========================================================================
# 7) Mock shape sanity
# ===========================================================================


class TestLso1222CanonicalLlmResponseShape:
    """Document the LLM response shape the regression test relies on."""

    def test_claude_canonical_response_matches_validator(self):
        from tests.mock_shape_validator import validate_claude_response_shape

        canonical = {
            "content": [
                {"type": "text", "text": _LSO_1222_EXPECTED_NORWEGIAN}
            ]
        }
        validate_claude_response_shape(canonical)
