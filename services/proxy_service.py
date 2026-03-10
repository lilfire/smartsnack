"""Service for proxying images and API requests from allowed external domains."""

import json
import logging
import re
import urllib.request
import urllib.error
from urllib.parse import urlparse, urlencode

from config import OFF_NUTRITION_COMPARE_MAP

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


def _nutrition_field_similarity(local_val: float, off_val: float) -> float:
    """Compute similarity (0.0-1.0) between two nutrition values."""
    if abs(local_val - off_val) < 0.1:
        return 1.0
    if local_val == 0 and off_val == 0:
        return 1.0
    denominator = max(abs(local_val), abs(off_val))
    if denominator == 0:
        return 1.0
    diff = abs(local_val - off_val) / denominator
    if diff <= 0.05:
        return 1.0
    if diff >= 0.50:
        return 0.0
    return 1.0 - (diff - 0.05) / 0.45


def _compute_nutrition_similarity(nutrition: dict, product: dict) -> float:
    """Compute nutrition similarity score (0-25) between local and OFF data."""
    nutriments = product.get("nutriments") or {}
    if not nutriments:
        return 0

    similarities = []
    for local_key, off_key in OFF_NUTRITION_COMPARE_MAP.items():
        local_val = nutrition.get(local_key)
        off_val = nutriments.get(off_key)
        if local_val is None or off_val is None:
            continue
        try:
            local_val = float(local_val)
            off_val = float(off_val)
        except (TypeError, ValueError):
            continue
        similarities.append(_nutrition_field_similarity(local_val, off_val))

    if not similarities:
        return 0
    return (sum(similarities) / len(similarities)) * 25


def _compute_certainty(query: str, product: dict, nutrition: dict | None = None) -> int:
    """Compute a 0-100 certainty score for how well a product matches the query.

    Based on name word overlap, brand match, and optionally nutrition similarity.
    With nutrition: name up to 60, brand up to 15, nutrition up to 25.
    Without nutrition: name up to 80, brand up to 20 (preserves original behavior).
    """
    query_lower = query.lower().strip()
    query_words = query_lower.split()
    if not query_words:
        return 0

    has_nutrition = bool(nutrition)
    if has_nutrition:
        name_word_max, name_exact_bonus, name_all_bonus = 45, 15, 8
        brand_max = 15
    else:
        name_word_max, name_exact_bonus, name_all_bonus = 60, 20, 10
        brand_max = 20

    # Check both name fields, take the best score
    names = [
        (product.get("product_name_no") or "").lower(),
        (product.get("product_name") or "").lower(),
    ]

    best_name_score = 0
    for name in names:
        if not name:
            continue
        matches = sum(1 for w in query_words if w in name)
        word_score = (matches / len(query_words)) * name_word_max

        if query_lower in name:
            word_score += name_exact_bonus
        elif matches == len(query_words):
            word_score += name_all_bonus

        best_name_score = max(best_name_score, word_score)

    # Brand match
    brand = (product.get("brands") or "").lower()
    brand_score = 0
    if brand and query_words:
        brand_matches = sum(1 for w in query_words if w in brand)
        brand_score = (brand_matches / len(query_words)) * brand_max

    # Nutrition similarity
    nutri_score = 0
    if has_nutrition:
        nutri_score = _compute_nutrition_similarity(nutrition, product)

    score = int(min(100, best_name_score + brand_score + nutri_score))
    return max(0, score)


def off_search(query: str, nutrition: dict | None = None) -> dict:
    """Proxy a product name search to the OpenFoodFacts API.

    Queries both search-a-licious (Elasticsearch) and classic search.pl,
    then combines and deduplicates results sorted by completeness.
    Optionally accepts local nutrition data to improve certainty scoring.
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

    # Ensure both are lists of dicts (guard against unexpected API formats)
    if not isinstance(products_a, list):
        products_a = []
    if not isinstance(products_c, list):
        products_c = []

    # Combine and deduplicate by barcode (code), keeping first occurrence
    seen = set()
    combined = []
    for p in products_a + products_c:
        if not isinstance(p, dict):
            continue
        code = p.get("code", "")
        key = code if code else id(p)
        if key not in seen:
            seen.add(key)
            combined.append(p)

    # Compute certainty score for each product and sort by it
    for p in combined:
        try:
            p["certainty"] = _compute_certainty(cleaned, p, nutrition)
        except Exception:
            p["certainty"] = 0
    combined.sort(key=lambda p: p.get("certainty", 0), reverse=True)

    return {"products": combined, "count": len(combined)}


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
        hits = data["hits"]
        # Handle nested Elasticsearch format: {"hits": {"total": ..., "hits": [...]}}
        if isinstance(hits, dict) and "hits" in hits:
            hits = hits["hits"]
        # Elasticsearch hits may wrap product data in "_source"
        if isinstance(hits, list) and hits and "_source" in hits[0]:
            hits = [h["_source"] for h in hits if isinstance(h, dict) and "_source" in h]
        data["products"] = hits if isinstance(hits, list) else []
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
