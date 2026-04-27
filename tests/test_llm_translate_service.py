"""Tests for services/llm_translate_service.py"""

import os
import types
from unittest.mock import MagicMock, patch

import pytest

import services.llm_translate_service as svc


# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------

def test_is_available_false_when_no_keys(monkeypatch):
    for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    assert svc.is_available() is False


@pytest.mark.parametrize("key", [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"
])
def test_is_available_true_when_key_set(monkeypatch, key):
    for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(key, "test-key")
    assert svc.is_available() is True


# ---------------------------------------------------------------------------
# _build_prompt() — language names & structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,name", [
    ("no", "Norwegian"),
    ("en", "English"),
    ("se", "Swedish"),
])
def test_build_prompt_language_names(code, name):
    prompt = svc._build_prompt("sugar, water", code)
    assert name in prompt


def test_build_prompt_contains_ingredients():
    text = "sugar, water, salt"
    prompt = svc._build_prompt(text, "en")
    assert text in prompt


def test_build_prompt_structure():
    prompt = svc._build_prompt("sugar", "no")
    assert "Rules:" in prompt
    assert "Ingredients:" in prompt
    assert "Return only the translated ingredients text" in prompt


def test_build_prompt_unknown_lang_uses_code():
    prompt = svc._build_prompt("sugar", "fr")
    assert "fr" in prompt


# ---------------------------------------------------------------------------
# translate_ingredients() — Claude backend
# ---------------------------------------------------------------------------

def test_translate_returns_translation_via_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_content = types.SimpleNamespace(text="Sukker, vann")
    mock_msg = types.SimpleNamespace(content=[mock_content])

    mock_client = MagicMock(spec=["messages"])
    mock_client.messages.create.return_value = mock_msg
    mock_anthropic = types.SimpleNamespace(Anthropic=lambda **kwargs: mock_client)

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        result = svc.translate_ingredients("Sugar, water", "no")

    assert result == "Sukker, vann"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["max_tokens"] == 2048
    assert call_kwargs["temperature"] == 0
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# translate_ingredients() — OpenAI backend
# ---------------------------------------------------------------------------

def test_translate_returns_translation_via_openai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_choice = types.SimpleNamespace(message=types.SimpleNamespace(content="Sukker, vann"))
    mock_resp = types.SimpleNamespace(choices=[mock_choice])

    mock_client = MagicMock(spec=["chat"])
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai = types.SimpleNamespace(OpenAI=lambda **kwargs: mock_client)

    with patch.dict("sys.modules", {"openai": mock_openai}):
        result = svc.translate_ingredients("Sugar, water", "no")

    assert result == "Sukker, vann"


# ---------------------------------------------------------------------------
# translate_ingredients() — Gemini backend
# ---------------------------------------------------------------------------

