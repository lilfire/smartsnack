import os
import json

from config import SUPPORTED_LANGUAGES, TRANSLATIONS_DIR


def get_available_languages():
    languages = []
    for lang in SUPPORTED_LANGUAGES:
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        languages.append({
            "code": lang,
            "label": data.get("lang_label", lang),
            "flag": data.get("lang_flag", ""),
        })
    return languages


def get_translations(lang):
    if lang not in SUPPORTED_LANGUAGES:
        raise LookupError("Unsupported language")
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(filepath):
        raise LookupError("Translation file not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
