"""OCR service for extracting text from ingredient images using EasyOCR."""

import base64
import re

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["no", "en"], gpu=False)
    return _reader


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

    if len(image_bytes) > 10 * 1024 * 1024:
        raise ValueError("Image too large (max 10 MB)")

    reader = _get_reader()
    results = reader.readtext(image_bytes, detail=0, paragraph=True)

    if not results:
        return ""

    return " ".join(results)
