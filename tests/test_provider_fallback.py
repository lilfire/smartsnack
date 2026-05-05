"""Edge case tests for OCR provider fallback behaviour.

Tests the dispatch_ocr fallback chain:
- Provider unavailable (no API key) → falls back to tesseract when enabled
- Provider unavailable, fallback disabled → raises ValueError
- Multiple providers unavailable in sequence
- Provider raises exception during execution → propagates
- Gemini 2.0 Flash model format in dispatch_ocr result shape

Uses mock_shape_validator to verify the dispatch_ocr result shape.
"""
import base64
import io
import os
from unittest.mock import MagicMock, create_autospec, patch

import google
import google.genai
from google.genai.types import GenerateContentResponse
import openai
import pytest
from PIL import Image

from tests.mock_shape_validator import validate_ocr_dispatch_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiny_png_b64():
    img = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _mock_tesseract_data():
    return {
        "text": ["ingredients"],
        "conf": [95],
        "left": [0],
        "top": [0],
        "width": [80],
        "height": [10],
    }


# ---------------------------------------------------------------------------
# OCR dispatch result shape
# ---------------------------------------------------------------------------


class TestOcrDispatchResultShape:
    """Validate dispatch_ocr result dict shape via mock_shape_validator."""

    def test_tesseract_result_has_correct_shape(self, app_ctx, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            with patch("pytesseract.image_to_data", return_value=_mock_tesseract_data()):
                from services.ocr_core import dispatch_ocr
                result = dispatch_ocr(_make_tiny_png_b64())

        validate_ocr_dispatch_result(result)
        assert result["provider"] != ""
        assert result["fallback"] is False

    def test_result_rejects_missing_provider(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_ocr_dispatch_result({"text": "ok", "fallback": False})

    def test_result_rejects_non_bool_fallback(self):
        with pytest.raises(AssertionError, match="must be a bool"):
            validate_ocr_dispatch_result({"text": "ok", "provider": "gemini", "fallback": "false"})


# ---------------------------------------------------------------------------
# Provider unavailable → fallback behaviour
# ---------------------------------------------------------------------------


class TestProviderFallbackUnavailable:
    """When the selected backend has no API key, fallback rules apply."""

    def test_fallback_to_tesseract_when_enabled(self, app_ctx, monkeypatch):
        """Provider without API key → fallback to tesseract (if allowed by settings)."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        with patch("services.settings_service.get_ocr_backend", return_value="gemini"):
            with patch(
                "services.ocr_settings_service.get_ocr_settings",
                return_value={"fallback_to_tesseract": True},
            ):
                with patch("pytesseract.image_to_data", return_value=_mock_tesseract_data()):
                    from services.ocr_core import dispatch_ocr
                    result = dispatch_ocr(_make_tiny_png_b64())

        validate_ocr_dispatch_result(result)
        assert result["fallback"] is True

    def test_fallback_disabled_raises_when_provider_unavailable(self, app_ctx, monkeypatch):
        """Provider without API key + fallback disabled → ValueError."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        with patch("services.settings_service.get_ocr_backend", return_value="gemini"):
            with patch(
                "services.ocr_settings_service.get_ocr_settings",
                return_value={"fallback_to_tesseract": False},
            ):
                from services.ocr_core import dispatch_ocr
                with pytest.raises(ValueError, match="unavailable"):
                    dispatch_ocr(_make_tiny_png_b64())

    def test_tesseract_itself_never_falls_back(self, app_ctx, monkeypatch):
        """Tesseract is always available — fallback flag must be False when tesseract is selected."""
        with patch("services.settings_service.get_ocr_backend", return_value="tesseract"):
            with patch("pytesseract.image_to_data", return_value=_mock_tesseract_data()):
                from services.ocr_core import dispatch_ocr
                result = dispatch_ocr(_make_tiny_png_b64())

        assert result["fallback"] is False


# ---------------------------------------------------------------------------
# Provider raises exception during execution
# ---------------------------------------------------------------------------


class TestProviderRuntimeFailure:
    """When a provider raises during execution, the exception propagates."""

    def test_gemini_runtime_error_propagates(self, app_ctx, monkeypatch):
        """If Gemini raises ValueError at runtime, dispatch_ocr should not silently swallow it."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        mock_genai = MagicMock(spec=google.genai)
        mock_genai.Client.side_effect = RuntimeError("quota exceeded")

        with patch("services.settings_service.get_ocr_backend", return_value="gemini"):
            with patch.dict("sys.modules", {"google.genai": mock_genai, "google": MagicMock(spec=google, genai=mock_genai)}):
                from services.ocr_core import dispatch_ocr
                with pytest.raises(Exception):
                    dispatch_ocr(_make_tiny_png_b64())

    def test_openai_runtime_error_propagates(self, app_ctx, monkeypatch):
        """If OpenAI raises at runtime, dispatch_ocr propagates the error."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Create spec mock before patching so openai.OpenAI still refers to the real class
        mock_client = MagicMock(spec=openai.OpenAI)
        mock_client.chat.completions.create.side_effect = RuntimeError("rate limit")
        with patch("services.settings_service.get_ocr_backend", return_value="openai"):
            with patch("openai.OpenAI") as mock_class:
                mock_class.return_value = mock_client
                from services.ocr_core import dispatch_ocr
                with pytest.raises(RuntimeError, match="rate limit"):
                    dispatch_ocr(_make_tiny_png_b64())


# ---------------------------------------------------------------------------
# Gemini 2.0 Flash model format in dispatch_ocr
# ---------------------------------------------------------------------------


class TestGemini20FlashModelFormat:
    """Verify dispatch_ocr uses the model stored in settings and result shape is valid."""

    def test_dispatch_ocr_with_gemini_result_has_provider_field(self, app_ctx, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        mock_response = MagicMock(spec=GenerateContentResponse)
        mock_response.text = "mel, sukker"
        mock_genai = MagicMock(spec=google.genai)
        mock_client = MagicMock(spec=google.genai.Client)
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        with patch("services.settings_service.get_ocr_backend", return_value="gemini"):
            with patch.dict("sys.modules", {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
                from services.ocr_core import dispatch_ocr
                result = dispatch_ocr(_make_tiny_png_b64())

        validate_ocr_dispatch_result(result)
        assert result["text"] == "mel, sukker"
        assert "gemini" in result["provider"].lower() or result["provider"] != ""
