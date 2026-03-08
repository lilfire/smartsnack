"""Service for interacting with the Open Food Facts API."""

import json
import logging
import urllib.request
import urllib.error
import urllib.parse

from services.settings_service import get_off_credentials

logger = logging.getLogger(__name__)

OFF_API_URL = "https://world.openfoodfacts.org/cgi/product_jqm2.pl"


def add_product_to_off(product_data):
    creds = get_off_credentials()
    if not creds["off_user_id"] or not creds["off_password"]:
        raise ValueError("off_err_no_credentials")

    code = product_data.get("code", "").strip()
    if not code:
        raise ValueError("off_err_no_ean")

    product_name = product_data.get("product_name", "").strip()
    if not product_name:
        raise ValueError("off_err_no_name")

    fields = {
        "user_id": creds["off_user_id"],
        "password": creds["off_password"],
        "code": code,
        "product_name": product_name,
    }

    # Optional text fields
    for key in ("brands", "stores", "ingredients_text", "quantity", "serving_size"):
        val = product_data.get(key, "").strip()
        if val:
            fields[key] = val

    # Nutriment fields mapping: local field name -> OFF field name
    nutriment_map = {
        "energy-kcal": "nutriment_energy-kcal",
        "energy-kj": "nutriment_energy-kj",
        "fat": "nutriment_fat",
        "saturated-fat": "nutriment_saturated-fat",
        "carbohydrates": "nutriment_carbohydrates",
        "sugars": "nutriment_sugars",
        "proteins": "nutriment_proteins",
        "fiber": "nutriment_fiber",
        "salt": "nutriment_salt",
    }

    for local_key, off_key in nutriment_map.items():
        val = product_data.get(local_key)
        if val is not None and val != "":
            fields[off_key] = str(val)

    fields["nutrition_data_per"] = "100g"

    encoded = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        OFF_API_URL,
        data=encoded,
        headers={
            "User-Agent": "SmartSnack/1.0 (smartsnack-app)",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if data.get("status") != 1:
                raise RuntimeError(data.get("status_verbose", "Unknown error from OFF"))
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("OFF API HTTP error %s: %s", e.code, body)
        raise RuntimeError("off_err_api")
    except urllib.error.URLError as e:
        logger.error("OFF API URL error: %s", e.reason)
        raise RuntimeError("off_err_network")
