"""Unit tests for services/ocr_core.py.

The VisionBackend is mocked for every test.  langdetect.detect is patched
so language-detection behaviour is deterministic.
"""

from unittest.mock import MagicMock, call, patch

import pytest

MODULE_DETECT = "services.ocr_locale_validator"


def _make_backend(extract_return="", translate_return=""):
    backend = MagicMock()
    backend.extract.return_value = extract_return
    backend.translate.return_value = translate_return
    return backend


class TestExtractWithLocaleValidation:
    def test_match_passthrough(self):
        """Correct language on first call — returned unchanged, no retry or translate."""
        from services.ocr_core import extract_with_locale_validation

        backend = _make_backend(extract_return="Ingredienser: mel, sukker")
        with patch(f"{MODULE_DETECT}.detect", return_value="no"):
            result = extract_with_locale_validation("img==", "no", backend)

        assert result["text"] == "Ingredienser: mel, sukker"
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "no"
        backend.extract.assert_called_once_with("img==", "no")
        backend.translate.assert_not_called()

    def test_retry_fn_calls_backend_extract_again(self):
        """On locale mismatch, retry_fn re-calls backend.extract with same args."""
        from services.ocr_core import extract_with_locale_validation

        original = "This is English"
        retry_text = "Dette er norsk"
        backend = _make_backend(translate_return="unused")
        backend.extract.side_effect = [original, retry_text]

        with patch(f"{MODULE_DETECT}.detect", side_effect=["en", "no"]):
            result = extract_with_locale_validation("img==", "no", backend)

        assert result["text"] == retry_text
        assert result["localeMismatch"] is False
        assert backend.extract.call_count == 2
        backend.extract.assert_called_with("img==", "no")

    def test_translate_fn_calls_backend_translate(self):
        """When retry still has wrong language, translate_fn calls backend.translate."""
        from services.ocr_core import extract_with_locale_validation

        original = "This is English"
        retry_text = "Det här är svenska"
        translated = "Dette er norsk oversatt tekst"
        backend = _make_backend(translate_return=translated)
        backend.extract.side_effect = [original, retry_text]

        with patch(f"{MODULE_DETECT}.detect", side_effect=["en", "sv", "no"]):
            result = extract_with_locale_validation("img==", "no", backend)

        assert result["text"] == translated
        assert result["localeMismatch"] is False
        backend.translate.assert_called_once_with(retry_text, "no")

    def test_locale_mismatch_flag_surfaced_when_all_fail(self):
        """localeMismatch=True when retry and translate both produce wrong language."""
        from services.ocr_core import extract_with_locale_validation

        original = "This is English"
        retry_text = "Det här är svenska"
        translated = "Esto es español"
        backend = _make_backend(translate_return=translated)
        backend.extract.side_effect = [original, retry_text]

        with patch(f"{MODULE_DETECT}.detect", side_effect=["en", "sv", "es"]):
            result = extract_with_locale_validation("img==", "no", backend)

        assert result["text"] == original
        assert result["localeMismatch"] is True
        assert result["detectedLanguage"] == "en"

    def test_empty_text_safe_passthrough(self):
        """Empty extraction is returned as-is without any correction or detection."""
        from services.ocr_core import extract_with_locale_validation

        backend = _make_backend(extract_return="")
        with patch(f"{MODULE_DETECT}.detect") as mock_detect:
            result = extract_with_locale_validation("img==", "no", backend)

        assert result["text"] == ""
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] is None
        mock_detect.assert_not_called()
        backend.translate.assert_not_called()
        assert backend.extract.call_count == 1

    def test_result_keys_present(self):
        """Return dict always contains text, localeMismatch, and detectedLanguage."""
        from services.ocr_core import extract_with_locale_validation

        backend = _make_backend(extract_return="Ingredienser: mel")
        with patch(f"{MODULE_DETECT}.detect", return_value="no"):
            result = extract_with_locale_validation("img==", "no", backend)

        assert set(result.keys()) >= {"text", "localeMismatch", "detectedLanguage"}

    def test_different_languages_work(self):
        """Works with any requested_language, not hard-coded to Norwegian."""
        from services.ocr_core import extract_with_locale_validation

        backend = _make_backend(extract_return="Ingredients: flour, sugar")
        with patch(f"{MODULE_DETECT}.detect", return_value="en"):
            result = extract_with_locale_validation("img==", "en", backend)

        assert result["text"] == "Ingredients: flour, sugar"
        assert result["localeMismatch"] is False
        assert result["detectedLanguage"] == "en"

    def test_vision_backend_protocol_satisfied(self):
        """An object implementing extract + translate satisfies VisionBackend protocol."""
        from services.ocr_core import VisionBackend

        class ConcreteBackend:
            def extract(self, image_b64: str, language: str) -> str:
                return ""

            def translate(self, text: str, target_language: str) -> str:
                return ""

        assert isinstance(ConcreteBackend(), VisionBackend)

    def test_non_backend_fails_protocol(self):
        """An object missing required methods does not satisfy VisionBackend."""
        from services.ocr_core import VisionBackend

        class NotABackend:
            pass

        assert not isinstance(NotABackend(), VisionBackend)
