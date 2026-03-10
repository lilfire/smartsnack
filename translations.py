"""Internationalization system for translations stored as JSON files."""

import logging
import os
import re
import json
import sqlite3
import tempfile
import threading

from config import TRANSLATIONS_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from db import get_db

logger = logging.getLogger(__name__)

_translations_cache = {}
_cache_mtimes = {}
_cache_lock = threading.Lock()
_file_locks = {}
_file_locks_lock = threading.Lock()


def _get_file_lock(filepath: str) -> threading.Lock:
    """Get or create a per-file lock for thread-safe file operations."""
    with _file_locks_lock:
        if filepath not in _file_locks:
            _file_locks[filepath] = threading.Lock()
        return _file_locks[filepath]


def _load_translations(lang: str) -> dict:
    """Load translations for a language, with mtime-based cache invalidation."""
    if lang not in SUPPORTED_LANGUAGES:
        return {}
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    try:
        current_mtime = os.path.getmtime(filepath)
    except OSError:
        return {}
    with _cache_lock:
        if lang in _translations_cache and _cache_mtimes.get(lang) == current_mtime:
            return _translations_cache[lang]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        with _cache_lock:
            _translations_cache[lang] = data
            _cache_mtimes[lang] = current_mtime
        return data
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load translations for %s: %s", lang, e)
        return {}


def _get_current_lang() -> str:
    """Get the current language from user settings."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key='language'"
        ).fetchone()
        return row["value"] if row else DEFAULT_LANGUAGE
    except sqlite3.Error:
        return DEFAULT_LANGUAGE


def _t(key: str, lang: str = None) -> str:
    """Translate a key to the given or current language."""
    if lang is None:
        lang = _get_current_lang()
    tr = _load_translations(lang)
    return tr.get(key, key)


def _category_key(name: str) -> str:
    """Generate a translation key for a category name."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return f"category_{slug}"


def _category_label(name: str, lang: str = None) -> str:
    """Get the translated label for a category, falling back to the name."""
    key = _category_key(name)
    label = _t(key, lang=lang)
    if label == key:
        return name
    return label


def _flag_key(name: str) -> str:
    """Generate a translation key for a flag name."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return f"flag_{slug}"


def _flag_label(name: str, lang: str = None) -> str:
    """Get the translated label for a flag, falling back to the name."""
    key = _flag_key(name)
    label = _t(key, lang=lang)
    if label == key:
        return name
    return label


def _pq_label(name: str, lang: str = None) -> str:
    """Get the translated label for a protein quality entry."""
    label = _t(f"pq_{name}_label", lang=lang)
    if label == f"pq_{name}_label":
        return name
    return label


def _pq_keywords(name: str, lang: str = None) -> list:
    """Get translated keywords for a protein quality entry."""
    raw = _t(f"pq_{name}_keywords", lang=lang)
    if raw == f"pq_{name}_keywords":
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _pq_all_keywords(name: str) -> list:
    """Get all keywords across all languages for a protein quality entry."""
    seen = set()
    result = []
    for lang in SUPPORTED_LANGUAGES:
        for kw in _pq_keywords(name, lang=lang):
            lw = kw.lower()
            if lw not in seen:
                seen.add(lw)
                result.append(kw)
    return result


def _atomic_write_json(filepath: str, data: dict) -> None:
    """Write JSON data to a file atomically using a temp file + rename."""
    dir_name = os.path.dirname(filepath)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _set_translation_key(key: str, values_by_lang: dict) -> None:
    """Set a translation key across one or more languages."""
    if not re.match(r'^[a-z][a-z0-9_.]*$', key):
        raise ValueError(f"Invalid translation key format: {key}")
    for lang, value in values_by_lang.items():
        if lang not in SUPPORTED_LANGUAGES:
            continue
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        file_lock = _get_file_lock(filepath)
        # Thread lock protects against concurrent access within this process.
        # Cross-process safety relies on atomic file writes (temp + rename).
        with file_lock:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {}
            data[key] = value
            _atomic_write_json(filepath, data)
        with _cache_lock:
            _translations_cache.pop(lang, None)


def _delete_translation_key(key: str) -> None:
    """Delete a translation key from all languages."""
    for lang in SUPPORTED_LANGUAGES:
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        file_lock = _get_file_lock(filepath)
        with file_lock:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if key in data:
                del data[key]
                _atomic_write_json(filepath, data)
                with _cache_lock:
                    _translations_cache.pop(lang, None)
