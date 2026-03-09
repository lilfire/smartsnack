"""Tests for services/translation_service.py — reading translation files."""

import pytest


class TestGetAvailableLanguages:
    def test_returns_languages(self):
        from services.translation_service import get_available_languages
        langs = get_available_languages()
        assert len(langs) >= 1
        codes = [l["code"] for l in langs]
        assert "no" in codes

    def test_language_structure(self):
        from services.translation_service import get_available_languages
        langs = get_available_languages()
        for lang in langs:
            assert "code" in lang
            assert "label" in lang
            assert "flag" in lang


class TestGetTranslations:
    def test_valid_language(self):
        from services.translation_service import get_translations
        data = get_translations("no")
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_unsupported_language(self):
        from services.translation_service import get_translations
        with pytest.raises(LookupError, match="Unsupported language"):
            get_translations("xx")
