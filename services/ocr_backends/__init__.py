"""Vision-based OCR backends for ingredient extraction.

Exports:
  _HARDENED_SYSTEM_PROMPT  — language-agnostic 4-step system prompt
  build_ingredient_prompt  — user message containing only the language code
  _INGREDIENT_PROMPT       — backward-compat alias (default language)
  dispatch_ocr             — route to the correct backend
"""
import os

from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

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
    "3.  Every regulated allergen term in the target language — and compound words\n"
    "    that contain them — must be written in ALL CAPS, including inside\n"
    "    sub-ingredient parentheses. Apply your language knowledge to identify the\n"
    "    full set of allergen terms for the target language.\n"
    "4.  Use the decimal separator that is standard in the target language.\n"
    "5.  Preserve E-numbers exactly as printed: E270, E150d, E471, E904a.\n"
    "6.  Sub-ingredients go in parentheses immediately after their parent ingredient.\n"
    "7.  Preserve percentages from the label.\n"
    "8.  Append a trace-allergen notice at the very end, phrased naturally in the\n"
    "    target language, as the final sentence.\n"
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


def build_ingredient_prompt(language: "str | None" = None) -> str:
    """Return the user message for ingredient extraction.

    Passes only the language code so the LLM resolves allergen vocabulary,
    decimal separator, and trace-notice phrasing from its own language knowledge.
    The system prompt (_HARDENED_SYSTEM_PROMPT) carries all normalisation rules.

    Falls back to the default language for None, empty string, or unknown codes.
    """
    lang = (language or "").strip() or DEFAULT_LANGUAGE
    return (
        f"Language: {lang}\n"
        "Return the ingredient list for the language stated above — extracted if that language "
        "is present, or translated from another language if not. "
        "Return an empty string only if no readable ingredient list exists anywhere on the label. "
        "Do not output reasoning, explanations, or step labels."
    )


# Backward-compat alias — code that references _INGREDIENT_PROMPT still works.
_INGREDIENT_PROMPT = build_ingredient_prompt()


def dispatch_ocr(
    image_base64: str,
    backend: str = "tesseract",
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Route ingredient OCR to the specified backend.

    Args:
        image_base64: Raw base64 string or data URI (data:image/...;base64,...).
        backend: One of "tesseract", "claude", "openai", "gemini", "groq",
                 "openrouter". Defaults to "tesseract".
        language: Language code for the target output. Must be one of the
                  supported languages (derived from the translations directory).
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

    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}")

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
