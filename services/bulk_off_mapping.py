"""Pure helpers for mapping OpenFoodFacts product data to local DB fields.

Split out of bulk_service.py to keep modules focused (and under the 500-line
limit). These functions have no job-state or threading concerns.
"""

import base64
import io
import logging
import re

from config import _VALID_COLUMNS
from services import proxy_service

logger = logging.getLogger(__name__)


def _build_update_sql(field_updates: dict) -> tuple[str, list]:
    """Build a safe SET clause for UPDATE, validating all field names.

    Raises ValueError if any field name is not in the column whitelist.
    Returns (set_clause_string, ordered_values_list).
    """
    for f in field_updates:
        if f not in _VALID_COLUMNS:
            raise ValueError(f"Invalid column name in update: {f!r}")
    set_clauses = [f"{f} = ?" for f in field_updates]
    return ", ".join(set_clauses), list(field_updates.values())


def _parse_off_nutriment(nutriments, key):
    """Extract a nutriment value from OFF data, preferring per-100g."""
    val = nutriments.get(f"{key}_100g")
    if val is None:
        val = nutriments.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _should_update(off_val, local_val):
    """Return True if we should overwrite the local value with the OFF value.

    Overwrite unless OFF value is empty/zero and local already has a value.
    """
    if off_val is None:
        return False
    if isinstance(off_val, str):
        if not off_val.strip():
            return False
    elif isinstance(off_val, (int, float)):
        if (
            off_val == 0
            and local_val is not None
            and local_val != ""
            and local_val != 0
        ):
            return False
    return True


def _map_off_product(product, local_row, priority=None):
    """Map OFF product data to local DB fields. Returns dict of fields to update.

    ``priority`` is the user's OFF language priority list.  Only the **first**
    (top) language is checked for name and ingredients – if the #1 language
    has no data the field is left unchanged so we don't overwrite with a
    less-preferred language.
    """
    updates = {}
    top_lang = (priority[0] if priority else "no")
    n = product.get("nutriments") or {}

    # Nutrition fields
    nutrition_map = {
        "kcal": "energy-kcal",
        "energy_kj": "energy-kj",
        "fat": "fat",
        "saturated_fat": "saturated-fat",
        "carbs": "carbohydrates",
        "sugar": "sugars",
        "protein": "proteins",
        "fiber": "fiber",
        "salt": "salt",
    }
    for local_field, off_key in nutrition_map.items():
        off_val = _parse_off_nutriment(n, off_key)
        if _should_update(off_val, local_row.get(local_field)):
            if local_field in ("kcal", "energy_kj"):
                updates[local_field] = round(off_val)
            elif local_field == "salt":
                updates[local_field] = round(off_val, 2)
            else:
                updates[local_field] = round(off_val, 1)

    # Name – only use the #1 priority language
    name = (product.get(f"product_name_{top_lang}") or "").strip()
    if name and _should_update(name, local_row.get("name")):
        updates["name"] = name

    # Brand
    brand = product.get("brands") or ""
    if _should_update(brand, local_row.get("brand")):
        updates["brand"] = brand.strip()

    # Stores
    stores = product.get("stores") or ""
    if not stores and product.get("stores_tags"):
        tags = product["stores_tags"]
        if isinstance(tags, list) and tags:
            stores = ", ".join(t.replace("-", " ").title() for t in tags)
    if _should_update(stores, local_row.get("stores")):
        updates["stores"] = stores.strip()

    # Ingredients – only use the #1 priority language
    ing = (product.get(f"ingredients_text_{top_lang}") or "").strip()
    if ing and _should_update(ing, local_row.get("ingredients")):
        updates["ingredients"] = ing

    # Weight (product_quantity)
    qty = product.get("product_quantity")
    if qty:
        try:
            w = round(float(qty))
            if _should_update(w, local_row.get("weight")):
                updates["weight"] = w
        except (ValueError, TypeError):
            pass

    # Portion (serving_size)
    serving = product.get("serving_size") or ""
    m = re.search(r"([\d.]+)\s*g", serving)
    if m:
        try:
            p = round(float(m.group(1)))
            if _should_update(p, local_row.get("portion")):
                updates["portion"] = p
        except (ValueError, TypeError):
            pass

    return updates


def _fetch_off_image(product):
    """Fetch and resize product image from OFF. Returns base64 data URI or None."""
    img_url = (
        product.get("image_front_url")
        or product.get("image_url")
        or product.get("image_front_small_url")
        or ""
    )
    if not img_url:
        return None
    try:
        img_data, content_type = proxy_service.proxy_image(img_url)
        # Resize to max 400px using PIL if available
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(img_data))
            max_dim = 400
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                buf = io.BytesIO()
                fmt = "JPEG" if "jpeg" in content_type else "PNG"
                img.save(buf, format=fmt, quality=85)
                img_data = buf.getvalue()
                if fmt == "JPEG":
                    content_type = "image/jpeg"
                else:
                    content_type = "image/png"
        except Exception:
            pass  # PIL not available or image can't be processed, use original size

        b64 = base64.b64encode(img_data).decode("ascii")
        mime = content_type.split(";")[0].strip()
        data_uri = f"data:{mime};base64,{b64}"
        # Check size limit (2 MB)
        if len(data_uri) > 2 * 1024 * 1024:
            return None
        return data_uri
    except Exception as e:
        logger.debug("Failed to fetch image for product: %s", e)
        return None
