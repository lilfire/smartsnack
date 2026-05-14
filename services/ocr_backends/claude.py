"""Claude vision backend for ingredient OCR.

Uses the Anthropic Messages API with vision support.
Requires: pip install anthropic
"""

import re

from . import _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt


def _parse_image(image_base64: str) -> tuple[str, str]:
    """Return (raw_b64_data, media_type) from a raw or data-URI string."""
    if image_base64.startswith("data:"):
        m = re.match(r"data:image/([^;]+);base64,(.+)", image_base64, re.DOTALL)
        if m:
            return m.group(2).strip(), f"image/{m.group(1)}"
    return image_base64.strip(), "image/jpeg"


def extract(image_base64: str, language: str) -> str:
    """Extract ingredients from *image_base64* using Claude vision.

    Args:
        image_base64: Raw base64 string or data URI.
        language: Target language code ("no", "en", "se").

    Returns:
        Cleaned ingredient text, or empty string when none found.

    Raises:
        RuntimeError: If the anthropic package is not installed.
        ValueError: If *language* is unsupported.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package required for Claude backend: pip install anthropic"
        ) from exc

    img_data, media_type = _parse_image(image_base64)
    user_text = build_ingredient_prompt(language)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=_HARDENED_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": img_data,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )
    return response.content[0].text.strip()
