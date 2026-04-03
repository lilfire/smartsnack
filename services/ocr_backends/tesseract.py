"""Tesseract OCR backend."""
import io

from PIL import Image, ImageEnhance

_MIN_CONFIDENCE = 30


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
