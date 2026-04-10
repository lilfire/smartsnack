"""Tests for OCR settings blueprint endpoints."""

import json

import pytest


class TestGetProviders:
    """Tests for GET /api/ocr/providers."""

    def test_returns_tesseract_by_default(self, client, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        resp = client.get("/api/ocr/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "providers" in data
        assert len(data["providers"]) == 1
        assert data["providers"][0]["key"] == "tesseract"

    def test_returns_all_providers_with_keys(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
        monkeypatch.setenv("OPENAI_API_KEY", "ok-test")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        resp = client.get("/api/ocr/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        keys = [p["key"] for p in data["providers"]]
        assert keys == ["tesseract", "claude_vision", "gemini", "openai"]

    def test_providers_include_models(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        resp = client.get("/api/ocr/providers")
        data = resp.get_json()
        claude = next(p for p in data["providers"] if p["key"] == "claude_vision")
        assert "models" in claude
        assert isinstance(claude["models"], list)
        assert len(claude["models"]) > 0
        tesseract = next(p for p in data["providers"] if p["key"] == "tesseract")
        assert tesseract["models"] == []

    def test_no_api_keys_in_response(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
        resp = client.get("/api/ocr/providers")
        body = resp.get_data(as_text=True)
        assert "sk-secret" not in body


class TestGetSettings:
    """Tests for GET /api/ocr/settings."""

    def test_returns_defaults(self, client):
        resp = client.get("/api/ocr/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["provider"] == "tesseract"
        assert data["fallback_to_tesseract"] is False
        assert "models" in data

    def test_returns_saved_settings(self, client):
        client.post(
            "/api/ocr/settings",
            data=json.dumps({"provider": "claude_vision", "fallback_to_tesseract": True}),
            content_type="application/json",
        )
        resp = client.get("/api/ocr/settings")
        data = resp.get_json()
        assert data["provider"] == "claude_vision"
        assert data["fallback_to_tesseract"] is True

    def test_returns_saved_model(self, client):
        client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "openai",
                "fallback_to_tesseract": False,
                "models": {"openai": "gpt-4o-mini"},
            }),
            content_type="application/json",
        )
        resp = client.get("/api/ocr/settings")
        data = resp.get_json()
        assert data["models"].get("openai") == "gpt-4o-mini"


class TestPostSettings:
    """Tests for POST /api/ocr/settings."""

    def test_save_settings(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({"provider": "gemini", "fallback_to_tesseract": True}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_missing_provider(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({"fallback_to_tesseract": True}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_provider(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({"provider": "invalid", "fallback_to_tesseract": False}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_body(self, client):
        resp = client.post("/api/ocr/settings", content_type="application/json")
        assert resp.status_code == 400

    def test_fallback_defaults_to_false(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({"provider": "tesseract"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        get_resp = client.get("/api/ocr/settings")
        data = get_resp.get_json()
        assert data["fallback_to_tesseract"] is False

    def test_save_valid_model(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
                "models": {"claude_vision": "claude-haiku-4-5-20251001"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_invalid_model_for_fixed_list_provider(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "gemini",
                "fallback_to_tesseract": False,
                "models": {"gemini": "gemini-nonexistent-model"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_provider_in_models_dict(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "tesseract",
                "fallback_to_tesseract": False,
                "models": {"bogus_provider": "some-model"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_openrouter_empty_string_rejected(self, client):
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

    def test_openrouter_free_text_accepted(self, client):
        resp = client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": "anthropic/claude-3.5-sonnet"},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_models_omitted_leaves_existing(self, client):
        client.post(
            "/api/ocr/settings",
            data=json.dumps({
                "provider": "openai",
                "fallback_to_tesseract": False,
                "models": {"openai": "gpt-4o-mini"},
            }),
            content_type="application/json",
        )
        client.post(
            "/api/ocr/settings",
            data=json.dumps({"provider": "openai", "fallback_to_tesseract": False}),
            content_type="application/json",
        )
        resp = client.get("/api/ocr/settings")
        data = resp.get_json()
        assert data["models"].get("openai") == "gpt-4o-mini"
