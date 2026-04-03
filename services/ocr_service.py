"""OCR service public interface.

All logic lives in ocr_core and services/ocr_backends/.
This module re-exports the public API for backward compatibility.
"""
from services.ocr_core import (  # noqa: F401
    _detect_mime_type,
    _PROVIDERS,
    extract_text,
    get_available_backends,
    dispatch_ocr,
    dispatch_ocr_bytes,
)
from services.ocr_backends.tesseract import (  # noqa: F401
    _prepare_images,
    _sort_and_join,
    _avg_confidence_tesseract,
)
from services.ocr_backends.gemini import (  # noqa: F401
    _convert_for_gemini,
    _svg_to_png,
)
