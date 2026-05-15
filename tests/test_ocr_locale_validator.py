"""Unit tests for services/ocr_locale_validator.py.

All langdetect.detect calls are patched at the module level so tests are
deterministic and need no real language-detection heuristics.
"""

from unittest.mock import MagicMock, patch

import pytest

MODULE = "services.ocr_locale_validator"


def _make_fns(retry_return="", translate_return=""):
    retry_fn = MagicMock(return_value=retry_return)
    translate_fn = MagicMock(return_value=translate_return)
    return retry_fn, translate_fn


class TestValidateAndCorrect:
    def test_match_passthrough(self):
        """When detected language matches requested, return text unchanged without calling retry or translate."""
        from services.ocr_locale_validator import validate_and_correct

        retry_fn, translate_fn = _make_fns()
        text = "Dette er norsk tekst med ingredienser"

        with patch(f"{MODULE}.detect", return_value="no"):
            result = validate_and_correct(text, "no", retry_fn, translate_fn)

        assert result["text"] == text
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "no"
        retry_fn.assert_not_called()
        translate_fn.assert_not_called()

    def test_level1_retry_success(self):
        """Mismatch on first detect; retry_fn returns correct-language text — no translate needed."""
        from services.ocr_locale_validator import validate_and_correct

        original = "This is English text"
        retry_text = "Dette er norsk tekst etter retry"
        retry_fn, translate_fn = _make_fns(retry_return=retry_text)

        # detect: "en" for original, "no" for retry result
        with patch(f"{MODULE}.detect", side_effect=["en", "no"]):
            result = validate_and_correct(original, "no", retry_fn, translate_fn)

        assert result["text"] == retry_text
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "no"
        retry_fn.assert_called_once()
        translate_fn.assert_not_called()

    def test_level2_translate_fallback(self):
        """Retry produces wrong language; translate_fn is called and returns correct-language text."""
        from services.ocr_locale_validator import validate_and_correct

        original = "This is English text"
        retry_text = "Det här är svenska"
        translated = "Dette er norsk oversatt tekst"
        retry_fn, translate_fn = _make_fns(retry_return=retry_text, translate_return=translated)

        # detect: "en" (original), "sv" (retry), "no" (translated)
        with patch(f"{MODULE}.detect", side_effect=["en", "sv", "no"]):
            result = validate_and_correct(original, "no", retry_fn, translate_fn)

        assert result["text"] == translated
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "no"
        retry_fn.assert_called_once()
        translate_fn.assert_called_once_with(retry_text)

    def test_level3_flag_only(self):
        """All correction attempts fail; localeMismatch=True is surfaced and original text returned."""
        from services.ocr_locale_validator import validate_and_correct

        original = "This is English text"
        retry_text = "Det här är svenska"
        translated = "Esto es español"
        retry_fn, translate_fn = _make_fns(retry_return=retry_text, translate_return=translated)

        # detect: "en" (original), "sv" (retry), "es" (translated)
        with patch(f"{MODULE}.detect", side_effect=["en", "sv", "es"]):
            result = validate_and_correct(original, "no", retry_fn, translate_fn)

        assert result["text"] == original
        assert result["localeMismatch"] is True
        assert result["detectedLanguage"] == "en"
        retry_fn.assert_called_once()
        translate_fn.assert_called_once()

    def test_empty_text_returns_safe(self):
        """Empty and whitespace-only text is returned without detection or correction."""
        from services.ocr_locale_validator import validate_and_correct

        retry_fn, translate_fn = _make_fns()

        for empty in ("", "   ", None):
            with patch(f"{MODULE}.detect") as mock_detect:
                result = validate_and_correct(empty, "no", retry_fn, translate_fn)

            assert result["text"] == empty
            assert result["localeMismatch"] is False
            assert result["detectedLanguage"] is None
            mock_detect.assert_not_called()

        retry_fn.assert_not_called()
        translate_fn.assert_not_called()

    def test_langdetect_exception_treated_as_passthrough(self):
        """LangDetectException on initial detection is treated as unknown → no mismatch flagged."""
        from langdetect import LangDetectException
        from services.ocr_locale_validator import validate_and_correct

        text = "x"  # too short for reliable detection
        retry_fn, translate_fn = _make_fns()

        with patch(f"{MODULE}.detect", side_effect=LangDetectException(0, "no profile")):
            result = validate_and_correct(text, "no", retry_fn, translate_fn)

        assert result["text"] == text
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] is None
        retry_fn.assert_not_called()
        translate_fn.assert_not_called()

    def test_retry_empty_falls_through_to_translate_on_original(self):
        """When retry_fn returns an empty string, translate_fn is called with the original text."""
        from services.ocr_locale_validator import validate_and_correct

        original = "This is English text"
        translated = "Dette er norsk oversatt tekst"
        retry_fn = MagicMock(return_value="")
        translate_fn = MagicMock(return_value=translated)

        # detect: "en" (original), "no" (translated) — retry is empty so _detect_safe skips it
        with patch(f"{MODULE}.detect", side_effect=["en", "no"]):
            result = validate_and_correct(original, "no", retry_fn, translate_fn)

        assert result["text"] == translated
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "no"
        retry_fn.assert_called_once()
        # translate is called with original since retry returned empty
        translate_fn.assert_called_once_with(original)
