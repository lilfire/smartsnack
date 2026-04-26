"""Service for proxying images and API requests from allowed external domains."""

import json
import logging
import re
import urllib.request
import urllib.error
from urllib.parse import urlparse, urlencode

from config import OFF_NUTRITION_COMPARE_MAP, SUPPORTED_LANGUAGES
from translations import _category_label

# Base fields always requested from OFF search (language-specific fields added dynamically)
_OFF_SEARCH_BASE_FIELDS = (
    "code,product_name,brands,stores,stores_tags,"
    "nutriments,image_front_small_url,image_front_url,image_url,"
    "serving_size,product_quantity,ingredients_text,completeness,lang"
)

logger = logging.getLogger(__name__)

# Magic bytes for allowed image formats
_IMAGE_MAGIC_BYTES = (
    b"\xff\xd8\xff",          # JPEG
    b"\x89PNG\r\n\x1a\n",    # PNG
    b"GIF87a",                # GIF87a
    b"GIF89a",                # GIF89a
    b"RIFF",                  # WebP (RIFF container)
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, "Redirects not allowed", headers, fp
        )


_no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler)


def proxy_image(url: str) -> tuple[bytes, str]:
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL")
    # Upgrade HTTP to HTTPS to prevent plaintext requests
    if url.startswith("http://"):
        url = "https://" + url[7:]
    parsed = urlparse(url)
    allowed_domains = (".openfoodfacts.org", ".openfoodfacts.net")
    if not parsed.hostname or not any(
        parsed.hostname == d.lstrip(".") or parsed.hostname.endswith(d)
        for d in allowed_domains
    ):
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
            # S8: Validate magic bytes to ensure actual image content
            if not any(data.startswith(magic) for magic in _IMAGE_MAGIC_BYTES):
                raise ValueError("Response is not a valid image (bad magic bytes)")
            return data, ct
    except (ValueError, PermissionError):
        raise
    except Exception as e:
        logger.error("Image proxy error: %s", e)
        raise RuntimeError("Failed to fetch image") from e


_OFF_API_BASE = "https://world.openfoodfacts.org/api/v2"
_OFF_SEARCH_BASE = "https://world.openfoodfacts.org/cgi/search.pl"
_OFF_SEARCH_A_LICIOUS = "https://search.openfoodfacts.org/search"


def _pick_by_priority(product: dict, field_prefix: str, priority: list) -> str:
    """Return the first non-empty language-keyed variant of a field in priority order."""
    for lang in priority:
        val = product.get(f"{field_prefix}_{lang}", "")
        if val and val.strip():
            return val.strip()
    return product.get(field_prefix, "") or ""


def _build_search_fields(priority: list) -> str:
    """Build the OFF search fields string including all priority language variants."""
    lang_fields = ",".join(
        f"product_name_{l},ingredients_text_{l}" for l in priority
    )
    return f"{_OFF_SEARCH_BASE_FIELDS},{lang_fields}"


def _normalize_text(s: str) -> str:
    """Normalize Unicode punctuation for consistent text comparison.

    Replaces smart/curly quotes, dashes, and other variants with their
    ASCII equivalents so that e.g. \u2019 (right single quote) matches '.
    """
    s = s.replace("\u2019", "'").replace("\u2018", "'")  # curly single quotes
    s = s.replace("\u201c", '"').replace("\u201d", '"')  # curly double quotes
    s = s.replace("\u2013", "-").replace("\u2014", "-")  # en-dash, em-dash
    return s.lower().strip()


