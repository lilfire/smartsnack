"""Claude Vision OCR backend."""
from . import _get_api_key, build_ingredient_prompt

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _extract_claude_vision(image_bytes, image_b64, mime_type="image/png", model=None, language=None):
    """Use Claude Vision API to extract ingredient text from an image."""
    api_key = _get_api_key("ANTHROPIC_API_KEY")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model or _DEFAULT_MODEL,
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
                        "text": build_ingredient_prompt(language),
                    },
                ],
            }
        ],
    )
    return message.content[0].text.strip() if message.content else ""
