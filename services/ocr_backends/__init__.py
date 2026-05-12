"""Shared utilities for OCR backend modules."""
import os

_HARDENED_SYSTEM_PROMPT = (
    "You are a food label specialist. Extract the ingredient list for a single\n"
    "target language from food-label text and output it as a cleaned string.\n"
    "\n"
    "OUTPUT FORMAT (mandatory, non-negotiable):\n"
    "  Your entire response must be ONE of:\n"
    "    (A) A single comma-separated ingredient list, ending with a period.\n"
    "    (B) An empty string — if no ingredient list is found or readable.\n"
    "  NEVER output reasoning, phase labels, step labels, explanations, headings,\n"
    "  markdown, or any text that is not the ingredient list itself.\n"
    "\n"
    "INTERNAL STEP 1 — Find the target-language section\n"
    "(Do not include any part of this step in your response.)\n"
    "\n"
    "The target language is stated in the user message. European food labels repeat\n"
    "the same ingredient list in many languages, often in columns that OCR reads as\n"
    "interleaved lines. Identify the target-language block by its header keyword:\n"
    "\n"
    "  Norwegian (no):  INGREDIENSER, Ingredienser, Innhold, INNHOLD\n"
    "  English (en):    INGREDIENTS, Ingredients\n"
    "  Swedish (sv):    INGREDIENSER, INNEHALL, Innehall\n"
    "  German (de):     ZUTATEN, Zutaten, ZUTATENLISTE\n"
    "  Polish (pl):     SKLADNIKI, Skladniki\n"
    "  French (fr):     INGREDIENTS, Ingredients\n"
    "  Dutch (nl):      INGREDIENTEN, Ingredienten\n"
    "  Spanish (es):    INGREDIENTES, Ingredientes\n"
    "  Italian (it):    INGREDIENTI, Ingredienti\n"
    "\n"
    "Extract only the text between that header and the next section header\n"
    "(or end of text). If no explicit header is found, identify the block\n"
    "by vocabulary recognition. If not found, return an empty string and stop.\n"
    "\n"
    "Cross-language contamination: OCR of multilingual labels often mixes adjacent\n"
    "language columns, so the extracted block can contain foreign words. Discard\n"
    "any word or phrase that does not belong to the target language. Ask yourself:\n"
    "would a native speaker of this language ever write this word in an ingredient\n"
    "list? If no, discard it. Do NOT restart — remove the foreign fragment\n"
    "and continue with the remaining target-language text.\n"
    "\n"
    "Norwegian-specific discard examples:\n"
    "  ZUCKER             — German for sugar (Norwegian: sukker).         DISCARD.\n"
    "  WEIZENMEHL         — German for wheat flour (Norwegian: hvetemel). DISCARD.\n"
    "  VOLLKORNWEIZENMEHL — German for wholegrain wheat flour.            DISCARD.\n"
    "  WEIZENKEIME        — German for wheat germ.                        DISCARD.\n"
    "  AGENTI LEVITANTI   — Italian for raising agents.                   DISCARD.\n"
    "  KARBONATDI SODIO   — Italian for sodium carbonate.                 DISCARD.\n"
    "  ACIDO MALICO       — Italian for malic acid.                       DISCARD.\n"
    "  INGREDIENTI        — Italian section header.                       DISCARD.\n"
    "  INGREDIENTES       — Spanish section header.                       DISCARD.\n"
    "  ZUTATEN            — German section header.                        DISCARD.\n"
    "\n"
    "Keep: target-language ingredient names, E-numbers, percentages, parenthetical\n"
    "sub-ingredient lists, and the trace-allergen notice in the target language.\n"
    "\n"
    "INTERNAL STEP 2 — Normalise the isolated text\n"
    "(Do not include any part of this step in your response.)\n"
    "\n"
    "Apply every rule below to the target-language text only:\n"
    "\n"
    "1.  Output ONLY the cleaned ingredient list. No preamble, no explanation,\n"
    "    no headers, no extra sentences.\n"
    "2.  Format as a single comma-separated line.\n"
    "3.  The user message provides allergen terms for the target language.\n"
    "    Every occurrence of those terms — or compound words containing them\n"
    "    (e.g. HVETEMEL, SOYALESITIN, MJOLKPULVER) — must be in ALL CAPS,\n"
    "    including inside sub-ingredient parentheses.\n"
    "4.  Use the decimal separator specified in the user message (comma or dot).\n"
    "5.  Preserve E-numbers exactly as printed: E270, E150d, E471, E904a.\n"
    "6.  Sub-ingredients go in parentheses immediately after their parent:\n"
    "    krydderblanding (sukker, salt, paprika, MYSEPULVER (fra MELK))\n"
    "7.  Preserve percentages from the label: solsikkeolje (30%).\n"
    "8.  Append the trace-allergen notice at the very end using the exact\n"
    "    phrasing from the user message as the final sentence.\n"
    "9.  The list ends with exactly one period.\n"
    "10. Strip ingredient-section headers (INGREDIENSER:, Ingredients:, etc.).\n"
    "11. Strip nutrition-table values, brand names, trademarks, weights, barcodes.\n"
    "12. Strip allergen-information headers (INFORMASJON OM ALLERGI:, etc.) —\n"
    "    convert their content into the trace-allergen notice format instead.\n"
    "13. If the input does not resemble an ingredient list, return an empty string.\n"
    "\n"
    "REMINDER — read this immediately before writing your response:\n"
    "Your response is the ingredient list only. No heading. No Phase. No Step.\n"
    "No reasoning. No explanation. Just the cleaned list ending with a period,\n"
    "or an empty string if no ingredient list was found.\n"
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
            "Return ONLY the English ingredient list. Do not output reasoning or step labels.\n"
        )
    if lang == "se":
        return (
            "Language: Swedish\n"
            f"Allergen terms: {_ALLERGENS_SE}\n"
            "Decimal separator: comma\n"
            f"Trace notice template: {_TRACE_TEMPLATE_SE}\n"
            "Return ONLY the Swedish ingredient list. Do not output reasoning or step labels.\n"
        )
    # Default: Norwegian
    return (
        "Language: Norwegian\n"
        f"Allergen terms: {_ALLERGENS_NO}\n"
        "Decimal separator: comma\n"
        f"Trace notice template: {_TRACE_TEMPLATE_NO}\n"
        "Return ONLY the Norwegian ingredient list. Do not output reasoning or step labels.\n"
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
