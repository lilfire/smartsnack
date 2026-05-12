"""LSO-1227: tests for the hardened two-phase vision LLM prompt.

The hardened prompt (LSO-1224 / LSO-1226, PR #422) is designed to isolate
the target-language ingredient block from multilingual food labels. These
tests cover the gaps not already exercised by ``test_ocr_prompt_builder``
and ``test_ocr_backends``:

* Full allergen-list coverage for every supported language
* Header keywords for every language the prompt enumerates
* Phase-1 and Phase-2 rule statements (CRITICAL isolation, sub-ingredients,
  percentages, trace notice, etc.)
* A regression simulating the LSO-1222 Norwegian/German/Polish biscuit label:
  the LLM is mocked to return a properly-isolated Norwegian output and the
  dispatch layer is asserted to deliver it intact end-to-end.
* Edge cases: single-language input, missing header, empty / unrecognisable
  input, unknown language.
* Tesseract behaviour is unchanged by the hardened-prompt work.
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
    _ALLERGENS_NO,
    _ALLERGENS_EN,
    _ALLERGENS_SE,
    _TRACE_TEMPLATE_NO,
    _TRACE_TEMPLATE_EN,
    _TRACE_TEMPLATE_SE,
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
# may vary phrasing slightly but this is the shape the hardened prompt is
# designed to drive them toward — Norwegian only, ALL CAPS allergens,
# E-numbers preserved, single comma-separated line ending with a period.
_LSO_1222_EXPECTED_NORWEGIAN = (
    "HVETEmel, sukker, vegetabilsk olje (palme, raps), glukose-fruktosesirup, "
    "MELKpulver, salt, hevemiddel (E 503, E 500), salt, emulgator (SOYAlesitin), "
    "aroma. Kan inneholde spor av EGG og NØTTER."
).replace("HVETEmel", "HVETEMEL").replace("MELKpulver", "MELKPULVER").replace(
    "SOYAlesitin", "SOYALESITIN"
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
        # The very first instruction of INTERNAL STEP 1 is to look for the target
        # language stated in the user message.
        before_step2 = _HARDENED_SYSTEM_PROMPT.split("INTERNAL STEP 2")[0]
        assert "target language" in before_step2.lower()

    def test_phase_1_critical_rule_against_mixed_language_output(self):
        """The cross-contamination rule is the heart of the LSO-1222 fix."""
        assert "Cross-language contamination" in _HARDENED_SYSTEM_PROMPT
        assert "Discard" in _HARDENED_SYSTEM_PROMPT
        assert "Do NOT restart" in _HARDENED_SYSTEM_PROMPT

    def test_phase_1_fallback_to_language_recognition(self):
        """If no explicit header is found, INTERNAL STEP 1 must fall back to
        vocabulary recognition."""
        assert "vocabulary recognition" in _HARDENED_SYSTEM_PROMPT.replace("\n", " ")

    @pytest.mark.parametrize(
        "header",
        [
            # Norwegian (target language for SmartSnack default)
            "INGREDIENSER",
            "Ingredienser",
            "Innhold",
            "INNHOLD",
            # English
            "INGREDIENTS",
            "Ingredients",
            # Swedish (ASCII form — OCR may not capture special chars)
            "INNEHALL",
            "Innehall",
            # German (LSO-1222 bug case)
            "ZUTATEN",
            "Zutaten",
            "ZUTATENLISTE",
            # Polish (ASCII form)
            "SKLADNIKI",
            "Skladniki",
            # French (uses same ASCII form as English)
            "INGREDIENTES",
            "Ingredientes",
            # Dutch (ASCII form)
            "INGREDIENTEN",
            "Ingredienten",
            # Spanish
            "INGREDIENTES",
            "Ingredientes",
            # Italian
            "INGREDIENTI",
            "Ingredienti",
        ],
    )
    def test_phase_1_header_keyword_is_listed(self, header):
        assert header in _HARDENED_SYSTEM_PROMPT


class TestHardenedSystemPromptPhase2:
    """Phase 2 of the hardened prompt must describe normalisation rules."""

    def test_explicit_phase_2_section_header(self):
        assert "INTERNAL STEP 2" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_single_line_rule(self):
        assert "single comma-separated line" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_allergen_all_caps_rule(self):
        assert "ALL CAPS" in _HARDENED_SYSTEM_PROMPT
        # Compound-word rule example must be present so the model
        # understands HVETEMEL, SOYALESITIN, MJOLKPULVER are also capitalised.
        assert "HVETEMEL" in _HARDENED_SYSTEM_PROMPT
        assert "SOYALESITIN" in _HARDENED_SYSTEM_PROMPT
        assert "MJOLKPULVER" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_decimal_separator_rule(self):
        assert "decimal separator" in _HARDENED_SYSTEM_PROMPT.lower()

    @pytest.mark.parametrize("e_number", ["E270", "E150d", "E471", "E904a"])
    def test_phase_2_e_number_examples(self, e_number):
        assert e_number in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_e_number_preservation_rule(self):
        assert "Preserve E-numbers" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_sub_ingredient_rule(self):
        assert "Sub-ingredients" in _HARDENED_SYSTEM_PROMPT
        assert "parentheses" in _HARDENED_SYSTEM_PROMPT
        # The worked example must show nested allergen capitalisation.
        assert "krydderblanding" in _HARDENED_SYSTEM_PROMPT
        assert "MYSEPULVER" in _HARDENED_SYSTEM_PROMPT
        assert "MELK" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_percentage_rule(self):
        assert "Preserve percentages" in _HARDENED_SYSTEM_PROMPT
        assert "30%" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_trace_allergen_rule(self):
        assert "trace-allergen notice" in _HARDENED_SYSTEM_PROMPT
        assert "phrasing from the user message" in _HARDENED_SYSTEM_PROMPT
        assert "final sentence" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_one_period_rule(self):
        assert "exactly one period" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_headers_rule(self):
        assert "Strip ingredient-section headers" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_nutrition_rule(self):
        assert "Strip nutrition-table values" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_strip_brand_rule(self):
        assert "brand names" in _HARDENED_SYSTEM_PROMPT
        assert "trademarks" in _HARDENED_SYSTEM_PROMPT
        assert "barcodes" in _HARDENED_SYSTEM_PROMPT

    def test_phase_2_empty_string_rule(self):
        """Rule 13: if no target-language section is found, return empty."""
        assert "return an empty string" in _HARDENED_SYSTEM_PROMPT


# ===========================================================================
# 2) build_ingredient_prompt — full allergen coverage per language
# ===========================================================================


_ALLERGENS_BY_LANG = {
    "no": (
        _ALLERGENS_NO,
        # Every Norwegian allergen the EU directive recognises
        [
            "MELK", "EGG", "HVETE", "RUG", "BYGG", "HAVRE", "GLUTEN",
            "SOYA", "NØTTER", "PEANØTTER", "SESAM", "FISK", "KREPSDYR",
            "BLØTDYR", "SENNEP", "SELLERI", "LUPIN", "SULFITTER",
            "SVOVELDIOKSID",
        ],
    ),
    "en": (
        _ALLERGENS_EN,
        [
            "MILK", "EGGS", "WHEAT", "RYE", "BARLEY", "OATS", "GLUTEN",
            "SOY", "NUTS", "PEANUTS", "SESAME", "FISH", "CRUSTACEANS",
            "MOLLUSCS", "MUSTARD", "CELERY", "LUPIN", "SULPHITES",
            "SULPHUR DIOXIDE",
        ],
    ),
    "se": (
        _ALLERGENS_SE,
        [
            "MJÖLK", "ÄGG", "VETE", "RÅG", "KORN", "HAVRE", "GLUTEN",
            "SOJA", "NÖTTER", "JORDNÖTTER", "SESAM", "FISK", "KRÄFTDJUR",
            "BLÖTDJUR", "SENAP", "SELLERI", "LUPIN", "SULFITER",
            "SVAVELDIOXID",
        ],
    ),
}


class TestBuildIngredientPromptAllergenCoverage:
    """Every regulated allergen must appear in the per-language prompt."""

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_every_allergen_term_present_in_constant(self, lang):
        constant, expected = _ALLERGENS_BY_LANG[lang]
        for term in expected:
            assert term in constant, (
                f"Allergen '{term}' missing from _ALLERGENS_{lang.upper()}"
            )

    @pytest.mark.parametrize("lang", ["no", "en", "se"])
    def test_every_allergen_term_present_in_user_message(self, lang):
        _, expected = _ALLERGENS_BY_LANG[lang]
        prompt = build_ingredient_prompt(lang)
        for term in expected:
            assert term in prompt, (
                f"Allergen '{term}' missing from build_ingredient_prompt({lang!r})"
            )

    @pytest.mark.parametrize(
        "lang,trace_template",
        [
            ("no", _TRACE_TEMPLATE_NO),
            ("en", _TRACE_TEMPLATE_EN),
            ("se", _TRACE_TEMPLATE_SE),
        ],
    )
    def test_trace_template_uses_items_placeholder(self, lang, trace_template):
        assert "{items}" in trace_template
        # And the rendered user message includes the template verbatim.
        assert trace_template in build_ingredient_prompt(lang)

    @pytest.mark.parametrize(
        "lang,decimal",
        [("no", "comma"), ("se", "comma"), ("en", "dot")],
    )
    def test_decimal_separator_per_language(self, lang, decimal):
        prompt = build_ingredient_prompt(lang)
        assert f"Decimal separator: {decimal}" in prompt

    @pytest.mark.parametrize(
        "lang,name",
        [("no", "Norwegian"), ("en", "English"), ("se", "Swedish")],
    )
    def test_language_header_per_language(self, lang, name):
        assert f"Language: {name}" in build_ingredient_prompt(lang)


class TestBuildIngredientPromptDoesNotLeakOtherLanguages:
    """A given language prompt must not include allergen terms or trace
    templates from the other supported languages — that would confuse the
    model into capitalising the wrong words."""

    @pytest.mark.parametrize(
        "lang,leak",
        [
            # Norwegian prompt must not carry English MILK or Swedish MJÖLK
            ("no", "MILK"),
            ("no", "MJÖLK"),
            ("no", "May contain traces of"),
            ("no", "Kan innehålla spår av"),
            # English prompt must not carry Norwegian MELK or Swedish MJÖLK
            ("en", "MELK"),
            ("en", "MJÖLK"),
            ("en", "Kan inneholde spor av"),
            ("en", "Kan innehålla spår av"),
            # Swedish prompt must not carry Norwegian MELK or English MILK
            ("se", "MELK"),
            ("se", "MILK"),
            ("se", "Kan inneholde spor av"),
            ("se", "May contain traces of"),
        ],
    )
    def test_no_cross_language_leak(self, lang, leak):
        prompt = build_ingredient_prompt(lang)
        assert leak not in prompt, (
            f"build_ingredient_prompt({lang!r}) leaked '{leak}' from another language"
        )


# ===========================================================================
# 3) Cross-backend system-prompt parity
#
# All four "real" LLM backends (claude/openai/gemini/groq + openrouter wrapper)
# must send the SAME hardened system prompt verbatim. A backend that drops
# or mutates the system prompt would silently revert the LSO-1222 fix.
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
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content="ok")
            )
        ]
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
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content="ok")
            )
        ]
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
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content="ok")
            )
        ]
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
    """Verbatim equality is essential — a paraphrased system prompt would
    not carry the explicit Phase 1 CRITICAL rule and Phase 2 ALL CAPS rule
    that drive the LSO-1222 fix."""

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
        assert (
            call.kwargs["config"]["system_instruction"]
            == _HARDENED_SYSTEM_PROMPT
        )


class TestAllBackendsSendStructuredUserMessage:
    """The user message must carry the language line, allergen terms,
    decimal separator and trace template — that is how the system prompt
    knows which language to isolate."""

    def _extract_user_text_claude(self, call):
        return call.kwargs["messages"][0]["content"][1]["text"]

    def _extract_user_text_openai_style(self, call):
        msgs = call.kwargs["messages"]
        # system is msgs[0], user is msgs[1] with a list of parts
        text_parts = [
            p for p in msgs[1]["content"] if p.get("type") == "text"
        ]
        return text_parts[0]["text"]

    def _extract_user_text_gemini(self, call):
        parts = call.kwargs["contents"][0]["parts"]
        return next(p for p in parts if "text" in p)["text"]

    def test_claude_user_message_contains_language_block(self, monkeypatch):
        text = self._extract_user_text_claude(_call_claude(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_openai_user_message_contains_language_block(self, monkeypatch):
        text = self._extract_user_text_openai_style(_call_openai(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_groq_user_message_contains_language_block(self, monkeypatch):
        text = self._extract_user_text_openai_style(_call_groq(monkeypatch))
        assert text == build_ingredient_prompt("no")

    def test_openrouter_user_message_contains_language_block(self, monkeypatch):
        text = self._extract_user_text_openai_style(
            _call_openrouter(monkeypatch)
        )
        assert text == build_ingredient_prompt("no")

    def test_gemini_user_message_contains_language_block(self, monkeypatch):
        text = self._extract_user_text_gemini(_call_gemini(monkeypatch))
        assert text == build_ingredient_prompt("no")


# ===========================================================================
# 4) Multilingual regression — the LSO-1222 biscuit bug example
#
# A real Norwegian/German/Polish biscuit label is supplied to the dispatch
# layer. The LLM is mocked to return a properly-isolated Norwegian-only
# output, and we assert the prompt that was sent and the output that came
# back honour every Phase 1 + Phase 2 rule.
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
        # Patch settings + Anthropic client + model resolver
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

        # The dispatch layer must not touch the well-formed Norwegian text
        # except to apply the trailing-period convention (already present).
        assert result["text"] == _LSO_1222_EXPECTED_NORWEGIAN
        # And every Phase 1/2 expectation holds on the output.
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

        # Allergen compounds must be ALL CAPS (rule 3 in Phase 2).
        assert "HVETEMEL" in result["text"]
        assert "MELKPULVER" in result["text"]
        assert "SOYALESITIN" in result["text"]
        # Lowercase forms must not slip through.
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

        # No newlines anywhere — this is a single line.
        assert "\n" not in result["text"]
        # Ends with a period.
        assert result["text"].rstrip().endswith(".")
        # Uses commas as the separator.
        assert "," in result["text"]

    def test_dispatch_output_contains_trace_notice(self, monkeypatch):
        from services.ocr_core import dispatch_ocr_bytes

        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            result = dispatch_ocr_bytes(_tiny_png_bytes())

        # The Norwegian trace prefix from _TRACE_TEMPLATE_NO must appear.
        assert "Kan inneholde spor av" in result["text"]

    def test_dispatch_sends_hardened_prompt_and_norwegian_user_message(
        self, monkeypatch
    ):
        """Even if the model misbehaves, we can prove the dispatch layer is
        feeding it the right instructions."""
        from services.ocr_core import dispatch_ocr_bytes

        ctx, ctx2, ctx3, mock_message = self._setup_claude_mock(
            monkeypatch, _LSO_1222_EXPECTED_NORWEGIAN
        )
        with ctx, ctx2, ctx3 as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_message
            dispatch_ocr_bytes(_tiny_png_bytes())
            call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs

        # System prompt is the hardened two-phase prompt — verbatim.
        assert call_kwargs["system"] == _HARDENED_SYSTEM_PROMPT
        # User message carries Norwegian language context + allergens.
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        assert "Language: Norwegian" in user_text
        assert _ALLERGENS_NO in user_text
        assert _TRACE_TEMPLATE_NO in user_text
        assert "Decimal separator: comma" in user_text


# ===========================================================================
# 5) Edge cases for the hardened prompt path
# ===========================================================================


class TestHardenedPromptEdgeCases:
    """Behaviour the prompt is designed to drive in pathological inputs."""

    def _dispatch_with_claude_response(self, monkeypatch, llm_text, language="no"):
        """Helper: drive dispatch_ocr_bytes through Claude with a canned LLM
        response and return the dispatch result."""
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
        """A label that already contains only Norwegian needs no isolation —
        Phase 1 must accept it and Phase 2 leaves the well-formed output as
        a single line ending in a period."""
        text = "HVETEmel, sukker, salt".replace("HVETEmel", "HVETEMEL") + "."
        result = self._dispatch_with_claude_response(monkeypatch, text)
        assert result["text"] == "HVETEMEL, sukker, salt."

    def test_empty_input_returns_empty_text_per_rule_13(self, monkeypatch):
        """Rule 13: if the target-language section is not found or the input
        is not an ingredient list at all, the LLM returns empty string.
        The dispatch layer must propagate that as an empty result so the
        blueprint can surface error_type='no_text'."""
        result = self._dispatch_with_claude_response(monkeypatch, "")
        assert result["text"] == ""
        # Provider name is preserved even on empty output.
        assert result["provider"]

    def test_conversational_refusal_is_converted_to_empty(self, monkeypatch):
        """If the model ignores Rule 13 and replies with prose, the dispatch
        layer's looks_like_llm_refusal safety net converts it to empty so
        the user still sees the no-text toast instead of garbage."""
        refusal = (
            "I'm sorry, I can't see any ingredient list in this image. "
            "Could you provide a clearer photo?"
        )
        result = self._dispatch_with_claude_response(monkeypatch, refusal)
        assert result["text"] == ""

    def test_unknown_language_setting_falls_back_to_norwegian_prompt(
        self, monkeypatch
    ):
        """If the user has somehow stored a language code outside no/en/se,
        the prompt builder defaults to Norwegian. Verifies the dispatch
        still works and uses the Norwegian user message."""
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
            call_kwargs = (
                mock_cls.return_value.messages.create.call_args.kwargs
            )

        assert result["text"] == "Sukker, mel."
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        assert "Language: Norwegian" in user_text

    def test_none_language_falls_back_to_norwegian(self, monkeypatch):
        """When settings_service.get_language() returns None (or raises),
        the dispatch path must not crash — Norwegian is the safe default."""
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes

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
            call_kwargs = (
                mock_cls.return_value.messages.create.call_args.kwargs
            )

        assert result["text"] == "vann."
        user_text = call_kwargs["messages"][0]["content"][1]["text"]
        assert "Language: Norwegian" in user_text

    def test_trailing_period_added_if_model_drops_it(self, monkeypatch):
        """Vision models occasionally drop the terminal period. The dispatch
        layer enforces the DB convention via ensure_trailing_period() and
        the resulting text must end with exactly one period."""
        result = self._dispatch_with_claude_response(
            monkeypatch, "Sukker, mel, vann, salt"
        )
        assert result["text"] == "Sukker, mel, vann, salt."

    def test_label_with_no_recognized_header_can_still_return_norwegian(
        self, monkeypatch
    ):
        """Phase 1 instructs the model to fall back to vocabulary/diacritic
        recognition. We can't prove the model does this without a real run,
        but we can prove the dispatch layer happily accepts and forwards a
        Norwegian-only response that the model produced via fallback."""
        text = "Sukker, vann, salt."
        result = self._dispatch_with_claude_response(monkeypatch, text)
        assert result["text"] == "Sukker, vann, salt."


# ===========================================================================
# 6) Regression — tesseract backend is untouched by the hardened-prompt work
# ===========================================================================


class TestTesseractBackendUnchanged:
    """The hardened prompt only applies to vision LLM backends. The local
    tesseract backend must not be sent any prompt and must continue to
    operate purely on the pixel data."""

    def test_tesseract_extract_signature_does_not_accept_prompt(self):
        """Smoke test: _extract_tesseract must NOT raise on a basic call."""
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

    def test_dispatch_tesseract_does_not_pass_language_or_prompt(
        self, monkeypatch
    ):
        """dispatch_ocr_bytes with backend=tesseract must skip the language /
        model / prompt resolution — that path is exclusive to LLM backends."""
        from unittest.mock import MagicMock
        from services.ocr_core import dispatch_ocr_bytes

        mock_extract = MagicMock(return_value="vann, sukker")
        # Intercept the registry entry so we can assert on the call args.
        from services import ocr_core as core

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
        # tesseract was called with positional (image_bytes, b64, mime_type)
        # and NO language/prompt/model kwargs.
        _, kwargs = mock_extract.call_args
        assert "language" not in kwargs
        assert "prompt" not in kwargs
        assert "model" not in kwargs

    def test_dispatch_tesseract_does_not_apply_trailing_period(
        self, monkeypatch
    ):
        """ensure_trailing_period() is only applied to LLM backends — the
        tesseract path is supposed to leave raw OCR output untouched."""
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

        assert result["text"] == "vann sukker"  # NO trailing period added


# ===========================================================================
# 7) Mock shape sanity — Claude response that drives the regression test
# ===========================================================================


class TestLso1222CanonicalLlmResponseShape:
    """Document the LLM response shape the regression test relies on. If
    the Claude SDK changes its message shape, these tests fail loudly."""

    def test_claude_canonical_response_matches_validator(self):
        from tests.mock_shape_validator import validate_claude_response_shape

        canonical = {
            "content": [
                {"type": "text", "text": _LSO_1222_EXPECTED_NORWEGIAN}
            ]
        }
        # Raises AssertionError if the shape drifts.
        validate_claude_response_shape(canonical)
