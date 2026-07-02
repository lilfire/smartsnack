"""Tests for OCR API key gating (LSO-1689).

When OCR_API_KEY env var is set, all /api/ocr/* routes require a matching
X-API-Key header. When the env var is absent, gating is disabled.
"""

import pytest
from unittest.mock import patch


@pytest.fixture()
def ocr_client(app):
    """Flask test client with CSRF header for OCR tests."""
    from tests.conftest import _CsrfTestClient
    return _CsrfTestClient(app.test_client())


def _ocr_result(text="Sukker, mel", provider="Tesseract", fallback=False):
    return {"text": text, "provider": provider, "fallback": fallback}


class TestOcrApiKeyGating:
    """API key check applied to OCR endpoints."""

    def test_returns_401_when_key_configured_and_header_missing(
        self, ocr_client, monkeypatch
    ):
        monkeypatch.setenv("OCR_API_KEY", "secret-key")
        resp = ocr_client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "unauthorized"}

    def test_returns_401_when_key_configured_and_header_wrong(
        self, ocr_client, monkeypatch
    ):
        monkeypatch.setenv("OCR_API_KEY", "secret-key")
        resp = ocr_client._inner.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
            headers={"X-Requested-With": "SmartSnack", "X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "unauthorized"}

    @patch(
        "services.ocr_service.dispatch_ocr",
        return_value=_ocr_result(),
    )
    def test_passes_when_key_configured_and_header_correct(
        self, mock_dispatch, ocr_client, monkeypatch
    ):
        monkeypatch.setenv("OCR_API_KEY", "secret-key")
        resp = ocr_client._inner.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
            headers={"X-Requested-With": "SmartSnack", "X-API-Key": "secret-key"},
        )
        assert resp.status_code == 200

    @patch(
        "services.ocr_service.dispatch_ocr",
        return_value=_ocr_result(),
    )
    def test_passes_when_key_not_configured(
        self, mock_dispatch, ocr_client, monkeypatch
    ):
        monkeypatch.delenv("OCR_API_KEY", raising=False)
        resp = ocr_client.post(
            "/api/ocr/ingredients",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 200

    def test_nutrition_endpoint_gated_when_key_configured(
        self, ocr_client, monkeypatch
    ):
        """Key check applies to /api/ocr/nutrition too (via bp.before_request)."""
        monkeypatch.setenv("OCR_API_KEY", "secret-key")
        resp = ocr_client.post(
            "/api/ocr/nutrition",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
        )
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "unauthorized"}

    @patch(
        "services.ocr_service.dispatch_nutrition_ocr_bytes",
        return_value={"values": {"kcal": 200}, "provider": "Test", "fallback": False},
    )
    def test_nutrition_passes_with_correct_key(
        self, mock_dispatch, ocr_client, monkeypatch
    ):
        monkeypatch.setenv("OCR_API_KEY", "correct")
        resp = ocr_client._inner.post(
            "/api/ocr/nutrition",
            json={"image": "data:image/png;base64,iVBORw0KGgo="},
            headers={"X-Requested-With": "SmartSnack", "X-API-Key": "correct"},
        )
        assert resp.status_code == 200
