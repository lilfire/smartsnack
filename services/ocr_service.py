"""OCR service for extracting text from ingredient images.

Supports multiple backends controlled by user settings (ocr_provider):
- "tesseract" (default): uses pytesseract
- "claude_vision": uses Claude Vision API via anthropic SDK
- "gemini": uses Google Gemini API via google-genai SDK
- "openai": uses OpenAI Vision API via openai SDK
- "openrouter": uses OpenRouter Vision API via openai SDK (base_url override)
- "llm": alias for claude_vision (backward compatibility)
"""

import base64
import io
import logging
import os
import re

from PIL import Image, ImageEnhance

from config import OCR_BACKENDS, DEFAULT_OCR_BACKEND

logger = logging.getLogger(__name__)


_INGREDIENT_PROMPT = (
    "Extract the ingredient text from this food label image. "
    "Return only the ingredient text, nothing else."
)


# ---------------------------------------------------------------------------
# API key helper
# ---------------------------------------------------------------------------

def _get_api_key(env_var):
    """Get provider-specific API key, falling back to LLM_API_KEY."""
    key = os.environ.get(env_var, "")
    if not key:
        key = os.environ.get("LLM_API_KEY", "")
    if not key:
        raise ValueError(
            f"API key required: set {env_var} or LLM_API_KEY environment variable"
        )
    return key


# ---------------------------------------------------------------------------
# Image preprocessing (shared by tesseract backend)
# ---------------------------------------------------------------------------

def _prepare_images(image_bytes):
    """Return a list of PIL Image variants to try OCR on.

    Returns [upscaled_enhanced, original] so we can pick the best.
    """
    variants = []

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Variant 1: gentle preprocessing — upscale + mild contrast
    w, h = image.size
    if max(w, h) < 1500:
        scale = 1500 / max(w, h)
        upscaled = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    else:
        upscaled = image.copy()

    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.4)
    upscaled = ImageEnhance.Sharpness(upscaled).enhance(1.5)
    variants.append(upscaled.convert("L"))

    # Variant 2: original image as-is
    variants.append(image)

    return variants


# ---------------------------------------------------------------------------
# Spatial sorting (tesseract output format)
# ---------------------------------------------------------------------------

def _sort_and_join(items):
    """Sort OCR result dicts by position (top-to-bottom, left-to-right) and join.

    Each item: {"left": int, "top": int, "width": int, "height": int, "text": str}
    """
    if not items:
        return ""

    enriched = []
    for item in items:
        top = item["top"]
        bottom = top + item["height"]
        left = item["left"]
        height = item["height"]
        text = item["text"].strip()
        if text:
            enriched.append((top, bottom, left, height, text))

    if not enriched:
        return ""

    enriched.sort(key=lambda x: x[0])

    lines = []
    current_line = [enriched[0]]
    for item in enriched[1:]:
        line_mid = sum((it[0] + it[1]) / 2 for it in current_line) / len(current_line)
        curr_mid = (item[0] + item[1]) / 2
        avg_height = sum(it[3] for it in current_line) / len(current_line)
        if abs(curr_mid - line_mid) < avg_height * 0.5:
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]
    lines.append(current_line)

    text_parts = []
    for line in lines:
        line.sort(key=lambda x: x[2])
        line_text = " ".join(item[4] for item in line if item[4])
        if line_text:
            text_parts.append(line_text)

    return " ".join(text_parts)


# ---------------------------------------------------------------------------
# Tesseract backend
# ---------------------------------------------------------------------------

_MIN_CONFIDENCE = 30


def _avg_confidence_tesseract(data):
    """Average confidence from pytesseract output dict, ignoring low-conf words."""
    confs = [c for c, t in zip(data["conf"], data["text"])
             if isinstance(c, (int, float)) and c >= _MIN_CONFIDENCE and t.strip()]
    return sum(confs) / len(confs) if confs else 0.0


def _extract_tesseract(image_bytes, image_b64, mime_type="image/jpeg"):
    """Run pytesseract on image variants, return best text."""
    import pytesseract

    variants = _prepare_images(image_bytes)

    best_text = ""
    best_confidence = -1.0

    for variant in variants:
        data = pytesseract.image_to_data(
            variant,
            lang="nor+eng",
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )

        # Filter low-confidence words and build items for spatial sorting
        items = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = data["conf"][i]
            if text and isinstance(conf, (int, float)) and conf >= _MIN_CONFIDENCE:
                items.append({
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                    "text": text,
                })

        confidence = _avg_confidence_tesseract(data)
        if confidence > best_confidence:
            best_confidence = confidence
            best_text = _sort_and_join(items)

    return best_text


# ---------------------------------------------------------------------------
# Claude Vision backend
# ---------------------------------------------------------------------------

