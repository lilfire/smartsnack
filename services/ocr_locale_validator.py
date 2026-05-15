"""Locale validator for LLM-generated text with cascading correction.

Validates that LLM output is in the requested language and applies a
three-level correction cascade when a mismatch is detected:
  Level 1 — retry:     call retry_fn() and re-detect
  Level 2 — translate: call translate_fn(text) on the best available text
  Level 3 — flag:      surface localeMismatch=True and return original text
"""

from langdetect import detect, DetectorFactory, LangDetectException

# Fix seed for deterministic detection across runs.
DetectorFactory.seed = 0


def validate_and_correct(text, requested_language, retry_fn, translate_fn):
    """Validate the detected language of *text* and attempt cascaded correction.

    Args:
        text: str — the LLM output to validate.
        requested_language: str — ISO 639-1 code of the expected language
            (e.g. ``"no"``, ``"en"``, ``"sv"``).
        retry_fn: callable() -> str — re-runs the upstream LLM call to get a
            fresh result. Called at most once.
        translate_fn: callable(str) -> str — translates its argument into
            *requested_language*. Called at most once.

    Returns:
        dict with keys:
            ``text``            (str)       — final text, original or corrected.
            ``localeMismatch``  (bool)      — True only when all correction
                                             attempts failed to produce the
                                             requested language.
            ``detectedLanguage`` (str|None) — language code detected in the
                                             initial *text*, or None when
                                             detection was not possible.
    """
    if not text or not text.strip():
        return {"text": text, "localeMismatch": False, "detectedLanguage": None}

    detected = _detect_safe(text)

    if detected is None or detected == requested_language:
        return {"text": text, "localeMismatch": False, "detectedLanguage": detected}

    # Level 1: retry — ask the LLM again.
    retry_text = retry_fn()
    retry_detected = _detect_safe(retry_text) if retry_text else None
    if retry_detected == requested_language:
        return {
            "text": retry_text,
            "localeMismatch": False,
            "detectedLanguage": retry_detected,
        }

    # Level 2: translate — pass the best available text to translate_fn.
    source = retry_text if retry_text else text
    translated = translate_fn(source)
    translate_detected = _detect_safe(translated) if translated else None
    if translate_detected == requested_language:
        return {
            "text": translated,
            "localeMismatch": False,
            "detectedLanguage": translate_detected,
        }

    # Level 3: flag — all attempts exhausted; surface the mismatch flag.
    return {"text": text, "localeMismatch": True, "detectedLanguage": detected}


def _detect_safe(text):
    """Return the ISO 639-1 language code for *text*, or None on failure."""
    if not text or not text.strip():
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None
