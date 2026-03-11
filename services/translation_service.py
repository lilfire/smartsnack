"""Service for reading translation files and available languages."""

import logging
import os
import json

from config import SUPPORTED_LANGUAGES, TRANSLATIONS_DIR

logger = logging.getLogger(__name__)


def get_available_languages() -> list:
    languages = []
    for lang in SUPPORTED_LANGUAGES:
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load translation file %s: %s", filepath, e)
            continue
        languages.append(
            {
                "code": lang,
                "label": data.get("lang_label", lang),
                "flag": data.get("lang_flag", ""),
            }
        )
    return languages


def get_translations(lang: str) -> dict:
    if lang not in SUPPORTED_LANGUAGES:
        raise LookupError("Unsupported language")
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(filepath):
        raise LookupError("Translation file not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
