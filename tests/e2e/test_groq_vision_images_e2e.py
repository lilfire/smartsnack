"""Live e2e: Groq vision extraction with locale-correction post-process (LSO-1253).

Asserts on the output of ``extract_with_locale_validation`` (services/ocr_core.py),
not the raw Groq response. The cascade — detect → retry → translate → flag —
guarantees the final text is in the requested language, so the language-term
assertion stays deterministic when Groq picks a different language section of
a multilingual label.

Gated by RUN_GROQ_E2E=1 (set in CI only on development/main pushes).
Set RUN_GROQ_E2E=1 locally to opt in; also requires GROQ_API_KEY.
"""
import base64
import os
from pathlib import Path

import pytest

from services.llm_translate_service import translate_ingredients
from services.ocr_backends import dispatch_ocr, looks_like_llm_refusal
from services.ocr_core import extract_with_locale_validation
from tests.e2e.groq_helpers import skip_on_groq_quota

FIXTURES = Path(__file__).parent / "fixtures"
_GROQ_KEY = os.environ.get("GROQ_API_KEY")
_RUN_GROQ_E2E = os.environ.get("RUN_GROQ_E2E") == "1"


def _load_b64(filename: str) -> str:
    """Load a fixture image and return its base64 encoding."""
    return base64.b64encode((FIXTURES / filename).read_bytes()).decode()


class _GroqVisionBackend:
    """VisionBackend adapter: Groq for extraction, LLM cascade for translation."""

    def extract(self, image_b64: str, language: str) -> str:
        return dispatch_ocr(image_b64, backend="groq", language=language)

    def translate(self, text: str, target_language: str) -> str:
        return translate_ingredients(text, target_language)


@pytest.mark.skipif(
    not (_RUN_GROQ_E2E and _GROQ_KEY),
    reason="Groq E2E skipped: requires RUN_GROQ_E2E=1 and GROQ_API_KEY",
)
class TestGroqVisionEnglish:
    """Verify the post-process pipeline produces English ingredient text."""

    @pytest.mark.parametrize(
        "image_name,expected_terms",
        [
            ("de.jpg", ["starch", "palm", "egg", "milk", "wheat", "sugar", "salt"]),
            (
                "china_ingriditens.jpg",
                ["oil", "salt", "sugar", "starch", "seed", "flour", "rice"],
            ),
            ("multi.jpg", ["flour", "wheat", "salt", "sugar", "oil", "calcium"]),
            ("ingredients_list.jpg", ["wheat", "milk", "egg", "soy", "sugar", "oil"]),
        ],
    )
    def test_groq_english_extraction(self, image_name, expected_terms):
        with skip_on_groq_quota():
            result = extract_with_locale_validation(
                _load_b64(image_name), "en", _GroqVisionBackend()
            )
        text = result["text"]
        assert text, f"Empty result for {image_name} (language=en)"
        assert not looks_like_llm_refusal(text), (
            f"LLM refusal for {image_name} (language=en): {text!r}"
        )
        assert not result["localeMismatch"], (
            f"Locale post-process cascade exhausted for {image_name}.\n"
            f"detectedLanguage={result.get('detectedLanguage')!r}\nGot: {text!r}"
        )
        assert any(term in text.lower() for term in expected_terms), (
            f"No expected English term found for {image_name}.\n"
            f"Expected any of: {expected_terms}\nGot: {text!r}"
        )


@pytest.mark.skipif(
    not (_RUN_GROQ_E2E and _GROQ_KEY),
    reason="Groq E2E skipped: requires RUN_GROQ_E2E=1 and GROQ_API_KEY",
)
class TestGroqVisionNorwegian:
    """Verify the post-process pipeline produces Norwegian ingredient text."""

    @pytest.mark.parametrize(
        "image_name,expected_terms",
        [
            (
                "de.jpg",
                [
                    "stivelse",
                    "palmeolje",
                    "egg",
                    "melk",
                    "hvete",
                    "sukker",
                    "salt",
                    "gjær",
                ],
            ),
            (
                "china_ingriditens.jpg",
                ["olje", "salt", "sukker", "stivelse", "mel", "ris", "reke"],
            ),
            ("multi.jpg", ["mel", "hvete", "palmeolje", "sukker", "salt", "olje"]),
            (
                "ingredients_list.jpg",
                ["hvete", "melk", "egg", "soya", "sukker", "olje"],
            ),
        ],
    )
    def test_groq_norwegian_extraction(self, image_name, expected_terms):
        with skip_on_groq_quota():
            result = extract_with_locale_validation(
                _load_b64(image_name), "no", _GroqVisionBackend()
            )
        text = result["text"]
        assert text, f"Empty result for {image_name} (language=no)"
        assert not looks_like_llm_refusal(text), (
            f"LLM refusal for {image_name} (language=no): {text!r}"
        )
        assert not result["localeMismatch"], (
            f"Locale post-process cascade exhausted for {image_name}.\n"
            f"detectedLanguage={result.get('detectedLanguage')!r}\nGot: {text!r}"
        )
        assert any(term in text.lower() for term in expected_terms), (
            f"No expected Norwegian term found for {image_name}.\n"
            f"Expected any of: {expected_terms}\nGot: {text!r}"
        )
