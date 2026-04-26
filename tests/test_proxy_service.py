"""Tests for services/proxy_service.py — image proxy service."""

import http.client
import pytest
from unittest.mock import patch, create_autospec


def _make_http_response_mock(content_type, body):
    """Create an autospec'd HTTPResponse mock configured as a context manager."""
    mock_resp = create_autospec(http.client.HTTPResponse, instance=True)
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = create_autospec(
        http.client.HTTPResponse.__exit__, return_value=False
    )
    return mock_resp

from tests.mock_shape_validator import validate_proxy_response


class TestProxyImage:
    def test_invalid_url(self):
        from services.proxy_service import proxy_image

        with pytest.raises(ValueError, match="Invalid URL"):
            proxy_image("")

    def test_non_http_url(self):
        from services.proxy_service import proxy_image

        with pytest.raises(ValueError, match="Invalid URL"):
            proxy_image("ftp://example.com/image.jpg")

    def test_disallowed_domain(self):
        from services.proxy_service import proxy_image

        with pytest.raises(PermissionError, match="Domain not allowed"):
            proxy_image("https://evil.com/image.jpg")

    def test_allowed_domain(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("image/jpeg", b"\xff\xd8\xff\xe0" * 100)
        with patch.object(_no_redirect_opener, "open", return_value=mock_resp, autospec=True):
            data, ct = proxy_image("https://images.openfoodfacts.org/test.jpg")
            validate_proxy_response(data, ct)
            assert ct == "image/jpeg"
            assert len(data) > 0

    def test_http_to_https_upgrade(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("image/png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 400)
        with patch.object(
            _no_redirect_opener, "open", return_value=mock_resp, autospec=True
        ) as mock_open:
            proxy_image("http://images.openfoodfacts.org/test.png")
            # Check that the URL was upgraded to HTTPS
            call_args = mock_open.call_args
            req = call_args[0][0]
            assert req.full_url.startswith("https://")

    def test_too_large_image(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("image/jpeg", b"x" * (5 * 1024 * 1024 + 2))
        with patch.object(_no_redirect_opener, "open", return_value=mock_resp, autospec=True):
            with pytest.raises(ValueError, match="too large"):
                proxy_image("https://images.openfoodfacts.org/big.jpg")

    def test_svg_rejected(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("image/svg+xml", b"<svg></svg>")
        with patch.object(_no_redirect_opener, "open", return_value=mock_resp, autospec=True):
            with pytest.raises(ValueError, match="not an allowed image"):
                proxy_image("https://images.openfoodfacts.org/test.svg")

    def test_non_image_content_type(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("text/html", b"<html></html>")
        with patch.object(_no_redirect_opener, "open", return_value=mock_resp, autospec=True):
            with pytest.raises(ValueError, match="not an allowed image"):
                proxy_image("https://images.openfoodfacts.org/page.html")

    def test_openfoodfacts_net_allowed(self):
        from services.proxy_service import proxy_image, _no_redirect_opener

        mock_resp = _make_http_response_mock("image/jpeg", b"\xff\xd8\xff\xe0")
        with patch.object(_no_redirect_opener, "open", return_value=mock_resp, autospec=True):
            data, ct = proxy_image("https://images.openfoodfacts.net/test.jpg")
            validate_proxy_response(data, ct)
            assert ct == "image/jpeg"


class TestProxyResponseShapeValidation:
    """Validate the proxy response tuple shape and the validator itself."""

    def test_valid_jpeg_response(self):
        validate_proxy_response(b"\xff\xd8\xff\xe0" * 10, "image/jpeg")

    def test_valid_png_response(self):
        validate_proxy_response(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image/png")

    def test_rejects_empty_bytes(self):
        with pytest.raises(AssertionError, match="not be empty"):
            validate_proxy_response(b"", "image/jpeg")

    def test_rejects_non_bytes_data(self):
        with pytest.raises(AssertionError, match="must be bytes"):
            validate_proxy_response("not bytes", "image/jpeg")

    def test_rejects_disallowed_content_type(self):
        with pytest.raises(AssertionError, match="Unexpected content-type"):
            validate_proxy_response(b"\x00" * 10, "image/svg+xml")
