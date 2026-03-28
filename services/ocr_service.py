"""OCR service for extracting text from ingredient images.

Supports multiple backends controlled by OCR_BACKEND env var:
- "tesseract" (default): uses pytesseract
- "claude_vision": uses Claude Vision API via anthropic SDK
- "gemini": uses Google Gemini API via google-genai SDK
- "openai": uses OpenAI Vision API via openai SDK
- "llm": alias for claude_vision (backward compatibility)
"""

import base64
import io
import os
import re

from PIL import Image, ImageEnhance

_OCR_BACKEND = os.environ.get("OCR_BACKEND", "tesseract")

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


def _extract_tesseract(image_bytes, image_b64):
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

def _extract_claude_vision(image_bytes, image_b64):
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
                            "media_type": "image/png",
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
# Gemini backend
# ---------------------------------------------------------------------------

def _extract_gemini(image_bytes, image_b64):
    """Use Google Gemini API to extract ingredient text from an image."""
    api_key = _get_api_key("GEMINI_API_KEY")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/png",
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

def _extract_openai(image_bytes, image_b64):
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
                            "url": f"data:image/png;base64,{image_b64}",
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
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "tesseract": _extract_tesseract,
    "claude_vision": _extract_claude_vision,
    "gemini": _extract_gemini,
    "openai": _extract_openai,
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
    if raw.startswith("data:"):
        match = re.match(r"data:image/[^;]+;base64,(.+)", raw, re.DOTALL)
        if not match:
            raise ValueError("Invalid data URI format")
        raw = match.group(1)

    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        raise ValueError("Invalid base64 data")

    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image too large (max 5 MB)")

    provider = _PROVIDERS.get(_OCR_BACKEND)
    if provider is None:
        raise ValueError(
            f"Unknown OCR backend: '{_OCR_BACKEND}'. "
            f"Valid options: {', '.join(sorted(_PROVIDERS.keys()))}"
        )

    return provider(image_bytes, raw)
