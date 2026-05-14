"""Tesseract/EasyOCR backend — wraps the existing ocr_service.

This backend ignores the language parameter and system prompt; it delegates
to the EasyOCR-based ocr_service for local, offline text extraction.
"""

from services import ocr_service


def extract(image_base64: str) -> str:
    """Extract text from image using EasyOCR (no LLM, no prompts)."""
    return ocr_service.extract_text(image_base64)
