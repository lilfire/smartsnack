import os
import re
import json

from config import TRANSLATIONS_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from db import get_db


_translations_cache = {}


def _load_translations(lang):
    if lang in _translations_cache:
        return _translations_cache[lang]
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _translations_cache[lang] = data
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def _get_current_lang():
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM user_settings WHERE key='language'").fetchone()
        return row["value"] if row else DEFAULT_LANGUAGE
    except Exception:
        return DEFAULT_LANGUAGE


def _t(key, lang=None):
    if lang is None:
        lang = _get_current_lang()
    tr = _load_translations(lang)
    return tr.get(key, key)


def _category_key(name):
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return f"category_{slug}"


def _category_label(name, lang=None):
    key = _category_key(name)
    label = _t(key, lang=lang)
    if label == key:
        return name
    return label


def _pq_label(name, lang=None):
    label = _t(f"pq_{name}_label", lang=lang)
    if label == f"pq_{name}_label":
        return name
    return label


def _pq_keywords(name, lang=None):
    raw = _t(f"pq_{name}_keywords", lang=lang)
    if raw == f"pq_{name}_keywords":
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _pq_all_keywords(name):
    seen = set()
    result = []
    for lang in SUPPORTED_LANGUAGES:
        for kw in _pq_keywords(name, lang=lang):
            lw = kw.lower()
            if lw not in seen:
                seen.add(lw)
                result.append(kw)
    return result


def _set_translation_key(key, values_by_lang):
    if not re.match(r'^[a-z][a-z0-9_.]*$', key):
        raise ValueError(f"Invalid translation key format: {key}")
    for lang, value in values_by_lang.items():
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        data[key] = value
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        _translations_cache.pop(lang, None)


def _delete_translation_key(key):
    for lang in SUPPORTED_LANGUAGES:
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if key in data:
            del data[key]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            _translations_cache.pop(lang, None)
