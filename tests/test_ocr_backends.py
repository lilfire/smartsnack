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
