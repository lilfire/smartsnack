"""E2E 404 / 400 error-path tests for product + EAN endpoints.

Phase 2D-2 of LSO-1352 (audit items 12–17). One test per missing branch:

- Item 12 — ``POST /api/products/<pid>/check-duplicate`` — malformed/empty
  JSON body must surface 400 from ``_require_json``.
- Item 13 — ``DELETE /api/products/<pid>`` — non-existent pid returns
  ``404 {"error": "Product not found"}``.
- Item 14 — ``GET /api/products/<pid>/eans`` — unknown pid returns 404 with
  ``"Product not found"``.
- Item 15 — ``POST /api/products/<pid>/eans`` — unknown pid returns 404.
- Item 16 — ``DELETE /api/products/<pid>/eans/<ean_id>`` — unknown ean_id
  (and unknown pid) returns 404 with the appropriate ``LookupError`` text.
- Item 17 — ``PATCH /api/products/<pid>/eans/<ean_id>/set-primary`` — unknown
  ean_id returns 404.

All assertions are status-code + error-text specific (Rule 18).
"""

import json
import urllib.error
import urllib.request


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-Requested-With": "SmartSnack"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _raw_request(method, url, raw_body, content_type="application/json", timeout=5):
    """POST/PUT helper that sends *raw* body bytes (for malformed-JSON tests)."""
    headers = {
        "X-Requested-With": "SmartSnack",
        "Content-Type": content_type,
    }
    req = urllib.request.Request(
        url,
        data=raw_body if isinstance(raw_body, (bytes, bytearray)) else raw_body.encode(),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


# ---------------------------------------------------------------------------
# Item 12: POST /api/products/<pid>/check-duplicate — malformed JSON -> 400
# ---------------------------------------------------------------------------


class TestCheckDuplicateBadBody:
    """``check-duplicate`` validates body via ``_require_json`` -> 400."""

    def test_missing_body_returns_400(self, live_url, api_create_product):
        """No body + JSON content-type yields ``None`` from
        ``request.get_json(silent=True)`` -> ``ValueError("Invalid or missing
        JSON body")`` -> 400."""
        product = api_create_product(name="CheckDupNoBody")
        pid = product["id"]
        # Send raw empty body so Flask cannot parse it.
        status, body = _raw_request(
            "POST", f"{live_url}/api/products/{pid}/check-duplicate", raw_body=""
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid or missing JSON body"}

    def test_malformed_json_body_returns_400(self, live_url, api_create_product):
        """Invalid JSON syntax in body yields the same 400."""
        product = api_create_product(name="CheckDupBadJson")
        pid = product["id"]
        status, body = _raw_request(
            "POST",
            f"{live_url}/api/products/{pid}/check-duplicate",
            raw_body="{not-json",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid or missing JSON body"}

    def test_non_json_content_type_returns_400(self, live_url, api_create_product):
        """Content-type ``text/plain`` makes Flask's silent JSON parser return
        ``None``; the route surfaces the same 400."""
        product = api_create_product(name="CheckDupTextPlain")
        pid = product["id"]
        status, body = _raw_request(
            "POST",
            f"{live_url}/api/products/{pid}/check-duplicate",
            raw_body="ean=123",
            content_type="text/plain",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid or missing JSON body"}

    def test_empty_json_object_succeeds(self, live_url, api_create_product):
        """``{}`` is *valid* JSON; the route reads optional ``ean``/``name`` and
        returns 200 with ``duplicate: None`` — pin this so a future tightening
        is visible."""
        product = api_create_product(name="CheckDupEmptyObj")
        pid = product["id"]
        status, body = _request(
            "POST", f"{live_url}/api/products/{pid}/check-duplicate", payload={}
        )
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("duplicate") is None


# ---------------------------------------------------------------------------
# Item 13: DELETE /api/products/<pid> — unknown pid -> 404
# ---------------------------------------------------------------------------


class TestDeleteProductNotFound:
    """``DELETE /api/products/<pid>`` returns 404 for non-existent ids."""

    def test_delete_unknown_pid_returns_404(self, live_url):
        """Unknown pid -> ``delete_product`` returns 0 rows ->
        ``404 {"error": "Product not found"}``."""
        status, body = _request("DELETE", f"{live_url}/api/products/9999999")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}

    def test_delete_pid_zero_returns_404(self, live_url):
        """pid 0 is not a real auto-increment id -> 404."""
        status, body = _request("DELETE", f"{live_url}/api/products/0")
        assert status == 404
        assert body == {"error": "Product not found"}


# ---------------------------------------------------------------------------
# Item 14: GET /api/products/<pid>/eans — unknown pid -> 404
# ---------------------------------------------------------------------------


class TestListEansNotFound:
    """``GET /api/products/<pid>/eans`` raises ``LookupError`` -> 404."""

    def test_list_eans_unknown_pid_returns_404(self, live_url):
        status, body = _request("GET", f"{live_url}/api/products/9999998/eans")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}


# ---------------------------------------------------------------------------
# Item 15: POST /api/products/<pid>/eans — unknown pid -> 404
# ---------------------------------------------------------------------------


class TestAddEanNotFound:
    """``POST /api/products/<pid>/eans`` raises ``LookupError`` -> 404."""

    def test_add_ean_unknown_pid_returns_404(self, live_url):
        """The product-existence check is in ``services.product_eans.add_ean``
        *after* the format check, so we pass a valid EAN to reach the lookup."""
        status, body = _request(
            "POST",
            f"{live_url}/api/products/9999997/eans",
            payload={"ean": "1234567890123"},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}

    def test_add_invalid_ean_returns_400_before_pid_check(self, live_url):
        """Format-check fires before product-existence check — pin the order so
        a refactor that swaps them is visible."""
        status, body = _request(
            "POST",
            f"{live_url}/api/products/9999996/eans",
            payload={"ean": "not-digits"},
        )
        assert status == 400, f"Expected 400 for bad EAN, got {status}: {body}"
        assert body == {"error": "EAN must be 8-13 digits"}


# ---------------------------------------------------------------------------
# Item 16: DELETE /api/products/<pid>/eans/<ean_id> — unknown ean_id -> 404
# ---------------------------------------------------------------------------


class TestDeleteEanNotFound:
    """``DELETE /api/products/<pid>/eans/<ean_id>`` 404s for unknown ids."""

    def test_delete_ean_unknown_pid_returns_404(self, live_url):
        """Unknown pid raises ``LookupError("Product not found")``."""
        status, body = _request(
            "DELETE", f"{live_url}/api/products/9999995/eans/1"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}

    def test_delete_ean_unknown_ean_id_returns_404(self, live_url, api_create_product):
        """Real product, fictional ``ean_id`` -> ``EAN not found``."""
        product = api_create_product(name="DelEanUnknown", ean="3001234567890")
        pid = product["id"]
        status, body = _request(
            "DELETE", f"{live_url}/api/products/{pid}/eans/8888888"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "EAN not found"}


# ---------------------------------------------------------------------------
# Item 17: PATCH /api/products/<pid>/eans/<ean_id>/set-primary
# ---------------------------------------------------------------------------


class TestSetPrimaryEanNotFound:
    """``PATCH .../set-primary`` 404s for unknown pid / ean_id."""

    def test_set_primary_unknown_pid_returns_404(self, live_url):
        status, body = _request(
            "PATCH", f"{live_url}/api/products/9999994/eans/1/set-primary"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}

    def test_set_primary_unknown_ean_id_returns_404(
        self, live_url, api_create_product
    ):
        """Real product, missing ``ean_id`` -> ``EAN not found``."""
        product = api_create_product(name="SetPrimaryUnknown", ean="3001234567891")
        pid = product["id"]
        status, body = _request(
            "PATCH", f"{live_url}/api/products/{pid}/eans/7777777/set-primary"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "EAN not found"}
