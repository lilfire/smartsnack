"""Service for proxying images and API requests from allowed external domains."""

import json
import logging
import re
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
_OFF_SEARCH_BASE = "https://world.openfoodfacts.org/cgi/search.pl"
_OFF_SEARCH_A_LICIOUS = "https://search.openfoodfacts.org/search"
_OFF_SEARCH_FIELDS = (
    "code,product_name,product_name_no,brands,stores,stores_tags,"
    "nutriments,image_front_small_url,image_front_url,image_url,"
    "serving_size,product_quantity,ingredients_text,"
    "ingredients_text_no,ingredients_text_en,completeness"
)


def _clean_search_query(query: str) -> str:
    """Remove special characters that break OFF search."""
    cleaned = re.sub(r'[+#@!?*]', ' ', query)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _sort_by_completeness(data: dict) -> dict:
    """Sort products by completeness so most complete entries appear first."""
    if "products" in data and isinstance(data["products"], list):
        data["products"].sort(
            key=lambda p: float(p.get("completeness") or 0),
            reverse=True,
        )
    return data


def off_search(query: str) -> dict:
    """Proxy a product name search to the OpenFoodFacts API.

    Queries both search-a-licious (Elasticsearch) and classic search.pl,
    then combines and deduplicates results sorted by completeness.
    """
    if not query or len(query.strip()) < 2:
        raise ValueError("Query too short")
    cleaned = _clean_search_query(query)

    products_a = []
    products_c = []

    # Search-a-licious (better fuzzy/multi-field search)
    try:
        data = _off_search_a_licious(cleaned)
        products_a = data.get("products") or data.get("hits") or []
    except Exception:
        logger.info("search-a-licious unavailable")

    # Classic search.pl
    try:
        data = _off_search_classic(cleaned)
        products_c = data.get("products") or []
    except Exception:
        logger.info("search.pl unavailable")

    # Combine and deduplicate by barcode (code), keeping first occurrence
    seen = set()
    combined = []
    for p in products_a + products_c:
        code = p.get("code", "")
        key = code if code else id(p)
        if key not in seen:
            seen.add(key)
            combined.append(p)

    result = {"products": combined, "count": len(combined)}
    return _sort_by_completeness(result)


def _off_search_a_licious(query: str) -> dict:
    """Search via the search-a-licious Elasticsearch API (POST with JSON body)."""
    body = json.dumps({"q": query, "page_size": 20}).encode()
    req = urllib.request.Request(
        _OFF_SEARCH_A_LICIOUS,
        data=body,
        headers={
            "User-Agent": "SmartSnack/1.0",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read(2 * 1024 * 1024))
    except Exception as e:
        logger.error("search-a-licious error: %s", e)
        raise RuntimeError("Failed to fetch from search-a-licious") from e
    # Normalize: search-a-licious returns "hits", frontend expects "products"
    if "hits" in data and "products" not in data:
        data["products"] = data["hits"]
    return data


def _off_search_classic(query: str) -> dict:
    """Search via the classic search.pl CGI endpoint."""
    params = urlencode({
        "search_terms": query,
        "search_simple": "1",
        "action": "process",
        "json": "1",
        "page_size": "20",
        "fields": _OFF_SEARCH_FIELDS,
    })
    url = f"{_OFF_SEARCH_BASE}?{params}"
    return _off_get_json(url)


def off_product(code: str) -> dict:
    """Proxy a product lookup by EAN/barcode to the OpenFoodFacts API."""
    if not code or not code.strip().isdigit():
        raise ValueError("Invalid product code")
    url = f"{_OFF_API_BASE}/product/{code.strip()}.json"
    try:
        return _off_get_json(url)
    except RuntimeError:
        # OFF API v2 returns 404 for unknown products;
        # return a "not found" payload so the frontend shows
        # "No products found" instead of "Network error".
        return {"status": 0, "status_verbose": "product not found"}


def _off_get_json(url: str, timeout: int = 30) -> dict:
    """Fetch JSON from the OpenFoodFacts API."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSnack/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(2 * 1024 * 1024)  # 2 MB max
            return json.loads(data)
    except Exception as e:
        logger.error("OFF API proxy error for %s: %s", url, e)
        raise RuntimeError("Failed to fetch from OpenFoodFacts") from e
