"""Request parsing and validation helpers used across blueprints."""

import math
import os
import re

from flask import request, jsonify

from config import _PQ_MAX_KEYWORDS, _PQ_MAX_KEYWORD_LEN, _MAX_CATEGORY_NAME_LEN

_API_KEY = os.environ.get("SMARTSNACK_API_KEY", "")


def _check_api_key():
    """Check API key if SMARTSNACK_API_KEY is configured.

    Returns a 401 JSON response if the key is required but missing/wrong,
    or None if access is allowed.
    """
    if not _API_KEY:
        return None
    provided = request.headers.get("X-API-Key") or request.args.get("api_key", "")
    if provided != _API_KEY:
        return jsonify({"error": "Unauthorized: invalid or missing API key"}), 401
    return None


def _require_json() -> dict:
    """Parse JSON from request body, raising ValueError on failure."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValueError("Invalid or missing JSON body")
    return data


def _num(data: dict, field: str) -> float | None:
    v = data.get(field)
    if v is None or v == "":
        return None
    try:
        result = float(v)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid numeric value for {field}") from e
    if not math.isfinite(result):
        raise ValueError(f"Invalid numeric value for {field}")
    return result


def _safe_float(v, label: str = "value") -> float:
    try:
        result = float(v)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid numeric value for {label}") from e
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric value for {label}")
    return result


def _validate_keywords(keywords) -> tuple[list | None, str | None]:
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if not isinstance(keywords, list):
        return None, "keywords must be a list or comma-separated string"
    if len(keywords) > _PQ_MAX_KEYWORDS:
        return None, f"Too many keywords (max {_PQ_MAX_KEYWORDS})"
    for kw in keywords:
        if not isinstance(kw, str) or len(kw) > _PQ_MAX_KEYWORD_LEN:
            return None, f"Each keyword must be a string of max {_PQ_MAX_KEYWORD_LEN} chars"
    return keywords, None


_CATEGORY_NAME_RE = re.compile(r"^[\w\s\-]+$", re.UNICODE)


def _validate_category_name(name: str) -> str | None:
    if not name or len(name) > _MAX_CATEGORY_NAME_LEN:
        return "Invalid category name"
    if not _CATEGORY_NAME_RE.match(name):
        return "Invalid category name"
    return None
