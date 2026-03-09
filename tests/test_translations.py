"""Tests for translations.py — i18n system."""

import json
import os
import pytest


class TestCategoryKey:
    def test_simple_name(self):
        from translations import _category_key
        assert _category_key("Snacks") == "category_snacks"

    def test_name_with_spaces(self):
        from translations import _category_key
        assert _category_key("Ice Cream") == "category_ice_cream"

    def test_name_with_special_chars(self):
        from translations import _category_key
        assert _category_key("Snacks & Drinks") == "category_snacks_drinks"

    def test_preserves_numbers(self):
        from translations import _category_key
        assert _category_key("Group 1") == "category_group_1"


class TestCategoryLabel:
    def test_fallback_to_name(self, app_ctx):
        from translations import _category_label
        # With no translation set, should return the name itself
        result = _category_label("UnknownCategory999")
        assert result == "UnknownCategory999"

    def test_translated_label(self, app_ctx, translations_dir):
        from translations import _category_label, _set_translation_key, _category_key
        key = _category_key("TestCat")
        _set_translation_key(key, {"no": "Testkategori"})
        result = _category_label("TestCat", lang="no")
        assert result == "Testkategori"


class TestT:
    def test_existing_key(self, app_ctx, translations_dir):
        from translations import _t, _set_translation_key
        _set_translation_key("test_key_123", {"no": "Testverdi"})
        assert _t("test_key_123", lang="no") == "Testverdi"

    def test_missing_key_returns_key(self, app_ctx):
        from translations import _t
        assert _t("nonexistent_key_xyz", lang="no") == "nonexistent_key_xyz"

    def test_unsupported_language(self, app_ctx):
        from translations import _t
        assert _t("some_key", lang="xx") == "some_key"


class TestPqFunctions:
    def test_pq_label_fallback(self, app_ctx):
        from translations import _pq_label
        assert _pq_label("unknown_source") == "unknown_source"

    def test_pq_keywords_empty(self, app_ctx):
        from translations import _pq_keywords
        result = _pq_keywords("unknown_source")
        assert result == []

    def test_pq_all_keywords_deduplicates(self, app_ctx, translations_dir):
        from translations import _pq_all_keywords, _set_translation_key
        _set_translation_key("pq_test_item_keywords", {
            "no": "melk, ost",
            "en": "milk, cheese",
        })
        result = _pq_all_keywords("test_item")
        # Should include keywords from both languages, deduplicated
        assert len(result) == len(set(k.lower() for k in result))


class TestAtomicWriteJson:
    def test_writes_file(self, tmp_path):
        from translations import _atomic_write_json
        filepath = str(tmp_path / "test.json")
        _atomic_write_json(filepath, {"key": "value"})
        with open(filepath) as f:
            data = json.load(f)
        assert data == {"key": "value"}

    def test_overwrites_existing(self, tmp_path):
        from translations import _atomic_write_json
        filepath = str(tmp_path / "test.json")
        _atomic_write_json(filepath, {"old": True})
        _atomic_write_json(filepath, {"new": True})
        with open(filepath) as f:
            data = json.load(f)
        assert data == {"new": True}


class TestSetDeleteTranslationKey:
    def test_set_and_read_back(self, app_ctx, translations_dir):
        from translations import _set_translation_key, _load_translations
        _set_translation_key("test_set_key", {"no": "verdi"})
        data = _load_translations("no")
        assert data.get("test_set_key") == "verdi"

    def test_delete_key(self, app_ctx, translations_dir):
        from translations import _set_translation_key, _delete_translation_key, _load_translations
        _set_translation_key("test_del_key", {"no": "slett meg"})
        _delete_translation_key("test_del_key")
        data = _load_translations("no")
        assert "test_del_key" not in data

    def test_invalid_key_format_raises(self, app_ctx, translations_dir):
        from translations import _set_translation_key
        with pytest.raises(ValueError, match="Invalid translation key"):
            _set_translation_key("INVALID-KEY!", {"no": "value"})


class TestGetCurrentLang:
    def test_returns_default(self, app_ctx):
        from translations import _get_current_lang
        lang = _get_current_lang()
        assert lang == "no"
