"""Service for OCR provider listing and settings persistence."""

import os

from config import OCR_BACKENDS
from db import get_db

VALID_PROVIDERS = set(OCR_BACKENDS.keys())


def get_providers():
    """Return available OCR providers based on env var presence.

    Tesseract is always included first. LLM providers are included
    only when their corresponding env var is set and non-empty.
    Never exposes actual API key values.
    """
    providers = []
    for key, info in OCR_BACKENDS.items():
        env_key = info.get("env_key")
        if env_key is not None and not os.environ.get(env_key):
            continue
        providers.append({
            "key": key,
            "label": info["name"],
            "models": info.get("models", []),
        })
    return providers


def get_ocr_settings():
    """Load current OCR settings from the database.

    Returns default (tesseract, fallback=false) if no settings exist.
    Includes a models dict with the stored model per provider.
    """
    conn = get_db()
    provider_row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?", ("ocr_provider",)
    ).fetchone()
    fallback_row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?", ("ocr_fallback_to_tesseract",)
    ).fetchone()

    models = {}
    for provider_key, info in OCR_BACKENDS.items():
        provider_models = info.get("models", [])
        if not provider_models and provider_key != "openrouter":
            continue
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key = ?",
            (f"ocr_model_{provider_key}",),
        ).fetchone()
        if row:
            stored = row["value"]
            # Fall back to first entry if stored value no longer in list
            if provider_models and stored not in provider_models:
                stored = provider_models[0]
            models[provider_key] = stored
        elif provider_models:
            models[provider_key] = provider_models[0]

    return {
        "provider": provider_row["value"] if provider_row else "tesseract",
        "fallback_to_tesseract": (fallback_row["value"] == "1") if fallback_row else False,
        "models": models,
    }


def save_ocr_settings(provider, fallback_to_tesseract, models=None):
    """Persist OCR provider, fallback preference, and optional model choices.

    Raises ValueError if provider is not a valid provider key.
    If models dict is None or omitted, existing model preferences are unchanged.
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
    if models is not None:
        for provider_key, model_value in models.items():
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
                (f"ocr_model_{provider_key}", model_value),
            )
    conn.commit()


def get_model_for_provider(provider_key):
    """Return the stored model for a provider, falling back to config default.

    Returns None for providers with no model list and no stored value (e.g. tesseract).
    For OpenRouter (empty fixed list, free-text), returns stored value or None.
    """
    info = OCR_BACKENDS.get(provider_key, {})
    provider_models = info.get("models", [])
    is_free_text = info.get("env_key") is not None and not provider_models

    conn = get_db()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (f"ocr_model_{provider_key}",),
    ).fetchone()

    if row:
        stored = row["value"]
        if provider_models and stored not in provider_models:
            # Stale value — fall back to first entry
            return provider_models[0]
        return stored

    if provider_models:
        return provider_models[0]

    # Free-text provider with no stored value, or tesseract
    return None
