"""Tests for OCR settings blueprint endpoints."""

import json

import pytest


class TestGetProviders:
    """Tests for GET /api/ocr/providers."""

    def test_returns_tesseract_by_default(self, client, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
        resp = client.get("/api/ocr/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        keys = [p["key"] for p in data["providers"]]
        assert keys == ["tesseract", "claude_vision", "gemini", "openai"]

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