def test_translate_returns_translation_via_gemini(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_resp = types.SimpleNamespace(text="Sukker, vann")
    mock_model = MagicMock(spec=["generate_content"])
    mock_model.generate_content.return_value = mock_resp
    mock_genai = types.SimpleNamespace(
        configure=lambda **kwargs: None,
        GenerativeModel=lambda *args, **kwargs: mock_model,
    )

    mock_google = types.SimpleNamespace(generativeai=mock_genai)

    with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": mock_google}):
        result = svc.translate_ingredients("Sugar, water", "no")

    assert result == "Sukker, vann"


# ---------------------------------------------------------------------------
# translate_ingredients() — Groq backend
# ---------------------------------------------------------------------------

def test_translate_returns_translation_via_groq(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    mock_choice = types.SimpleNamespace(message=types.SimpleNamespace(content="Sukker, vann"))
    mock_resp = types.SimpleNamespace(choices=[mock_choice])

    mock_client = MagicMock(spec=["chat"])
    mock_client.chat.completions.create.return_value = mock_resp
    mock_groq = types.SimpleNamespace(Groq=lambda **kwargs: mock_client)

    with patch.dict("sys.modules", {"groq": mock_groq}):
        result = svc.translate_ingredients("Sugar, water", "no")

    assert result == "Sukker, vann"


# ---------------------------------------------------------------------------
# translate_ingredients() — error handling & edge cases
# ---------------------------------------------------------------------------

def test_translate_returns_original_on_exception(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_client = MagicMock(spec=["messages"])
    mock_client.messages.create.side_effect = Exception("API error")
    mock_anthropic = types.SimpleNamespace(Anthropic=lambda **kwargs: mock_client)

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        result = svc.translate_ingredients("Sugar, water", "no")

    assert result == "Sugar, water"


def test_translate_empty_text_returns_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    result = svc.translate_ingredients("", "no")
    assert result == ""


def test_translate_no_backends_returns_original(monkeypatch):
    for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    result = svc.translate_ingredients("Sugar, water", "no")
    assert result == "Sugar, water"


def test_translate_backend_priority_claude_first(monkeypatch):
    """Claude is tried before OpenAI when both keys are set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_content = types.SimpleNamespace(text="from-claude")
    mock_msg = types.SimpleNamespace(content=[mock_content])
    mock_client = MagicMock(spec=["messages"])
    mock_client.messages.create.return_value = mock_msg
    mock_anthropic = types.SimpleNamespace(Anthropic=lambda **kwargs: mock_client)

    mock_openai_constructor = MagicMock(spec=["__call__"])
    mock_openai = types.SimpleNamespace(OpenAI=mock_openai_constructor)

    with patch.dict("sys.modules", {"anthropic": mock_anthropic, "openai": mock_openai}):
        result = svc.translate_ingredients("Sugar", "no")

    assert result == "from-claude"
    mock_openai_constructor.assert_not_called()


# ---------------------------------------------------------------------------
# off_search() integration — translation conditions
# ---------------------------------------------------------------------------

def test_off_search_translates_when_all_conditions_met():
    """Translation IS called when ingredients non-empty, lang mismatch, LLM available, no native variant."""
    from services.proxy_service import off_search
    import services.llm_translate_service as translate_svc

    product = {
        "code": "1234",
        "lang": "de",
        "product_name": "Testprodukt",
        "product_name_no": "",
        "ingredients_text": "Zucker, Wasser",
        "ingredients_text_no": "",
        "nutriments": {},
        "completeness": 0.5,
    }

    with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}, autospec=True), \
         patch("services.proxy_service._off_search_classic", return_value={"products": []}, autospec=True), \
         patch("services.settings_service.get_off_language_priority", return_value=["no", "en"], autospec=True), \
         patch.object(translate_svc, "is_available", return_value=True, autospec=True), \
         patch.object(translate_svc, "translate_ingredients", return_value="Sukker, vann", autospec=True) as mock_translate:
        result = off_search("Testprodukt")

    p = result["products"][0]
    assert p["ingredients_text"] == "Sukker, vann"
    assert p.get("ingredients_translated") is True
    mock_translate.assert_called_once_with("Zucker, Wasser", "no")


def test_off_search_no_translation_when_lang_matches():
    """Translation NOT called when product lang matches user's priority language."""
    from services.proxy_service import off_search
    import services.llm_translate_service as translate_svc

    product = {
        "code": "1234",
        "lang": "no",
        "product_name": "Testprodukt",
        "ingredients_text": "Sukker, vann",
        "ingredients_text_no": "",
        "nutriments": {},
        "completeness": 0.5,
    }

    with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}, autospec=True), \
         patch("services.proxy_service._off_search_classic", return_value={"products": []}, autospec=True), \
         patch("services.settings_service.get_off_language_priority", return_value=["no", "en"], autospec=True), \
         patch.object(translate_svc, "is_available", return_value=True, autospec=True), \
         patch.object(translate_svc, "translate_ingredients", return_value="should not be called", autospec=True) as mock_translate:
        result = off_search("Testprodukt")

    mock_translate.assert_not_called()
    assert result["products"][0].get("ingredients_translated") is None


def test_off_search_no_translation_when_ingredients_empty():
    """Translation NOT called when ingredients_text is empty."""
    from services.proxy_service import off_search
    import services.llm_translate_service as translate_svc

    product = {
        "code": "1234",
        "lang": "de",
        "product_name": "Testprodukt",
        "ingredients_text": "",
        "ingredients_text_no": "",
        "nutriments": {},
        "completeness": 0.5,
    }

    with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}, autospec=True), \
         patch("services.proxy_service._off_search_classic", return_value={"products": []}, autospec=True), \
         patch("services.settings_service.get_off_language_priority", return_value=["no", "en"], autospec=True), \
         patch.object(translate_svc, "is_available", return_value=True, autospec=True), \
         patch.object(translate_svc, "translate_ingredients", autospec=True) as mock_translate:
        off_search("Testprodukt")

    mock_translate.assert_not_called()


def test_off_search_no_translation_when_llm_unavailable():
    """Translation NOT called when no LLM backend is available."""
    from services.proxy_service import off_search
    import services.llm_translate_service as translate_svc

    product = {
        "code": "1234",
        "lang": "de",
        "product_name": "Testprodukt",
        "ingredients_text": "Zucker, Wasser",
        "ingredients_text_no": "",
        "nutriments": {},
        "completeness": 0.5,
    }

    with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}, autospec=True), \
         patch("services.proxy_service._off_search_classic", return_value={"products": []}, autospec=True), \
         patch("services.settings_service.get_off_language_priority", return_value=["no", "en"], autospec=True), \
         patch.object(translate_svc, "is_available", return_value=False, autospec=True), \
         patch.object(translate_svc, "translate_ingredients", autospec=True) as mock_translate:
        off_search("Testprodukt")

    mock_translate.assert_not_called()


def test_off_search_no_translation_when_native_variant_exists():
    """Translation NOT called when native language variant already found by _pick_by_priority."""
    from services.proxy_service import off_search
    import services.llm_translate_service as translate_svc

    product = {
        "code": "1234",
        "lang": "de",
        "product_name": "Testprodukt",
        "ingredients_text": "Zucker, Wasser",
        "ingredients_text_no": "Sukker, vann",  # native variant present
        "nutriments": {},
        "completeness": 0.5,
    }

    with patch("services.proxy_service._off_search_a_licious", return_value={"products": [product]}, autospec=True), \
         patch("services.proxy_service._off_search_classic", return_value={"products": []}, autospec=True), \
         patch("services.settings_service.get_off_language_priority", return_value=["no", "en"], autospec=True), \
         patch.object(translate_svc, "is_available", return_value=True, autospec=True), \
         patch.object(translate_svc, "translate_ingredients", autospec=True) as mock_translate:
        off_search("Testprodukt")

    mock_translate.assert_not_called()
