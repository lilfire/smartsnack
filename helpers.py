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


def _require_json(expect: type | None = dict):
    """Parse JSON from request body, raising ValueError on failure.

    ``expect`` is the required top-level JSON type. The default ``dict``
    rejects string/array/number bodies with a 400-mapped ValueError —
    callers immediately use ``.get()``/``.pop()``, which crashed with
    AttributeError → 500 on non-object bodies. Handlers whose body is a
    JSON array validated downstream (the weights endpoints) pass
    ``expect=None`` to skip the type check.
    """
    data = request.get_json(silent=True)
    if data is None:
        raise ValueError("Invalid or missing JSON body")
    if expect is not None and not isinstance(data, expect):
        raise ValueError("Request body must be a JSON object")
    return data


def _str_field(data: dict, field: str, default: str = "") -> str:
    """Return ``data[field]`` as a string, mapping JSON ``null`` to ``default``.

    Use this when a route accepts an optional string field and downstream code
    calls ``.strip()``. ``data.get(field, "")`` returns ``None`` (not the
    default) when the key is present but its value is ``null``, which crashes
    ``.strip()`` with ``AttributeError`` → 500. This helper normalises that to
    the default so the caller's ``.strip()`` is always safe. Non-string
    values (e.g. a numeric EAN like ``7038010009457``) are coerced with
    ``str()`` so downstream string methods never crash.
    """
    val = data.get(field, default)
    if val is None:
        return default
    if not isinstance(val, str):
        return str(val)
    return val


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
            return (
                None,
                f"Each keyword must be a string of max {_PQ_MAX_KEYWORD_LEN} chars",
            )
    return keywords, None


_CATEGORY_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f]+\Z")


def _validate_category_name(name: str) -> str | None:
    if not name or not name.strip() or len(name) > _MAX_CATEGORY_NAME_LEN:
        return "Invalid category name"
    if not _CATEGORY_NAME_RE.match(name):
        return "Invalid category name"
    return None
