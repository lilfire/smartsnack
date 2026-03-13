"""Tests for services/translation_service.py — reading translation files."""

import json
from unittest.mock import patch, mock_open

import pytest


class TestGetAvailableLanguages:
    def test_returns_languages(self):
        from services.translation_service import get_available_languages

        langs = get_available_languages()
        assert len(langs) >= 1
        codes = [lang_item["code"] for lang_item in langs]
        assert "no" in codes

    def test_language_structure(self):
        from services.translation_service import get_available_languages

        langs = get_available_languages()
        for lang in langs:
            assert "code" in lang
            assert "label" in lang
            assert "flag" in lang

    def test_skips_missing_translation_file(self):
        import os
        from services.translation_service import get_available_languages

        original_isfile = os.path.isfile

        def fake_isfile(path):
            if path.endswith("en.json"):
                return False
            return original_isfile(path)

        with patch("services.translation_service.os.path.isfile", side_effect=fake_isfile):
            langs = get_available_languages()
            codes = [l["code"] for l in langs]
            assert "en" not in codes
            assert "no" in codes

    def test_skips_language_on_json_decode_error(self):
        from services.translation_service import get_available_languages

        call_count = {"n": 0}
        original_json_load = json.load

        def fake_json_load(f):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise json.JSONDecodeError("err", "doc", 0)
            return original_json_load(f)

        with patch("services.translation_service.json.load", side_effect=fake_json_load):
            langs = get_available_languages()
            assert len(langs) >= 1

    def test_skips_language_on_os_error(self):
        from services.translation_service import get_available_languages

        call_count = {"n": 0}

        original_open = open

        def fake_open(path, *args, **kwargs):
            if isinstance(path, str) and path.endswith(".json"):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise OSError("Permission denied")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            langs = get_available_languages()
            assert len(langs) >= 1


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

    def test_raises_when_file_missing(self):
        from services.translation_service import get_translations

        with patch("services.translation_service.os.path.isfile", return_value=False):
            with pytest.raises(LookupError, match="Translation file not found"):
                get_translations("no")

    def test_raises_on_os_error(self):
        from services.translation_service import get_translations

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            with pytest.raises(LookupError, match="Translation file could not be read"):
                get_translations("no")

    def test_raises_on_json_decode_error(self):
        from services.translation_service import get_translations

        with patch(
            "services.translation_service.json.load",
            side_effect=json.JSONDecodeError("err", "doc", 0),
        ):
            with pytest.raises(LookupError, match="Translation file could not be read"):
                get_translations("no")
