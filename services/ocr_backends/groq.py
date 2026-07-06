"""Groq Vision OCR backend."""
import time

from . import _get_api_key, _HARDENED_SYSTEM_PROMPT, build_ingredient_prompt

_DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# LSO-1802: Groq occasionally returns 503 "over capacity" and instructs
# clients to back off exponentially. Three attempts at 2s / 4s / 8s covers
# the typical burst without blocking OCR for more than ~14s worst case.
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 2


def _to_data_uri(image_base64: str) -> str:
    """Ensure the string is a data URI (wraps raw base64 if needed)."""
    if image_base64.startswith("data:"):
        return image_base64
    return f"data:image/jpeg;base64,{image_base64}"


def _is_transient_overload(exc: Exception) -> bool:
    """True when *exc* is a 503 over-capacity / overloaded response.

    Only retries transient server overload — not 429 rate limits (client
    should back off longer) or auth/validation errors (retry cannot help).
    """
    try:
        import groq as _groq
        if isinstance(exc, _groq.InternalServerError):
            if getattr(exc, "status_code", None) == 503:
                return True
            msg = str(exc).lower()
            return "over capacity" in msg or "overloaded" in msg
    except ImportError:
        pass
    return False


def _sleep(seconds: float) -> None:
    """Indirection so tests can patch retry backoff without a real sleep."""
    time.sleep(seconds)


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

    last_exc: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
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
        except Exception as exc:
            last_exc = exc
            if not _is_transient_overload(exc) or attempt == _RETRY_ATTEMPTS - 1:
                raise
            _sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))
    # Unreachable — the loop either returns or re-raises. Present for type/lint.
    raise last_exc  # pragma: no cover
