"""Service for OCR provider listing and settings persistence."""

import os

from db import get_db

VALID_PROVIDERS = {"tesseract", "claude_vision", "gemini", "openai"}

_LLM_PROVIDERS = [
    {"env_var": "ANTHROPIC_API_KEY", "key": "claude_vision", "label": "Claude Vision"},
    {"env_var": "GEMINI_API_KEY", "key": "gemini", "label": "Gemini"},
    {"env_var": "OPENAI_API_KEY", "key": "openai", "label": "OpenAI"},
]


def get_providers():
    """Return available OCR providers based on env var presence.

    Tesseract is always included first. LLM providers are included
    only when their corresponding env var is set and non-empty.
    Never exposes actual API key values.
    """
    providers = [{"key": "tesseract", "label": "Tesseract OCR"}]
    for p in _LLM_PROVIDERS:
        if os.environ.get(p["env_var"]):
            providers.append({"key": p["key"], "label": p["label"]})
    return providers


def get_ocr_settings():
    """Load current OCR settings from the database.

    Returns default (tesseract, fallback=false) if no settings exist.
    """
    conn = get_db()
    provider_row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?", ("ocr_provider",)
    ).fetchone()
    fallback_row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?", ("ocr_fallback_to_tesseract",)
    ).fetchone()
    return {
        "provider": provider_row["value"] if provider_row else "tesseract",
        "fallback_to_tesseract": (fallback_row["value"] == "1") if fallback_row else False,
    }


def save_ocr_settings(provider, fallback_to_tesseract):
    """Persist OCR provider and fallback preference.

    Raises ValueError if provider is not a valid provider key.
    """
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Invalid provider: {provider}")
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
        ("ocr_provider", provider),
    )
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
        ("ocr_fallback_to_tesseract", "1" if fallback_to_tesseract else "0"),
    )
    conn.commit()
