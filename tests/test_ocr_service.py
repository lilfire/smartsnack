"""Tests for OCR service — multi-provider OCR backends."""

import base64
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiny_png():
    """Create a minimal valid PNG image and return raw bytes."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _b64(raw_bytes):
    return base64.b64encode(raw_bytes).decode()


def _data_uri(raw_bytes, mime="image/png"):
    return f"data:{mime};base64,{_b64(raw_bytes)}"


def _make_tesseract_data(texts, confs, lefts=None, tops=None, widths=None, heights=None):
    """Build a pytesseract-style output dict."""
    n = len(texts)
    return {
        "left": lefts or [i * 50 for i in range(n)],
        "top": tops or [10] * n,
        "width": widths or [40] * n,
        "height": heights or [20] * n,
        "text": texts,
        "conf": confs,
    }


# ---------------------------------------------------------------------------
# extract_text — input validation (backend-agnostic)
# ---------------------------------------------------------------------------

class TestExtractTextValidation:
    """Input validation should work regardless of backend."""

    def test_none_input_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text(None)

    def test_empty_string_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text("")

    def test_non_string_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="No image provided"):
            extract_text(123)

    def test_invalid_data_uri_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="Invalid data URI"):
            extract_text("data:text/plain;base64,abc")

    def test_invalid_base64_raises(self):
        from services.ocr_service import extract_text

        with pytest.raises(ValueError, match="Invalid base64"):
            extract_text("!!!not-base64!!!")

    def test_image_too_large_raises(self):
        from services.ocr_service import extract_text

        huge = base64.b64encode(b"\x00" * (6 * 1024 * 1024)).decode()
        with pytest.raises(ValueError, match="too large"):
            extract_text(huge)


# ---------------------------------------------------------------------------
# Tesseract backend
# ---------------------------------------------------------------------------

class TestTesseractBackend:
    """Tests for the pytesseract-based OCR backend."""

    def _setup_tesseract_env(self):
        """Ensure ocr_service uses tesseract backend."""
        import importlib
        import services.ocr_service as mod
        # Force tesseract backend
        mod._OCR_BACKEND = "tesseract"
        return mod

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_extract_text_calls_pytesseract(self, mock_output, mock_itd):
        """extract_text should call pytesseract.image_to_data with correct params."""
        mod = self._setup_tesseract_env()

        mock_itd.return_value = _make_tesseract_data(
            texts=["Sukker", "mel"],
            confs=[90, 85],
            lefts=[10, 60],
            tops=[10, 10],
        )

        png_bytes = _make_tiny_png()
        result = mod.extract_text(_b64(png_bytes))

        assert mock_itd.called
        assert "Sukker" in result
        assert "mel" in result

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_extract_text_with_data_uri(self, mock_output, mock_itd):
        """Should handle data URI format input."""
        mod = self._setup_tesseract_env()

        mock_itd.return_value = _make_tesseract_data(
            texts=["ingredienser"],
            confs=[92],
        )

        png_bytes = _make_tiny_png()
        result = mod.extract_text(_data_uri(png_bytes))

        assert result == "ingredienser"

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_filters_low_confidence(self, mock_output, mock_itd):
        """Words with confidence < 30 should be dropped."""
        mod = self._setup_tesseract_env()

        mock_itd.return_value = _make_tesseract_data(
            texts=["good", "noise"],
            confs=[80, 10],
            lefts=[10, 60],
        )

        png_bytes = _make_tiny_png()
        result = mod.extract_text(_b64(png_bytes))

        assert "good" in result
        assert "noise" not in result

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_empty_ocr_returns_empty_string(self, mock_output, mock_itd):
        """When OCR produces no text, return empty string."""
        mod = self._setup_tesseract_env()

        mock_itd.return_value = _make_tesseract_data(texts=[], confs=[])

        png_bytes = _make_tiny_png()
        result = mod.extract_text(_b64(png_bytes))

        assert result == ""

    @patch("pytesseract.image_to_data")
    @patch("pytesseract.Output", new_callable=lambda: type("Output", (), {"DICT": "dict"}))
    def test_multi_variant_picks_best(self, mock_output, mock_itd):
        """Should try multiple image variants and pick highest confidence."""
        mod = self._setup_tesseract_env()

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_tesseract_data(texts=["blurry"], confs=[40])
            else:
                return _make_tesseract_data(texts=["sharp"], confs=[95])

        mock_itd.side_effect = side_effect

        png_bytes = _make_tiny_png()
        result = mod.extract_text(_b64(png_bytes))

        assert "sharp" in result
        assert mock_itd.call_count == 2


# ---------------------------------------------------------------------------
# Claude Vision backend
# ---------------------------------------------------------------------------

class TestClaudeVisionBackend:
    """Tests for the Claude Vision OCR backend."""

    def _setup_env(self):
        import services.ocr_service as mod
        mod._OCR_BACKEND = "claude_vision"
        return mod

    def test_extract_text_calls_claude_vision(self):
        """When OCR_BACKEND=claude_vision, should use Claude Vision."""
        mod = self._setup_env()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sukker, hvetemel, vann, salt")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic", return_value=mock_client):
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                assert mock_client.messages.create.called
                assert result == "sukker, hvetemel, vann, salt"

    def test_claude_vision_with_data_uri(self):
        mod = self._setup_env()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="ingredients list")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic", return_value=mock_client):
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_data_uri(png_bytes))

                assert result == "ingredients list"

    def test_missing_api_key_raises(self):
        """Should raise ValueError when no API key is available."""
        mod = self._setup_env()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                mod.extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self):
        """Should use LLM_API_KEY when ANTHROPIC_API_KEY is not set."""
        mod = self._setup_env()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="ingredients here")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with patch("anthropic.Anthropic", return_value=mock_client) as mock_cls:
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="fallback-key")
                assert result == "ingredients here"

    def test_empty_response(self):
        mod = self._setup_env()

        mock_msg = MagicMock()
        mock_msg.content = []
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic", return_value=mock_client):
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

class TestGeminiBackend:
    """Tests for the Gemini Vision OCR backend."""

    def _setup_env(self):
        import services.ocr_service as mod
        mod._OCR_BACKEND = "gemini"
        return mod

    def _patch_genai(self, mock_client):
        """Create sys.modules patches for google.genai with mock_client."""
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_google = MagicMock()
        mock_google.genai = mock_genai
        return patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}), mock_genai

    def test_extract_text_calls_gemini(self):
        """Should call google.genai.Client with correct API shape."""
        mod = self._setup_env()

        mock_response = MagicMock()
        mock_response.text = "sukker, mel, vann"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        patcher, mock_genai = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}, clear=False):
            with patcher:
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                mock_genai.Client.assert_called_once_with(api_key="test-gemini-key")
                mock_client.models.generate_content.assert_called_once()
                call_kwargs = mock_client.models.generate_content.call_args
                assert call_kwargs[1]["model"] == "gemini-2.0-flash"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self):
        mod = self._setup_env()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                mod.extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self):
        mod = self._setup_env()

        mock_response = MagicMock()
        mock_response.text = "ingredients"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        patcher, mock_genai = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with patcher:
                png_bytes = _make_tiny_png()
                mod.extract_text(_b64(png_bytes))

                mock_genai.Client.assert_called_once_with(api_key="fallback-key")

    def test_empty_response(self):
        mod = self._setup_env()

        mock_response = MagicMock()
        mock_response.text = ""

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        patcher, _ = self._patch_genai(mock_client)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patcher:
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

class TestOpenAIBackend:
    """Tests for the OpenAI Vision OCR backend."""

    def _setup_env(self):
        import services.ocr_service as mod
        mod._OCR_BACKEND = "openai"
        return mod

    def test_extract_text_calls_openai(self):
        """Should call openai.OpenAI with correct API shape."""
        mod = self._setup_env()

        mock_choice = MagicMock()
        mock_choice.message.content = "sukker, mel, vann"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=False):
            with patch("openai.OpenAI", return_value=mock_client) as mock_cls:
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="test-openai-key")
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args
                assert call_kwargs[1]["model"] == "gpt-4o"
                assert result == "sukker, mel, vann"

    def test_missing_api_key_raises(self):
        mod = self._setup_env()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)

            png_bytes = _make_tiny_png()
            with pytest.raises(ValueError, match="API key"):
                mod.extract_text(_b64(png_bytes))

    def test_falls_back_to_llm_api_key(self):
        mod = self._setup_env()

        mock_choice = MagicMock()
        mock_choice.message.content = "ingredients"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"LLM_API_KEY": "fallback-key"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with patch("openai.OpenAI", return_value=mock_client) as mock_cls:
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                mock_cls.assert_called_once_with(api_key="fallback-key")

    def test_empty_response(self):
        mod = self._setup_env()

        mock_choice = MagicMock()
        mock_choice.message.content = ""

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("openai.OpenAI", return_value=mock_client):
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                assert result == ""


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Verify OCR_BACKEND=llm still routes to Claude Vision."""

    def test_llm_routes_to_claude_vision(self):
        """OCR_BACKEND=llm should use the Claude Vision provider (anthropic SDK)."""
        import services.ocr_service as mod
        mod._OCR_BACKEND = "llm"

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sukker, mel")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("anthropic.Anthropic", return_value=mock_client):
                png_bytes = _make_tiny_png()
                result = mod.extract_text(_b64(png_bytes))

                assert mock_client.messages.create.called
                assert result == "sukker, mel"

    def test_llm_alias_in_providers_registry(self):
        """The _PROVIDERS dict should map 'llm' to claude_vision handler."""
        import services.ocr_service as mod

        assert "llm" in mod._PROVIDERS
        assert mod._PROVIDERS["llm"] == mod._PROVIDERS["claude_vision"]


