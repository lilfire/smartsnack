"""Gemini vision backend for ingredient OCR.

Uses the google-generativeai SDK (GenerativeModel with system_instruction).
Requires: pip install google-generativeai
"""

import base64
import re

from . import _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt


def _parse_image(image_base64: str) -> tuple[bytes, str]:
    """Return (raw_bytes, mime_type) from a raw or data-URI string."""
    if image_base64.startswith("data:"):
        m = re.match(r"data:image/([^;]+);base64,(.+)", image_base64, re.DOTALL)
        if m:
            return base64.b64decode(m.group(2).strip()), f"image/{m.group(1)}"
    return base64.b64decode(image_base64.strip()), "image/jpeg"


def extract(image_base64: str, language: str) -> str:
    """Extract ingredients from *image_base64* using Gemini vision.

    Args:
        image_base64: Raw base64 string or data URI.
        language: Target language code ("no", "en", "se").

    Returns:
        Cleaned ingredient text, or empty string when none found.

    Raises:
        RuntimeError: If the google-generativeai package is not installed.
        ValueError: If *language* is unsupported.
    """
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai package required for Gemini backend: "
            "pip install google-generativeai"
        ) from exc

    raw_bytes, mime_type = _parse_image(image_base64)
    user_text = build_ingredient_prompt(language)

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=_HARDENED_SYSTEM_PROMPT,
    )
    image_part = {"mime_type": mime_type, "data": raw_bytes}
    response = model.generate_content([image_part, user_text])
    return response.text.strip()
