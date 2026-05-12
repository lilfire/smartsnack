"""Shared utilities for OCR backend modules."""
import os

_HARDENED_SYSTEM_PROMPT = (
    "You are a food label specialist. Your job is to extract and clean up the\n"
    "ingredient list for a single target language from raw OCR text that may\n"
    "contain packaging text in multiple languages.\n"
    "\n"
    "## Phase 1 — Isolate the target-language section\n"
    "\n"
    "The target language is stated in the user message. European food products\n"
    "frequently carry identical ingredient lists repeated in multiple languages.\n"
    "Identify section boundaries by looking for these ingredient-header keywords:\n"
    "\n"
    "  Norwegian (no):  INGREDIENSER, Ingredienser, Innhold, INNHOLD\n"
    "  English (en):    INGREDIENTS, Ingredients\n"
    "  Swedish (sv):    INGREDIENSER, INNEHÅLL, Innehåll\n"
    "  German (de):     ZUTATEN, Zutaten, ZUTATENLISTE\n"
    "  Polish (pl):     SKŁADNIKI, Składniki\n"
    "  French (fr):     INGRÉDIENTS, Ingrédients\n"
    "  Dutch (nl):      INGREDIËNTEN, Ingrediënten\n"
    "  Spanish (es):    INGREDIENTES, Ingredientes\n"
    "  Italian (it):    INGREDIENTI, Ingredienti\n"
    "\n"
    "Find the ingredient block whose header matches the target language. Extract\n"
    "only the text between that header and the next section header (or end of text).\n"
    "If no explicit header is found, identify the correct block by language\n"
    "recognition (vocabulary, diacritics, common function words).\n"
    "\n"
    "CRITICAL: Do not let any word, phrase, or fragment from a different-language\n"
    "section appear in your output. If you notice your output contains words from\n"
    "multiple languages, discard it and restart Phase 1.\n"
    "\n"
    "## Phase 2 — Normalise the isolated text\n"
    "\n"
    "Apply every rule below to the isolated target-language text only:\n"
    "\n"
    "1.  Output ONLY the cleaned ingredient list. No preamble, no explanation,\n"
    "    no headers, no extra sentences.\n"
    "2.  Format as a single comma-separated line.\n"
    "3.  The user message provides a list of allergen terms for the target language.\n"
    "    Every occurrence of those terms — or compound words that contain them\n"
    "    (e.g. HVETEMEL, SOYALESITIN, MJØLKPULVER) — must be written in ALL CAPS,\n"
    "    including inside sub-ingredient parentheses.\n"
    "4.  Use the decimal separator for the target language as specified in the user\n"
    "    message (comma or dot).\n"
    "5.  Preserve E-numbers exactly as printed: E270, E150d, E471, E904a.\n"
    "    Never expand, rephrase, or remove them.\n"
    "6.  Sub-ingredients go in parentheses immediately after their parent ingredient:\n"
    "    krydderblanding (sukker, salt, paprika, MYSEPULVER (fra MELK))\n"
    "7.  Preserve percentages from the label: solsikkeolje (30%).\n"
    "8.  The trace-allergen notice belongs at the very end. The exact phrasing is\n"
    "    supplied in the user message. Write it as the final sentence, ending with\n"
    "    a period.\n"
    "9.  The list ends with exactly one period.\n"
    "10. Strip any ingredient-section headers (e.g. \"INGREDIENSER:\", \"Ingredients:\",\n"
    "    \"Innhold:\", \"INNÄLL:\") — they must not appear in the output.\n"
    "11. Strip any nutrition-table values that leaked into the OCR text.\n"
    "12. Strip brand names, trademark notices, weight declarations, and barcodes.\n"
    "13. If the target-language section is not found or the input does not resemble\n"
    "    an ingredient list at all, return an empty string — nothing else.\n"
)

# Norwegian allergen terms (SmartSnack default language)
_ALLERGENS_NO = (
    "MELK, EGG, HVETE, RUG, BYGG, HAVRE, GLUTEN, SOYA, NØTTER, "
    "PEANØTTER, SESAM, FISK, KREPSDYR, BLØTDYR, SENNEP, SELLERI, "
    "LUPIN, SULFITTER, SVOVELDIOKSID"
)
_TRACE_TEMPLATE_NO = "Kan inneholde spor av {items}."

_ALLERGENS_EN = (
    "MILK, EGGS, WHEAT, RYE, BARLEY, OATS, GLUTEN, SOY, NUTS, "
    "PEANUTS, SESAME, FISH, CRUSTACEANS, MOLLUSCS, MUSTARD, CELERY, "
    "LUPIN, SULPHITES, SULPHUR DIOXIDE"
)
_TRACE_TEMPLATE_EN = "May contain traces of {items}."

_ALLERGENS_SE = (
    "MJÖLK, ÄGG, VETE, RÅG, KORN, HAVRE, GLUTEN, SOJA, NÖTTER, "
    "JORDNÖTTER, SESAM, FISK, KRÄFTDJUR, BLÖTDJUR, SENAP, SELLERI, "
    "LUPIN, SULFITER, SVAVELDIOXID"
)
_TRACE_TEMPLATE_SE = "Kan innehålla spår av {items}."

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


def build_ingredient_prompt(language: str | None = None) -> str:
    """Return the structured user message for ingredient extraction.

    Tells the vision LLM the target language, allergen terms, decimal separator,
    and trace-notice template. The system prompt (_HARDENED_SYSTEM_PROMPT)
    carries all normalisation rules.

    Falls back to Norwegian for None, empty string, or unknown language codes.
    """
    lang = (language or "").strip() or "no"
    if lang not in ("no", "en", "se"):
        lang = "no"

    if lang == "en":
        return (
            "Language: English\n"
            f"Allergen terms: {_ALLERGENS_EN}\n"
            "Decimal separator: dot\n"
            f"Trace notice template: {_TRACE_TEMPLATE_EN}\n"
        )
    if lang == "se":
        return (
            "Language: Swedish\n"
            f"Allergen terms: {_ALLERGENS_SE}\n"
            "Decimal separator: comma\n"
            f"Trace notice template: {_TRACE_TEMPLATE_SE}\n"
        )
    # Default: Norwegian
    return (
        "Language: Norwegian\n"
        f"Allergen terms: {_ALLERGENS_NO}\n"
        "Decimal separator: comma\n"
        f"Trace notice template: {_TRACE_TEMPLATE_NO}\n"
    )


# Backward-compatible alias
_INGREDIENT_PROMPT = build_ingredient_prompt()


# Phrases that indicate a vision LLM refused or asked for clarification
# instead of returning the ingredient list. Real ingredient lists are
# comma-separated product names and never contain these markers, so
# substring matching is safe.
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
    """Ensure ingredient text ends with terminal punctuation.

    The SmartSnack DB stores every ingredient string with a trailing period.
    Vision models occasionally drop it, so the dispatch layer applies this
    minimal fix-up. Empty input returns empty (so the no-text path still
    fires). Strings already ending in ``. ! ?`` are left untouched.
    """
    if not text:
        return ""
    stripped = text.rstrip()
    if not stripped:
        return ""
    if stripped[-1] in ".!?":
        return stripped
    return stripped + "."


def looks_like_llm_refusal(text: str) -> bool:
    """Return True if ``text`` looks like a conversational LLM refusal or
    clarification request rather than an extracted ingredient list.

    Vision models occasionally ignore the prompt's empty-string rule and
    reply with prose like "I'm happy to help, but I don't see an image of
    a food label.". The OCR dispatch layer uses this helper as a safety
    net to convert such responses into the existing no-text error path.
    """
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
