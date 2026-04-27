"""LLM translation service for OFF ingredients text."""

import logging
import os

logger = logging.getLogger(__name__)

_LANG_NAMES = {
    "no": "Norwegian",
    "en": "English",
    "se": "Swedish",
}

_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"]


def is_available() -> bool:
    """Return True if at least one LLM backend is configured."""
    return any(os.environ.get(k) for k in _KEYS)


def _build_prompt(text: str, target_lang: str) -> str:
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    return (
        f"Translate the following food product ingredients list into {lang_name}.\n\n"
        "Rules:\n"
        "- Return only the translated ingredients text.\n"
        "- Do not add explanations, comments, or formatting.\n"
        "- Preserve the original structure: commas, semicolons, parentheses, "
        "and percentage values must stay in place.\n"
        f"- If the text is already in {lang_name}, return it exactly as provided.\n"
        "- Do not add or remove any ingredients.\n\n"
        f"Ingredients:\n{text}"
    )


def _try_claude(prompt: str) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip() if msg.content else None


def _try_openai(prompt: str) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    import openai
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = resp.choices[0] if resp.choices else None
    return choice.message.content.strip() if choice and choice.message.content else None


def _try_gemini(prompt: str) -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content(
        prompt,
        generation_config={"max_output_tokens": 2048, "temperature": 0},
    )
    return resp.text.strip() if resp.text else None


def _try_groq(prompt: str) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    import groq
    client = groq.Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = resp.choices[0] if resp.choices else None
    return choice.message.content.strip() if choice and choice.message.content else None


_BACKENDS = [_try_claude, _try_openai, _try_gemini, _try_groq]


def translate_ingredients(text: str, target_lang: str) -> str:
    """Translate ingredients text into target_lang using the first available LLM backend.

    Returns the translated text, or the original text if translation fails or
    no LLM backend is available. Never raises an exception.
    """
    if not text:
        return text
    prompt = _build_prompt(text, target_lang)
    try:
        for backend in _BACKENDS:
            result = backend(prompt)
            if result is not None:
                return result
    except Exception as e:
        logger.warning("LLM translation failed: %s", e)
    return text
