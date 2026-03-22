"""OCR service for extracting text from ingredient images using EasyOCR."""

import base64
import io
import re

_reader = None

# EasyOCR readtext parameters tuned for food label text
_OCR_PARAMS = dict(
    detail=1,
    paragraph=False,
    width_ths=0.7,
    text_threshold=0.6,
    low_text=0.4,
    link_threshold=0.4,
)


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["no", "en"], gpu=False)
    return _reader


def _prepare_images(image_bytes):
    """Return a list of image variants to try OCR on.

    Returns [upscaled_grayscale, original_bytes] so we can pick the best.
    """
    from PIL import Image, ImageEnhance

    variants = []

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Variant 1: gentle preprocessing — upscale + mild contrast on grayscale
    w, h = image.size
    if max(w, h) < 1500:
        scale = 1500 / max(w, h)
        upscaled = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    else:
        upscaled = image.copy()

    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.4)
    upscaled = ImageEnhance.Sharpness(upscaled).enhance(1.5)
    import numpy as np
    gray = np.array(upscaled.convert("L"))
    variants.append(gray)

    # Variant 2: original image bytes (let EasyOCR handle it)
    variants.append(image_bytes)

    return variants


def _avg_confidence(results):
    """Average confidence score for a set of OCR results."""
    if not results:
        return 0.0
    return sum(conf for _, _, conf in results) / len(results)


def _sort_and_join(results):
    """Sort OCR results by position (top-to-bottom, left-to-right) and join.

    Groups text boxes into lines based on vertical overlap, then orders
    left-to-right within each line.
    """
    if not results:
        return ""

    # results: [([[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence), ...]
    items = []
    for bbox, text, _conf in results:
        top_y = min(pt[1] for pt in bbox)
        bottom_y = max(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        height = bottom_y - top_y
        items.append((top_y, bottom_y, left_x, height, text.strip()))

    if not items:
        return ""

    # Sort by top_y to process top-to-bottom
    items.sort(key=lambda x: x[0])

    # Group into lines: items whose vertical midpoints are close enough
    # belong on the same line
    lines = []
    current_line = [items[0]]
    for item in items[1:]:
        # Compare current item's midpoint against the line's average midpoint
        line_mid = sum((it[0] + it[1]) / 2 for it in current_line) / len(current_line)
        curr_mid = (item[0] + item[1]) / 2
        avg_height = sum(it[3] for it in current_line) / len(current_line)
        if abs(curr_mid - line_mid) < avg_height * 0.5:
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]
    lines.append(current_line)

    # Sort each line left-to-right, then join
    text_parts = []
    for line in lines:
        line.sort(key=lambda x: x[2])
        line_text = " ".join(item[4] for item in line if item[4])
        if line_text:
            text_parts.append(line_text)

    return " ".join(text_parts)


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
    variants = _prepare_images(image_bytes)

    # Run OCR on each variant, pick the one with highest average confidence
    best_results = []
    best_confidence = -1.0

    for variant in variants:
        results = reader.readtext(variant, **_OCR_PARAMS)
        confidence = _avg_confidence(results)
        if confidence > best_confidence:
            best_confidence = confidence
            best_results = results

    return _sort_and_join(best_results)
