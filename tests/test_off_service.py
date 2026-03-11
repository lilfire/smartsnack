"""Tests for services/off_service.py — Open Food Facts API integration."""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestAddProductToOff:
    def test_missing_credentials(self, app_ctx):
        from services.off_service import add_product_to_off

        with pytest.raises(ValueError, match="no_credentials"):
            add_product_to_off({"code": "123", "product_name": "Test"})

    def test_missing_ean(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_ean"):
            add_product_to_off({"product_name": "Test"})

    def test_missing_name(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_name"):
            add_product_to_off({"code": "12345678"})

    def test_successful_submission(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": 1}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = add_product_to_off(
                {
                    "code": "12345678",
                    "product_name": "Test Product",
                    "brands": "TestBrand",
                }
            )
            assert result["status"] == 1

    def test_api_error(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials
        import urllib.error

        set_off_credentials("user", "pass")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url", 500, "Server Error", {}, MagicMock(read=lambda: b"error")
            ),
        ):
            with pytest.raises(RuntimeError, match="off_err_api"):
                add_product_to_off({"code": "123", "product_name": "Test"})

    def test_network_error(self, app_ctx):
        from services.off_service import add_product_to_off
        from services.settings_service import set_off_credentials
        import urllib.error

        set_off_credentials("user", "pass")
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
        ):
            with pytest.raises(RuntimeError, match="off_err_network"):
                add_product_to_off({"code": "123", "product_name": "Test"})
