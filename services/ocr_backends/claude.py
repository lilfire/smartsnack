"""Claude Vision OCR backend."""
from . import _get_api_key, _INGREDIENT_PROMPT


def _extract_claude_vision(image_bytes, image_b64, mime_type="image/png"):
    """Use Claude Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("ANTHROPIC_API_KEY")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
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
    return message.content[0].text.strip() if message.content else ""
