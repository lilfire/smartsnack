"""Vision-based OCR backends for ingredient extraction.

Exports:
  _HARDENED_SYSTEM_PROMPT  — language-agnostic 4-step system prompt
  build_ingredient_prompt  — locale-specific user message for a language code
  _INGREDIENT_PROMPT       — backward-compat alias (Norwegian defaults)
  dispatch_ocr             — route to the correct backend
"""
import os

_LANGUAGE_CONFIG = {
    "no": {
        "name": "Norwegian",
        "allergen_terms": (
            "MELK, EGG, HVETE, RUG, BYGG, HAVRE, GLUTEN, SOYA, NØTTER, "
            "PEANØTTER, SESAM, FISK, KREPSDYR, BLØTDYR, SENNEP, SELLERI, "
            "LUPIN, SULFITTER, SVOVELDIOKSID"
        ),
        "decimal_sep": ",",
        "trace_template": "Kan inneholde spor av {items}.",
    },
    "en": {
        "name": "English",
        "allergen_terms": (
            "MILK, EGGS, WHEAT, RYE, BARLEY, OATS, GLUTEN, SOY, NUTS, "
            "PEANUTS, SESAME, FISH, CRUSTACEANS, MOLLUSCS, MUSTARD, CELERY, "
            "LUPIN, SULPHITES, SULPHUR DIOXIDE"
        ),
        "decimal_sep": ".",
        "trace_template": "May contain traces of {items}.",
    },
    "se": {
        "name": "Swedish",
        "allergen_terms": (
            "MJÖLK, ÄGG, VETE, RÅG, KORN, HAVRE, GLUTEN, SOJA, NÖTTER, "
            "JORDNÖTTER, SESAM, FISK, KRÄFTDJUR, BLÖTDJUR, SENAP, SELLERI, "
            "LUPIN, SULFITER, SVAVELDIOXID"
        ),
        "decimal_sep": ",",
        "trace_template": "Kan innehålla spår av {items}.",
    },
}

# Module-level aliases for each language (used by test_hardened_vision_prompt.py)
_ALLERGENS_NO = _LANGUAGE_CONFIG["no"]["allergen_terms"]
_TRACE_TEMPLATE_NO = _LANGUAGE_CONFIG["no"]["trace_template"]
_ALLERGENS_EN = _LANGUAGE_CONFIG["en"]["allergen_terms"]
_TRACE_TEMPLATE_EN = _LANGUAGE_CONFIG["en"]["trace_template"]
_ALLERGENS_SE = _LANGUAGE_CONFIG["se"]["allergen_terms"]
_TRACE_TEMPLATE_SE = _LANGUAGE_CONFIG["se"]["trace_template"]

_HARDENED_SYSTEM_PROMPT = """\
You are a food label OCR specialist. Extract ingredient lists from food product images.

Follow these four steps precisely:

Step 1 — Locate sections
Scan the image for all text sections. Identify the one that contains the ingredient \
list (typically labeled with a word meaning "Ingredients" in any language). Ignore all \
other sections such as nutrition facts, preparation instructions, and marketing text.

Step 2 — Select and translate
Extract the ingredient list text from the section matching the target language supplied \
in the user message. If that language section is absent but an ingredient list exists in \
another language, translate the ingredient list into the target language. If no ingredient \
list is present anywhere in the image, return an empty string.

Step 3 — Normalise
- Preserve the original order of ingredients.
- Use the decimal separator specified in the user message for all numbers.
- Any allergen term that appears in ALL CAPS in the original text must remain ALL CAPS.
- Do not add, remove, or reorder ingredients.
- Expand clearly identifiable abbreviations.
- Remove duplicate whitespace and fix obvious OCR errors; do not paraphrase.

Step 4 — Output
Return ONLY the cleaned ingredient list as plain text. No preamble, no section labels, \
no explanations, no markdown formatting. If no ingredients were found, return an empty \
string.\
"""

_SUPPORTED_BACKENDS = frozenset(
    ("tesseract", "claude", "openai", "gemini", "groq", "openrouter")
)

