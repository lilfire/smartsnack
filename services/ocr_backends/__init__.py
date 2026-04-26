"""Shared utilities for OCR backend modules."""
import os

_LANGUAGE_NAMES = {
    "no": "Norwegian (Bokmål)",
    "en": "English",
    "se": "Swedish",
}

_BASE_RULES = (
    "- Return the ingredient list text as it appears on the label"
    " (translated if a target language is given).\n"
    "- Do NOT include the section header. Strip any leading label word such as "
    '"INGREDIENSER", "INGREDIENTS", "ZUTATEN", "INGRÉDIENTS", "AINESOSAT", '
    '"SKŁADNIKI", or any similar word that introduces the ingredient section.\n'
    "- Do NOT prefix the output with phrases like "
    '"The ingredient text is:", "The label reads:", or similar.\n'
    "- Do NOT rephrase, summarize, paraphrase, or add any text that is not "
    "part of the ingredient list itself.\n"
    "- If no ingredient list is visible in the image, return an empty string.\n"
    "- Output nothing except the ingredient list text."
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
            f"You are reading a food label image. Extract the ingredient list "
            f"and translate it to {lang_name}.\n\n"
            f"Rules:\n"
        )
    else:
        task = (
            "You are reading a food label image. Extract ONLY the ingredient list.\n\n"
            "Rules:\n"
        )
    return task + _BASE_RULES


# Backward-compatible alias
_INGREDIENT_PROMPT = build_ingredient_prompt()


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
