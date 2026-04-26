"""Google Gemini OCR backend."""
import io
import logging

from PIL import Image

from . import _get_api_key, build_ingredient_prompt

logger = logging.getLogger("services.ocr_service")

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
    except Exception as e:
        from services.ocr_core import _detect_mime_type
        logger.warning("OCR: PIL failed to open image (%s), falling back to mime detection", e)
        return image_bytes, _detect_mime_type(image_bytes)

    mime_type = _PIL_FORMAT_TO_MIME.get(pil_format, "image/png")

    if mime_type in _GEMINI_SUPPORTED_MIME_TYPES:
        return image_bytes, mime_type

    # Convert unsupported format to PNG
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    converted_bytes = buf.getvalue()
    logger.info("OCR: converted %s \u2192 image/png for Gemini", pil_format.lower())
    return converted_bytes, "image/png"


_DEFAULT_MODEL = "gemini-2.0-flash"


def _extract_gemini(image_bytes, image_b64, mime_type="image/png", model=None, prompt=None, language=None):
    """Use Google Gemini API to extract text from an image.

    The `prompt` kwarg selects the extraction task (ingredients vs. nutrition);
    defaults to the ingredient prompt with optional language translation.
    """
    api_key = _get_api_key("GEMINI_API_KEY")

    image_bytes, mime_type = _convert_for_gemini(image_bytes)

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model or _DEFAULT_MODEL,
        contents=[
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_bytes,
                        }
                    },
                    {"text": prompt or build_ingredient_prompt(language)},
                ]
            }
        ],
    )
    return response.text.strip() if response.text else ""
