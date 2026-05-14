"""Live e2e: Groq vision extraction — 4 real food-label images, EN + NO (LSO-1253).

Tests that dispatch_ocr(backend="groq") correctly handles real-world images
spanning multiple source languages (DE, ZH, multilingual EU, EN/ES).
Each image is tested once with language="en" and once with language="no",
exercising both Path A (extract target-language section that already exists)
and Path B (translate from another language).

Skipped unless GROQ_API_KEY is present (wired by LSO-1250).

Fixture setup: the 4 source images live in tests/e2e/fixtures/. They were
downloaded from the LSO-1253 issue attachments and committed alongside
this file. See the LSO-1253 spec document for the download command.
"""
import base64
import os
from pathlib import Path

import pytest

from services.ocr_backends import dispatch_ocr, looks_like_llm_refusal

FIXTURES = Path(__file__).parent / "fixtures"
_GROQ_KEY = os.environ.get("GROQ_API_KEY")


def _load_b64(filename: str) -> str:
    """Load a fixture image and return its base64 encoding."""
    return base64.b64encode((FIXTURES / filename).read_bytes()).decode()


@pytest.mark.skipif(not _GROQ_KEY, reason="requires live GROQ_API_KEY")
class TestGroqVisionEnglish:
    """Verify Groq vision returns English ingredient text for each real label.

    A single matched English food term per image is sufficient to confirm
    real extraction (or translation, for non-English source labels), as
    opposed to an empty string or a conversational refusal.
    """

    @pytest.mark.parametrize(
        "image_name,expected_terms",
        [
            ("de.jpg", ["starch", "palm", "egg", "milk", "wheat", "sugar", "salt"]),
            (
                "china_ingriditens.jpg",
                ["oil", "salt", "sugar", "starch", "seed", "flour", "rice"],
            ),
            ("multi.jpg", ["flour", "wheat", "palm", "sugar", "salt", "oil"]),
            ("ingredients_list.jpg", ["wheat", "milk", "egg", "soy", "sugar", "oil"]),
        ],
    )
    def test_groq_english_extraction(self, image_name, expected_terms):
        result = dispatch_ocr(_load_b64(image_name), backend="groq", language="en")
        assert result, f"Empty result for {image_name} (language=en)"
        assert not looks_like_llm_refusal(result), (
            f"LLM refusal for {image_name} (language=en): {result!r}"
        )
        assert any(term in result.lower() for term in expected_terms), (
            f"No expected English term found for {image_name}.\n"
            f"Expected any of: {expected_terms}\nGot: {result!r}"
        )


@pytest.mark.skipif(not _GROQ_KEY, reason="requires live GROQ_API_KEY")
class TestGroqVisionNorwegian:
    """Verify Groq vision returns Norwegian ingredient text for each real label."""

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
        result = dispatch_ocr(_load_b64(image_name), backend="groq", language="no")
        assert result, f"Empty result for {image_name} (language=no)"
        assert not looks_like_llm_refusal(result), (
            f"LLM refusal for {image_name} (language=no): {result!r}"
        )
        assert any(term in result.lower() for term in expected_terms), (
            f"No expected Norwegian term found for {image_name}.\n"
            f"Expected any of: {expected_terms}\nGot: {result!r}"
        )