_NUTRITION_PROMPT = (
    "Extract the per-100g nutrition values from this food label image. "
    "Return ONLY valid JSON, no prose, no markdown fences. Use this exact "
    "shape, omitting any field not present on the label. Values must be "
    "plain numbers (no units, decimal point not comma) per 100 g:\n"
    "{\n"
    '  "kcal": number,\n'
    '  "energy_kj": number,\n'
    '  "fat": number,\n'
    '  "saturated_fat": number,\n'
    '  "carbs": number,\n'
    '  "sugar": number,\n'
    '  "fiber": number,\n'
    '  "protein": number,\n'
    '  "salt": number\n'
    "}"
)


def build_ingredient_prompt(language: str) -> str:
    """Return the user message for ingredient OCR for the given language code.

    Raises:
        ValueError: If language is not a supported code (no, en, se).
    """
    cfg = _LANGUAGE_CONFIG.get(language)
    if cfg is None:
        raise ValueError(f"Unsupported language: {language!r}")
    return (
        f"Language: {cfg['name']}\n"
        f"Allergen terms (ALL CAPS): {cfg['allergen_terms']}\n"
        f"Decimal separator: {cfg['decimal_sep']}\n"
        f"Trace notice template: {cfg['trace_template']}\n\n"
        "Return the ingredient list for the language stated above — extracted if that language is present, or translated from another language if not. Return an empty string only if no readable ingredient list exists anywhere on the label. Do not output reasoning, explanations, or step labels."
    )


# Backward-compat alias — code that references _INGREDIENT_PROMPT still works.
_INGREDIENT_PROMPT = build_ingredient_prompt("no")


def dispatch_ocr(
    image_base64: str,
    backend: str = "tesseract",
    language: str = "no",
) -> str:
    """Route ingredient OCR to the specified backend.

    Args:
        image_base64: Raw base64 string or data URI (data:image/...;base64,...).
        backend: One of "tesseract", "claude", "openai", "gemini", "groq",
                 "openrouter". Defaults to "tesseract".
        language: Language code for the target output: "no", "en", or "se".
                  Ignored by the tesseract backend.

    Returns:
        Extracted ingredient text, or empty string when none found.

    Raises:
        ValueError: If backend is not recognised.
        ValueError: If language is not supported (for LLM backends).
    """
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(f"Unknown OCR backend: {backend!r}")

    if backend == "tesseract":
        from .tesseract import extract
        return extract(image_base64)

    if backend == "claude":
        from .claude import extract
    elif backend == "openai":
        from .openai import extract
    elif backend == "gemini":
        from .gemini import extract
    elif backend == "groq":
        from .groq import extract
    else:  # openrouter
        from .openrouter import extract

    return extract(image_base64, language)  # type: ignore[return-value]


# Phrases that indicate a vision LLM refused or asked for clarification
# instead of returning the ingredient list.
_CONVERSATIONAL_MARKERS = (
    "i'm happy to help",
    "i'd be happy to help",
    "i am happy to help",
    "i don't see",
    "i do not see",
    "i can't see",
    "i cannot see",
    "i'm unable to",
    "i am unable to",
    "i'm sorry",
    "i am sorry",
    "sorry, ",
    "unfortunately,",
    "please provide",
    "please upload",
    "could you provide",
    "could you share",
    "no ingredient list",
    "no food label",
    "the image appears",
    "the image is too",
    "this appears to be",
)


def ensure_trailing_period(text: str) -> str:
    """Ensure ingredient text ends with terminal punctuation."""
    if not text:
        return ""
    stripped = text.rstrip()
    if not stripped:
        return ""
    if stripped[-1] in ".!?":
        return stripped
    return stripped + "."


def looks_like_llm_refusal(text: str) -> bool:
    """Return True if text looks like a conversational LLM refusal."""
    if not text:
        return False
    stripped = text.strip().lower()
    if not stripped:
        return False
    return any(marker in stripped for marker in _CONVERSATIONAL_MARKERS)


def _get_api_key(env_var):
    """Get provider-specific API key, falling back to LLM_API_KEY."""
    key = os.environ.get(env_var, "")
    if not key:
        key = os.environ.get("LLM_API_KEY", "")
    if not key:
        raise ValueError(
            f"API key required: set {env_var} or LLM_API_KEY environment variable"
        )
    return key
