"""Blueprint for OCR ingredient extraction endpoint."""

from flask import Blueprint, jsonify, request
from PIL import UnidentifiedImageError

from extensions import limiter
from helpers import _require_json
from services import ocr_service

bp = Blueprint("ocr", __name__)

_TOKEN_LIMIT_KEYWORDS = ("token limit", "token_limit", "usage budget", "quota exceeded")
_QUOTA_KEYWORDS = ("resource_exhausted", "quota exceeded", "rate limit", "rate_limit")


def _is_token_limit_error(message):
    """Check if an error message indicates a token/usage limit issue."""
    lower = message.lower()
    return any(kw in lower for kw in _TOKEN_LIMIT_KEYWORDS)


def _is_quota_error(exc):
    """Check if an exception is a provider quota / rate-limit error."""
    http_status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if http_status == 429:
        return True
    msg = str(exc).lower()
    return any(kw in msg for kw in _QUOTA_KEYWORDS)


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


def _handle_ocr_exception(exc):
    """Map a provider exception to a Flask error response.

    Shared between /api/ocr/ingredients and /api/ocr/nutrition so both
    endpoints surface the same structured error taxonomy to the frontend.
    """
    if isinstance(exc, ValueError):
        return _error_response(str(exc), 400)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return _error_response(
            "OCR provider is not responding", 503, error_type="provider_timeout",
        )
    if isinstance(exc, (UnidentifiedImageError, OSError)):
        return _error_response(
            "Invalid or corrupt image", 400, error_type="invalid_image",
        )
    if _is_timeout_or_connection_error(exc):
        return _error_response(
            "OCR provider is not responding", 503, error_type="provider_timeout",
        )
    if _is_quota_error(exc):
        return _error_response(
            "OCR provider quota exceeded",
            429,
            error_type="provider_quota",
            error_detail="The selected OCR provider has reached its usage quota.",
        )
    http_status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(http_status, int) and 400 <= http_status < 500:
        return _error_response(
            f"OCR provider error: {exc}", http_status,
            error_type="provider_error",
            error_detail=str(exc),
        )
    exc_name = type(exc).__name__
    return _error_response(
        "OCR processing failed", 500, error_type="generic",
        error_detail=f"OCR processing failed ({exc_name})",
    )


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
            if _is_quota_error(e):
                return _error_response(
                    "OCR provider quota exceeded",
                    429,
                    error_type="provider_quota",
                    error_detail="The selected OCR provider has reached its usage quota.",
                )
            http_status = getattr(e, "status_code", None) or getattr(e, "code", None)
            if isinstance(http_status, int) and 400 <= http_status < 500:
                return _error_response(
                    f"OCR provider error: {e}", http_status,
                    error_type="provider_error",
                    error_detail=str(e),
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
            if _is_quota_error(e):
                return _error_response(
                    "OCR provider quota exceeded",
                    429,
                    error_type="provider_quota",
                    error_detail="The selected OCR provider has reached its usage quota.",
                )
            http_status = getattr(e, "status_code", None) or getattr(e, "code", None)
            if isinstance(http_status, int) and 400 <= http_status < 500:
                return _error_response(
                    f"OCR provider error: {e}", http_status,
                    error_type="provider_error",
                    error_detail=str(e),
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


def _read_request_image_bytes():
    """Return raw image bytes from either a multipart upload or a JSON data URI.

    Returns (image_bytes, error_response). Exactly one is None.
    """
    import base64
    import re as _re

    if "image" in request.files:
        image_bytes = request.files["image"].read()
        if not image_bytes:
            return None, _error_response("No image provided", 400)
        return image_bytes, None

    try:
        data = _require_json()
    except ValueError as e:
        return None, _error_response(str(e), 400)

    image = data.get("image", "")
    if not image or not isinstance(image, str):
        return None, _error_response("No image provided", 400)

    raw = image
    if raw.startswith("data:"):
        match = _re.match(r"data:image/[^;]+;base64,(.+)", raw, _re.DOTALL)
        if not match:
            return None, _error_response("Invalid data URI format", 400)
        raw = match.group(1)

    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        return None, _error_response("Invalid base64 data", 400)

    if not image_bytes:
        return None, _error_response("No image provided", 400)

    return image_bytes, None


@bp.route("/api/ocr/nutrition", methods=["POST"])
@limiter.limit("10 per minute")
def ocr_nutrition():
    """Extract per-100g nutrition values from a food label image.

    Accepts either a multipart upload (field "image") or a JSON body
    {"image": "<base64 or data URI>"}.

    Success response:
        {"values": {...}, "provider": str, "fallback": bool, "count": int}

    If the provider returns no usable values, responds 200 with:
        {"values": {}, "error": "...", "error_type": "no_values",
         "provider": str, "fallback": bool, "count": 0}
    """
    image_bytes, err = _read_request_image_bytes()
    if err is not None:
        return err

    try:
        result = ocr_service.dispatch_nutrition_ocr_bytes(image_bytes)
    except Exception as exc:  # noqa: BLE001 — map any provider error via helper
        return _handle_ocr_exception(exc)

    values = result.get("values") or {}
    provider = result.get("provider", "")
    fallback = bool(result.get("fallback", False))

    if not values:
        return jsonify({
            "values": {},
            "count": 0,
            "error": "No nutrition values found in image",
            "error_type": "no_values",
            "provider": provider,
            "fallback": fallback,
        }), 200

    return jsonify({
        "values": values,
        "count": len(values),
        "provider": provider,
        "fallback": fallback,
    })
