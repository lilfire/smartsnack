"""OpenRouter Vision OCR backend."""
import os

from . import _get_api_key, build_ingredient_prompt

_OPENROUTER_SYSTEM_PROMPT = (
    "You are a precise food label reader. Your only job is to extract the exact "
    "ingredient list from a food label image. Output the raw ingredient text as it "
    "appears on the label — no commentary, no formatting changes, no summaries. "
    "If no ingredient list is visible, output an empty string."
)


_DEFAULT_MODEL = "google/gemini-2.0-flash-001"


def _extract_openrouter(image_bytes, image_b64, mime_type="image/jpeg", model=None, prompt=None, language=None):
    """Use OpenRouter Vision API to extract text from an image.

    The `prompt` kwarg selects the extraction task (ingredients vs. nutrition);
    defaults to the ingredient prompt with optional language translation. A
    task-specific system prompt is used for ingredients; for any custom prompt
    the system message is dropped and the user prompt is relied on for
    instructions.
    """
    api_key = _get_api_key("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)

    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://smartsnack.app"},
    )
    ingredient_prompt = build_ingredient_prompt(language)
    user_prompt = prompt or ingredient_prompt
    messages = []
    if not prompt:
        messages.append({"role": "system", "content": _OPENROUTER_SYSTEM_PROMPT})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}",
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=messages,
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""
