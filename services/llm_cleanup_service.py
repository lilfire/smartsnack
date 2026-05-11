"""LLM-based ingredient text cleanup service using Anthropic Claude."""

import json
import os

import anthropic

import config

SYSTEM_PROMPT = (
    "You are a food label specialist. Your job is to clean up and normalise a raw\n"
    "ingredient list that was extracted from a food product image. The input may\n"
    "contain OCR artifacts, garbled text, incorrect reading order, or formatting\n"
    "issues.\n"
    "\n"
    "Output rules — follow every one of them:\n"
    "\n"
    "1. Output ONLY the cleaned ingredient list. No preamble, no explanation,\n"
    "   no headers, no extra sentences.\n"
    "2. Format as a single comma-separated line.\n"
    "3. The user message provides a list of allergen terms for the target language.\n"
    "   Every occurrence of those terms — or compound words that contain them\n"
    "   (e.g. HVETEMEL, SOYALESITIN, MJÖLKPULVER) — must be written in ALL CAPS,\n"
    "   including inside sub-ingredient parentheses.\n"
    "4. Use the decimal separator for the target language as specified in the user\n"
    "   message (comma or dot).\n"
    "5. Preserve E-numbers exactly as printed: E270, E150d, E471, E904a.\n"
    "   Never expand, rephrase, or remove them.\n"
    "6. Sub-ingredients go in parentheses immediately after their parent ingredient:\n"
    "   krydderblanding (sukker, salt, paprika, MYSEPULVER (fra MELK))\n"
    "7. Preserve percentages from the label: solsikkeolje (30%).\n"
    "8. The trace-allergen notice belongs at the very end. The exact phrasing is\n"
    "   supplied in the user message. Write it as the final sentence, ending with\n"
    "   a period.\n"
    "9. The list ends with exactly one period.\n"
    "10. Strip any label headers from the input (e.g. \"INGREDIENSER:\", \"Ingredients:\",\n"
    "    \"Innhold:\", \"INNÄLL:\") — they must not appear in the output.\n"
    "11. Strip any nutrition table values that leaked into the OCR text.\n"
    "12. If the input does not resemble an ingredient list at all (empty, or only\n"
    "    unrelated content), return an empty string — nothing else."
)

_REFUSAL_PHRASES = (
    "I cannot",
    "I don't see",
    "please provide",
    "I'm happy to help",
)


def cleanup_ingredients(raw_text: str, lang: str = "no") -> dict:
    """Clean up raw OCR ingredient text using the Anthropic LLM.

    Returns a dict with keys:
      - ``text``: cleaned text (or raw_text on skip/error)
      - ``llm_cleanup_skipped``: True if the LLM call was skipped or failed
    """
    if not raw_text:
        return {"text": "", "llm_cleanup_skipped": True}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"text": raw_text, "llm_cleanup_skipped": True}

    try:
        trans_file = os.path.join(config.TRANSLATIONS_DIR, f"{lang}.json")
        with open(trans_file, "r", encoding="utf-8") as f:
            trans = json.load(f)
    except Exception:
        return {"text": raw_text, "llm_cleanup_skipped": True}

    user_message = (
        f"Target language: {trans.get('lang_label', '')}\n"
        f"Decimal separator: {trans.get('decimal_separator', ',')}\n"
        f"Allergen terms (write these in ALL CAPS): {trans.get('allergen_terms', '')}\n"
        f"Trace-allergen notice template: {trans.get('trace_notice_template', '')}\n"
        "\nClean up the following ingredient text extracted from a food label.\n"
        "Apply all output rules from your instructions and return only the corrected list.\n"
        "\nRaw extracted text:\n"
        f"{raw_text}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=8.0)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        response_text = message.content[0].text

        for phrase in _REFUSAL_PHRASES:
            if phrase in response_text:
                return {"text": raw_text, "llm_cleanup_skipped": True}

        return {"text": response_text, "llm_cleanup_skipped": False}

    except Exception:
        return {"text": raw_text, "llm_cleanup_skipped": True}
