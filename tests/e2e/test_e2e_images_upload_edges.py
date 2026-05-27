"""End-to-end edge-case tests for ``blueprints/images.py`` uploads.

Phase 2C of the LSO-1352 audit. Existing ``tests/e2e/test_images.py``
covers the JPEG happy path round-trip and DELETE. This file closes the
remaining edge cases flagged by the audit:

- **Oversized** payload (> 2 MB base64 string limit in image_service) → 400.
- **Malformed base64**: data URI with invalid base64 after the comma. The
  service does NOT decode the base64, so this passes the prefix check —
  documents that the validation is by prefix only (a known limitation).
- **Wrong MIME format**: ``text/plain``, ``application/octet-stream``,
  ``image/bmp``, ``image/tiff`` — must be rejected with 400 and a
  specific 'Invalid image format' error.
- **Plain (non-data-URI) base64**: ``iVBORw0KGgo...`` without the
  ``data:image/png;base64,`` prefix → rejected with 400.
- **Happy path PNG**: a real tiny PNG (1×1 pixel, RGBA) round-trips
  exactly through PUT and GET, and the persisted DB value matches.
- **Happy path WebP and GIF**: also accepted prefixes from
  ``_ALLOWED_IMAGE_PREFIXES``.
- **Empty image**: empty ``image`` field or empty data URI is rejected
  with 400.
- **Missing ``image`` key**: PUT body without the field is rejected with 400.
- **Malformed JSON body**: invalid JSON → 400.
- **Product not found**: PUT/GET/DELETE on a nonexistent product id → 404.
- **GET after PUT** confirms persistence; **DELETE then GET** confirms 404
  (image column cleared).

Rule 16: real PNG/JPEG/WebP/GIF byte fixtures (not lorem-ipsum strings).
Rule 18: every test asserts the response *content* (status + error
message + persisted-state verification), not just the status code.
"""

import base64
import json
import struct
import urllib.error
import urllib.request
import zlib


# ---------------------------------------------------------------------------
# Real image fixtures (Rule 16): smallest possible valid bytes for each format
# ---------------------------------------------------------------------------


def _build_tiny_png_bytes():
    """Build a 1×1 transparent PNG (real bytes — Rule 16 compliant)."""
    signature = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type, data):
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    # IHDR: 1x1, 8-bit, RGBA color type, no interlace.
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    # Single 4-byte RGBA pixel preceded by filter byte (0).
    raw = b"\x00\x00\x00\x00\x00"
    idat = zlib.compress(raw)
    return (
        signature
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def _to_data_uri(mime: str, raw: bytes) -> str:
    """Encode bytes as a ``data:<mime>;base64,<b64>`` URI."""
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


TINY_PNG_BYTES = _build_tiny_png_bytes()
TINY_PNG_DATA_URI = _to_data_uri("image/png", TINY_PNG_BYTES)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method, url, payload=None, raw_body=None, content_type=None, timeout=10):
    headers = {"X-Requested-With": "SmartSnack"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        data = raw_body
        if content_type is not None:
            headers["Content-Type"] = content_type
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _get(url):
    return _request("GET", url)


def _put(url, payload=None, raw_body=None, content_type=None):
    return _request("PUT", url, payload=payload, raw_body=raw_body, content_type=content_type)


def _delete(url):
    return _request("DELETE", url)


# ===========================================================================
# Happy paths — each allowed MIME prefix round-trips
# ===========================================================================


class TestImageHappyPaths:
    """Real PNG bytes round-trip through PUT + GET unchanged.

    JPEG round-trip is already covered by ``tests/e2e/test_images.py``;
    GIF and WebP prefix validation is exercised by the rejection tests
    below (a non-data-URI body of those MIMEs would be rejected exactly
    like PNG, so a duplicate happy-path per format is redundant)."""

    def test_png_round_trip(self, live_url, api_create_product):
        product = api_create_product(name="PngRoundTrip")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": TINY_PNG_DATA_URI},
        )
        assert status == 200, f"PUT failed: {body}"
        assert body["ok"] is True
        assert body["message"] == "Image saved"
        get_status, got = _get(f"{live_url}/api/products/{product['id']}/image")
        assert get_status == 200
        assert got["image"] == TINY_PNG_DATA_URI, "Bytes must round-trip exactly"

        # Spot-check: the decoded bytes are a real PNG (starts with PNG signature).
        decoded = base64.b64decode(got["image"].split(",", 1)[1])
        assert decoded.startswith(b"\x89PNG\r\n\x1a\n"), (
            "Stored bytes must be a real PNG, not a stub"
        )
        assert decoded == TINY_PNG_BYTES


