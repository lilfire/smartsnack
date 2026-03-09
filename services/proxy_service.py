"""Service for proxying images and API requests from allowed external domains."""

import json
import logging
import urllib.request
import urllib.error
from urllib.parse import urlparse, urlencode

logger = logging.getLogger(__name__)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirects not allowed", headers, fp)


_no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler)


def proxy_image(url: str) -> tuple[bytes, str]:
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL")
    # Upgrade HTTP to HTTPS to prevent plaintext requests
    if url.startswith("http://"):
        url = "https://" + url[7:]
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
        raise RuntimeError("Failed to fetch image") from e


_OFF_API_BASE = "https://world.openfoodfacts.org/api/v2"
_OFF_SEARCH_FIELDS = (
    "code,product_name,product_name_no,brands,stores,stores_tags,"
    "nutriments,image_front_small_url,image_front_url,image_url,"
    "serving_size,product_quantity,ingredients_text,"
    "ingredients_text_no,ingredients_text_en"
)


def off_search(query: str) -> dict:
    """Proxy a product name search to the OpenFoodFacts API."""
    if not query or len(query.strip()) < 2:
        raise ValueError("Query too short")
    params = urlencode({
        "search_terms": query,
        "page_size": "20",
        "fields": _OFF_SEARCH_FIELDS,
    })
    url = f"{_OFF_API_BASE}/search?{params}"
    return _off_get_json(url)


def off_product(code: str) -> dict:
    """Proxy a product lookup by EAN/barcode to the OpenFoodFacts API."""
    if not code or not code.strip().isdigit():
        raise ValueError("Invalid product code")
    url = f"{_OFF_API_BASE}/product/{code.strip()}.json"
    return _off_get_json(url)


def _off_get_json(url: str) -> dict:
    """Fetch JSON from the OpenFoodFacts API."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSnack/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(2 * 1024 * 1024)  # 2 MB max
            return json.loads(data)
    except Exception as e:
        logger.error("OFF API proxy error for %s: %s", url, e)
        raise RuntimeError("Failed to fetch from OpenFoodFacts") from e
