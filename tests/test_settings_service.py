"""Tests for services/settings_service.py — language and credentials."""

import pytest

from db import get_db


class TestGetSetLanguage:
    def test_get_default_language(self, app_ctx):
        from services.settings_service import get_language

        assert get_language() == "no"

    def test_set_valid_language(self, app_ctx):
        from services.settings_service import set_language, get_language

        result = set_language("en")
        assert result == "en"
        assert get_language() == "en"

    def test_set_unsupported_language(self, app_ctx):
        from services.settings_service import set_language

        with pytest.raises(ValueError, match="Unsupported language"):
            set_language("xx")

    def test_strips_whitespace(self, app_ctx):
        from services.settings_service import set_language

        result = set_language("  no  ")
        assert result == "no"


class TestEncryptDecrypt:
    def test_roundtrip(self, app_ctx):
        from services.settings_service import _encrypt, _decrypt

        plaintext = "my secret password"
        encrypted = _encrypt(plaintext)
        assert encrypted.startswith("fernet:")
        decrypted = _decrypt(encrypted)
        assert decrypted == plaintext

    def test_different_encryptions(self, app_ctx):
        from services.settings_service import _encrypt

        enc1 = _encrypt("test")
        enc2 = _encrypt("test")
        # Fernet uses random IV so they should differ
        assert enc1 != enc2

    def test_no_secret_key_generates_random(self, app_ctx, monkeypatch):
        monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "")
        from services.settings_service import _encrypt

        # Should not raise — generates a random key when env var is empty
        result = _encrypt("test")
        assert result.startswith("fernet:")


class TestOffCredentials:
    def test_get_empty_credentials(self, app_ctx):
        from services.settings_service import get_off_credentials

        creds = get_off_credentials()
        assert creds["off_user_id"] == ""
        assert creds["off_password"] == ""

    def test_set_and_get_credentials(self, app_ctx):
        from services.settings_service import set_off_credentials, get_off_credentials

        set_off_credentials("user@example.com", "mypassword")
        creds = get_off_credentials()
        assert creds["off_user_id"] == "user@example.com"
        assert creds["off_password"] == "mypassword"

    def test_password_encrypted_in_db(self, app_ctx):
        from services.settings_service import set_off_credentials

        set_off_credentials("user@example.com", "mypassword")
        from db import get_db

        row = (
            get_db()
            .execute("SELECT value FROM user_settings WHERE key='off_password'")
            .fetchone()
        )
        assert row["value"].startswith("fernet:")
        assert "mypassword" not in row["value"]


class TestOcrBackendKeyAlignment:
    """Fix 1: get/set_ocr_backend must use 'ocr_provider' DB key to match
    what ocr_settings_service.save_ocr_settings() writes."""

    def test_get_ocr_backend_reads_ocr_provider_key(self, app_ctx):
        """get_ocr_backend() should read the 'ocr_provider' key from DB."""
        from services.settings_service import get_ocr_backend

        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('ocr_provider', 'gemini')"
        )
        conn.commit()

        assert get_ocr_backend() == "gemini"

    def test_set_ocr_backend_writes_ocr_provider_key(self, app_ctx):
        """set_ocr_backend() should write to the 'ocr_provider' key in DB."""
        from services.settings_service import set_ocr_backend

        set_ocr_backend("claude_vision")

        conn = get_db()
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key='ocr_provider'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "claude_vision"

    def test_roundtrip_with_ocr_settings_service(self, app_ctx):
        """Value written by ocr_settings_service should be readable by get_ocr_backend()."""
        from services.ocr_settings_service import save_ocr_settings
        from services.settings_service import get_ocr_backend

        save_ocr_settings("openai", fallback_to_tesseract=True)
        assert get_ocr_backend() == "openai"
