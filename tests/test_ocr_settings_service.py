"""Tests for OCR settings service (provider listing + settings persistence)."""

import os

import pytest


@pytest.fixture()
def ocr_service(app_ctx):
    """Import the service inside an app context so DB is available."""
    from services import ocr_settings_service
    return ocr_settings_service


class TestGetProviders:
    """Tests for get_providers()."""

    def test_tesseract_always_present(self, ocr_service, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        providers = ocr_service.get_providers()
        assert len(providers) == 1
        assert providers[0]["key"] == "tesseract"
        assert providers[0]["label"] == "Tesseract OCR"

    def test_tesseract_is_always_first(self, ocr_service, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
        monkeypatch.setenv("OPENAI_API_KEY", "ok-test")
        providers = ocr_service.get_providers()
        assert providers[0]["key"] == "tesseract"

    def test_claude_vision_when_anthropic_key_set(self, ocr_service, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        providers = ocr_service.get_providers()
        keys = [p["key"] for p in providers]
        assert "claude_vision" in keys
        assert providers[1]["label"] == "Claude Vision"

    def test_gemini_when_key_set(self, ocr_service, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        providers = ocr_service.get_providers()
        keys = [p["key"] for p in providers]
        assert "gemini" in keys

    def test_openai_when_key_set(self, ocr_service, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "ok-test")
        providers = ocr_service.get_providers()
        keys = [p["key"] for p in providers]
        assert "openai" in keys

    def test_all_providers_when_all_keys_set(self, ocr_service, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
        monkeypatch.setenv("OPENAI_API_KEY", "ok-test")
        providers = ocr_service.get_providers()
        keys = [p["key"] for p in providers]
        assert keys == ["tesseract", "claude_vision", "gemini", "openai"]

    def test_empty_env_var_not_included(self, ocr_service, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        providers = ocr_service.get_providers()
        keys = [p["key"] for p in providers]
        assert "claude_vision" not in keys

    def test_no_api_key_values_exposed(self, ocr_service, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-123")
        monkeypatch.setenv("GEMINI_API_KEY", "gk-secret-456")
        monkeypatch.setenv("OPENAI_API_KEY", "ok-secret-789")
        providers = ocr_service.get_providers()
        for p in providers:
            # Only key and label should be present
            assert set(p.keys()) == {"key", "label"}
            assert "secret" not in str(p)


class TestGetSettings:
    """Tests for get_ocr_settings()."""

    def test_default_settings(self, ocr_service):
        settings = ocr_service.get_ocr_settings()
        assert settings["provider"] == "tesseract"
        assert settings["fallback_to_tesseract"] is False

    def test_returns_saved_settings(self, ocr_service):
        ocr_service.save_ocr_settings("claude_vision", True)
        settings = ocr_service.get_ocr_settings()
        assert settings["provider"] == "claude_vision"
        assert settings["fallback_to_tesseract"] is True


class TestSaveSettings:
    """Tests for save_ocr_settings()."""

    def test_save_and_load(self, ocr_service):
        ocr_service.save_ocr_settings("gemini", True)
        settings = ocr_service.get_ocr_settings()
        assert settings["provider"] == "gemini"
        assert settings["fallback_to_tesseract"] is True

    def test_save_overwrite(self, ocr_service):
        ocr_service.save_ocr_settings("gemini", True)
        ocr_service.save_ocr_settings("openai", False)
        settings = ocr_service.get_ocr_settings()
        assert settings["provider"] == "openai"
        assert settings["fallback_to_tesseract"] is False

    def test_save_invalid_provider_raises(self, ocr_service):
        with pytest.raises(ValueError, match="Invalid provider"):
            ocr_service.save_ocr_settings("invalid_provider", False)

    def test_save_tesseract_provider(self, ocr_service):
        ocr_service.save_ocr_settings("tesseract", False)
        settings = ocr_service.get_ocr_settings()
        assert settings["provider"] == "tesseract"