# ---------------------------------------------------------------------------
# Unknown backend
# ---------------------------------------------------------------------------

class TestUnknownBackend:
    """Verify clear error message for invalid OCR_BACKEND values."""

    def test_unknown_backend_raises_value_error(self):
        import services.ocr_service as mod
        mod._OCR_BACKEND = "invalid_provider"

        png_bytes = _make_tiny_png()
        with pytest.raises(ValueError, match="Unknown OCR backend"):
            mod.extract_text(_b64(png_bytes))

    def test_error_message_includes_backend_name(self):
        import services.ocr_service as mod
        mod._OCR_BACKEND = "banana_vision"

        png_bytes = _make_tiny_png()
        with pytest.raises(ValueError, match="banana_vision"):
            mod.extract_text(_b64(png_bytes))


# ---------------------------------------------------------------------------
# OCR_BACKEND config — all provider names
# ---------------------------------------------------------------------------

class TestOCRBackendConfig:
    """Verify OCR_BACKEND env var controls which backend is used."""

    @patch.dict(os.environ, {}, clear=False)
    def test_default_backend_is_tesseract(self):
        """Without OCR_BACKEND set, default to tesseract."""
        os.environ.pop("OCR_BACKEND", None)
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "tesseract"

    @patch.dict(os.environ, {"OCR_BACKEND": "llm"}, clear=False)
    def test_llm_backend_selected(self):
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "llm"

    @patch.dict(os.environ, {"OCR_BACKEND": "tesseract"}, clear=False)
    def test_tesseract_backend_selected(self):
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "tesseract"

    @patch.dict(os.environ, {"OCR_BACKEND": "claude_vision"}, clear=False)
    def test_claude_vision_backend_selected(self):
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "claude_vision"

    @patch.dict(os.environ, {"OCR_BACKEND": "gemini"}, clear=False)
    def test_gemini_backend_selected(self):
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "gemini"

    @patch.dict(os.environ, {"OCR_BACKEND": "openai"}, clear=False)
    def test_openai_backend_selected(self):
        import importlib
        import services.ocr_service as mod
        importlib.reload(mod)

        assert mod._OCR_BACKEND == "openai"

    def test_all_providers_in_registry(self):
        """All valid backend names should be in the _PROVIDERS dict."""
        import services.ocr_service as mod
        expected = {"tesseract", "claude_vision", "gemini", "openai", "llm"}
        assert expected == set(mod._PROVIDERS.keys())


