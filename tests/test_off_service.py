"""Tests for services/off_service.py — Open Food Facts API integration."""

import base64
import json
import pytest
from unittest.mock import patch, MagicMock

from tests.mock_shape_validator import (
    validate_off_add_product_response,
    validate_off_upload_image_response,
)


_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
    b"\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\xa7\xe6\xdb\xed\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)
_PNG_DATA_URI = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode("ascii")


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
            validate_off_add_product_response(result)
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


class TestUploadImageToOff:
    def test_missing_credentials(self, app_ctx):
        from services.off_service import upload_image_to_off

        with pytest.raises(ValueError, match="no_credentials"):
            upload_image_to_off("12345678", _PNG_DATA_URI)

    def test_missing_ean(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="no_ean"):
            upload_image_to_off("", _PNG_DATA_URI)

    def test_bad_image_missing_prefix(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="bad_image"):
            upload_image_to_off("12345678", "notadataurl")

    def test_bad_image_not_base64(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        with pytest.raises(ValueError, match="bad_image"):
            upload_image_to_off("12345678", "data:image/png;base64,")

    def test_successful_upload(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"status": "status ok", "imagefield": "front"}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            captured["body"] = req.data
            captured["content_type"] = req.headers.get("Content-type", "")
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = upload_image_to_off("12345678", _PNG_DATA_URI)
            validate_off_upload_image_response(result)
            assert result["status"] == "status ok"

        assert "product_image_upload.pl" in captured["url"]
        assert captured["content_type"].startswith("multipart/form-data; boundary=")
        body = captured["body"]
        assert b'name="user_id"' in body
        assert b'name="password"' in body
        assert b'name="code"' in body
        assert b"12345678" in body
        assert b'name="imagefield"' in body
        assert b"front" in body
        assert b'name="imgupload_front"' in body
        assert _PNG_1x1 in body

    def test_off_status_error(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"status": "status not ok", "status_verbose": "boom"}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="boom"):
                upload_image_to_off("12345678", _PNG_DATA_URI)

    def test_http_error(self, app_ctx):
        from services.off_service import upload_image_to_off
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
                upload_image_to_off("12345678", _PNG_DATA_URI)

    def test_network_error(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials
        import urllib.error

        set_off_credentials("user", "pass")
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
        ):
            with pytest.raises(RuntimeError, match="off_err_network"):
                upload_image_to_off("12345678", _PNG_DATA_URI)

    def test_invalid_json_response(self, app_ctx):
        from services.off_service import upload_image_to_off
        from services.settings_service import set_off_credentials

        set_off_credentials("user", "pass")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="off_err_api"):
                upload_image_to_off("12345678", _PNG_DATA_URI)


class TestOffApiMockShapes:
    """Validate canonical dict forms of OFF API responses match documented shapes.

    If the OFF API changes its response structure, update these dicts and the
    validators in mock_shape_validator.py — these tests will fail to remind you.
    """

    def test_add_product_canonical_response(self):
        validate_off_add_product_response({"status": 1})

    def test_add_product_rejects_missing_status(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_off_add_product_response({"product_id": "abc"})

    def test_add_product_rejects_string_status(self):
        with pytest.raises(AssertionError, match="must be an int"):
            validate_off_add_product_response({"status": "ok"})

    def test_upload_image_canonical_response(self):
        validate_off_upload_image_response({"status": "status ok", "imagefield": "front"})

    def test_upload_image_rejects_missing_imagefield(self):
        with pytest.raises(AssertionError, match="missing keys"):
            validate_off_upload_image_response({"status": "status ok"})

    def test_upload_image_rejects_int_status(self):
        with pytest.raises(AssertionError, match="must be a str"):
            validate_off_upload_image_response({"status": 1, "imagefield": "front"})
