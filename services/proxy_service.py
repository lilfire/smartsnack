"""Service for proxying images from allowed external domains."""

import logging
import urllib.request
import urllib.error
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirects not allowed", headers, fp)


_no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler)


def proxy_image(url):
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL")
    parsed = urlparse(url)
    allowed_domains = (".openfoodfacts.org", ".openfoodfacts.net")
    if not parsed.hostname or not any(parsed.hostname == d.lstrip(".") or parsed.hostname.endswith(d) for d in allowed_domains):
        raise PermissionError("Domain not allowed")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSnack/1.0"})
        with _no_redirect_opener.open(req, timeout=10) as resp:
            ct = resp.headers.get("Content-Type", "image/jpeg")
            if not ct.startswith("image/") or "svg" in ct.lower():
                raise ValueError("Response is not an allowed image type")
            max_size = 5 * 1024 * 1024  # 5 MB
            data = resp.read(max_size + 1)
            if len(data) > max_size:
                raise ValueError("Image too large")
            return data, ct
    except (ValueError, PermissionError):
        raise
    except Exception as e:
        logger.error("Image proxy error: %s", e)
        raise RuntimeError("Failed to fetch image")
