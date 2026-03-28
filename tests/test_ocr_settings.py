"""Tests for OCR settings: config, service, API endpoints, and dispatch wiring."""

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
            "SELECT value FROM user_settings WHERE key='ocr_backend'"
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


class TestOcrDispatchWiring:
    """Tests for OCR dispatch reading from user_settings with tesseract fallback."""

    def test_dispatch_uses_tesseract_by_default(self, app_ctx, monkeypatch):
        """When no backend is set, dispatch should use tesseract (extract_text)."""
        from services import ocr_service, settings_service

        called_with = {}

        def mock_extract_text(image_base64):
            called_with["backend"] = "tesseract"
            return "mock text"

        monkeypatch.setattr(ocr_service, "extract_text", mock_extract_text)
        result = ocr_service.dispatch_ocr("fake_image_data")
        assert called_with.get("backend") == "tesseract"

    def test_dispatch_falls_back_to_tesseract_when_stored_unavailable(
        self, app_ctx, monkeypatch
    ):
        """If stored backend becomes unavailable, fall back to tesseract."""
        from services import settings_service, ocr_service

        # Store claude_vision as the selected backend
        settings_service.set_ocr_backend("claude_vision")

        # But remove the API key so it's unavailable
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        called_with = {}
        original_extract = ocr_service.extract_text

        def mock_extract_text(image_base64):
            called_with["called"] = True
            return "fallback text"

        monkeypatch.setattr(ocr_service, "extract_text", mock_extract_text)

        result = ocr_service.dispatch_ocr("fake_image_data")
        assert called_with.get("called") is True

    def test_dispatch_ocr_returns_text(self, app_ctx, monkeypatch):
        from services import ocr_service

        def mock_extract_text(image_base64):
            return "ingredient text"

        monkeypatch.setattr(ocr_service, "extract_text", mock_extract_text)
        result = ocr_service.dispatch_ocr("fake_image_data")
        assert result == "ingredient text"
