"""OCR service for extracting text from ingredient images using EasyOCR."""

import base64
import io
import re

import numpy as np

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["no", "en"], gpu=False)
    return _reader


def _preprocess_image(image_bytes):
    """Preprocess image to improve OCR accuracy.

    Converts to grayscale, enhances contrast/sharpness, applies adaptive
    thresholding, and upscales small images.
    """
    import cv2
    from PIL import Image, ImageEnhance

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Upscale small images — OCR works better on larger text
    w, h = image.size
    if max(w, h) < 1500:
        scale = 1500 / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Enhance contrast and sharpness
    image = ImageEnhance.Contrast(image).enhance(1.8)
    image = ImageEnhance.Sharpness(image).enhance(2.0)

    # Convert to grayscale numpy array for OpenCV processing
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    # Adaptive thresholding to handle uneven lighting
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    # Light denoise to clean up artifacts without losing text detail
    binary = cv2.medianBlur(binary, 3)

    return binary


def _sort_and_join(results):
    """Sort OCR results by position (top-to-bottom, left-to-right) and join.

    Groups text boxes into lines based on vertical overlap, then orders
    left-to-right within each line.
    """
    if not results:
        return ""

    # results format: [([[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence), ...]
    # Extract (top_y, left_x, text) for sorting
    items = []
    for bbox, text, _conf in results:
        top_y = min(pt[1] for pt in bbox)
        bottom_y = max(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        height = bottom_y - top_y
        items.append((top_y, bottom_y, left_x, height, text.strip()))

    if not items:
        return ""

    # Sort by top_y first to process top-to-bottom
    items.sort(key=lambda x: x[0])

    # Group into lines: boxes whose vertical centers are within half a
    # typical line height of each other belong on the same line
    lines = []
    current_line = [items[0]]
    for item in items[1:]:
        prev_mid = (current_line[-1][0] + current_line[-1][1]) / 2
        curr_mid = (item[0] + item[1]) / 2
        avg_height = (current_line[-1][3] + item[3]) / 2
        if abs(curr_mid - prev_mid) < avg_height * 0.6:
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

    preprocessed = _preprocess_image(image_bytes)

    reader = _get_reader()
    results = reader.readtext(
        preprocessed,
        detail=1,
        paragraph=False,
        contrast_ths=0.3,
        adjust_contrast=0.7,
        width_ths=0.8,
        text_threshold=0.6,
        low_text=0.3,
        link_threshold=0.3,
    )

    return _sort_and_join(results)