# ---------------------------------------------------------------------------
# _sort_and_join (tesseract format)
# ---------------------------------------------------------------------------

class TestSortAndJoin:
    """Test spatial sorting of tesseract OCR results."""

    def test_empty_items(self):
        from services.ocr_service import _sort_and_join
        assert _sort_and_join([]) == ""

    def test_single_line(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 100, "top": 10, "width": 40, "height": 20, "text": "world"},
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "hello"},
        ]
        result = _sort_and_join(items)
        assert result == "hello world"

    def test_multi_line(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 10, "top": 50, "width": 40, "height": 20, "text": "line2"},
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "line1"},
        ]
        result = _sort_and_join(items)
        assert result == "line1 line2"

    def test_whitespace_only_text_skipped(self):
        from services.ocr_service import _sort_and_join

        items = [
            {"left": 10, "top": 10, "width": 40, "height": 20, "text": "  "},
            {"left": 60, "top": 10, "width": 40, "height": 20, "text": "valid"},
        ]
        result = _sort_and_join(items)
        assert result == "valid"


# ---------------------------------------------------------------------------
# _prepare_images
# ---------------------------------------------------------------------------

class TestPrepareImages:
    """Test image preprocessing pipeline."""

    def test_returns_two_variants(self):
        from services.ocr_service import _prepare_images

        png_bytes = _make_tiny_png()
        variants = _prepare_images(png_bytes)
        assert len(variants) == 2

    def test_upscales_small_images(self):
        from PIL import Image
        from services.ocr_service import _prepare_images

        # Create a small 50x50 image
        img = Image.new("RGB", (50, 50), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        variants = _prepare_images(buf.getvalue())
        # First variant should be a PIL image that's been upscaled
        first = variants[0]
        assert isinstance(first, Image.Image)
        assert max(first.size) >= 1500

    def test_large_image_not_upscaled(self):
        from PIL import Image
        from services.ocr_service import _prepare_images

        img = Image.new("RGB", (2000, 1500), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        variants = _prepare_images(buf.getvalue())
        first = variants[0]
        assert isinstance(first, Image.Image)
        # Should keep original size
        assert first.size == (2000, 1500)


# ---------------------------------------------------------------------------
# _avg_confidence_tesseract
# ---------------------------------------------------------------------------

class TestAvgConfidenceTesseract:
    """Test confidence averaging."""

    def test_empty_data(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [], "text": []}
        assert _avg_confidence_tesseract(data) == 0.0

    def test_filters_low_confidence(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [90, 10, 80], "text": ["a", "b", "c"]}
        # Only 90 and 80 pass (>= 30), avg = 85
        assert _avg_confidence_tesseract(data) == 85.0

    def test_filters_empty_text(self):
        from services.ocr_service import _avg_confidence_tesseract

        data = {"conf": [90, 80], "text": ["word", "  "]}
        # Only first passes (text is non-empty after strip)
        assert _avg_confidence_tesseract(data) == 90.0


# ---------------------------------------------------------------------------
# Blueprint integration (endpoint contract)
# ---------------------------------------------------------------------------

class TestOCRBlueprint:
    """Test the /api/ocr/ingredients endpoint contract is preserved."""

    @patch("services.ocr_service.extract_text")
    def test_post_returns_text(self, mock_extract, client):
        mock_extract.return_value = "sukker, mel"
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "sukker, mel"

    def test_post_no_image_returns_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    @patch("services.ocr_service.extract_text")
    def test_post_empty_result(self, mock_extract, client):
        mock_extract.return_value = ""
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == ""
        assert "error" in data  # "No text found in image"

    @patch("services.ocr_service.extract_text", side_effect=ValueError("bad input"))
    def test_post_value_error_returns_400(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "bad"},
        )
        assert resp.status_code == 400

    @patch("services.ocr_service.extract_text", side_effect=RuntimeError("boom"))
    def test_post_runtime_error_returns_500(self, mock_extract, client):
        resp = client.post(
            "/api/ocr/ingredients",
            json={"image": "dGVzdA=="},
        )
        assert resp.status_code == 500
