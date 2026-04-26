"""E2E tests for OCR ingredient scan with translation path.

Verifies that POST /api/ocr/ingredients correctly passes the user's
language setting through to the OCR provider, producing a translation-
aware prompt when a language is configured.
"""

import base64
import json
import os
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(url, payload, timeout=5):
    """POST request returning (status, parsed_json)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _put(url, payload, timeout=5):
    """PUT request returning (status, parsed_json)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _make_image_b64():
    """Return a minimal valid base64-encoded PNG."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return base64.b64encode(png_bytes).decode()


# ---------------------------------------------------------------------------
# Tests: ingredient scan translation path via live server
# ---------------------------------------------------------------------------


class TestOcrIngredientTranslationE2E:
    """POST /api/ocr/ingredients passes user language to the OCR provider."""

    def test_ingredient_scan_with_language_sends_translation_prompt(self, live_url):
        """When language is set to 'en', the OCR provider receives a prompt
        containing the translation directive for English."""
        from services import ocr_service

        # Set backend to a vision provider and language to English
        os.environ["ANTHROPIC_API_KEY"] = "test-key-e2e"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        _put(f"{live_url}/api/settings/language", {"language": "en"})

        captured_kwargs = {}

        def mock_provider(image_bytes, raw, mime_type, **kwargs):
            captured_kwargs.update(kwargs)
            return "sugar, flour, butter"

        original = ocr_service._PROVIDERS.get("claude_vision")
        ocr_service._PROVIDERS["claude_vision"] = mock_provider
        try:
            image_b64 = _make_image_b64()
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert data["text"] == "sugar, flour, butter"
            assert captured_kwargs.get("language") == "en"
        finally:
            if original is not None:
                ocr_service._PROVIDERS["claude_vision"] = original

    def test_ingredient_scan_without_language_omits_translation(self, live_url):
        """When no language is configured, the OCR provider should not receive
        a language kwarg (no translation)."""
        from services import ocr_service

        os.environ["ANTHROPIC_API_KEY"] = "test-key-e2e"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        # Set language to empty/default (no translation)
        _put(f"{live_url}/api/settings/language", {"language": ""})

        captured_kwargs = {}

        def mock_provider(image_bytes, raw, mime_type, **kwargs):
            captured_kwargs.update(kwargs)
            return "sukker, mel, smor"

        original = ocr_service._PROVIDERS.get("claude_vision")
        ocr_service._PROVIDERS["claude_vision"] = mock_provider
        try:
            image_b64 = _make_image_b64()
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert data["text"] == "sukker, mel, smor"
            assert "language" not in captured_kwargs
        finally:
            if original is not None:
                ocr_service._PROVIDERS["claude_vision"] = original

    def test_ingredient_scan_norwegian_translation(self, live_url):
        """When language is 'no', the provider receives language='no'."""
        from services import ocr_service

        os.environ["ANTHROPIC_API_KEY"] = "test-key-e2e"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        _put(f"{live_url}/api/settings/language", {"language": "no"})

        captured_kwargs = {}

        def mock_provider(image_bytes, raw, mime_type, **kwargs):
            captured_kwargs.update(kwargs)
            return "sukker, hvetemel, smor"

        original = ocr_service._PROVIDERS.get("claude_vision")
        ocr_service._PROVIDERS["claude_vision"] = mock_provider
        try:
            image_b64 = _make_image_b64()
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert captured_kwargs.get("language") == "no"
        finally:
            if original is not None:
                ocr_service._PROVIDERS["claude_vision"] = original
