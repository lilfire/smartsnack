"""E2E tests for proxy endpoints: image proxy."""

import json
import urllib.error
import urllib.request
from unittest.mock import patch


def _get_raw(url):
    """Issue GET and return (status, content_type, body_bytes)."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, "", exc.read()


def _get_json(url):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# Minimal valid JPEG (smallest possible)
_TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)


def test_proxy_image_success(live_url):
    """GET /api/proxy-image?url=... returns image data when mocked."""
    with patch("services.proxy_service.proxy_image") as mock_proxy:
        mock_proxy.return_value = (_TINY_JPEG, "image/jpeg")
        url = f"{live_url}/api/proxy-image?url=https://images.openfoodfacts.org/test.jpg"
        status, ct, body = _get_raw(url)

    assert status == 200
    assert "image" in ct
    assert body == _TINY_JPEG


def test_proxy_image_no_url(live_url):
    """GET /api/proxy-image without url returns 400."""
    with patch("services.proxy_service.proxy_image") as mock_proxy:
        mock_proxy.side_effect = ValueError("Invalid URL")
        status, body = _get_json(f"{live_url}/api/proxy-image")

    assert status == 400
    assert "error" in body


def test_proxy_image_forbidden_domain(live_url):
    """GET /api/proxy-image with non-allowed domain returns 403."""
    with patch("services.proxy_service.proxy_image") as mock_proxy:
        mock_proxy.side_effect = PermissionError("Domain not allowed")
        url = f"{live_url}/api/proxy-image?url=https://evil.com/img.jpg"
        status, body = _get_json(url)

    assert status == 403
    assert "error" in body


def test_proxy_image_upstream_error(live_url):
    """GET /api/proxy-image returns 502 on upstream failure."""
    with patch("services.proxy_service.proxy_image") as mock_proxy:
        mock_proxy.side_effect = RuntimeError("Failed to fetch image")
        url = f"{live_url}/api/proxy-image?url=https://images.openfoodfacts.org/bad.jpg"
        status, body = _get_json(url)

    assert status == 502
    assert "error" in body
