"""Tests for translations.py — i18n system."""

import json
import os
import re
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


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

        _set_translation_key(
            "pq_test_item_keywords",
            {
                "no": "melk, ost",
                "en": "milk, cheese",
            },
        )
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
        from translations import (
            _set_translation_key,
            _delete_translation_key,
            _load_translations,
        )

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


class TestTranslationKeyConsistency:
    """Ensure all translation files have the same keys."""

    @staticmethod
    def _load_all():
        import os

        translations = {}
        trans_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "translations")
        for filename in sorted(os.listdir(trans_dir)):
            if filename.endswith(".json"):
                lang = filename.removesuffix(".json")
                with open(os.path.join(trans_dir, filename), encoding="utf-8") as f:
                    translations[lang] = json.load(f)
        return translations

    def test_all_files_have_same_keys(self):
        translations = self._load_all()
        assert len(translations) >= 2, "Need at least 2 translation files"

        all_keys = {lang: set(data.keys()) for lang, data in translations.items()}
        reference_lang = "no"
        reference_keys = all_keys[reference_lang]

        errors = []
        for lang, keys in all_keys.items():
            if lang == reference_lang:
                continue
            missing = reference_keys - keys
            extra = keys - reference_keys
            if missing:
                errors.append(f"{lang}.json missing keys: {sorted(missing)}")
            if extra:
                errors.append(f"{lang}.json has extra keys not in {reference_lang}.json: {sorted(extra)}")

        assert not errors, "Translation key mismatches:\n" + "\n".join(errors)

    def test_no_empty_values(self):
        translations = self._load_all()
        errors = []
        for lang, data in translations.items():
            for key, value in data.items():
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{lang}.json: key '{key}' has empty or non-string value")
        assert not errors, "Empty translation values:\n" + "\n".join(errors)


class TestTranslationKeysUsedInSource:
    """Ensure every translation key used in source code exists in translation files."""

    # Dynamic key prefixes generated at runtime from DB data (category names, flags, etc.)
    DYNAMIC_PREFIXES = ("category_", "flag_", "pq_", "bulk_report_")

    @staticmethod
    def _load_all_translation_keys():
        trans_dir = os.path.join(ROOT_DIR, "translations")
        all_keys = set()
        for filename in os.listdir(trans_dir):
            if filename.endswith(".json"):
                with open(os.path.join(trans_dir, filename), encoding="utf-8") as f:
                    all_keys.update(json.load(f).keys())
        return all_keys

    @staticmethod
    def _extract_keys_from_js():
        """Extract translation keys from t('key') calls and lookup tables in JS."""
        keys = set()
        js_dir = os.path.join(ROOT_DIR, "static", "js")
        # Match t('key') or t("key") — also window.__t('key')
        t_call_re = re.compile(r"""\bt\(\s*['"]([a-z_][a-z0-9_]*)['"]""")
        # Match string values in object literals like { foo: 'translation_key' }
        obj_value_re = re.compile(r""":\s*['"]([a-z_][a-z0-9_]*)['"]""")

        for filename in os.listdir(js_dir):
            if not filename.endswith(".js") or filename.endswith(".test.js"):
                continue
            filepath = os.path.join(js_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            # Direct t() calls
            keys.update(t_call_re.findall(content))

            # Lookup table values (e.g. _VOLUME_LABELS, _FIELD_LABEL_KEYS)
            for match in re.finditer(
                r"(?:const|let|var)\s+_[A-Z_]+\s*=\s*\{([^}]+)\}", content
            ):
                block = match.group(1)
                for val in obj_value_re.findall(block):
                    # Only include values that look like translation keys
                    if "_" in val:
                        keys.add(val)

        return keys

    @staticmethod
    def _extract_keys_from_html():
        """Extract translation keys from data-i18n* attributes in HTML templates."""
        keys = set()
        templates_dir = os.path.join(ROOT_DIR, "templates")
        attr_re = re.compile(r'data-i18n(?:-(?:html|placeholder|title|aria-label))?="([a-z_][a-z0-9_]*)"')

        for dirpath, _, filenames in os.walk(templates_dir):
            for filename in filenames:
                if not filename.endswith(".html"):
                    continue
                filepath = os.path.join(dirpath, filename)
                with open(filepath, encoding="utf-8") as f:
                    keys.update(attr_re.findall(f.read()))

        return keys

    @staticmethod
    def _extract_keys_from_python():
        """Extract translation keys from _t('key') calls in Python source."""
        keys = set()
        t_call_re = re.compile(r"""_t\(\s*['"]([a-z_][a-z0-9_]*)['"]""")

        # Scan blueprints and services
        for subdir in ["blueprints", "services"]:
            scan_dir = os.path.join(ROOT_DIR, subdir)
            if not os.path.isdir(scan_dir):
                continue
            for filename in os.listdir(scan_dir):
                if not filename.endswith(".py"):
                    continue
                with open(os.path.join(scan_dir, filename), encoding="utf-8") as f:
                    keys.update(t_call_re.findall(f.read()))

        return keys

    def test_all_source_keys_exist_in_translations(self):
        translation_keys = self._load_all_translation_keys()

        source_keys = set()
        source_keys.update(self._extract_keys_from_js())
        source_keys.update(self._extract_keys_from_html())
        source_keys.update(self._extract_keys_from_python())

        # Filter out dynamic keys that are built at runtime from DB data
        static_keys = {
            k for k in source_keys
            if not any(k.startswith(p) for p in self.DYNAMIC_PREFIXES)
        }

        missing = static_keys - translation_keys
        assert not missing, (
            "Translation keys used in source code but missing from all translation files:\n"
            + "\n".join(f"  - {k}" for k in sorted(missing))
        )

    def test_critical_dynamic_keys_exist(self):
        """Verify that critical keys constructed at runtime via concatenation are present.

        The static analysis above skips 'bulk_report_' prefix keys because they are built
        dynamically (e.g. t('bulk_report_' + item.status)).  This test explicitly checks the
        known status-derived keys so a missing key is caught even though the prefix is excluded.
        """
        translation_keys = self._load_all_translation_keys()
        required = [
            "bulk_report_skipped",
            "bulk_report_error",
            "bulk_report_updated",
        ]
        missing = [k for k in required if k not in translation_keys]
        assert not missing, (
            "Critical dynamic translation keys missing from all translation files:\n"
            + "\n".join(f"  - {k}" for k in missing)
        )
