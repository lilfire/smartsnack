"""Integration tests for POST /api/ocr/ingredients with LLM cleanup.

Uses Flask test client — no browser required.
Mocks all external services (OCR, Anthropic LLM) following E2E test conventions.
"""

import base64
from unittest.mock import patch

import pytest


# Minimal 1×1 white PNG encoded as base64 (valid image format)
_TINY_PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


@pytest.fixture()
def _mock_ocr(monkeypatch):
    """Patch ocr_service.extract_text to return a fixed string."""
    def _factory(text="linser, solsikkeolje, paprika"):
        return patch("services.ocr_service.extract_text", return_value=text)
    return _factory


@pytest.fixture()
def _mock_llm(monkeypatch):
    """Patch llm_cleanup_service.cleanup_ingredients with a configurable result."""
    def _factory(text="linser, solsikkeolje, paprika.", skipped=False):
        return patch(
            "services.llm_cleanup_service.cleanup_ingredients",
            return_value={"text": text, "llm_cleanup_skipped": skipped},
        )
    return _factory


class TestOcrIngredientsEndpoint:
    def test_response_contains_llm_cleanup_skipped_field(self, client, _mock_ocr, _mock_llm):
        with _mock_ocr(), _mock_llm():
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "llm_cleanup_skipped" in data
        assert data["llm_cleanup_skipped"] is False

    def test_lang_parameter_passed_to_cleanup(self, client, _mock_ocr):
        with _mock_ocr("raw text"), \
             patch("services.llm_cleanup_service.cleanup_ingredients",
                   return_value={"text": "cleaned", "llm_cleanup_skipped": False}) as mock_cleanup:
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG, "lang": "en"})
        assert resp.status_code == 200
        mock_cleanup.assert_called_once_with("raw text", "en")

    def test_lang_defaults_to_no(self, client, _mock_ocr):
        with _mock_ocr("raw text"), \
             patch("services.llm_cleanup_service.cleanup_ingredients",
                   return_value={"text": "cleaned", "llm_cleanup_skipped": False}) as mock_cleanup:
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        assert resp.status_code == 200
        mock_cleanup.assert_called_once_with("raw text", "no")

    def test_cleaned_text_returned_when_llm_succeeds(self, client, _mock_ocr, _mock_llm):
        with _mock_ocr("INGREDIENSER: sukker, salt"), \
             _mock_llm("sukker, salt.", skipped=False):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        data = resp.get_json()
        assert data["text"] == "sukker, salt."
        assert data["llm_cleanup_skipped"] is False

    def test_raw_text_returned_when_api_key_missing(self, client, _mock_ocr, _mock_llm):
        raw = "raw unprocessed ingredients"
        with _mock_ocr(raw), _mock_llm(raw, skipped=True):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        data = resp.get_json()
        assert data["text"] == raw
        assert data["llm_cleanup_skipped"] is True

    def test_raw_text_returned_when_llm_fails(self, client, _mock_ocr, _mock_llm):
        raw = "linser, solsikkeolje"
        with _mock_ocr(raw), _mock_llm(raw, skipped=True):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        data = resp.get_json()
        assert data["text"] == raw
        assert data["llm_cleanup_skipped"] is True

    def test_missing_image_returns_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_image_returns_400(self, client):
        resp = client.post("/api/ocr/ingredients", json={"image": ""})
        assert resp.status_code == 400

    def test_no_text_in_image_returns_llm_cleanup_skipped(self, client):
        with patch("services.ocr_service.extract_text", return_value=""):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == ""
        assert data["llm_cleanup_skipped"] is True

    def test_ocr_value_error_returns_400(self, client):
        with patch("services.ocr_service.extract_text", side_effect=ValueError("Invalid base64 data")):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_ocr_exception_returns_500(self, client):
        with patch("services.ocr_service.extract_text", side_effect=RuntimeError("OCR crash")):
            resp = client.post("/api/ocr/ingredients", json={"image": _TINY_PNG})
        assert resp.status_code == 500

    def test_non_json_body_returns_400(self, client):
        resp = client._inner.post(
            "/api/ocr/ingredients",
            data="not json",
            headers={
                "Content-Type": "text/plain",
                "X-Requested-With": "SmartSnack",
            },
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()
