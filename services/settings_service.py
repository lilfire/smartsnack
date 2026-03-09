"""Service for managing user settings (language, OFF credentials)."""

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from db import get_db
from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

_FERNET_PREFIX = "fernet:"


def _get_fernet() -> Fernet:
    """Return a Fernet instance using a key derived from the environment secret."""
    secret = os.environ.get("SMARTSNACK_SECRET_KEY", "")
    if not secret:
        logger.warning(
            "SMARTSNACK_SECRET_KEY not set; using insecure default key"
        )
        secret = "smartsnack-default-key-change-me"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    """Encrypt plaintext using Fernet, returning a prefixed token string."""
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return _FERNET_PREFIX + token.decode("ascii")


def _decrypt(stored: str) -> str:
    """Decrypt a stored value. Handles both Fernet and legacy XOR formats."""
    if stored.startswith(_FERNET_PREFIX):
        token = stored[len(_FERNET_PREFIX):].encode("ascii")
        return _get_fernet().decrypt(token).decode("utf-8")
    # Legacy XOR fallback for existing data
    try:
        key = os.environ.get("SMARTSNACK_SECRET_KEY", "")
        if not key:
            key = "smartsnack-default-key-change-me"
        key_bytes = key.encode("utf-8")[:32].ljust(32, b"\0")
        encrypted = base64.b64decode(stored)
        decrypted = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(encrypted))
        return decrypted.decode("utf-8")
    except Exception:
        return stored


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
            password = _decrypt(pass_row["value"])
        except (InvalidToken, Exception):
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
    encrypted_password = _encrypt(password.strip())
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) "
        "VALUES ('off_password', ?)", (encrypted_password,),
    )
    conn.commit()
