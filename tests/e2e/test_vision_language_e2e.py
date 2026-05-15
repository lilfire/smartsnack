"""Live e2e: vision OCR language routing fix (LSO-1248).

Calls the Groq vision API with a synthetic multilingual food-label image and
asserts that the returned text is non-empty and that different target languages
produce different outputs — proving that build_ingredient_prompt() correctly
routes the model via the native language name, not a bare ISO code.

Gated by RUN_GROQ_E2E=1 (set in CI only on development/main pushes).
Set RUN_GROQ_E2E=1 locally to opt in; also requires GROQ_API_KEY.
"""
import base64
import io
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

from config import SUPPORTED_LANGUAGES
from services.ocr_backends import dispatch_ocr
from tests.e2e.groq_helpers import skip_on_groq_quota


_GROQ_KEY = os.environ.get("GROQ_API_KEY")
_RUN_GROQ_E2E = os.environ.get("RUN_GROQ_E2E") == "1"


def _make_multilingual_label_b64() -> str:
    """Return a base64-encoded PNG of a synthetic multilingual food label.

    Draws three language sections (Norwegian, English, Swedish) with distinct
    headings and ingredient words so the vision LLM can distinguish them by
    language. Uses the DejaVu font if available; falls back to the Pillow
    default bitmap font.
    """
    img = Image.new("RGB", (800, 220), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=22
        )
    except Exception:
        font = ImageFont.load_default()

    draw.text(
        (20, 15),
        "INGREDIENSER: Sukker, hvetemel, palmeolje, salt, gjær.",
        font=font,
        fill=(0, 0, 0),
    )
    draw.text(
        (20, 80),
        "INGREDIENTS: Sugar, wheat flour, palm oil, salt, yeast.",
        font=font,
        fill=(0, 0, 0),
    )
    draw.text(
        (20, 145),
        "INGREDIENSER: Socker, vetemjol, palmolja, salt, jast.",
        font=font,
        fill=(0, 0, 0),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


_LABEL_B64 = _make_multilingual_label_b64()


@pytest.mark.skipif(
    not (_RUN_GROQ_E2E and _GROQ_KEY),
    reason="Groq E2E skipped: requires RUN_GROQ_E2E=1 and GROQ_API_KEY",
)
class TestVisionLanguageRoutingLive:
    """Verify that the native-name fix in build_ingredient_prompt() routes
    the Groq vision model to the correct language section on a multilingual label.

    Assertion strategy: compare outputs across languages — if language routing
    were broken (bare ISO code sent instead of native name), the model would
    likely return the same text regardless of target language.
    """

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_groq_returns_nonempty_for_target_language(self, lang):
        """dispatch_ocr must return a non-empty ingredient string for each language."""
        with skip_on_groq_quota():
            result = dispatch_ocr(_LABEL_B64, backend="groq", language=lang)
        assert result, (
            f"dispatch_ocr(backend='groq', language={lang!r}) returned empty. "
            "The vision LLM should extract or translate the multilingual label."
        )

    def test_different_languages_produce_distinct_outputs(self):
        """Norwegian and English results must differ, confirming language routing.

        If the fix regresses (bare code again), the LLM often outputs the
        same section for all codes, making this assertion fail.
        """
        with skip_on_groq_quota():
            no_result = dispatch_ocr(_LABEL_B64, backend="groq", language="no")
            en_result = dispatch_ocr(_LABEL_B64, backend="groq", language="en")

        assert no_result, "Norwegian extraction returned empty"
        assert en_result, "English extraction returned empty"
        assert no_result != en_result, (
            "Norwegian and English outputs are identical — language routing may be broken.\n"
            f"no: {no_result!r}\nen: {en_result!r}"
        )
