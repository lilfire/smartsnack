"""Core OCR service: image validation, backend registry, and public dispatch API."""
import base64
import logging
import os
import re

from config import OCR_BACKENDS, DEFAULT_OCR_BACKEND
from services.ocr_backends import _NUTRITION_PROMPT
from services.ocr_backends.tesseract import _extract_tesseract
from services.ocr_backends.claude import _extract_claude_vision
from services.ocr_backends.gemini import _extract_gemini
from services.ocr_backends.openai import _extract_openai
from services.ocr_backends.openrouter import _extract_openrouter
from services.ocr_backends.groq import _extract_groq
from services.nutrition_parser import parse_nutrition_response

logger = logging.getLogger("services.ocr_service")


# ---------------------------------------------------------------------------
# MIME type detection
# ---------------------------------------------------------------------------

def _detect_mime_type(image_bytes):
    """Detect image MIME type from magic bytes. Defaults to image/jpeg."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "tesseract": _extract_tesseract,
    "claude_vision": _extract_claude_vision,
    "gemini": _extract_gemini,
    "openai": _extract_openai,
    "openrouter": _extract_openrouter,
    "groq": _extract_groq,
    "llm": _extract_claude_vision,  # backward compatibility alias
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_available_backends():
    """Return list of OCR backends with availability based on env vars.

    Returns list of dicts: {"id": "...", "name": "...", "available": bool}.
    tesseract is always available (no key needed).
    """
    result = []
    for backend_id, info in OCR_BACKENDS.items():
        env_key = info.get("env_key")
        available = env_key is None or bool(os.environ.get(env_key))
        result.append({
            "id": backend_id,
            "name": info["name"],
            "available": available,
        })
    return result


def extract_text(image_base64):
    """Extract text from a base64-encoded image.

    Accepts either a raw base64 string or a data URI (data:image/...;base64,...).
    Returns the extracted text as a single string.
    Raises ValueError on invalid input.
    """
    if not image_base64 or not isinstance(image_base64, str):
        raise ValueError("No image provided")

    raw = image_base64
    mime_type = None
    if raw.startswith("data:"):
        match = re.match(r"data:(image/[^;]+);base64,(.+)", raw, re.DOTALL)
        if not match:
            raise ValueError("Invalid data URI format")
        mime_type = match.group(1)
        raw = match.group(2)

    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        raise ValueError("Invalid base64 data")

    if mime_type is None:
        mime_type = _detect_mime_type(image_bytes)

    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image too large (max 5 MB)")

    from services import settings_service

    backend_id = settings_service.get_ocr_backend()
    provider = _PROVIDERS.get(backend_id)
    if provider is None:
        raise ValueError(
            f"Unknown OCR backend: '{backend_id}'. "
            f"Valid options: {', '.join(sorted(_PROVIDERS.keys()))}"
        )

    return provider(image_bytes, raw, mime_type)


def dispatch_ocr(image_base64, prompt=None):
    """Dispatch OCR to the user-selected backend, falling back to tesseract.

    Reads the selected backend from user_settings. If the stored backend
    is unavailable, falls back to tesseract and logs a warning. The optional
    `prompt` kwarg overrides the default ingredient prompt for vision backends.

    Returns a dict: {"text": str, "provider": str, "fallback": bool}.
    """
    from services import settings_service
    from services import ocr_settings_service

    requested_id = settings_service.get_ocr_backend()
    fallback = False

    # Check if the selected backend is available
    backends = {b["id"]: b for b in get_available_backends()}
    backend = backends.get(requested_id)

    if not backend or not backend["available"]:
        # Check user preference before falling back
        ocr_settings = ocr_settings_service.get_ocr_settings()
        if not ocr_settings.get("fallback_to_tesseract", False):
            raise ValueError(
                f"Selected OCR provider '{requested_id}' is unavailable "
                f"and fallback to tesseract is disabled"
            )
        logger.warning(
            "Stored OCR backend '%s' is unavailable, falling back to tesseract",
            requested_id,
        )
        fallback = requested_id != DEFAULT_OCR_BACKEND
        requested_id = DEFAULT_OCR_BACKEND

    backend_id = requested_id

    # Validate and decode the image (shared logic from extract_text)
    if not image_base64 or not isinstance(image_base64, str):
        raise ValueError("No image provided")

    raw = image_base64
    mime_type = None
    if raw.startswith("data:"):
        match = re.match(r"data:(image/[^;]+);base64,(.+)", raw, re.DOTALL)
        if not match:
            raise ValueError("Invalid data URI format")
        mime_type = match.group(1)
        raw = match.group(2)

    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        raise ValueError("Invalid base64 data")

    if mime_type is None:
        mime_type = _detect_mime_type(image_bytes)

    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image too large (max 5 MB)")

    provider_fn = _PROVIDERS.get(backend_id)
    if provider_fn is None:
        raise ValueError(
            f"Unknown OCR backend: '{backend_id}'. "
            f"Valid options: {', '.join(sorted(_PROVIDERS.keys()))}"
        )

    # Resolve display name from config
    provider_name = OCR_BACKENDS.get(backend_id, {}).get("name", backend_id)
    model = None
    lang = None
    if backend_id != DEFAULT_OCR_BACKEND:
        try:
            from services import ocr_settings_service
            model = ocr_settings_service.get_model_for_provider(backend_id)
        except RuntimeError:
            pass  # No app context — backend falls back to its own default
        try:
            lang = settings_service.get_language()
        except RuntimeError:
            pass  # No app context — backend uses default prompt
    kwargs = {}
    if model:
        kwargs["model"] = model
    if prompt:
        kwargs["prompt"] = prompt
    if lang:
        kwargs["language"] = lang
    text = provider_fn(image_bytes, raw, mime_type, **kwargs)

    return {"text": text, "provider": provider_name, "fallback": fallback}


def dispatch_ocr_bytes(image_bytes, prompt=None):
    """Dispatch OCR to the user-selected backend from raw image bytes.

    Accepts raw bytes (e.g. from a multipart/form-data upload). The optional
    `prompt` kwarg overrides the default ingredient prompt for vision backends.
    Returns a dict: {"text": str, "provider": str, "fallback": bool}.
    """
    from services import settings_service

    if not image_bytes:
        raise ValueError("No image provided")

    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image too large (max 5 MB)")

    requested_id = settings_service.get_ocr_backend()
    fallback = False

    backends = {b["id"]: b for b in get_available_backends()}
    backend = backends.get(requested_id)

    if not backend or not backend["available"]:
        logger.warning(
            "Stored OCR backend '%s' is unavailable, falling back to tesseract",
            requested_id,
        )
        fallback = requested_id != DEFAULT_OCR_BACKEND
        requested_id = DEFAULT_OCR_BACKEND

    backend_id = requested_id
    provider_fn = _PROVIDERS.get(backend_id)
    if provider_fn is None:
        raise ValueError(
            f"Unknown OCR backend: '{backend_id}'. "
            f"Valid options: {', '.join(sorted(_PROVIDERS.keys()))}"
        )

    raw_b64 = base64.b64encode(image_bytes).decode()
    mime_type = _detect_mime_type(image_bytes)
    provider_name = OCR_BACKENDS.get(backend_id, {}).get("name", backend_id)
    model = None
    lang = None
    if backend_id != DEFAULT_OCR_BACKEND:
        try:
            from services import ocr_settings_service
            model = ocr_settings_service.get_model_for_provider(backend_id)
        except RuntimeError:
            pass  # No app context — backend falls back to its own default
        try:
            from services import settings_service
            lang = settings_service.get_language()
        except RuntimeError:
            pass  # No app context — backend uses default prompt
    kwargs = {}
    if model:
        kwargs["model"] = model
    if prompt:
        kwargs["prompt"] = prompt
    if lang:
        kwargs["language"] = lang
    text = provider_fn(image_bytes, raw_b64, mime_type, **kwargs)

    return {"text": text, "provider": provider_name, "fallback": fallback}


def dispatch_nutrition_ocr_bytes(image_bytes):
    """Dispatch nutrition-label OCR from raw image bytes.

    Wraps dispatch_ocr_bytes with the nutrition prompt, then parses the
    returned text into a dict of canonical nutrition fields via
    nutrition_parser.parse_nutrition_response.

    Returns a dict:
        {
          "values":   dict[str, float],  # cleaned nutrition values
          "text":     str,               # raw provider output (for debugging)
          "provider": str,               # display name
          "fallback": bool,              # True if we fell back to tesseract
        }
    """
    result = dispatch_ocr_bytes(image_bytes, prompt=_NUTRITION_PROMPT)
    raw_text = result.get("text") or ""
    values = parse_nutrition_response(raw_text)
    return {
        "values": values,
        "text": raw_text,
        "provider": result.get("provider", ""),
        "fallback": bool(result.get("fallback", False)),
    }
