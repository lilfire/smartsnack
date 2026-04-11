"""Groq Vision OCR backend."""
from . import _get_api_key, _INGREDIENT_PROMPT

_DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _extract_groq(image_bytes, image_b64, mime_type="image/png", model=None, prompt=None):
    """Use Groq Vision API to extract text from an image.

    The `prompt` kwarg selects the extraction task (ingredients vs. nutrition);
    defaults to _INGREDIENT_PROMPT for backward compatibility.
    """
    api_key = _get_api_key("GROQ_API_KEY")

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model or _DEFAULT_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt or _INGREDIENT_PROMPT,
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""
