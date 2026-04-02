"""Tests for OCR settings: config, service, API endpoints, and dispatch wiring."""

import logging
import os

import pytest


class TestOcrConfig:
    """Tests for OCR_BACKENDS and DEFAULT_OCR_BACKEND in config.py."""

    def test_ocr_backends_exists(self):
        from config import OCR_BACKENDS
        assert isinstance(OCR_BACKENDS, dict)

    def test_ocr_backends_has_tesseract(self):
        from config import OCR_BACKENDS
        assert "tesseract" in OCR_BACKENDS
        assert OCR_BACKENDS["tesseract"]["env_key"] is None

    def test_ocr_backends_has_claude_vision(self):
        from config import OCR_BACKENDS
        assert "claude_vision" in OCR_BACKENDS
        assert OCR_BACKENDS["claude_vision"]["env_key"] == "ANTHROPIC_API_KEY"

    def test_ocr_backends_has_gemini(self):
        from config import OCR_BACKENDS
        assert "gemini" in OCR_BACKENDS
        assert OCR_BACKENDS["gemini"]["env_key"] == "GEMINI_API_KEY"

    def test_ocr_backends_has_openai(self):
        from config import OCR_BACKENDS
        assert "openai" in OCR_BACKENDS
        assert OCR_BACKENDS["openai"]["env_key"] == "OPENAI_API_KEY"

    def test_ocr_backends_have_name(self):
        from config import OCR_BACKENDS
        for backend_id, backend in OCR_BACKENDS.items():
            assert "name" in backend, f"{backend_id} missing 'name'"
            assert isinstance(backend["name"], str)

    def test_default_ocr_backend(self):
        from config import DEFAULT_OCR_BACKEND
        assert DEFAULT_OCR_BACKEND == "tesseract"