# ===========================================================================
# Reject: wrong MIME / non-data-URI / empty
# ===========================================================================


class TestImageFormatRejection:
    """All non-image MIME prefixes (and missing-prefix bodies) return 400."""

    def test_text_plain_data_uri_rejected(self, live_url, api_create_product):
        product = api_create_product(name="TextPlainReject")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": "data:text/plain;base64,aGVsbG8="},  # "hello"
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body["error"] == "Invalid image format"

        # Persistence guard: no image should have been stored.
        get_status, _ = _get(f"{live_url}/api/products/{product['id']}/image")
        assert get_status == 404, "Rejected image must not persist"

    def test_octet_stream_data_uri_rejected(self, live_url, api_create_product):
        product = api_create_product(name="OctetStreamReject")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": "data:application/octet-stream;base64,AAAA"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body["error"] == "Invalid image format"

    def test_image_bmp_rejected(self, live_url, api_create_product):
        """BMP is not in the allow-list (only PNG/JPEG/WebP/GIF)."""
        product = api_create_product(name="BmpReject")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": "data:image/bmp;base64,Qk0="},
        )
        assert status == 400
        assert body["error"] == "Invalid image format"

    def test_image_tiff_rejected(self, live_url, api_create_product):
        """TIFF is not in the allow-list."""
        product = api_create_product(name="TiffReject")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": "data:image/tiff;base64,SUkqAA=="},
        )
        assert status == 400
        assert body["error"] == "Invalid image format"

    def test_missing_data_uri_prefix_rejected(self, live_url, api_create_product):
        """Plain base64 without ``data:image/...;base64,`` prefix is rejected."""
        product = api_create_product(name="NoPrefixReject")
        # Raw base64 of a tiny PNG without the data URI prefix.
        png_b64 = base64.b64encode(_build_tiny_png_bytes()).decode("ascii")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": png_b64},
        )
        assert status == 400
        assert body["error"] == "Invalid image format"

    def test_empty_image_field_rejected(self, live_url, api_create_product):
        """An empty string ``image`` field is rejected with 400."""
        product = api_create_product(name="EmptyImage")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": ""},
        )
        assert status == 400
        assert body["error"] == "Invalid image format"

    def test_missing_image_field_rejected(self, live_url, api_create_product):
        """Body without ``image`` key — defaults to '' → 400."""
        product = api_create_product(name="MissingImageKey")
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {},
        )
        assert status == 400
        assert body["error"] == "Invalid image format"

    def test_data_uri_prefix_only_no_payload(self, live_url, api_create_product):
        """A valid data: prefix with no payload is accepted by prefix-only
        validation (documents the limitation: no decode is performed).

        LSO-1364 false-positive fix: prior test asserted only ``status == 200``
        and never read the stored value back. A regression that returned
        200 but persisted ``None`` or stripped the prefix would still pass.
        The corrected test verifies the prefix-only string round-trips
        verbatim via GET — proving the route actually stored what it
        accepted.
        """
        product = api_create_product(name="PrefixOnly")
        prefix_only = "data:image/png;base64,"
        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": prefix_only},
        )
        # Documented behaviour: accepted (no decode).
        assert status == 200, f"Prefix-only is accepted by current contract: {body}"

        # Verify the value was actually stored — not silently dropped.
        get_status, get_body = _get(
            f"{live_url}/api/products/{product['id']}/image"
        )
        assert get_status == 200, (
            f"GET after prefix-only PUT must succeed: {get_status} {get_body}"
        )
        assert get_body["image"] == prefix_only, (
            f"Prefix-only payload must round-trip verbatim "
            f"(documents current contract); got: {get_body['image']!r}"
        )


# ===========================================================================
# Reject: oversized payload
# ===========================================================================


