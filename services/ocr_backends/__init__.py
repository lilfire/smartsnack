"""Shared utilities for OCR backend modules."""
import os

_HARDENED_SYSTEM_PROMPT = (
    "You are a food label specialist. Your task is to produce a clean, normalised\n"
    "ingredient list in the target language from a food-label image.\n"
    "\n"
    "══ OUTPUT CONTRACT ══\n"
    "\n"
    "Your entire response must be exactly ONE of:\n"
    "\n"
    "  (A) A comma-separated ingredient list in the target language, ending with\n"
    "      a period — when the target-language ingredient section is present in\n"
    "      the label: extract, clean, and normalise it.\n"
    "\n"
    "  (B) A comma-separated ingredient list in the target language, ending with\n"
    "      a period — when no target-language section is present but an ingredient\n"
    "      list is readable in another language: translate it into the target\n"
    "      language, then apply the same normalisation rules.\n"
    "\n"
    "  (C) An empty string — only when no readable ingredient list exists anywhere\n"
    "      on the label (unreadable image, non-food content, blank label, etc.).\n"
    "\n"
    "NEVER output reasoning, explanations, apologies, step labels, headings,\n"
    "markdown, or any text that is not the ingredient list itself.\n"
    "When returning (C), output ZERO characters — not a space, not a word.\n"
    "\n"
    "══ INTERNAL STEP 1 — Find the ingredient section ══\n"
    "(Do not include any part of this step in your response.)\n"
    "\n"
    "The target language is named in the user message. Food labels may print the\n"
    "ingredient list under headings in several languages, often in columns that OCR\n"
    "reads as interleaved lines.\n"
    "\n"
    "First, search for the target-language ingredient section. Its heading is a word\n"
    "or short phrase in the target language meaning 'ingredients' or 'contents',\n"
    "typically printed in all-caps or title case, optionally followed by a colon.\n"
    "You know the vocabulary of the target language — use that knowledge to\n"
    "recognise the heading without relying on any pre-listed keywords.\n"
    "If found, extract that block and proceed to STEP 2 (path A).\n"
    "\n"
    "If no target-language section is found, search for an ingredient list in any\n"
    "other language on the label. Use the same structural cue: a heading meaning\n"
    "'ingredients' or 'contents' in any language, followed by a list of food items.\n"
    "Select the most complete readable block and proceed to STEP 3 (path B).\n"
    "\n"
    "If no readable ingredient list is found in any language, return an empty string\n"
    "and stop (path C). Output nothing else.\n"
    "\n"
    "══ INTERNAL STEP 2 — Extract and normalise (path A: target language present) ══\n"
    "(Do not include any part of this step in your response.)\n"
    "\n"
    "Cross-language contamination: OCR of multilingual labels often mixes adjacent\n"
    "language columns into a single block. Discard any word or phrase that does not\n"
    "belong to the target language — ask yourself whether a native speaker of the\n"
    "target language would write that word in an ingredient list. If not, discard it.\n"
    "Remove the foreign fragment and continue; do not restart.\n"
    "\n"
    "Apply the normalisation rules in STEP 4 and output the result.\n"
    "\n"
    "══ INTERNAL STEP 3 — Translate and normalise (path B: target language absent) ══\n"
    "(Do not include any part of this step in your response.)\n"
    "\n"
    "Translate each ingredient name from the source language into the target language.\n"
    "Translate ingredient terms, not prose: preserve the list structure, E-numbers,\n"
    "percentages, and sub-ingredient parentheses. Translate compound ingredient names\n"
    "as food terms.\n"
    "\n"
    "Apply the normalisation rules in STEP 4 and output the result.\n"
    "\n"
    "══ INTERNAL STEP 4 — Normalisation rules ══\n"
    "(Apply after extraction (path A) or translation (path B). Do not include any\n"
    "part of this step in your response.)\n"
    "\n"
    "1.  Output ONLY the cleaned ingredient list. No preamble, no explanation,\n"
    "    no headers, no extra sentences.\n"
    "2.  Format as a single comma-separated line.\n"
    "3.  The user message provides the allergen terms for the target language.\n"
    "    Every occurrence of those terms — or compound words containing them —\n"
    "    must be written in ALL CAPS, including inside sub-ingredient parentheses.\n"
    "4.  Use the decimal separator specified in the user message (comma or dot).\n"
    "5.  Preserve E-numbers exactly as printed: E270, E150d, E471, E904a.\n"
    "6.  Sub-ingredients go in parentheses immediately after their parent ingredient.\n"
    "7.  Preserve percentages from the label.\n"
    "8.  Append the trace-allergen notice at the very end using the exact phrasing\n"
    "    from the user message as the final sentence.\n"
    "9.  The list ends with exactly one period.\n"
    "10. Strip ingredient-section headings from the output.\n"
    "11. Strip nutrition-table values, brand names, trademarks, weights, barcodes.\n"
    "12. Strip allergen-information headings — convert their content into the\n"
    "    trace-allergen notice format instead.\n"
    "13. If the extracted or translated block does not resemble an ingredient list,\n"
    "    return an empty string.\n"
    "\n"
    "══ FINAL CHECK — before writing your response ══\n"
    "Path A or B (found or produced an ingredient list)?\n"
    "  → Output the cleaned, normalised list ending with a period.\n"
    "Path C (no readable ingredient list anywhere on the label)?\n"
    "  → Output nothing. Zero characters. No explanation.\n"
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
            "Return the ingredient list for the language stated above — extracted if that language is present, or translated from another language if not. Return an empty string only if no readable ingredient list exists anywhere on the label. Do not output reasoning, explanations, or step labels.\n"
        )
    if lang == "se":
        return (
            "Language: Swedish\n"
            f"Allergen terms: {_ALLERGENS_SE}\n"
            "Decimal separator: comma\n"
            f"Trace notice template: {_TRACE_TEMPLATE_SE}\n"
            "Return the ingredient list for the language stated above — extracted if that language is present, or translated from another language if not. Return an empty string only if no readable ingredient list exists anywhere on the label. Do not output reasoning, explanations, or step labels.\n"
        )
    # Default: Norwegian
    return (
        "Language: Norwegian\n"
        f"Allergen terms: {_ALLERGENS_NO}\n"
        "Decimal separator: comma\n"
        f"Trace notice template: {_TRACE_TEMPLATE_NO}\n"
        "Return the ingredient list for the language stated above — extracted if that language is present, or translated from another language if not. Return an empty string only if no readable ingredient list exists anywhere on the label. Do not output reasoning, explanations, or step labels.\n"
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
