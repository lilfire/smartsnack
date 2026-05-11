"""Tests for OCR model option feature (LSO-460).

Covers:
- config.py: OCR_BACKENDS includes models list per provider
- services/ocr_settings_service.py: saving/loading model per provider
- blueprints/ocr_settings.py: API validation of model values
- services/ocr_backends: each backend accepts optional model param
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Config tests: OCR_BACKENDS now has a "models" list per provider
# ---------------------------------------------------------------------------

class TestOcrBackendsModelsConfig:
    """Verify that OCR_BACKENDS entries contain a 'models' list."""

    def test_every_backend_has_models_key(self):
        from config import OCR_BACKENDS
        for key, info in OCR_BACKENDS.items():
            assert "models" in info, f"{key} missing 'models' key"
            assert isinstance(info["models"], list), f"{key} 'models' should be a list"

    def test_tesseract_has_empty_models(self):
        from config import OCR_BACKENDS
        assert OCR_BACKENDS["tesseract"]["models"] == []

    def test_claude_vision_has_models(self):
        from config import OCR_BACKENDS
        models = OCR_BACKENDS["claude_vision"]["models"]
        assert len(models) >= 1
        assert all(isinstance(m, str) for m in models)

    def test_gemini_has_models(self):
        from config import OCR_BACKENDS
        models = OCR_BACKENDS["gemini"]["models"]
        assert len(models) >= 1

    def test_openai_has_models(self):
        from config import OCR_BACKENDS
        models = OCR_BACKENDS["openai"]["models"]
        assert len(models) >= 1

    def test_groq_has_models(self):
        from config import OCR_BACKENDS
        models = OCR_BACKENDS["groq"]["models"]
        assert len(models) >= 1

    def test_openrouter_has_empty_models(self):
        """OpenRouter uses free-text model input, so models list is empty."""
        from config import OCR_BACKENDS
        assert OCR_BACKENDS["openrouter"]["models"] == []

    def test_first_model_is_default(self):
        """For providers with a fixed list, the first entry should be the default."""
        from config import OCR_BACKENDS
        for key, info in OCR_BACKENDS.items():
            if info["models"]:
                assert isinstance(info["models"][0], str), (
                    f"{key} first model should be a string"
                )


# ---------------------------------------------------------------------------
# Service tests: saving and loading model per provider
# ---------------------------------------------------------------------------

@pytest.fixture()
def ocr_service(app_ctx):
    from services import ocr_settings_service
    return ocr_settings_service


class TestModelSettingsPersistence:
    """Tests for model save/load in ocr_settings_service."""

    def test_get_settings_returns_models_dict(self, ocr_service):
        settings = ocr_service.get_ocr_settings()
        assert "models" in settings
        assert isinstance(settings["models"], dict)

    def test_get_settings_default_models_from_config(self, ocr_service):
        """When no models are saved, defaults should come from config."""
        from config import OCR_BACKENDS
        settings = ocr_service.get_ocr_settings()
        models = settings["models"]
        for provider_key, info in OCR_BACKENDS.items():
            if info["models"]:
                assert provider_key in models
                assert models[provider_key] == info["models"][0]

    def test_save_and_load_model_for_provider(self, ocr_service):
        from config import OCR_BACKENDS
        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        assert len(claude_models) >= 2, "Need at least 2 claude models for this test"

        non_default_model = claude_models[1]
        ocr_service.save_ocr_settings(
            "claude_vision", False, models={"claude_vision": non_default_model}
        )
        settings = ocr_service.get_ocr_settings()
        assert settings["models"]["claude_vision"] == non_default_model

    def test_save_model_does_not_overwrite_other_providers(self, ocr_service):
        """Saving a model for one provider should not affect others."""
        from config import OCR_BACKENDS
        gemini_models = OCR_BACKENDS["gemini"]["models"]
        if len(gemini_models) >= 2:
            ocr_service.save_ocr_settings(
                "gemini", False, models={"gemini": gemini_models[1]}
            )

        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        if len(claude_models) >= 2:
            ocr_service.save_ocr_settings(
                "claude_vision", False, models={"claude_vision": claude_models[1]}
            )

        settings = ocr_service.get_ocr_settings()
        # Gemini model should still be what we set
        if len(gemini_models) >= 2:
            assert settings["models"]["gemini"] == gemini_models[1]

    def test_save_without_models_preserves_existing(self, ocr_service):
        """Omitting models from save should not clear stored models."""
        from config import OCR_BACKENDS
        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        if len(claude_models) >= 2:
            ocr_service.save_ocr_settings(
                "claude_vision", False, models={"claude_vision": claude_models[1]}
            )
            # Save again without models
            ocr_service.save_ocr_settings("claude_vision", False)
            settings = ocr_service.get_ocr_settings()
            assert settings["models"]["claude_vision"] == claude_models[1]

    def test_stale_model_falls_back_to_first(self, ocr_service):
        """If stored model is no longer in config list, fall back to first."""
        from db import get_db
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
            ("ocr_model_claude_vision", "claude-nonexistent-model-999"),
        )
        conn.commit()

        from config import OCR_BACKENDS
        settings = ocr_service.get_ocr_settings()
        expected = OCR_BACKENDS["claude_vision"]["models"][0]
        assert settings["models"]["claude_vision"] == expected

    def test_openrouter_model_persists_any_string(self, ocr_service):
        """OpenRouter accepts free-text model strings."""
        ocr_service.save_ocr_settings(
            "openrouter", False, models={"openrouter": "anthropic/claude-3-opus"}
        )
        settings = ocr_service.get_ocr_settings()
        assert settings["models"]["openrouter"] == "anthropic/claude-3-opus"


# ---------------------------------------------------------------------------
# Blueprint tests: API validation for model values
# ---------------------------------------------------------------------------

class TestProvidersEndpointModels:
    """Tests for GET /api/ocr/providers returning models."""

    def test_providers_include_models_list(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        resp = client.get("/api/ocr/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        for provider in data["providers"]:
            assert "models" in provider, f"Provider {provider['key']} missing 'models'"
            assert isinstance(provider["models"], list)

    def test_tesseract_provider_has_empty_models(self, client):
        resp = client.get("/api/ocr/providers")
        data = resp.get_json()
        tesseract = next(p for p in data["providers"] if p["key"] == "tesseract")
        assert tesseract["models"] == []

    def test_claude_vision_provider_has_models(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        resp = client.get("/api/ocr/providers")
        data = resp.get_json()
        claude = next(
            (p for p in data["providers"] if p["key"] == "claude_vision"), None
        )
        assert claude is not None
        assert len(claude["models"]) >= 1

    def test_openrouter_provider_has_free_text_flag(self, client, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
        resp = client.get("/api/ocr/providers")
        data = resp.get_json()
        openrouter = next(
            (p for p in data["providers"] if p["key"] == "openrouter"), None
        )
        assert openrouter is not None
        assert openrouter["models"] == []


class TestSettingsEndpointModels:
    """Tests for GET/POST /api/ocr/settings with models."""

    def test_get_settings_returns_models(self, client):
        resp = client.get("/api/ocr/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "models" in data
        assert isinstance(data["models"], dict)

    def test_post_settings_with_valid_model(self, client):
        from config import OCR_BACKENDS
        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
                "models": {"claude_vision": claude_models[0]},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_post_settings_with_invalid_model_returns_400(self, client):
        """Submitting an invalid model for a fixed-list provider returns 400."""
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
                "models": {"claude_vision": "nonexistent-model-xyz"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_post_settings_openrouter_empty_model_returns_400(self, client):
        """OpenRouter with an empty string model should be rejected."""
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": ""},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_post_settings_openrouter_valid_model(self, client):
        """OpenRouter with a non-empty string model should succeed."""
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": "google/gemini-2.0-flash-001"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_post_settings_invalid_provider_key_in_models_returns_400(self, client):
        """Models dict with an unknown provider key should be rejected."""
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "tesseract",
                "fallback_to_tesseract": False,
                "models": {"unknown_provider": "some-model"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_post_settings_without_models_preserves_existing(self, client):
        """Omitting models from POST should not clear stored models."""
        from config import OCR_BACKENDS
        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        # First save with model
        client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
                "models": {"claude_vision": claude_models[0]},
            }),
            content_type="application/json",
        )
        # Save again without models
        client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
            }),
            content_type="application/json",
        )
        # Verify model persisted
        resp = client.get("/api/ocr/settings")
        data = resp.get_json()
        assert data["models"]["claude_vision"] == claude_models[0]

    def test_roundtrip_save_and_load_model(self, client):
        """Save model via POST, verify it appears in GET."""
        from config import OCR_BACKENDS
        gemini_models = OCR_BACKENDS["gemini"]["models"]
        if len(gemini_models) >= 2:
            model = gemini_models[1]
        else:
            model = gemini_models[0]

        client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "gemini",
                "fallback_to_tesseract": False,
                "models": {"gemini": model},
            }),
            content_type="application/json",
        )
        resp = client.get("/api/ocr/settings")
        data = resp.get_json()
        assert data["models"]["gemini"] == model


# ---------------------------------------------------------------------------
# Backend function tests: each backend accepts optional model param
# ---------------------------------------------------------------------------

class TestBackendModelParam:
    """Verify that each OCR backend function accepts an optional model kwarg."""

    def test_claude_backend_accepts_model(self):
        import inspect
        from services.ocr_backends.claude import _extract_claude_vision
        sig = inspect.signature(_extract_claude_vision)
        assert "model" in sig.parameters, (
            "_extract_claude_vision should accept a 'model' parameter"
        )
        param = sig.parameters["model"]
        assert param.default is not inspect.Parameter.empty, (
            "'model' should have a default value (optional)"
        )

    def test_gemini_backend_accepts_model(self):
        import inspect
        from services.ocr_backends.gemini import _extract_gemini
        sig = inspect.signature(_extract_gemini)
        assert "model" in sig.parameters

    def test_openai_backend_accepts_model(self):
        import inspect
        from services.ocr_backends.openai import _extract_openai
        sig = inspect.signature(_extract_openai)
        assert "model" in sig.parameters

    def test_groq_backend_accepts_model(self):
        import inspect
        from services.ocr_backends.groq import _extract_groq
        sig = inspect.signature(_extract_groq)
        assert "model" in sig.parameters

    def test_openrouter_backend_accepts_model(self):
        import inspect
        from services.ocr_backends.openrouter import _extract_openrouter
        sig = inspect.signature(_extract_openrouter)
        assert "model" in sig.parameters

    def test_tesseract_does_not_require_model(self):
        """Tesseract has no model concept; should still work without model param."""
        import inspect
        from services.ocr_backends.tesseract import _extract_tesseract
        sig = inspect.signature(_extract_tesseract)
        # Tesseract may or may not accept model, but must not require it
        for name, param in sig.parameters.items():
            if name == "model":
                assert param.default is not inspect.Parameter.empty


# ---------------------------------------------------------------------------
# Dispatch tests: model is passed through to backend
# ---------------------------------------------------------------------------

class TestDispatchPassesModel:
    """Verify that dispatch_ocr passes the stored model to the backend."""

    @staticmethod
    def _make_test_image_b64():
        import base64
        import io
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def test_dispatch_passes_model_to_backend(self, app_ctx, monkeypatch):
        """When a model is saved, dispatch should pass it to the provider."""
        from services import ocr_service, ocr_settings_service
        from config import OCR_BACKENDS

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        claude_models = OCR_BACKENDS["claude_vision"]["models"]
        if len(claude_models) >= 2:
            chosen_model = claude_models[1]
        else:
            chosen_model = claude_models[0]

        ocr_settings_service.save_ocr_settings(
            "claude_vision", False, models={"claude_vision": chosen_model}
        )

        # Also set the legacy backend setting
        from services import settings_service
        settings_service.set_ocr_backend("claude_vision")

        called_with = {}

        def mock_claude(image_bytes, image_b64, mime_type="image/png", model=None, language=None):
            called_with["model"] = model
            return "text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "claude_vision", mock_claude)
        ocr_service.dispatch_ocr(self._make_test_image_b64())

        assert called_with.get("model") == chosen_model
