"""OpenRouter Vision OCR backend."""
import os

from . import _get_api_key, _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt


_DEFAULT_MODEL = "google/gemini-2.0-flash-001"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _to_data_uri(image_base64: str) -> str:
    """Ensure the string is a data URI (wraps raw base64 if needed)."""
    if image_base64.startswith("data:"):
        return image_base64
    return f"data:image/jpeg;base64,{image_base64}"


def _extract_openrouter(image_bytes, image_b64, mime_type="image/jpeg", model=None, prompt=None, language=None):
    """Use OpenRouter Vision API to extract text from an image.

    The `prompt` kwarg selects the extraction task (ingredients vs. nutrition);
    defaults to the ingredient prompt with optional language translation.
    """
    api_key = _get_api_key("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)

    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url=_OPENROUTER_BASE_URL,
        default_headers={"HTTP-Referer": "https://smartsnack.app"},
    )
    ingredient_prompt = build_ingredient_prompt(language or "no")
    user_prompt = prompt or ingredient_prompt
    messages = []
    if not prompt:
        messages.append({"role": "system", "content": _HARDENED_SYSTEM_PROMPT})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}",
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=messages,
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""


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
