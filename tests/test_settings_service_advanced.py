"""Additional tests for settings_service — legacy decryption, edge cases."""

import base64

import pytest


class TestLegacyXorDecrypt:
    """Test the legacy XOR decryption fallback and migration to Fernet."""

    def _xor_encrypt(self, plaintext: str, key: str) -> str:
        """Reproduce the legacy XOR encryption for testing."""
        key_bytes = key.encode("utf-8")[:32].ljust(32, b"\0")
        plain_bytes = plaintext.encode("utf-8")
        encrypted = bytes(
            b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(plain_bytes)
        )
        return base64.b64encode(encrypted).decode("ascii")

    def test_legacy_xor_decryption(self, app_ctx, monkeypatch):
        from services.settings_service import _decrypt

        secret = "test-secret-key-for-unit-tests"
        legacy_encrypted = self._xor_encrypt("legacy_password", secret)
        result = _decrypt(legacy_encrypted)
        assert result == "legacy_password"

    def test_legacy_xor_migrates_to_fernet(self, app_ctx, db, monkeypatch):
        """After decrypting a legacy value, it should be re-encrypted with Fernet."""
        from services.settings_service import _decrypt

        secret = "test-secret-key-for-unit-tests"
        legacy_encrypted = self._xor_encrypt("migrate_me", secret)

        # Store legacy value in DB
        db.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('off_password', ?)",
            (legacy_encrypted,),
        )
        db.commit()

        result = _decrypt(legacy_encrypted)
        assert result == "migrate_me"

        # Verify it was re-encrypted with Fernet in DB
        row = db.execute(
            "SELECT value FROM user_settings WHERE key='off_password'"
        ).fetchone()
        assert row["value"].startswith("fernet:")

    def test_legacy_decrypt_invalid_base64_returns_as_is(self, app_ctx, monkeypatch):
        from services.settings_service import _decrypt

        # Not valid base64 and not fernet-prefixed
        result = _decrypt("not-valid-anything-!!!")
        assert result == "not-valid-anything-!!!"


class TestDecryptInvalidToken:
    def test_invalid_fernet_token(self, app_ctx):
        from services.settings_service import _decrypt
        from cryptography.fernet import InvalidToken

        with pytest.raises(InvalidToken):
            _decrypt("fernet:invalid-token-data")


class TestGetFernet:
    def test_missing_secret_key_generates_random(self, app_ctx, monkeypatch):
        monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "")
        from services.settings_service import _get_fernet

        # Should not raise — generates a random key when env var is empty
        fernet = _get_fernet()
        assert fernet is not None

    def test_valid_secret_key(self, app_ctx):
        from services.settings_service import _get_fernet

        fernet = _get_fernet()
        assert fernet is not None
