"""Shared utilities for OCR backend modules."""
import os

_INGREDIENT_PROMPT = (
    "Extract the ingredient text from this food label image. "
    "Return only the ingredient text, nothing else."
)


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
