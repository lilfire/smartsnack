"""Error scenario tests: network timeouts, HTTP errors, malformed responses, DB constraints."""

import io
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock, create_autospec


# ── OFF API: network timeout / URLError ────────────────────────────────────────


class TestOffNetworkTimeout:
    def _set_creds(self, app_ctx):
        from services.settings_service import set_off_credentials
        set_off_credentials("testuser", "testpass")

    def test_add_product_url_error_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        url_err = urllib.error.URLError(reason="timed out")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError, match="off_err_network"):
                add_product_to_off({"code": "1234567890", "product_name": "Test Product"})

    def test_upload_image_url_error_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import upload_image_to_off
        import base64
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
        url_err = urllib.error.URLError(reason="connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError, match="off_err_network"):
                upload_image_to_off("12345", data_uri)


# ── OFF API: HTTP error responses ──────────────────────────────────────────────


class TestOffHttpErrors:
    def _make_http_error(self, code: int, body: bytes = b"error") -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url="http://test", code=code, msg="Error",
            hdrs={}, fp=io.BytesIO(body)
        )

    def _set_creds(self, app_ctx):
        from services.settings_service import set_off_credentials
        set_off_credentials("testuser", "testpass")

    def test_add_product_429_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(429)):
            with pytest.raises(RuntimeError, match="off_err_api"):
                add_product_to_off({"code": "12345", "product_name": "Test"})

    def test_add_product_500_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(500)):
            with pytest.raises(RuntimeError, match="off_err_api"):
                add_product_to_off({"code": "12345", "product_name": "Test"})

    def test_add_product_403_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(403)):
            with pytest.raises(RuntimeError, match="off_err_api"):
                add_product_to_off({"code": "12345", "product_name": "Test"})

    def test_upload_image_429_raises_runtime_error(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import upload_image_to_off
        import base64
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(429)):
            with pytest.raises(RuntimeError, match="off_err_api"):
                upload_image_to_off("12345", data_uri)


# ── OFF API: malformed / unexpected responses ──────────────────────────────────


class TestOffMalformedResponse:
    def _mock_urlopen(self, body: bytes):
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def _set_creds(self, app_ctx):
        from services.settings_service import set_off_credentials
        set_off_credentials("testuser", "testpass")

    def test_add_product_status_not_1_raises(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        body = json.dumps({"status": 0, "status_verbose": "Product not saved"}).encode()
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            with pytest.raises(RuntimeError, match="Product not saved"):
                add_product_to_off({"code": "12345", "product_name": "Test"})

    def test_add_product_success_response(self, app_ctx):
        self._set_creds(app_ctx)
        from services.off_service import add_product_to_off
        body = json.dumps({"status": 1, "status_verbose": "fields saved"}).encode()
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(body)):
            result = add_product_to_off({"code": "12345", "product_name": "Test"})
            assert result["status"] == 1


# ── OFF API: input validation errors ──────────────────────────────────────────


