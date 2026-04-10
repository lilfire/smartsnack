"""Service for interacting with the Open Food Facts API."""

import base64
import json
import logging
import secrets
import urllib.request
import urllib.error
import urllib.parse

from services.settings_service import get_off_credentials

logger = logging.getLogger(__name__)

OFF_API_URL = "https://world.openfoodfacts.org/cgi/product_jqm2.pl"
OFF_IMAGE_UPLOAD_URL = "https://world.openfoodfacts.org/cgi/product_image_upload.pl"


def add_product_to_off(product_data: dict) -> dict:
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
        raise RuntimeError("off_err_api") from e
    except urllib.error.URLError as e:
        logger.error("OFF API URL error: %s", e.reason)
        raise RuntimeError("off_err_network") from e


def _decode_data_uri(image_data_uri: str) -> tuple[bytes, str]:
    """Decode a base64 data URI, returning (raw_bytes, content_type)."""
    if not image_data_uri or not image_data_uri.startswith("data:"):
        raise ValueError("off_err_bad_image")
    header, _, payload = image_data_uri.partition(",")
    if not payload or ";base64" not in header:
        raise ValueError("off_err_bad_image")
    content_type = header[len("data:") : header.index(";base64")] or "image/jpeg"
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, TypeError) as e:
        raise ValueError("off_err_bad_image") from e
    if not raw:
        raise ValueError("off_err_bad_image")
    return raw, content_type


def _build_multipart(fields: dict[str, str], file_field: str, filename: str,
                     content_type: str, file_bytes: bytes) -> tuple[bytes, str]:
    """Build a multipart/form-data body. Returns (body, content_type_header)."""
    boundary = "----smartsnack" + secrets.token_hex(16)
    crlf = b"\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(b"--" + boundary.encode("ascii"))
        parts.append(
            f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        )
        parts.append(b"")
        parts.append(str(value).encode("utf-8"))
    parts.append(b"--" + boundary.encode("ascii"))
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'
        .encode("utf-8")
    )
    parts.append(f"Content-Type: {content_type}".encode("ascii"))
    parts.append(b"")
    parts.append(file_bytes)
    parts.append(b"--" + boundary.encode("ascii") + b"--")
    parts.append(b"")
    body = crlf.join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def upload_image_to_off(code: str, image_data_uri: str, imagefield: str = "front") -> dict:
    """Upload a base64 data-URI product image to Open Food Facts.

    Sends a multipart/form-data POST to product_image_upload.pl. Raises
    ValueError for bad input and RuntimeError for network/API failures.
    """
    creds = get_off_credentials()
    if not creds["off_user_id"] or not creds["off_password"]:
        raise ValueError("off_err_no_credentials")

    code = (code or "").strip()
    if not code:
        raise ValueError("off_err_no_ean")

    raw_bytes, content_type = _decode_data_uri(image_data_uri)
    ext = "jpg"
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"
    elif "gif" in content_type:
        ext = "gif"

    fields = {
        "user_id": creds["off_user_id"],
        "password": creds["off_password"],
        "code": code,
        "imagefield": imagefield,
    }
    file_field = f"imgupload_{imagefield}"
    filename = f"{code}_{imagefield}.{ext}"

    body, ctype = _build_multipart(fields, file_field, filename, content_type, raw_bytes)
    req = urllib.request.Request(
        OFF_IMAGE_UPLOAD_URL,
        data=body,
        headers={
            "User-Agent": "SmartSnack/1.0 (smartsnack-app)",
            "Content-Type": ctype,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            status = data.get("status")
            if status not in ("status ok", "ok") and data.get("status_code") != 0:
                raise RuntimeError(data.get("status_verbose", "off_err_api"))
            return data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.error("OFF image upload HTTP error %s: %s", e.code, err_body)
        raise RuntimeError("off_err_api") from e
    except urllib.error.URLError as e:
        logger.error("OFF image upload URL error: %s", e.reason)
        raise RuntimeError("off_err_network") from e
    except json.JSONDecodeError as e:
        logger.error("OFF image upload invalid JSON response")
        raise RuntimeError("off_err_api") from e
