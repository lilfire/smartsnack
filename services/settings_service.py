"""Service for managing user settings (language, OFF credentials)."""

import base64
import os

from db import get_db
from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


def _get_encryption_key() -> bytes:
    """Return encryption key from environment or a default."""
    key = os.environ.get("SMARTSNACK_SECRET_KEY", "")
    if not key:
        key = "smartsnack-default-key-change-me"
    return key.encode("utf-8")[:32].ljust(32, b"\0")


def _xor_encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt plaintext using XOR with the given key, return base64."""
    data = plaintext.encode("utf-8")
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.b64encode(encrypted).decode("ascii")


def _xor_decrypt(encoded: str, key: bytes) -> str:
    """Decrypt base64-encoded XOR-encrypted data."""
    encrypted = base64.b64decode(encoded)
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
    return decrypted.decode("utf-8")


def get_language() -> str:
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key='language'"
    ).fetchone()
    return row["value"] if row else DEFAULT_LANGUAGE


def set_language(lang: str) -> str:
    lang = lang.strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) "
        "VALUES ('language', ?)", (lang,),
    )
    conn.commit()
    return lang


def get_off_credentials() -> dict:
    conn = get_db()
    user_row = conn.execute(
        "SELECT value FROM user_settings WHERE key='off_user_id'"
    ).fetchone()
    pass_row = conn.execute(
        "SELECT value FROM user_settings WHERE key='off_password'"
    ).fetchone()
    password = ""
    if pass_row and pass_row["value"]:
        try:
            password = _xor_decrypt(pass_row["value"], _get_encryption_key())
        except Exception:
            password = pass_row["value"]
    return {
        "off_user_id": user_row["value"] if user_row else "",
        "off_password": password,
    }


def set_off_credentials(user_id: str, password: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) "
        "VALUES ('off_user_id', ?)", (user_id.strip(),),
    )
    encrypted_password = _xor_encrypt(password.strip(), _get_encryption_key())
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) "
        "VALUES ('off_password', ?)", (encrypted_password,),
    )
    conn.commit()
