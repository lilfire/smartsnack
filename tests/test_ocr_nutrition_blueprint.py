"""Tests for POST /api/ocr/nutrition endpoint and dispatch_nutrition_ocr_bytes."""
import io
import json
import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def client(app):
    """Flask test client with CSRF header for OCR tests."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


def _nutrition_result(values=None, provider="Claude Vision", fallback=False, text="{}"):
    if values is None:
        values = {"kcal": 250.0, "fat": 12.5, "protein": 8.0}
    return {
        "values": values,
        "text": text,
        "provider": provider,
        "fallback": fallback,
    }


_VALID_PNG_DATA_URI = "data:image/png;base64,iVBORw0KGgo="


class TestNutritionSuccessResponse:
    """Happy path: endpoint returns a cleaned values dict with metadata."""

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(),
        autospec=True)
    def test_json_path_success(self, mock_dispatch, client):
        resp = client.post(
            "/api/ocr/nutrition",
            json={"image": _VALID_PNG_DATA_URI},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["values"] == {"kcal": 250.0, "fat": 12.5, "protein": 8.0}
        assert data["count"] == 3
        assert data["provider"] == "Claude Vision"
        assert data["fallback"] is False

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(),
        autospec=True)
    def test_multipart_path_success(self, mock_dispatch, client):
        data = io.BytesIO(b"\x89PNG\r\n\x1a\nfake-png-bytes")
        resp = client.post(
            "/api/ocr/nutrition",
            data={"image": (data, "label.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["values"] == {"kcal": 250.0, "fat": 12.5, "protein": 8.0}
        assert payload["count"] == 3

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(fallback=True, provider="Tesseract (Local)"),
        autospec=True)
    def test_fallback_true_propagated(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        data = resp.get_json()
        assert data["fallback"] is True
        assert data["provider"] == "Tesseract (Local)"

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(
            values={
                "kcal": 250.0,
                "energy_kj": 1050.0,
                "fat": 12.0,
                "saturated_fat": 4.0,
                "carbs": 30.0,
                "sugar": 5.0,
                "fiber": 3.0,
                "protein": 8.0,
                "salt": 0.8,
            }
        ),
     autospec=True)
    def test_full_nutrition_dict(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        data = resp.get_json()
        assert data["count"] == 9
        assert set(data["values"].keys()) == {
            "kcal", "energy_kj", "fat", "saturated_fat",
            "carbs", "sugar", "fiber", "protein", "salt",
        }


class TestNutritionNoValuesResponse:
    """Empty values dict returns 200 with error_type=no_values."""

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(values={}, provider="Gemini Vision"),
        autospec=True)
    def test_no_values_is_200(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        assert resp.status_code == 200

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value=_nutrition_result(values={}, provider="Gemini Vision"),
        autospec=True)
    def test_no_values_error_type(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        data = resp.get_json()
        assert data["error_type"] == "no_values"
        assert data["values"] == {}
        assert data["count"] == 0
        assert data["provider"] == "Gemini Vision"


class TestNutritionErrorMapping:
    """Provider exceptions must map to the shared OCR error taxonomy."""

    def test_missing_image_field(self, client):
        resp = client.post("/api/ocr/nutrition", json={"image": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "No image provided"
        assert data["error_type"] == "generic"

    def test_missing_json_body(self, client):
        resp = client.post("/api/ocr/nutrition", json={})
        assert resp.status_code == 400

    def test_invalid_data_uri(self, client):
        resp = client.post("/api/ocr/nutrition", json={"image": "data:garbage"})
        assert resp.status_code == 400

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        side_effect=ValueError("Token limit exceeded"),
        autospec=True)
    def test_token_limit_exceeded(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_type"] == "token_limit_exceeded"

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        side_effect=TimeoutError("provider timeout"),
        autospec=True)
    def test_provider_timeout(self, mock_dispatch, client):
        resp = client.post("/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI})
        assert resp.status_code == 503
        assert resp.get_json()["error_type"] == "provider_timeout"

    def test_provider_quota_by_status_code(self, client):
        class QuotaError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_nutrition_ocr_bytes",
            side_effect=QuotaError("too many requests", 429),
            autospec=True):
            resp = client.post(
                "/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI}
            )
            assert resp.status_code == 429
            assert resp.get_json()["error_type"] == "provider_quota"

    def test_provider_quota_by_message(self, client):
        with patch(
            "services.ocr_service.dispatch_nutrition_ocr_bytes",
            side_effect=Exception("quota exceeded for this month"),
            autospec=True):
            resp = client.post(
                "/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI}
            )
            assert resp.status_code == 429
            assert resp.get_json()["error_type"] == "provider_quota"

    def test_invalid_image_error(self, client):
        from PIL import UnidentifiedImageError

        with patch(
            "services.ocr_service.dispatch_nutrition_ocr_bytes",
            side_effect=UnidentifiedImageError("cannot identify image"),
            autospec=True):
            resp = client.post(
                "/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI}
            )
            assert resp.status_code == 400
            assert resp.get_json()["error_type"] == "invalid_image"

    def test_generic_error_fallback(self, client):
        with patch(
            "services.ocr_service.dispatch_nutrition_ocr_bytes",
            side_effect=Exception("something broke"),
            autospec=True):
            resp = client.post(
                "/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI}
            )
            assert resp.status_code == 500
            assert resp.get_json()["error_type"] == "generic"

    def test_provider_error_4xx(self, client):
        class ProviderError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        with patch(
            "services.ocr_service.dispatch_nutrition_ocr_bytes",
            side_effect=ProviderError("image too large", 413),
            autospec=True):
            resp = client.post(
                "/api/ocr/nutrition", json={"image": _VALID_PNG_DATA_URI}
            )
            assert resp.status_code == 413
            data = resp.get_json()
            assert data["error_type"] == "provider_error"
            assert "image too large" in data["error"]


class TestDispatchNutritionOcrBytes:
    """Unit tests for dispatch_nutrition_ocr_bytes wiring (prompt + parser)."""

    def test_dispatch_forwards_nutrition_prompt(self):
        from services.ocr_backends import _NUTRITION_PROMPT
        from services import ocr_core

        def fake_dispatch(image_bytes, prompt=None):
            assert prompt is _NUTRITION_PROMPT
            return {
                "text": '{"kcal": 250, "fat": 12.5}',
                "provider": "Claude Vision",
                "fallback": False,
            }

        with patch.object(ocr_core, "dispatch_ocr_bytes", side_effect=fake_dispatch, autospec=True):
            result = ocr_core.dispatch_nutrition_ocr_bytes(b"fake-image-bytes")

        assert result["values"] == {"kcal": 250.0, "fat": 12.5}
        assert result["provider"] == "Claude Vision"
        assert result["fallback"] is False

    def test_dispatch_passes_text_through_parser(self):
        from services import ocr_core

        # Norwegian label text (tesseract-style output) should still parse
        with patch.object(
            ocr_core,
            "dispatch_ocr_bytes",
            return_value={
                "text": "Energi 1050 kJ / 250 kcal\nFett 12 g\nProtein 8 g\nSalt 0,8 g",
                "provider": "Tesseract (Local)",
                "fallback": True,
            },
         autospec=True):
            result = ocr_core.dispatch_nutrition_ocr_bytes(b"fake")
        assert result["values"]["kcal"] == 250.0
        assert result["values"]["energy_kj"] == 1050.0
        assert result["values"]["fat"] == 12.0
        assert result["values"]["protein"] == 8.0
        assert result["values"]["salt"] == 0.8
        assert result["fallback"] is True

    def test_dispatch_empty_text_returns_empty_values(self):
        from services import ocr_core

        with patch.object(
            ocr_core,
            "dispatch_ocr_bytes",
            return_value={"text": "", "provider": "Tesseract (Local)", "fallback": False},
            autospec=True):
            result = ocr_core.dispatch_nutrition_ocr_bytes(b"fake")
        assert result["values"] == {}
        assert result["text"] == ""


class TestPromptThreadedThroughBackends:
    """Each vision backend must forward a prompt kwarg to its vendor SDK."""

    def test_claude_forwards_prompt(self):
        from services.ocr_backends import claude as claude_backend

        fake_message = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="result text")]
        )
        fake_anthropic = MagicMock(spec=["Anthropic"])
        fake_anthropic.Anthropic.return_value.messages.create.return_value = fake_message

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
            with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
                claude_backend._extract_claude_vision(
                    b"bytes", "b64", "image/png", prompt="CUSTOM PROMPT"
                )

        call = fake_anthropic.Anthropic.return_value.messages.create.call_args
        messages = call.kwargs["messages"]
        text_block = messages[0]["content"][1]
        assert text_block["text"] == "CUSTOM PROMPT"

    def test_gemini_forwards_prompt(self):
        from services.ocr_backends import gemini as gemini_backend

        fake_response = types.SimpleNamespace(text="result")
        fake_client = MagicMock(spec=["models"])
        fake_client.models.generate_content.return_value = fake_response
        fake_genai_module = MagicMock(spec=["Client"])
        fake_genai_module.Client.return_value = fake_client
        fake_google = types.SimpleNamespace(genai=fake_genai_module)

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
            with patch.dict(
                "sys.modules",
                {"google": fake_google, "google.genai": fake_genai_module},
            ):
                with patch.object(
                    gemini_backend,
                    "_convert_for_gemini",
                    return_value=(b"bytes", "image/png"),
                    autospec=True):
                    gemini_backend._extract_gemini(
                        b"bytes", "b64", "image/png", prompt="CUSTOM PROMPT"
                    )

        call = fake_client.models.generate_content.call_args
        contents = call.kwargs["contents"]
        text_part = contents[0]["parts"][1]
        assert text_part["text"] == "CUSTOM PROMPT"

    def test_openai_forwards_prompt(self):
        from services.ocr_backends import openai as openai_backend

        fake_choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="result")
        )
        fake_response = types.SimpleNamespace(choices=[fake_choice])
        fake_openai = MagicMock(spec=["OpenAI"])
        fake_openai.OpenAI.return_value.chat.completions.create.return_value = fake_response

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            with patch.dict("sys.modules", {"openai": fake_openai}):
                openai_backend._extract_openai(
                    b"bytes", "b64", "image/png", prompt="CUSTOM PROMPT"
                )

        call = fake_openai.OpenAI.return_value.chat.completions.create.call_args
        messages = call.kwargs["messages"]
        text_block = messages[0]["content"][1]
        assert text_block["text"] == "CUSTOM PROMPT"

    def test_groq_forwards_prompt(self):
        from services.ocr_backends import groq as groq_backend

        fake_choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="result")
        )
        fake_response = types.SimpleNamespace(choices=[fake_choice])
        fake_groq_module = MagicMock(spec=["Groq"])
        fake_groq_module.Groq.return_value.chat.completions.create.return_value = fake_response

        with patch.dict("os.environ", {"GROQ_API_KEY": "test"}):
            with patch.dict("sys.modules", {"groq": fake_groq_module}):
                groq_backend._extract_groq(
                    b"bytes", "b64", "image/png", prompt="CUSTOM PROMPT"
                )

        call = fake_groq_module.Groq.return_value.chat.completions.create.call_args
        messages = call.kwargs["messages"]
        text_block = messages[0]["content"][1]
        assert text_block["text"] == "CUSTOM PROMPT"

    def test_openrouter_forwards_prompt_and_drops_system(self):
        from services.ocr_backends import openrouter as openrouter_backend

        fake_choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="result")
        )
        fake_response = types.SimpleNamespace(choices=[fake_choice])
        fake_openai_module = MagicMock(spec=["OpenAI"])
        fake_openai_module.OpenAI.return_value.chat.completions.create.return_value = fake_response

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}):
            with patch.dict("sys.modules", {"openai": fake_openai_module}):
                openrouter_backend._extract_openrouter(
                    b"bytes", "b64", "image/png", prompt="CUSTOM PROMPT"
                )

        call = fake_openai_module.OpenAI.return_value.chat.completions.create.call_args
        messages = call.kwargs["messages"]
        # With custom prompt, system message must be dropped so the
        # ingredient-specific instructions don't leak into nutrition OCR.
        assert all(m["role"] != "system" for m in messages)
        # User prompt must be the custom one.
        user_msg = messages[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"][1]["text"] == "CUSTOM PROMPT"

    def test_openrouter_keeps_system_for_default_prompt(self):
        from services.ocr_backends import openrouter as openrouter_backend

        fake_choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="result")
        )
        fake_response = types.SimpleNamespace(choices=[fake_choice])
        fake_openai_module = MagicMock(spec=["OpenAI"])
        fake_openai_module.OpenAI.return_value.chat.completions.create.return_value = fake_response

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}):
            with patch.dict("sys.modules", {"openai": fake_openai_module}):
                openrouter_backend._extract_openrouter(
                    b"bytes", "b64", "image/png"  # no prompt kwarg → default
                )

        call = fake_openai_module.OpenAI.return_value.chat.completions.create.call_args
        messages = call.kwargs["messages"]
        # Default path keeps the ingredient system prompt.
        assert messages[0]["role"] == "system"