class TestGetAvailableBackends:
    """Tests for get_available_backends() in ocr_service."""

    def test_tesseract_always_available(self, app_ctx):
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        tesseract = next(b for b in backends if b["id"] == "tesseract")
        assert tesseract["available"] is True

    def test_tesseract_is_first(self, app_ctx):
        """Tesseract must always be the first backend in the list."""
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        assert backends[0]["id"] == "tesseract"

    def test_returns_list_of_dicts(self, app_ctx):
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        assert isinstance(backends, list)
        for b in backends:
            assert "id" in b
            assert "name" in b
            assert "available" in b

    def test_backend_without_key_unavailable(self, app_ctx, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        for b in backends:
            if b["id"] != "tesseract":
                assert b["available"] is False

    def test_backend_with_key_available(self, app_ctx, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        claude = next(b for b in backends if b["id"] == "claude_vision")
        assert claude["available"] is True

    def test_all_backends_present(self, app_ctx):
        from config import OCR_BACKENDS
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        ids = {b["id"] for b in backends}
        assert ids == set(OCR_BACKENDS.keys())

    def test_all_keys_set_all_available(self, app_ctx, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        from services import ocr_service
        backends = ocr_service.get_available_backends()
        for b in backends:
            assert b["available"] is True, f"{b['id']} should be available"

    def test_backends_never_expose_api_key_values(self, app_ctx, monkeypatch):
        """Security: backend list must never contain actual API key values."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-123")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-gemini-secret")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-secret-456")
        from services import ocr_service
        import json
        backends = ocr_service.get_available_backends()
        serialized = json.dumps(backends)
        assert "sk-ant-secret-123" not in serialized
        assert "AIzaSy-gemini-secret" not in serialized
        assert "sk-openai-secret-456" not in serialized
        # Also verify no env_key field is leaked to the client
        for b in backends:
            assert "env_key" not in b, f"Backend {b['id']} should not expose env_key"


class TestOcrSettingsService:
    """Tests for get_ocr_backend() and set_ocr_backend() in settings_service."""

    def test_get_ocr_backend_default(self, app_ctx):
        from services import settings_service
        backend = settings_service.get_ocr_backend()
        assert backend == "tesseract"

    def test_set_and_get_ocr_backend(self, app_ctx):
        from services import settings_service
        settings_service.set_ocr_backend("claude_vision")
        assert settings_service.get_ocr_backend() == "claude_vision"

    def test_set_invalid_backend_raises(self, app_ctx):
        from services import settings_service
        with pytest.raises(ValueError, match="[Uu]nrecognized"):
            settings_service.set_ocr_backend("nonexistent_backend")

    def test_set_ocr_backend_persists(self, app_ctx):
        from services import settings_service
        from db import get_db
        settings_service.set_ocr_backend("gemini")
        row = get_db().execute(
            "SELECT value FROM user_settings WHERE key='ocr_provider'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "gemini"


class TestOcrSettingsApi:
    """Tests for GET /api/settings/ocr and PUT /api/settings/ocr endpoints."""

    def test_get_ocr_settings(self, client):
        resp = client.get("/api/settings/ocr")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "current_backend" in data
        assert "available_backends" in data
        assert data["current_backend"] == "tesseract"
        assert isinstance(data["available_backends"], list)

    def test_get_ocr_settings_backends_have_fields(self, client):
        resp = client.get("/api/settings/ocr")
        data = resp.get_json()
        for b in data["available_backends"]:
            assert "id" in b
            assert "name" in b
            assert "available" in b

    def test_put_ocr_backend_valid(self, client):
        resp = client.put("/api/settings/ocr", json={"backend": "tesseract"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True

    def test_put_ocr_backend_invalid_id(self, client):
        resp = client.put("/api/settings/ocr", json={"backend": "bad_backend"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_put_ocr_backend_unavailable(self, client, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        resp = client.put("/api/settings/ocr", json={"backend": "claude_vision"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_put_ocr_backend_missing_field(self, client):
        resp = client.put("/api/settings/ocr", json={})
        assert resp.status_code == 400

    def test_put_then_get_reflects_change(self, client):
        client.put("/api/settings/ocr", json={"backend": "tesseract"})
        resp = client.get("/api/settings/ocr")
        data = resp.get_json()
        assert data["current_backend"] == "tesseract"

    def test_put_ocr_backend_non_json_body(self, client):
        resp = client.put(
            "/api/settings/ocr", data="not json", content_type="text/plain"
        )
        assert resp.status_code == 400

    def test_put_available_non_tesseract_backend(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        resp = client.put("/api/settings/ocr", json={"backend": "claude_vision"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert data.get("backend") == "claude_vision"

    def test_get_reflects_changed_backend(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        client.put("/api/settings/ocr", json={"backend": "claude_vision"})
        resp = client.get("/api/settings/ocr")
        data = resp.get_json()
        assert data["current_backend"] == "claude_vision"

    def test_api_response_never_contains_api_keys(self, client, monkeypatch):
        """Security: GET /api/settings/ocr must never expose API key values."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-secret")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-gemini-key")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key-789")
        resp = client.get("/api/settings/ocr")
        assert resp.status_code == 200
        raw = resp.get_data(as_text=True)
        assert "sk-ant-api-secret" not in raw
        assert "AIzaSy-gemini-key" not in raw
        assert "sk-openai-key-789" not in raw
        data = resp.get_json()
        for b in data["available_backends"]:
            assert set(b.keys()) <= {"id", "name", "available"}, (
                f"Backend {b['id']} has unexpected fields: {set(b.keys())}"
            )

    def test_tesseract_is_first_in_api_response(self, client):
        """Tesseract must always be the first option in the API response."""
        resp = client.get("/api/settings/ocr")
        data = resp.get_json()
        assert data["available_backends"][0]["id"] == "tesseract"


class TestOcrDispatchWiring:
    """Tests for OCR dispatch reading from user_settings with tesseract fallback."""

    @staticmethod
    def _make_test_image_b64():
        """Create a minimal valid base64-encoded PNG for dispatch tests."""
        import base64
        import io
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def test_dispatch_uses_tesseract_by_default(self, app_ctx, monkeypatch):
        """When no backend is set, dispatch should call the tesseract provider."""
        from services import ocr_service

        called_with = {}

        def mock_tesseract(image_bytes, image_b64):
            called_with["backend"] = "tesseract"
            return "mock text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "tesseract", mock_tesseract)
        result = ocr_service.dispatch_ocr(self._make_test_image_b64())
        assert called_with.get("backend") == "tesseract"
        assert result["text"] == "mock text"

    def test_dispatch_falls_back_to_tesseract_when_stored_unavailable(
        self, app_ctx, monkeypatch
    ):
        """If stored backend becomes unavailable, fall back to tesseract."""
        from services import settings_service, ocr_service, ocr_settings_service

        # Store claude_vision with fallback enabled
        ocr_settings_service.save_ocr_settings("claude_vision", fallback_to_tesseract=True)

        # But remove the API key so it's unavailable
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        called_with = {}

        def mock_tesseract(image_bytes, image_b64):
            called_with["backend"] = "tesseract"
            return "fallback text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "tesseract", mock_tesseract)

        result = ocr_service.dispatch_ocr(self._make_test_image_b64())
        assert called_with.get("backend") == "tesseract"
        assert result["text"] == "fallback text"
        assert result["fallback"] is True

    def test_dispatch_uses_selected_backend(self, app_ctx, monkeypatch):
        """When a valid available backend is selected, dispatch uses it."""
        from services import settings_service, ocr_service

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        settings_service.set_ocr_backend("claude_vision")

        called_with = {}

        def mock_claude(image_bytes, image_b64):
            called_with["backend"] = "claude_vision"
            return "claude text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "claude_vision", mock_claude)

        result = ocr_service.dispatch_ocr(self._make_test_image_b64())
        assert called_with.get("backend") == "claude_vision"
        assert result["text"] == "claude text"
        assert result["provider"] == "Claude Vision"
        assert result["fallback"] is False

    def test_dispatch_ocr_returns_text(self, app_ctx, monkeypatch):
        from services import ocr_service

        def mock_tesseract(image_bytes, image_b64):
            return "ingredient text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "tesseract", mock_tesseract)
        result = ocr_service.dispatch_ocr(self._make_test_image_b64())
        assert result["text"] == "ingredient text"

    def test_dispatch_fallback_logs_warning(self, app_ctx, monkeypatch, caplog):
        """Verify that falling back to tesseract logs a warning."""
        from services import ocr_service, ocr_settings_service

        ocr_settings_service.save_ocr_settings("claude_vision", fallback_to_tesseract=True)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setitem(
            ocr_service._PROVIDERS, "tesseract", lambda image_bytes, image_b64: "text"
        )

        with caplog.at_level(logging.WARNING, logger="services.ocr_service"):
            ocr_service.dispatch_ocr(self._make_test_image_b64())

        assert any("unavailable" in r.message.lower() for r in caplog.records)

    def test_dispatch_with_selected_backend(self, app_ctx, monkeypatch):
        """When a valid available backend is selected, dispatch uses the provider."""
        from services import settings_service, ocr_service

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        settings_service.set_ocr_backend("claude_vision")

        called = {}

        def mock_claude(image_bytes, image_b64):
            called["called"] = True
            return "text"

        monkeypatch.setitem(ocr_service._PROVIDERS, "claude_vision", mock_claude)
        result = ocr_service.dispatch_ocr(self._make_test_image_b64())
        assert called.get("called") is True
        assert result["text"] == "text"
