"""Blueprint for OCR ingredient extraction endpoint."""

from flask import Blueprint, jsonify, request
from PIL import UnidentifiedImageError

from extensions import limiter
from helpers import _require_json
from services import ocr_service

bp = Blueprint("ocr", __name__)

_TOKEN_LIMIT_KEYWORDS = ("token limit", "token_limit", "usage budget", "quota exceeded")


def _is_token_limit_error(message):
    """Check if an error message indicates a token/usage limit issue."""
    lower = message.lower()
    return any(kw in lower for kw in _TOKEN_LIMIT_KEYWORDS)


def _error_response(message, status_code, error_type=None, error_detail=None):
    """Build a structured error response with error_type and error_detail."""
    if error_type is None:
        error_type = (
            "token_limit_exceeded" if _is_token_limit_error(message) else "generic"
        )
    return jsonify({
        "error": message,
        "error_type": error_type,
        "error_detail": error_detail if error_detail is not None else message,
    }), status_code


def _is_timeout_or_connection_error(exc):
    """Check if an exception is a timeout or connection error by class name."""
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


@bp.route("/api/ocr/ingredients", methods=["POST"])
@limiter.limit("10 per minute")
def ocr_ingredients():
    if "image" in request.files:
        # Multipart/form-data upload path
        image_bytes = request.files["image"].read()
        if not image_bytes:
            return _error_response("No image provided", 400)
        try:
            result = ocr_service.dispatch_ocr_bytes(image_bytes)
        except ValueError as e:
            return _error_response(str(e), 400)
        except (TimeoutError, ConnectionError):
            return _error_response(
                "OCR provider is not responding", 503, error_type="provider_timeout",
            )
        except (UnidentifiedImageError, OSError):
            return _error_response(
                "Invalid or corrupt image", 400, error_type="invalid_image",
            )
        except Exception as e:
            if _is_timeout_or_connection_error(e):
                return _error_response(
                    "OCR provider is not responding", 503, error_type="provider_timeout",
                )
            http_status = getattr(e, "status_code", None) or getattr(e, "code", None)
            if isinstance(http_status, int) and 400 <= http_status < 500:
                return _error_response(
                    "Invalid or corrupt image", 400, error_type="invalid_image",
                )
            exc_name = type(e).__name__
            return _error_response(
                "OCR processing failed", 500, error_type="generic",
                error_detail=f"OCR processing failed ({exc_name})",
            )
    else:
        # JSON fallback (backward compatibility)
        try:
            data = _require_json()
        except ValueError as e:
            return _error_response(str(e), 400)

        image = data.get("image", "")
        if not image:
            return _error_response("No image provided", 400)

        try:
            result = ocr_service.dispatch_ocr(image)
        except ValueError as e:
            return _error_response(str(e), 400)
        except (TimeoutError, ConnectionError):
            return _error_response(
                "OCR provider is not responding", 503, error_type="provider_timeout",
            )
        except (UnidentifiedImageError, OSError):
            return _error_response(
                "Invalid or corrupt image", 400, error_type="invalid_image",
            )
        except Exception as e:
            if _is_timeout_or_connection_error(e):
                return _error_response(
                    "OCR provider is not responding", 503, error_type="provider_timeout",
                )
            http_status = getattr(e, "status_code", None) or getattr(e, "code", None)
            if isinstance(http_status, int) and 400 <= http_status < 500:
                return _error_response(
                    "Invalid or corrupt image", 400, error_type="invalid_image",
                )
            exc_name = type(e).__name__
            return _error_response(
                "OCR processing failed", 500, error_type="generic",
                error_detail=f"OCR processing failed ({exc_name})",
            )

    text = result["text"]
    provider = result["provider"]
    fallback = result["fallback"]

    if not text:
        return jsonify({
            "text": "",
            "error": "No text found in image",
            "error_type": "no_text",
            "provider": provider,
            "fallback": fallback,
        }), 200

    return jsonify({"text": text, "provider": provider, "fallback": fallback})
