"""Regression tests for the locale mismatch cascade in services/ocr_core.py.

These tests patch the dispatch layer directly — no live API key, no browser,
no external service required.  They verify that a vision LLM returning text
in the wrong locale triggers the correct cascade level:

  Level 1 — retry:     backend.extract called a second time
  Level 2 — translate: backend.translate called when retry still wrong locale
  Level 3 — flag:      localeMismatch=True returned when both levels fail
"""

from unittest.mock import MagicMock, patch

import pytest

DETECT_MODULE = "services.ocr_locale_validator"


def _mock_backend(extract_side_effect, translate_return=""):
    """Return a mock VisionBackend with given extract side_effect."""
    b = MagicMock()
    b.extract.side_effect = extract_side_effect
    b.translate.return_value = translate_return
    return b


class TestLocaleMismatchCascade:
    """Regression suite for the three-level locale correction cascade."""

    def test_level1_retry_triggered_on_locale_mismatch(self):
        """Vision LLM returns wrong locale → retry invoked; backend.extract called twice."""
        from services.ocr_core import extract_with_locale_validation

        french_text = "Ingrédients: farine, sucre, sel"
        english_retry = "Ingredients: flour, sugar, salt"
        backend = _mock_backend(
            extract_side_effect=[french_text, english_retry],
        )

        # detect: "fr" for original, "en" for retry
        with patch(f"{DETECT_MODULE}.detect", side_effect=["fr", "en"]):
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == english_retry
        assert result["localeMismatch"] is False
        assert backend.extract.call_count == 2
        backend.translate.assert_not_called()

    def test_level2_translate_triggered_when_retry_still_wrong(self):
        """Retry still returns wrong locale → translate_fn invoked; translate result returned."""
        from services.ocr_core import extract_with_locale_validation

        french_text = "Ingrédients: farine, sucre"
        swedish_retry = "Ingredienser: mjöl, socker"
        english_translated = "Ingredients: flour, sugar"
        backend = _mock_backend(
            extract_side_effect=[french_text, swedish_retry],
            translate_return=english_translated,
        )

        # detect: "fr" (original), "sv" (retry), "en" (translated)
        with patch(f"{DETECT_MODULE}.detect", side_effect=["fr", "sv", "en"]):
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == english_translated
        assert result["localeMismatch"] is False
        backend.translate.assert_called_once_with(swedish_retry, "en")

    def test_level3_flag_surfaced_when_all_attempts_fail(self):
        """Retry and translate both return wrong locale → localeMismatch=True, original text returned."""
        from services.ocr_core import extract_with_locale_validation

        french_text = "Ingrédients: farine, sucre"
        swedish_retry = "Ingredienser: mjöl, socker"
        spanish_translated = "Ingredientes: harina, azúcar"
        backend = _mock_backend(
            extract_side_effect=[french_text, swedish_retry],
            translate_return=spanish_translated,
        )

        # detect: "fr" (original), "sv" (retry), "es" (translated)
        with patch(f"{DETECT_MODULE}.detect", side_effect=["fr", "sv", "es"]):
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == french_text
        assert result["localeMismatch"] is True
        assert result["detectedLanguage"] == "fr"
        assert backend.extract.call_count == 2
        backend.translate.assert_called_once()

    def test_no_correction_when_locale_matches(self):
        """Correct locale on first extraction → no retry, no translate, localeMismatch=False."""
        from services.ocr_core import extract_with_locale_validation

        english_text = "Ingredients: oats, milk, honey"
        backend = _mock_backend(extract_side_effect=[english_text])

        with patch(f"{DETECT_MODULE}.detect", return_value="en"):
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == english_text
        assert result["localeMismatch"] is False
        assert backend.extract.call_count == 1
        backend.translate.assert_not_called()

    def test_retry_uses_same_image_and_language(self):
        """retry_fn passes the original image_b64 and language to backend.extract."""
        from services.ocr_core import extract_with_locale_validation

        backend = _mock_backend(
            extract_side_effect=["Ingrédients: farine", "Ingredients: flour"],
        )

        with patch(f"{DETECT_MODULE}.detect", side_effect=["fr", "en"]):
            extract_with_locale_validation("BASE64IMGDATA==", "en", backend)

        calls = backend.extract.call_args_list
        assert len(calls) == 2
        assert calls[0][0] == ("BASE64IMGDATA==", "en")
        assert calls[1][0] == ("BASE64IMGDATA==", "en")

    def test_translate_uses_target_language(self):
        """translate_fn passes the target language (not the detected language) to backend.translate."""
        from services.ocr_core import extract_with_locale_validation

        french_text = "Ingrédients: farine, sucre"
        backend = _mock_backend(
            extract_side_effect=[french_text, french_text],
            translate_return="Ingredients: flour, sugar",
        )

        # both detect calls return "fr"; translate returns "en"
        with patch(f"{DETECT_MODULE}.detect", side_effect=["fr", "fr", "en"]):
            extract_with_locale_validation("img==", "en", backend)

        backend.translate.assert_called_once()
        _, args, _ = backend.translate.mock_calls[0]
        # second arg to translate must be the requested language "en"
        assert args[1] == "en"

    def test_empty_extraction_not_flagged(self):
        """Empty string from backend is returned as-is with localeMismatch=False."""
        from services.ocr_core import extract_with_locale_validation

        backend = _mock_backend(extract_side_effect=[""])

        with patch(f"{DETECT_MODULE}.detect") as mock_detect:
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == ""
        assert result["localeMismatch"] is False
        mock_detect.assert_not_called()
        backend.translate.assert_not_called()
        assert backend.extract.call_count == 1
