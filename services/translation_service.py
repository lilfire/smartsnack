import os
import json

from config import SUPPORTED_LANGUAGES, TRANSLATIONS_DIR


def get_translations(lang):
    if lang not in SUPPORTED_LANGUAGES:
        raise LookupError("Unsupported language")
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(filepath):
        raise LookupError("Translation file not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
