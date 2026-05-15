"""Groq Vision OCR backend."""
from . import _get_api_key, _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt

_DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _to_data_uri(image_base64: str) -> str:
    """Ensure the string is a data URI (wraps raw base64 if needed)."""
    if image_base64.startswith("data:"):
        return image_base64
    return f"data:image/jpeg;base64,{image_base64}"


def _extract_groq(image_bytes, image_b64, mime_type="image/png", model=None, prompt=None, language=None):
    """Use Groq Vision API to extract text from an image.

    The `prompt` kwarg selects the extraction task (ingredients vs. nutrition);
    defaults to the ingredient prompt with optional language translation.
    """
    api_key = _get_api_key("GROQ_API_KEY")

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model or _DEFAULT_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _HARDENED_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt or build_ingredient_prompt(language or "no"),
                    },
                ],
            },
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""


def extract(image_base64: str, language: str) -> str:
    """Extract ingredients from *image_base64* using Groq vision.

    Args:
        image_base64: Raw base64 string or data URI.
        language: Target language code ("no", "en", "se").

    Returns:
        Cleaned ingredient text, or empty string when none found.

    Raises:
        RuntimeError: If the groq package is not installed.
        ValueError: If *language* is unsupported.
    """
    try:
        import groq as groq_sdk
    except ImportError as exc:
        raise RuntimeError(
            "groq package required for Groq backend: pip install groq"
        ) from exc

    img_url = _to_data_uri(image_base64)
    user_text = build_ingredient_prompt(language)

    client = groq_sdk.Groq()
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