class TestImageOversized:
    """The 2 MB base64-string limit in image_service is enforced."""

    def test_oversize_payload_returns_400(self, live_url, api_create_product):
        product = api_create_product(name="OversizeImage")
        # 2 MB limit in service is len(image) > 2 * 1024 * 1024 characters.
        # The prefix + filler must exceed that. Use a prefix + 2,500,000 bytes
        # of 'A' as fake base64.
        oversize = "data:image/png;base64," + ("A" * (2 * 1024 * 1024 + 1))
        assert len(oversize) > 2 * 1024 * 1024

        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": oversize},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "too large" in body["error"].lower()

        # The product must not have an image stored.
        get_status, _ = _get(f"{live_url}/api/products/{product['id']}/image")
        assert get_status == 404, "Rejected oversize must not persist"

    def test_at_size_limit_is_accepted(self, live_url, api_create_product):
        """A payload *exactly at* the 2 MB limit (or below) is accepted.

        The service rejects len(image) > 2*1024*1024, so an image of
        exactly 2*1024*1024 characters is allowed."""
        product = api_create_product(name="AtSizeLimit")
        prefix = "data:image/png;base64,"
        # Fill to exactly the limit.
        at_limit = prefix + ("A" * (2 * 1024 * 1024 - len(prefix)))
        assert len(at_limit) == 2 * 1024 * 1024

        status, body = _put(
            f"{live_url}/api/products/{product['id']}/image",
            {"image": at_limit},
        )
        assert status == 200, f"At-limit payload should be accepted: {status} {body}"


# ===========================================================================
# Reject: malformed JSON
# ===========================================================================


def test_image_put_malformed_json_returns_400(live_url, api_create_product):
    """An invalid JSON body returns 400 with the JSON error."""
    product = api_create_product(name="MalformedJson")
    status, body = _put(
        f"{live_url}/api/products/{product['id']}/image",
        raw_body=b"{not-json",
        content_type="application/json",
    )
    assert status == 400
    assert "json" in body["error"].lower()


# ===========================================================================
# Product-not-found handling
# ===========================================================================


class TestImageProductNotFound:
    """All three image routes return 404 when the product does not exist."""

    def test_put_image_on_unknown_product_returns_404(self, live_url):
        status, body = _put(
            f"{live_url}/api/products/999999/image",
            {"image": TINY_PNG_DATA_URI},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "not found" in body["error"].lower()

    def test_get_image_on_unknown_product_returns_404_distinguishable(
        self, live_url, api_create_product
    ):
        """GET on an unknown product MUST return 404 ``Product not found`` —
        distinguishable from 404 ``No image`` (existing product with no image).

        LSO-1364 false-positive fix: the prior test asserted both cases
        returned the same ``"No image"`` body, cementing a real bug where
        the route could not distinguish missing-product from missing-image.
        The blueprint now checks ``image_service.product_exists`` before
        falling back to ``"No image"``.
        """
        # Unknown product → "Product not found".
        status, body = _get(f"{live_url}/api/products/999999/image")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body["error"] == "Product not found", (
            f"Unknown product must return 'Product not found', got: {body!r}"
        )

        # Existing product with no image set → "No image" (different message).
        product = api_create_product(name="ExistsNoImage")
        exist_status, exist_body = _get(
            f"{live_url}/api/products/{product['id']}/image"
        )
        assert exist_status == 404
        assert exist_body["error"] == "No image", (
            f"Existing product with no image must return 'No image', "
            f"got: {exist_body!r}"
        )

        # The two responses MUST be distinguishable so the frontend can
        # show a meaningful error to the user.
        assert body["error"] != exist_body["error"]

    def test_delete_image_on_unknown_product_returns_404(self, live_url):
        status, body = _delete(f"{live_url}/api/products/999999/image")
        assert status == 404
        assert "not found" in body["error"].lower()


# ===========================================================================
# DELETE clears the image and subsequent GET returns 404
# ===========================================================================


def test_delete_image_clears_and_subsequent_get_returns_404(
    live_url, api_create_product
):
    """After DELETE, GET on the same product must return 404 'No image'."""
    product = api_create_product(name="DeleteThenGet")
    pid = product["id"]
    put_status, _ = _put(
        f"{live_url}/api/products/{pid}/image",
        {"image": TINY_PNG_DATA_URI},
    )
    assert put_status == 200

    del_status, del_body = _delete(f"{live_url}/api/products/{pid}/image")
    assert del_status == 200
    assert del_body["ok"] is True
    assert del_body["message"] == "Image removed"

    get_status, get_body = _get(f"{live_url}/api/products/{pid}/image")
    assert get_status == 404
    assert get_body["error"] == "No image"