def _clean_search_query(query: str) -> str:
    """Remove special characters that break OFF search."""
    cleaned = _normalize_text(query)
    cleaned = re.sub(r"[+#@!?*]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    if local_val == off_val:
        return 1.0
    denominator = max(abs(local_val), abs(off_val))
    if denominator == 0:
        return 1.0
    diff = abs(local_val - off_val) / denominator
    if diff >= 0.50:
        return 0.0
    return 1.0 - diff / 0.50


def _compute_nutrition_similarity(nutrition: dict, product: dict) -> float:
    """Compute nutrition similarity score (-25 to +25) between local and OFF data.

    Matching nutrition boosts the score; mismatching nutrition penalizes it.
    """
    nutriments = product.get("nutriments") or {}
    if not nutriments:
        return 0

    similarities = []
    for local_key, off_key in OFF_NUTRITION_COMPARE_MAP.items():
        local_val = nutrition.get(local_key)
        off_val = nutriments.get(off_key)
        # Skip fields where the user didn't provide a value
        if local_val is None:
            continue
        # User provided a value but OFF is missing it → mismatch
        if off_val is None:
            similarities.append(0.0)
            continue
        try:
            local_val = float(local_val)
            off_val = float(off_val)
        except (TypeError, ValueError):
            continue
        similarities.append(_nutrition_field_similarity(local_val, off_val))

    if not similarities:
        return 0
    avg = sum(similarities) / len(similarities)
    return (avg - 0.5) * 50


def _compute_certainty(
    query: str, product: dict, nutrition: dict | None = None, category: str = ""
) -> int:
    """Compute a 0-100 certainty score for how well a product matches the query.

    Based on name word overlap, brand match, optional category boost,
    and optionally nutrition similarity.
    """
    query_lower = _normalize_text(query)
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

    # Collect all product name variants dynamically (no hardcoded language codes)
    brand = _normalize_text(product.get("brands") or "")
    names = []
    for key, val in product.items():
        if key.startswith("product_name") and isinstance(val, str) and val.strip():
            names.append(_normalize_text(val))

    # Also try brand + name combinations so queries like
    # "Dave & Jon's Chokladboll" match product_name="Chokladboll" brand="Dave & Jon's"
    if brand:
        for name in list(names):
            names.append(brand + " " + name)

    best_name_score: float = 0
    for name in names:
        if not name:
            continue
        matches = sum(1 for w in query_words if w in name)
        word_score = (matches / len(query_words)) * name_word_max

        if query_lower in name:
            word_score += name_exact_bonus
        elif matches == len(query_words):
            word_score += name_all_bonus

        # Penalize product names that are much longer than the query
        name_words = len(name.split())
        if name_words > len(query_words):
            length_ratio = len(query_words) / name_words
            word_score *= (1 + length_ratio) / 2

        best_name_score = max(best_name_score, word_score)

    # Category boost (positive-only, never penalizes)
    if category and names:
        off_lang = (product.get("lang") or product.get("lc") or "").lower()
        langs_to_try = (
            [off_lang] if off_lang in SUPPORTED_LANGUAGES else list(SUPPORTED_LANGUAGES)
        )
        cat_labels = set()
        for lang in langs_to_try:
            label = _category_label(category, lang=lang).lower()
            if label:
                cat_labels.add(label)
        if cat_labels and any(
            any(cat in name for cat in cat_labels) for name in names if name
        ):
            cat_max = 3 if has_nutrition else 5
            best_name_score += cat_max

    # Brand match
    brand_score: float = 0
    if brand:
        brand_words = brand.split()
        brand_matches = sum(1 for w in brand_words if w in query_lower)
        brand_score = (brand_matches / len(brand_words)) * brand_max

    # Nutrition similarity
    nutri_score: float = 0
    if has_nutrition and nutrition is not None:
        nutri_score = _compute_nutrition_similarity(nutrition, product)

    score = int(min(100, best_name_score + brand_score + nutri_score))
    return max(0, score)


def off_search(query: str, nutrition: dict | None = None, category: str = "") -> dict:
    """Proxy a product name search to the OpenFoodFacts API.

    Queries both search-a-licious (Elasticsearch) and classic search.pl,
    then combines and deduplicates results sorted by completeness.
    Optionally accepts local nutrition data and category to improve certainty scoring.
    Language priority is loaded from user settings and applied to field selection.
    """
    if not query or len(query.strip()) < 2:
        raise ValueError("Query too short")
    cleaned = _clean_search_query(query)

    # Load priority once at request start; fall back to defaults outside app context
    try:
        from services.settings_service import get_off_language_priority
        priority = get_off_language_priority()
    except RuntimeError:
        priority = ["no", "en"]
    search_fields = _build_search_fields(priority)

    products_a: list[dict] = []
    products_c: list[dict] = []

    # Search-a-licious (better fuzzy/multi-field search)
    try:
        data = _off_search_a_licious(cleaned)
        products_a = data.get("products") or data.get("hits") or []
    except Exception:
        logger.info("search-a-licious unavailable")

    # Classic search.pl
    try:
        data = _off_search_classic(cleaned, search_fields)
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

    # Apply language priority to product_name and ingredients_text
    for p in combined:
        p["product_name"] = _pick_by_priority(p, "product_name", priority)
        p["ingredients_text"] = _pick_by_priority(p, "ingredients_text", priority)

    # Translate ingredients when not in user's target language
    from services import llm_translate_service
    if llm_translate_service.is_available():
        for p in combined:
            if (
                p.get("ingredients_text")
                and p.get("lang") != priority[0]
                and not p.get(f"ingredients_text_{priority[0]}", "").strip()
            ):
                p["ingredients_text"] = llm_translate_service.translate_ingredients(
                    p["ingredients_text"], priority[0]
                )
                p["ingredients_translated"] = True

    # Compute certainty score for each product and sort by it
    for p in combined:
        try:
            p["certainty"] = _compute_certainty(cleaned, p, nutrition, category)
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
            hits = [
                h["_source"] for h in hits if isinstance(h, dict) and "_source" in h
            ]
        data["products"] = hits if isinstance(hits, list) else []
    return data


def _off_search_classic(query: str, fields: str | None = None) -> dict:
    """Search via the classic search.pl CGI endpoint."""
    if fields is None:
        fields = _build_search_fields(["no", "en"])
    params = urlencode(
        {
            "search_terms": query,
            "search_simple": "1",
            "action": "process",
            "json": "1",
            "page_size": "20",
            "fields": fields,
        }
    )
    url = f"{_OFF_SEARCH_BASE}?{params}"
    return _off_get_json(url)


def off_product(code: str) -> dict:
    """Proxy a product lookup by EAN/barcode to the OpenFoodFacts API."""
    if not code or not code.strip().isdigit():
        raise ValueError("Invalid product code")
    url = f"{_OFF_API_BASE}/product/{code.strip()}.json"
    try:
        return _off_get_json(url)
    except _OffNotFoundError:
        # OFF API v2 returns 404 for unknown products;
        # return a "not found" payload so the frontend shows
        # "No products found" instead of "Network error".
        return {"status": 0, "status_verbose": "product not found"}


class _OffNotFoundError(Exception):
    """Raised when the OFF API returns 404 for an unknown product."""


def _off_get_json(url: str, timeout: int = 30) -> dict:
    """Fetch JSON from the OpenFoodFacts API."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSnack/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(2 * 1024 * 1024)  # 2 MB max
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise _OffNotFoundError("Product not found") from e
        logger.error("OFF API HTTP %s for %s: %s", e.code, url, e)
        raise RuntimeError(f"OFF API error (HTTP {e.code})") from e
    except Exception as e:
        logger.error("OFF API proxy error for %s: %s", url, e)
        raise RuntimeError("Failed to fetch from OpenFoodFacts") from e
