"""Unit tests for services/llm_cleanup_service.py."""

from unittest.mock import MagicMock, create_autospec, patch

import pytest
import anthropic as _anthropic
from anthropic.resources.messages.messages import Messages as _AnthropicMessages


def _make_anthropic_mock(response_text):
    """Return (MockAnthropic_cls, mock_client_instance) ready to return response_text.

    Uses create_autospec on the Messages resource (Rule 8 shape validation).
    """
    mock_messages = create_autospec(_AnthropicMessages, instance=True)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_messages.create.return_value = mock_response

    MockClass = MagicMock()
    mock_instance = MockClass.return_value
    mock_instance.messages = mock_messages
    return MockClass, mock_instance


def _patch_anthropic(MockClass):
    """Return a context manager that replaces the anthropic module in the service."""
    mock_mod = MagicMock()
    mock_mod.Anthropic = MockClass
    return patch("services.llm_cleanup_service.anthropic", mock_mod)


class TestCleanupIngredientsSuccess:
    def test_returns_cleaned_text_and_skipped_false(self, monkeypatch):
        MockClass, _ = _make_anthropic_mock("sukker, salt, HVETEMEL.")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("INGREDIENSER: sukker salt hvetemel", "no")

        assert result["text"] == "sukker, salt, HVETEMEL."
        assert result["llm_cleanup_skipped"] is False

    def test_passes_raw_text_to_api(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw ingredient text", "no")

        call_kwargs = mock_instance.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "raw ingredient text" in user_content


class TestCleanupIngredientsSkip:
    def test_empty_string_returns_empty_and_skipped(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        from services.llm_cleanup_service import cleanup_ingredients
        result = cleanup_ingredients("", "no")
        assert result == {"text": "", "llm_cleanup_skipped": True}

    def test_none_returns_empty_and_skipped(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        from services.llm_cleanup_service import cleanup_ingredients
        result = cleanup_ingredients(None, "no")
        assert result == {"text": "", "llm_cleanup_skipped": True}

    def test_missing_api_key_returns_raw_text(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from services.llm_cleanup_service import cleanup_ingredients
        result = cleanup_ingredients("linser, solsikkeolje", "no")
        assert result["text"] == "linser, solsikkeolje"
        assert result["llm_cleanup_skipped"] is True

    def test_empty_string_does_not_call_api(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("should not be called")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("", "no")

        mock_instance.messages.create.assert_not_called()

    def test_missing_api_key_does_not_call_api(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("should not be called")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw text", "no")

        mock_instance.messages.create.assert_not_called()


class TestRefusalDetection:
    @pytest.mark.parametrize("phrase,context", [
        ("I cannot", "I cannot process this text as it is not an ingredient list."),
        ("I don't see", "I don't see any ingredient list in the provided text."),
        ("please provide", "please provide the actual ingredient list text."),
        ("I'm happy to help", "I'm happy to help, but I need more context."),
    ])
    def test_refusal_phrase_triggers_skip(self, monkeypatch, phrase, context):
        MockClass, _ = _make_anthropic_mock(context)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("some text", "no")

        assert result["text"] == "some text"
        assert result["llm_cleanup_skipped"] is True


class TestErrorHandling:
    def test_api_error_returns_raw_text(self, monkeypatch):
        mock_messages = create_autospec(_AnthropicMessages, instance=True)
        mock_messages.create.side_effect = Exception("API connection error")
        MockClass = MagicMock()
        MockClass.return_value.messages = mock_messages
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("raw ingredients", "no")

        assert result["text"] == "raw ingredients"
        assert result["llm_cleanup_skipped"] is True

    def test_timeout_returns_raw_text(self, monkeypatch):
        mock_messages = create_autospec(_AnthropicMessages, instance=True)
        mock_messages.create.side_effect = TimeoutError("Request timed out")
        MockClass = MagicMock()
        MockClass.return_value.messages = mock_messages
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("raw text", "no")

        assert result["text"] == "raw text"
        assert result["llm_cleanup_skipped"] is True

    def test_anthropic_api_status_error_returns_raw_text(self, monkeypatch):
        mock_messages = create_autospec(_AnthropicMessages, instance=True)
        mock_messages.create.side_effect = _anthropic.APIStatusError(
            "timeout", response=MagicMock(status_code=408), body={}
        )
        MockClass = MagicMock()
        MockClass.return_value.messages = mock_messages
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("raw text", "no")

        assert result["text"] == "raw text"
        assert result["llm_cleanup_skipped"] is True


class TestLanguagePlaceholders:
    def _get_user_content(self, mock_instance):
        call_kwargs = mock_instance.messages.create.call_args.kwargs
        return call_kwargs["messages"][0]["content"]

    def test_norwegian_placeholders(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw text", "no")

        content = self._get_user_content(mock_instance)
        assert "Norsk" in content
        assert "Decimal separator: ," in content
        assert "MELK" in content
        assert "Kan inneholde spor av" in content

    def test_english_placeholders(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw text", "en")

        content = self._get_user_content(mock_instance)
        assert "English" in content
        assert "Decimal separator: ." in content
        assert "MILK" in content
        assert "May contain traces of" in content

    def test_swedish_placeholders(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw text", "se")

        content = self._get_user_content(mock_instance)
        assert "Svenska" in content
        assert "Decimal separator: ," in content
        assert "MJÖLK" in content
        assert "Kan innehålla spår av" in content

    def test_invalid_lang_returns_raw_text(self, monkeypatch):
        MockClass, _ = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            result = cleanup_ingredients("raw text", "xx")

        assert result["text"] == "raw text"
        assert result["llm_cleanup_skipped"] is True

    def test_correct_model_used(self, monkeypatch):
        MockClass, mock_instance = _make_anthropic_mock("cleaned")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with _patch_anthropic(MockClass):
            from services.llm_cleanup_service import cleanup_ingredients
            cleanup_ingredients("raw text", "no")

        call_kwargs = mock_instance.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["temperature"] == 0
