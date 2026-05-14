"""OpenRouter vision backend for ingredient OCR.

Uses the OpenAI-compatible API at openrouter.ai.
Requires: pip install openai
API key via environment variable: OPENROUTER_API_KEY
"""

import os

from . import _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "anthropic/claude-opus-4-7"


def _to_data_uri(image_base64: str) -> str:
    """Ensure the string is a data URI (wraps raw base64 if needed)."""
    if image_base64.startswith("data:"):
        return image_base64
    return f"data:image/jpeg;base64,{image_base64}"


def extract(image_base64: str, language: str) -> str:
    """Extract ingredients from *image_base64* using OpenRouter.

    Args:
        image_base64: Raw base64 string or data URI.
        language: Target language code ("no", "en", "se").

    Returns:
        Cleaned ingredient text, or empty string when none found.

    Raises:
        RuntimeError: If the openai package is not installed.
        ValueError: If *language* is unsupported.
    """
    try:
        import openai as openai_sdk
    except ImportError as exc:
        raise RuntimeError(
            "openai package required for OpenRouter backend: pip install openai"
        ) from exc

    img_url = _to_data_uri(image_base64)
    user_text = build_ingredient_prompt(language)

    client = openai_sdk.OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        base_url=_OPENROUTER_BASE_URL,
    )
    response = client.chat.completions.create(
        model=_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": _HARDENED_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img_url}},
                    {"type": "text", "text": user_text},
                ],
            },
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
