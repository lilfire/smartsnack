"""Parse per-100g nutrition values from OCR provider output.

Input is raw text from a vision LLM (ideally JSON) or from tesseract
(messy free text). Output is a clean dict keyed by the canonical
NUTRITION_FIELDS names, containing only values that pass sanity checks.
"""
import json
import logging
import re

logger = logging.getLogger("services.nutrition_parser")

_ALLOWED_FIELDS = (
    "kcal",
    "energy_kj",
    "fat",
    "saturated_fat",
    "carbs",
    "sugar",
    "fiber",
    "protein",
    "salt",
)

# Per-field sanity caps for per-100g values. kcal caps at 900 (pure fat is 900).
# Grams fields cap at 100 per 100g. Salt capped lower (no real food is 50%+ salt).
_SANITY_MAX = {
    "kcal": 900.0,
    "energy_kj": 3800.0,
    "fat": 100.0,
    "saturated_fat": 100.0,
    "carbs": 100.0,
    "sugar": 100.0,
    "fiber": 100.0,
    "protein": 100.0,
    "salt": 50.0,
}

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

# Matches a number (int or decimal, comma or dot, optional leading < or ~)
# and captures the first number of a range like "4-6" or "4–6".
_NUM_RE = r"[<~]?\s*(\d+(?:[.,]\d+)?)"

# Regex patterns per field. Each pattern captures the numeric value.
# Ordered: longer/more-specific variants first to avoid shadowing
# (e.g. "saturated fat" must match before "fat"; "energy kJ" before "kcal").
_REGEX_PATTERNS = {
    "energy_kj": [
        re.compile(rf"(?:energi|energy)[^0-9]{{0,20}}{_NUM_RE}\s*kj", re.IGNORECASE),
        re.compile(rf"{_NUM_RE}\s*kj", re.IGNORECASE),
    ],
    "kcal": [
        re.compile(rf"{_NUM_RE}\s*kcal", re.IGNORECASE),
    ],
    "saturated_fat": [
        re.compile(
            rf"(?:herav\s+mettede?(?:\s+fettsyrer)?|mettet\s+fett|of\s+which\s+saturates?|saturated\s+fat|saturates)"
            rf"[^0-9\n]{{0,20}}{_NUM_RE}\s*g",
            re.IGNORECASE,
        ),
    ],
    "fat": [
        re.compile(rf"(?:^|[^a-zA-Z])(?:fett|fat)[^0-9\n]{{0,20}}{_NUM_RE}\s*g", re.IGNORECASE | re.MULTILINE),
    ],
    "sugar": [
        re.compile(
            rf"(?:herav\s+sukker(?:arter)?|of\s+which\s+sugars?|sugars?)"
            rf"[^0-9\n]{{0,20}}{_NUM_RE}\s*g",
            re.IGNORECASE,
        ),
    ],
    "carbs": [
        re.compile(
            rf"(?:karbohydrater?|carbohydrates?|carbs)[^0-9\n]{{0,20}}{_NUM_RE}\s*g",
            re.IGNORECASE,
        ),
    ],
    "fiber": [
        re.compile(
            rf"(?:kostfiber|fiber|fibre)[^0-9\n]{{0,20}}{_NUM_RE}\s*g",
            re.IGNORECASE,
        ),
    ],
    "protein": [
        re.compile(rf"(?:protein|proteiner)[^0-9\n]{{0,20}}{_NUM_RE}\s*g", re.IGNORECASE),
    ],
    "salt": [
        re.compile(rf"(?:salt|sodium\s+chloride)[^0-9\n]{{0,20}}{_NUM_RE}\s*g", re.IGNORECASE),
    ],
}


def _to_float(raw):
    """Coerce a scalar (str/int/float) to float, handling decimal comma."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip().replace(",", ".")
        # Take first numeric token (handles ranges like "4-6" or "4–6 g")
        m = re.match(r"[<~]?\s*(-?\d+(?:\.\d+)?)", s)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _clean(values):
    """Filter to allow-list, coerce to float, drop out-of-range values."""
    out = {}
    for key, raw in (values or {}).items():
        if key not in _ALLOWED_FIELDS:
            continue
        num = _to_float(raw)
        if num is None:
            continue
        if num < 0:
            logger.debug("dropped %s=%s (negative)", key, raw)
            continue
        cap = _SANITY_MAX.get(key)
        if cap is not None and num > cap:
            logger.debug("dropped %s=%s (exceeds cap %s)", key, raw, cap)
            continue
        out[key] = num
    return out


def _strip_fences(text):
    """Remove ```json ... ``` fences or bare ``` fences if present."""
    if not text:
        return text
    stripped = text.strip()
    if "```" not in stripped:
        return stripped
    # Remove opening fence
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", stripped, count=1, flags=re.IGNORECASE)
    # Remove trailing fence
    stripped = re.sub(r"\n?```\s*$", "", stripped, count=1)
    return stripped.strip()


def _try_json(text):
    """Try to extract a JSON object from text. Returns dict or None."""
    if not text:
        return None
    candidate = _strip_fences(text)
    # Fast path: whole string is JSON
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Slow path: find first {...} block
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", candidate, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def parse_nutrition_text(text):
    """Regex-based extraction of nutrition values from free-text OCR output.

    Handles Norwegian and English labels. Returns a dict of canonical field
    names to float values; only fields successfully extracted are included.
    """
    if not text or not isinstance(text, str):
        return {}
    out = {}
    for field, patterns in _REGEX_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                out[field] = match.group(1)
                break
    return _clean(out)


def parse_nutrition_response(text):
    """Parse nutrition data from provider output (JSON first, regex fallback).

    Accepts raw text from a vision LLM (may include markdown fences) or
    tesseract. Returns a cleaned dict keyed by NUTRITION_FIELDS names.
    Empty dict on failure — never raises.
    """
    if not text or not isinstance(text, str):
        return {}
    parsed = _try_json(text)
    if parsed is not None:
        cleaned = _clean(parsed)
        if cleaned:
            return cleaned
    return parse_nutrition_text(text)