def _detect_mime_type(image_bytes):
    """Detect image MIME type from magic bytes. Defaults to image/jpeg."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


def _extract_claude_vision(image_bytes, image_b64, mime_type="image/png"):
    """Use Claude Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("ANTHROPIC_API_KEY")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _INGREDIENT_PROMPT,
                    },
                ],
            }
        ],
    )
    return message.content[0].text.strip() if message.content else ""


# ---------------------------------------------------------------------------
# Gemini image format conversion
# ---------------------------------------------------------------------------

_GEMINI_SUPPORTED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
})

_PIL_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
    "GIF": "image/gif",
}


def _svg_to_png(svg_bytes):
    """Convert SVG bytes to PNG bytes using cairosvg."""
    try:
        import cairosvg
    except ImportError:
        raise ValueError(
            "SVG conversion requires cairosvg: pip install cairosvg"
        )
    return cairosvg.svg2png(bytestring=svg_bytes)


def _convert_for_gemini(image_bytes):
    """Return (image_bytes, mime_type) ready for the Gemini API.

    If the image format is not supported by Gemini, convert to PNG.
    Supported formats: image/jpeg, image/png, image/webp, image/heic, image/heif.
    """
    # Detect SVG before PIL (PIL cannot open SVG)
    stripped = image_bytes.lstrip()
    if stripped.startswith(b"<svg") or (
        stripped.startswith(b"<?xml") and b"<svg" in stripped[:512]
    ):
        converted = _svg_to_png(image_bytes)
        logger.info("OCR: converted svg \u2192 image/png for Gemini")
        return converted, "image/png"

    try:
        img = Image.open(io.BytesIO(image_bytes))
        pil_format = img.format or "PNG"
    except Exception:
        return image_bytes, "image/png"

    mime_type = _PIL_FORMAT_TO_MIME.get(pil_format, "image/png")

    if mime_type in _GEMINI_SUPPORTED_MIME_TYPES:
        return image_bytes, mime_type

    # Convert unsupported format to PNG
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    converted_bytes = buf.getvalue()
    logger.info("OCR: converted %s \u2192 image/png for Gemini", pil_format.lower())
    return converted_bytes, "image/png"


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

def _extract_gemini(image_bytes, image_b64, mime_type="image/png"):
    """Use Google Gemini API to extract ingredient text from an image."""
    api_key = _get_api_key("GEMINI_API_KEY")

    image_bytes, mime_type = _convert_for_gemini(image_bytes)
    image_b64 = base64.b64encode(image_bytes).decode()

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_b64,
                        }
                    },
                    {"text": _INGREDIENT_PROMPT},
                ]
            }
        ],
    )
    return response.text.strip() if response.text else ""


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

def _extract_openai(image_bytes, image_b64, mime_type="image/png"):
    """Use OpenAI Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("OPENAI_API_KEY")

    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[
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
                        "text": _INGREDIENT_PROMPT,
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""


# ---------------------------------------------------------------------------
# OpenRouter backend
# ---------------------------------------------------------------------------

_OPENROUTER_SYSTEM_PROMPT = (
    "You are a precise food label reader. Your only job is to extract the exact "
    "ingredient list from a food label image. Output the raw ingredient text as it "
    "appears on the label — no commentary, no formatting changes, no summaries. "
    "If no ingredient list is visible, output an empty string."
)


def _extract_openrouter(image_bytes, image_b64, mime_type="image/jpeg"):
    """Use OpenRouter Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://smartsnack.app"},
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _OPENROUTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                    {"type": "text", "text": _INGREDIENT_PROMPT},
                ],
            },
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "tesseract": _extract_tesseract,
    "claude_vision": _extract_claude_vision,
    "gemini": _extract_gemini,
    "openai": _extract_openai,
    "openrouter": _extract_openrouter,
    "llm": _extract_claude_vision,  # backward compatibility alias
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# User-settings-driven backend detection and dispatch
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


def dispatch_ocr(image_base64):
    """Dispatch OCR to the user-selected backend, falling back to tesseract.

    Reads the selected backend from user_settings. If the stored backend
    is unavailable, falls back to tesseract and logs a warning.

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
    text = provider_fn(image_bytes, raw, mime_type)

    return {"text": text, "provider": provider_name, "fallback": fallback}


def dispatch_ocr_bytes(image_bytes):
    """Dispatch OCR to the user-selected backend from raw image bytes.

    Accepts raw bytes (e.g. from a multipart/form-data upload).
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
    provider_name = OCR_BACKENDS.get(backend_id, {}).get("name", backend_id)
    text = provider_fn(image_bytes, raw_b64)

    return {"text": text, "provider": provider_name, "fallback": fallback}
