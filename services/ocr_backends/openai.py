"""OpenAI Vision OCR backend."""
from . import _get_api_key, _INGREDIENT_PROMPT


def _extract_openai(image_bytes, image_b64, mime_type="image/png"):
    """Use OpenAI Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("OPENAI_API_KEY")

    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
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
                        "text": _INGREDIENT_PROMPT,
                    },
                ],
            }
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return content.strip() if content else ""
