"""Request parsing and validation helpers used across blueprints."""

import math
import re

from flask import request

from config import _PQ_MAX_KEYWORDS, _PQ_MAX_KEYWORD_LEN


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
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {field}")
    if not math.isfinite(result):
        raise ValueError(f"Invalid numeric value for {field}")
    return result


def _safe_float(v, label: str = "value") -> float:
    try:
        result = float(v)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {label}")
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


_MAX_CATEGORY_NAME_LEN = 100
_CATEGORY_NAME_RE = re.compile(r"^[\w\s\-]+$", re.UNICODE)


def _validate_category_name(name: str) -> str | None:
    if not name or len(name) > _MAX_CATEGORY_NAME_LEN:
        return "Invalid category name"
    if not _CATEGORY_NAME_RE.match(name):
        return "Invalid category name"
    return None
