"""Service for managing user settings (language, OFF credentials)."""

import base64
import hashlib
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from db import get_db
import json

from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, OCR_BACKENDS, DEFAULT_OCR_BACKEND

logger = logging.getLogger(__name__)


def _resolve_secret_key() -> str:
    """Return the encryption secret, generating a persistent random key if not set."""
    secret = os.environ.get("SMARTSNACK_SECRET_KEY", "")
    if secret:
        return secret
    # Generate a persistent key in the data directory so it survives restarts
    data_dir = os.path.dirname(os.environ.get("DB_PATH", "/data/smartsnack.sqlite"))
    key_file = os.path.join(data_dir, ".smartsnack_secret_key")
    try:
        if os.path.exists(key_file):
            secret = open(key_file).read().strip()
            if secret:
                return secret
        secret = secrets.token_hex(32)
        os.makedirs(data_dir, exist_ok=True)
        with open(key_file, "w") as f:
            f.write(secret)
        logger.warning(
            "SMARTSNACK_SECRET_KEY not set. Generated random key at %s. "
            "Set the environment variable for production use.",
            key_file,
        )
        return secret
    except OSError:
        raise RuntimeError(
            "SMARTSNACK_SECRET_KEY environment variable is required "
            "for credential encryption. Set it before starting the app."
        )

_FERNET_PREFIX = "fernet:"


def _get_fernet() -> Fernet:
    """Return a Fernet instance using a key derived from the environment secret."""
    secret = _resolve_secret_key()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    """Encrypt plaintext using Fernet, returning a prefixed token string."""
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return _FERNET_PREFIX + token.decode("ascii")


def _decrypt(stored: str) -> str:
    """Decrypt a stored value. Handles both Fernet and legacy XOR formats."""
    if stored.startswith(_FERNET_PREFIX):
        token = stored[len(_FERNET_PREFIX) :].encode("ascii")
        return _get_fernet().decrypt(token).decode("utf-8")
    # Legacy XOR fallback for existing data -- migrate to Fernet on read
    try:
        key = os.environ.get("SMARTSNACK_SECRET_KEY", "")
        if not key:
            logger.warning("Cannot decrypt legacy value: SMARTSNACK_SECRET_KEY not set")
            return stored
        key_bytes = key.encode("utf-8")[:32].ljust(32, b"\0")
        encrypted = base64.b64decode(stored)
        decrypted = bytes(
            b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(encrypted)
        )
        plaintext = decrypted.decode("utf-8")
        # Re-encrypt with Fernet so legacy XOR encoding is replaced
        try:
            re_encrypted = _encrypt(plaintext)
            conn = get_db()
            conn.execute(
                "UPDATE user_settings SET value = ? WHERE value = ?",
                (re_encrypted, stored),
            )
            conn.commit()
            logger.info("Migrated legacy XOR-encrypted value to Fernet")
        except Exception:
            logger.warning("Failed to re-encrypt legacy value with Fernet")
        return plaintext
    except (ValueError, UnicodeDecodeError):
        logger.warning("Failed to decrypt legacy value, returning as-is")
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
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('language', ?)",
        (lang,),
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
        except InvalidToken:
            logger.warning("Failed to decrypt OFF password")
            password = ""
    return {
        "off_user_id": user_row["value"] if user_row else "",
        "off_password": password,
    }


def set_off_credentials(user_id: str, password: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('off_user_id', ?)",
        (user_id.strip(),),
    )
    encrypted_password = _encrypt(password.strip())
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('off_password', ?)",
        (encrypted_password,),
    )
    conn.commit()


def get_ocr_backend() -> str:
    """Return the currently selected OCR backend ID, defaulting to tesseract."""
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key='ocr_provider'"
    ).fetchone()
    return row["value"] if row else DEFAULT_OCR_BACKEND


def set_ocr_backend(backend_id: str) -> str:
    """Store the selected OCR backend. Raises ValueError if unrecognized."""
    backend_id = backend_id.strip()
    if backend_id not in OCR_BACKENDS:
        raise ValueError(
            f"Unrecognized OCR backend '{backend_id}'. "
            f"Valid: {', '.join(OCR_BACKENDS.keys())}"
        )
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('ocr_provider', ?)",
        (backend_id,),
    )
    conn.commit()
    return backend_id


_OFF_LANGUAGE_PRIORITY_KEY = "off_language_priority"


def get_off_language_priority() -> list:
    """Return the OFF language priority list, defaulting to [current_language]."""
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (_OFF_LANGUAGE_PRIORITY_KEY,),
    ).fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            pass
    return [get_language()]


def set_off_language_priority(priority: list) -> None:
    """Save the OFF language priority list as JSON."""
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
        (_OFF_LANGUAGE_PRIORITY_KEY, json.dumps(priority)),
    )
    conn.commit()