class TestOffInputValidation:
    def test_add_product_no_credentials_raises(self, app_ctx):
        from services.off_service import add_product_to_off
        with pytest.raises(ValueError, match="no_credentials"):
            add_product_to_off({"code": "123", "product_name": "Test"})

    def test_add_product_missing_ean_raises(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials
        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_ean"):
            add_product_to_off({"product_name": "Test"})

    def test_add_product_missing_name_raises(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials
        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_name"):
            add_product_to_off({"code": "123456"})

    def test_upload_image_no_credentials_raises(self, app_ctx):
        from services.off_service import upload_image_to_off
        with pytest.raises(ValueError, match="no_credentials"):
            upload_image_to_off("12345", "data:image/png;base64,abc")

    def test_upload_image_invalid_data_uri_raises(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials
        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="bad_image"):
            upload_image_to_off("12345", "not-a-data-uri")

    def test_upload_image_empty_code_raises(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials
        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_ean"):
            upload_image_to_off("", "data:image/png;base64,abc")


# ── OCR backends: missing API key ──────────────────────────────────────────────


class TestOcrBackendMissingApiKey:
    def test_openai_backend_raises_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends import _get_api_key
        with pytest.raises(ValueError, match="API key required"):
            _get_api_key("OPENAI_API_KEY")

    def test_anthropic_backend_raises_when_no_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends import _get_api_key
        with pytest.raises(ValueError, match="API key required"):
            _get_api_key("ANTHROPIC_API_KEY")

    def test_gemini_backend_raises_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from services.ocr_backends import _get_api_key
        with pytest.raises(ValueError, match="API key required"):
            _get_api_key("GEMINI_API_KEY")

    def test_api_key_fallback_from_llm_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_API_KEY", "my-fallback-key")
        from services.ocr_backends import _get_api_key
        assert _get_api_key("OPENAI_API_KEY") == "my-fallback-key"


# ── OCR dispatch: backend error propagation ────────────────────────────────────


class TestOcrBackendErrorPropagation:
    def test_dispatch_ocr_propagates_provider_exception(self, app_ctx):
        """When a backend raises, dispatch_ocr propagates the error."""
        from services import ocr_core

        # Mock the provider function to simulate a network error
        mock_provider = create_autospec(
            ocr_core._PROVIDERS["tesseract"],
            return_value="",
        )
        mock_provider.side_effect = RuntimeError("simulated network failure")

        import base64
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), color=(128, 128, 128)).save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        with patch.dict(ocr_core._PROVIDERS, {"tesseract": mock_provider}):
            with pytest.raises(RuntimeError, match="simulated network failure"):
                ocr_core.dispatch_ocr(f"data:image/png;base64,{img_b64}")

    def test_dispatch_ocr_invalid_image_raises(self, app_ctx):
        from services import ocr_core
        with pytest.raises(ValueError, match="No image provided"):
            ocr_core.dispatch_ocr("")

    def test_dispatch_ocr_invalid_b64_raises(self, app_ctx):
        from services import ocr_core
        with pytest.raises(ValueError, match="Invalid base64"):
            ocr_core.dispatch_ocr("not-valid-base64!!!")


# ── DB constraint violations via import_service ────────────────────────────────


class TestDbConstraintsViaImport:
    def test_rollback_on_name_too_long(self, app_ctx, db):
        from services.import_service import import_products
        initial = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Good", "type": "Snacks", "ean": "7700000000001"},
                {"name": "x" * 201, "type": "Snacks"},
            ]})
        final = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert final == initial

    def test_rollback_on_invalid_numeric(self, app_ctx, db):
        from services.import_service import import_products
        initial = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        with pytest.raises(ValueError):
            import_products({"products": [
                {"name": "Bad Num", "type": "Snacks", "kcal": "not_a_num"},
            ]})
        final = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert final == initial

    def test_overwrite_same_ean_does_not_cause_integrity_error(self, app_ctx):
        from services.import_service import import_products
        ean = "7700000000002"
        import_products({"products": [{"name": "First", "type": "Snacks", "ean": ean}]})
        # Second overwrite should succeed without IntegrityError
        msg = import_products(
            {"products": [{"name": "Second", "type": "Snacks", "ean": ean}]},
            on_duplicate="overwrite"
        )
        assert "overwritten" in msg

    def test_allow_duplicate_same_ean_inserts_new_product_ean(self, app_ctx, db):
        from services.import_service import import_products
        ean = "7700000000003"
        import_products({"products": [{"name": "Orig", "type": "Snacks", "ean": ean}]})
        # allow_duplicate should insert a new product row without crashing
        import_products({"products": [{"name": "Dupe", "type": "Snacks", "ean": ean}]},
                        on_duplicate="allow_duplicate")
        count = db.execute("SELECT COUNT(*) FROM products WHERE name IN ('Orig','Dupe')").fetchone()[0]
        assert count == 2
