"""OpenAI Vision OCR backend."""
from . import _get_api_key, build_ingredient_prompt

_DEFAULT_MODEL = "gpt-4o"


def _extract_openai(image_bytes, image_b64, mime_type="image/png", model=None, language=None):
    """Use OpenAI Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("OPENAI_API_KEY")

    import openai

    client = openai.OpenAI(api_key=api_key)
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
                        "text": build_ingredient_prompt(language),
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""
