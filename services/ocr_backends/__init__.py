"""Shared utilities for OCR backend modules."""
import os

_LANGUAGE_NAMES = {
    "no": "Norwegian (Bokmål)",
    "en": "English",
    "se": "Swedish",
}

# Shared formatting rules. The SmartSnack database stores each ingredient
# string in a canonical shape (single comma-separated line, allergens in
# ALL CAPS, Norwegian decimal comma, trailing period, "may contain traces"
# warning at the end). Vision models follow this format much more reliably
# when the rules are spelled out and a concrete example is shown — see
# ``_FEWSHOT_EXAMPLE`` below.
_FORMATTING_RULES = (
    "- Output the ingredient list as a single line, with ingredients separated by commas.\n"
    "- Capitalize allergens in ALL CAPS — including any compound that contains them. "
    "Common allergen roots: MELK, MYSE, FLØTE, RØMME, OST, LAKTOSE, KASEIN, "
    "EGG, EGGE, HVETE, BYGG, RUG, HAVRE, GLUTEN, SPELT, SOYA, SESAM, LUPIN, "
    "PEANØTT, NØTT, MANDEL, HASSEL, CASHEW, VALNØTT, PARANØTT, PEKAN, "
    "PISTASJ, MAKADAMIA, FISK, SKALLDYR, KREPSDYR, BLØTDYR, SELLERI, "
    "SENNEP, SULFITT. Examples: HVETEMEL, HVETEGLUTEN, MYSEPROTEIN, "
    "MELKEPROTEINKONSENTRAT, SOYALECITIN, HELMELKPULVER, EGGEHVITEPULVER, "
    "PEANØTTBITER, HASSELNØTTER, NATRIUMMETABISULFITT.\n"
    "- Do NOT capitalize derived chemicals or unrelated words that merely contain "
    "those letters (e.g. \"melkesyre\", \"eggehvit\" inside a product name). "
    "Capitalize only when the word itself names an allergenic ingredient.\n"
    "- Use parentheses for sub-ingredients, e.g. \"krydderblanding (sukker, "
    "salt, paprika, MYSEPULVER (fra MELK), gjærekstrakt)\".\n"
    "- Preserve percentages from the label and use a comma as the decimal "
    "separator: write \"(15%)\", \"(0,4%)\", \"4,4%\" — never \"0.4%\".\n"
    "- Preserve E-numbers exactly as printed on the label (e.g. \"E270\", "
    "\"E 330\", \"E471\", \"E150d\"). Do NOT translate or expand them.\n"
    "- If the label includes a \"may contain traces\" notice, place it at "
    "the end as one sentence with the trace allergens in ALL CAPS — "
    "Norwegian: \"Kan inneholde spor av X, Y og Z.\"; English: \"May "
    "contain traces of X, Y and Z.\"; Swedish: \"Kan innehålla spår av "
    "X, Y och Z.\"\n"
    "- End the entire output with a single period."
)

# One-shot example showing every formatting rule applied at once. Models
# match the format much more reliably when given a worked example than
# when given rules alone. Norwegian is used because it is the dominant
# label language for this app.
_FEWSHOT_EXAMPLE = (
    "\n\nExample of correctly formatted output (use as a style reference, "
    "do NOT copy these ingredients into your response):\n"
    "Linsemel (37%), maismel, rismel, solsikke-/rapsolje, krydderblanding "
    "(sukker, salt, paprika, MYSEPULVER (fra MELK), gjærekstrakt, "
    "syrer (melkesyre, sitronsyre)), potetstivelse, salt, "
    "surhetsregulerende middel (E270). Kan inneholde spor av HVETE, "
    "RUG, BYGG og HAVRE."
)

_BASE_RULES_NO_TRANSLATION = (
    "- Return the ingredient list text exactly as it appears on the label, in its original language.\n"
    "- Do NOT include the section header. Strip any leading label word such as "
    '"INGREDIENSER", "INGREDIENTS", "ZUTATEN", "INGREDIENTS", "AINESOSAT", '
    '"SKLADNIKI", or any similar word that introduces the ingredient section.\n'
    "- Do NOT prefix the output with phrases like "
    '"The ingredient text is:", "The label reads:", or similar.\n'
    "- Do NOT rephrase, summarize, paraphrase, or add any text that is not "
    "part of the ingredient list itself.\n"
    "- If you cannot read or do not see an ingredient list in the image, output "
    "an empty string. Do NOT explain, apologize, ask for clarification, or write "
    "any prose.\n"
    "- Never output sentences such as \"I'm happy to help\", \"I don't see\", "
    "\"Please provide\", or any other conversational reply. The only allowed "
    "outputs are the ingredient list or an empty string.\n"
    + _FORMATTING_RULES + "\n"
    "- Output nothing except the formatted ingredient list text."
)

_BASE_RULES_WITH_TRANSLATION = (
    "- Translate ALL ingredient names to {lang_name}. "
    "The label may be written in any language -- always output in {lang_name} regardless of the source language.\n"
    "- Do NOT output any text in the original label language. Every ingredient name must be translated.\n"
    "- E-numbers (e.g. E471, E150d) and standard additive codes may be kept as-is if no common {lang_name} name exists.\n"
    "- Do NOT include the section header. Strip any leading label word such as "
    '"INGREDIENSER", "INGREDIENTS", "ZUTATEN", "INGREDIENTS", "AINESOSAT", '
    '"SKLADNIKI", or any similar word that introduces the ingredient section.\n'
    "- Do NOT prefix the output with phrases like "
    '"The ingredient text is:", "The label reads:", or similar.\n'
    "- Do NOT rephrase, summarize, or paraphrase. Translate the ingredient names and output the list only.\n"
    "- If you cannot read or do not see an ingredient list in the image, output "
    "an empty string. Do NOT explain, apologize, ask for clarification, or write "
    "any prose.\n"
    "- Never output sentences such as \"I'm happy to help\", \"I don't see\", "
    "\"Please provide\", or any other conversational reply. The only allowed "
    "outputs are the translated ingredient list or an empty string.\n"
    + _FORMATTING_RULES + "\n"
    "- Output nothing except the formatted, translated ingredient list."
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


def build_ingredient_prompt(language: str | None = None) -> str:
    """Return the ingredient extraction prompt, optionally with a translation instruction."""
    lang_name = _LANGUAGE_NAMES.get(language or "") if language else None
    if lang_name:
        task = (
            f"You are reading a food label image. The label may be written in any language.\n\n"
            f"Your task: Extract the ingredient list and translate every ingredient into {lang_name}. "
            f"Always output in {lang_name}, regardless of what language the original label is written in.\n\n"
            f"Rules:\n"
        )
        rules = _BASE_RULES_WITH_TRANSLATION.replace("{lang_name}", lang_name)
    else:
        task = (
            "You are reading a food label image. Extract ONLY the ingredient list.\n\n"
            "Rules:\n"
        )
        rules = _BASE_RULES_NO_TRANSLATION
    return task + rules + _FEWSHOT_EXAMPLE


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
