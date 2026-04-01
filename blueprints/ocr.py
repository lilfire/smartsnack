"""Blueprint for OCR ingredient extraction endpoint."""

from flask import Blueprint, jsonify
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
        "error_detail": error_detail or message,
    }), status_code


@bp.route("/api/ocr/ingredients", methods=["POST"])
@limiter.limit("10 per minute")
def ocr_ingredients():
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
            "Could not read image — the service is not responding. Try again shortly.",
            503,
            error_type="provider_timeout",
        )
    except (UnidentifiedImageError, OSError):
        return _error_response(
            "Could not read image — invalid image format. Try a different image.",
            400,
            error_type="invalid_image",
        )
    except Exception as exc:
        return _error_response(
            "OCR processing failed",
            500,
            error_type="generic",
            error_detail=f"{type(exc).__name__}: {exc}",
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
