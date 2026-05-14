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

_HARDENED_SYSTEM_PROMPT = (
    "You are a food-label ingredient extractor. Your sole output is a single plain-text"
    " ingredient list written in the target language specified in the user message."
    " Nothing else.\n"
    "\n"
    "INTERNAL STEP 1 — LOCATE INGREDIENT SECTIONS\n"
    "Scan the label for every ingredient section: a discrete block listing ingredients,"
    " typically preceded by a header in any language (e.g. \"Ingredients\", \"Zutaten\","
    " \"Ingrédients\", \"Ingredientes\", \"Ingredienser\", or equivalent in any language)."
    " Ignore nutritional tables, usage directions, legal disclaimers, marketing copy, and"
    " cross-contamination disclaimers unless they are a trace notice"
    " (\"may contain …\" or equivalent).\n"
    "\n"
    "INTERNAL STEP 2 — SELECT SOURCE\n"
    "A. If an ingredient section written in the target language is present on the label,"
    " use it. Go to STEP 3.\n"
    "B. If no target-language section exists but at least one ingredient section in another"
    " language is present, choose the most complete such section (longest, most detailed)"
    " and translate it into the target language. Go to STEP 3.\n"
    "C. If no readable ingredient section exists anywhere on the label, return an empty"
    " string. Stop.\n"
    "\n"
    "INTERNAL STEP 3 — NORMALISE\n"
    "Apply all of the following to the text selected or translated in STEP 2:\n"
    "1. Strip any section header from the beginning (e.g. \"Ingredienser:\","
    " \"Ingrédients:\", \"Ingredients:\", or equivalent in any language).\n"
    "2. Every allergen term listed in the user message must appear in ALL CAPS wherever it"
    " occurs in the output. All other text follows sentence-case or source capitalisation.\n"
    "3. Preserve all E-numbers exactly as written (e.g. E471, E500(i), E322).\n"
    "4. Use the decimal separator specified in the user message for all percentages"
    " (e.g. 12,5% or 12.5% depending on the separator).\n"
    "5. Keep percentage values immediately adjacent to the ingredient they quantify.\n"
    "6. Preserve sub-ingredient parenthetical groups"
    " (e.g. Chocolate (sugar, cocoa mass, butter)).\n"
    "7. Locate any \"may contain\" / equivalent trace-allergen statement on the label."
    " Rewrite it using the trace notice template from the user message, with the listed"
    " allergens in ALL CAPS. Place this rewritten trace notice at the very end of the"
    " output, after the main ingredient list.\n"
    "8. Do not carry over text from other-language sections, nutritional tables, serving"
    " instructions, or marketing claims.\n"
    "9. Ensure the output ends with exactly one period.\n"
    "\n"
    "INTERNAL STEP 4 — OUTPUT\n"
    "Return the normalised ingredient string from STEP 3. No section headers. No language"
    " labels. No explanations. No step markers. No markdown. No reasoning."
)

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
