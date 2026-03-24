"""Tests for services/settings_service.py — language and credentials."""

import pytest


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
