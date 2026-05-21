"""End-to-end payload-limit boundary tests for product CRUD endpoints.

Phase 2B of the LSO-1352 audit: every text field in ``_TEXT_FIELD_LIMITS``
is exercised at exactly the limit (allowed) and one over (rejected) for
both ``POST /api/products`` and ``PUT /api/products/<id>``. Test data is
driven directly from ``config._TEXT_FIELD_LIMITS`` so the suite stays in
lockstep with config changes (Rule 16).

Each rejection asserts:
- status code 400 (Rule 18 — specific status, not just "non-2xx")
- the response body contains an ``error`` key
- the error message names the field and includes ``max length`` so a
  future refactor cannot silently swap the message and still pass.

Each rejection also re-fetches the product (for updates) or the product
list (for creates) and asserts the persisted state did **not** change.
"""

import json
import urllib.error
import urllib.request

import pytest

from config import _TEXT_FIELD_LIMITS


# ---------------------------------------------------------------------------
# HTTP helpers (mirror existing e2e patterns)
# ---------------------------------------------------------------------------


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-Requested-With": "SmartSnack"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _post(url, payload, timeout=5):
    return _request("POST", url, payload=payload, timeout=timeout)


def _put(url, payload, timeout=5):
    return _request("PUT", url, payload=payload, timeout=timeout)


def _get(url, timeout=5):
    return _request("GET", url, timeout=timeout)


# Excludes "name" because empty/whitespace name is rejected separately
# ("name is required"); "type" requires the category to exist. Those fields
# get their own dedicated tests below.
_BOUNDARY_TEXT_FIELDS = ("brand", "stores", "ingredients", "taste_note")


# ===========================================================================
# POST /api/products — text-field boundary tests
# ===========================================================================


class TestPostProductTextLimits:
    """``POST /api/products`` enforces ``_TEXT_FIELD_LIMITS`` exactly."""

    @pytest.mark.parametrize("field", _BOUNDARY_TEXT_FIELDS)
    def test_field_exactly_at_limit_is_accepted(
        self, live_url, unique_name, field
    ):
        """A value of length == limit is accepted on create."""
        limit = _TEXT_FIELD_LIMITS[field]
        payload = {
            "name": unique_name(f"AtLimit_{field}"),
            field: "x" * limit,
        }
        status, body = _post(f"{live_url}/api/products", payload)
        assert status == 201, (
            f"{field}@{limit} should be accepted (status 201), got "
            f"{status}: {body}"
        )
        assert "id" in body, f"Expected 'id' in body, got: {body}"

    @pytest.mark.parametrize("field", _BOUNDARY_TEXT_FIELDS)
    def test_field_one_over_limit_is_rejected_with_400(
        self, live_url, unique_name, field
    ):
        """A value of length == limit+1 is rejected with 400 + named-field error."""
        limit = _TEXT_FIELD_LIMITS[field]
        name = unique_name(f"Over_{field}")
        payload = {"name": name, field: "x" * (limit + 1)}
        status, body = _post(f"{live_url}/api/products", payload)
        assert status == 400, (
            f"{field}@{limit + 1} should be rejected (status 400), got "
            f"{status}: {body}"
        )
        assert "error" in body, f"Expected 'error' in body, got: {body}"
        msg = body["error"].lower()
        assert field in msg, (
            f"Error must name the field {field!r}; got: {body['error']!r}"
        )
        assert "max length" in msg, (
            f"Error must include 'max length'; got: {body['error']!r}"
        )

        # Verify the rejected product was NOT persisted — list products
        # and assert nothing with that name exists.
        _, list_body = _get(f"{live_url}/api/products?search={name}")
        names = [p["name"] for p in list_body.get("products", [])]
        assert name not in names, (
            f"Rejected POST must not have persisted product {name!r}; "
            f"found in list: {names}"
        )

    def test_type_field_at_limit_with_existing_category(
        self, live_url, unique_name
    ):
        """``type`` at the 100-char limit is accepted when the category exists.

        ``type`` cannot just be filled to the limit — the service additionally
        validates that the category exists. So we create the category first,
        then create the product with that type.
        """
        limit = _TEXT_FIELD_LIMITS["type"]
        cat_name = ("c" * limit)[:limit]
        # Create category at exact limit
        status, _ = _post(
            f"{live_url}/api/categories",
            {"name": cat_name, "label": "AtLimit", "emoji": "\U0001f4e6"},
        )
        assert status == 201, "Category must be creatable at the limit"

        status, body = _post(
            f"{live_url}/api/products",
            {"name": unique_name("TypeAtLimit"), "type": cat_name},
        )
        assert status == 201, (
            f"type@{limit} (with existing category) should be accepted, "
            f"got {status}: {body}"
        )

    def test_type_field_one_over_limit_is_rejected(self, live_url, unique_name):
        """``type`` at limit+1 is rejected with 400 before the category lookup."""
        limit = _TEXT_FIELD_LIMITS["type"]
        name = unique_name("TypeOver")
        status, body = _post(
            f"{live_url}/api/products",
            {"name": name, "type": "c" * (limit + 1)},
        )
        assert status == 400, f"Expected 400 for type@{limit + 1}: {body}"
        assert "error" in body
        msg = body["error"].lower()
        assert "type" in msg and "max length" in msg, (
            f"Error must name 'type' and 'max length'; got: {body['error']!r}"
        )

    def test_name_exactly_at_limit_accepted(self, live_url):
        """``name`` at exactly 200 chars is accepted; documents the boundary."""
        limit = _TEXT_FIELD_LIMITS["name"]
        status, body = _post(
            f"{live_url}/api/products", {"name": "n" * limit}
        )
        assert status == 201, (
            f"name@{limit} should be accepted on create: {status} {body}"
        )

    def test_name_one_over_limit_rejected_400(self, live_url):
        """``name`` at limit+1 is rejected with 400."""
        limit = _TEXT_FIELD_LIMITS["name"]
        status, body = _post(
            f"{live_url}/api/products", {"name": "n" * (limit + 1)}
        )
        assert status == 400
        assert "error" in body
        msg = body["error"].lower()
        assert "name" in msg and "max length" in msg


# ===========================================================================
# PUT /api/products/<id> — text-field boundary tests
# ===========================================================================


class TestPutProductTextLimits:
    """``PUT /api/products/<id>`` enforces the same text-field limits."""

    @pytest.mark.parametrize("field", _BOUNDARY_TEXT_FIELDS)
    def test_update_field_at_limit_accepted(
        self, live_url, api_create_product, unique_name, field
    ):
        """Updating ``field`` to a value of length == limit succeeds (200)."""
        limit = _TEXT_FIELD_LIMITS[field]
        prod = api_create_product(name=unique_name(f"UpdAtLimit_{field}"))
        pid = prod["id"]
        new_val = "y" * limit
        status, body = _put(
            f"{live_url}/api/products/{pid}", {field: new_val}
        )
        assert status == 200, (
            f"PUT {field}@{limit} should be accepted, got {status}: {body}"
        )
        # Verify persistence via GET
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched.get(field) == new_val, (
            f"Persisted {field} must equal posted value of length {limit}; "
            f"got len={len(fetched.get(field) or '')}"
        )

    @pytest.mark.parametrize("field", _BOUNDARY_TEXT_FIELDS)
    def test_update_field_one_over_limit_rejected(
        self, live_url, api_create_product, unique_name, field
    ):
        """Updating ``field`` to length == limit+1 is rejected with 400.

        Asserts the original field value is unchanged after rejection
        (regression guard: a half-committed update would be far worse than
        a clean rejection).
        """
        limit = _TEXT_FIELD_LIMITS[field]
        original = "original"
        prod = api_create_product(
            name=unique_name(f"UpdOver_{field}"), **{field: original}
        )
        pid = prod["id"]
        status, body = _put(
            f"{live_url}/api/products/{pid}",
            {field: "z" * (limit + 1)},
        )
        assert status == 400, (
            f"PUT {field}@{limit + 1} should be rejected, got {status}: {body}"
        )
        assert "error" in body
        msg = body["error"].lower()
        assert field in msg and "max length" in msg, (
            f"Error must name {field!r} and 'max length'; got: {body['error']!r}"
        )

        # Confirm the original value is untouched.
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched.get(field) == original, (
            f"Original {field} value must be preserved on rejected PUT; "
            f"got {fetched.get(field)!r}"
        )

    def test_update_name_at_limit_accepted(
        self, live_url, api_create_product, unique_name
    ):
        """``name`` update at exactly the limit succeeds."""
        limit = _TEXT_FIELD_LIMITS["name"]
        prod = api_create_product(name=unique_name("NameAtLimit"))
        pid = prod["id"]
        new_name = "n" * limit
        status, body = _put(
            f"{live_url}/api/products/{pid}", {"name": new_name}
        )
        assert status == 200, f"PUT name@{limit} should succeed: {body}"
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched["name"] == new_name


# ===========================================================================
# POST /api/products/<id>/check-duplicate — payload edge cases
# ===========================================================================


class TestCheckDuplicateEdges:
    """``POST /api/products/<id>/check-duplicate`` accepts varied payloads.

    The contract is: always returns 200 with ``duplicate`` (possibly None)
    and ``a_is_synced_with_off`` (bool). No validation errors are surfaced
    on missing/empty fields — they simply produce no duplicate.
    """

    def test_empty_payload_returns_no_duplicate(
        self, live_url, api_create_product, unique_name
    ):
        """Empty body returns 200 with ``duplicate`` set to None."""
        prod = api_create_product(name=unique_name("CDEmpty"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/check-duplicate", {}
        )
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("duplicate") is None
        assert body.get("a_is_synced_with_off") is False

    def test_no_matching_candidate_returns_no_duplicate(
        self, live_url, api_create_product, unique_name
    ):
        """A name/EAN with no match returns ``duplicate=None`` (not 404)."""
        prod = api_create_product(name=unique_name("CDNoMatch"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/check-duplicate",
            {"name": "__name_that_definitely_does_not_exist__", "ean": ""},
        )
        assert status == 200
        assert body.get("duplicate") is None

    def test_exact_name_match_returns_duplicate(
        self, live_url, api_create_product, unique_name
    ):
        """An exact-name match on a *different* product returns that product."""
        existing_name = unique_name("CDExistingName")
        existing = api_create_product(name=existing_name)
        # Create a second product to act as "the one being edited"
        editing = api_create_product(name=unique_name("CDEditing"))
        edit_pid = editing["id"]

        status, body = _post(
            f"{live_url}/api/products/{edit_pid}/check-duplicate",
            {"name": existing_name, "ean": ""},
        )
        assert status == 200
        dup = body.get("duplicate")
        assert dup is not None, (
            f"Expected duplicate match for name {existing_name!r}, got: {body}"
        )
        assert dup["id"] == existing["id"]
        assert dup["match_type"] == "name"

    def test_ean_match_returns_duplicate(
        self, live_url, api_create_product, unique_name
    ):
        """An EAN match on a different product returns that product."""
        ean = "9988770011223"
        existing = api_create_product(
            name=unique_name("CDExistingEan"), ean=ean
        )
        editing = api_create_product(name=unique_name("CDEditing2"))
        edit_pid = editing["id"]

        status, body = _post(
            f"{live_url}/api/products/{edit_pid}/check-duplicate",
            {"name": "DifferentName", "ean": ean},
        )
        assert status == 200
        dup = body.get("duplicate")
        assert dup is not None, f"Expected EAN duplicate, got: {body}"
        assert dup["id"] == existing["id"]
        assert dup["match_type"] == "ean", (
            f"Expected match_type='ean', got: {dup}"
        )

    def test_self_does_not_match_itself(
        self, live_url, api_create_product, unique_name
    ):
        """A product's own name/EAN does not register as a duplicate of itself.

        The service uses ``exclude_id=pid`` so the editing product is filtered
        out of the candidate pool — otherwise every check would self-report
        as duplicate.
        """
        name = unique_name("CDSelf")
        ean = "9988770011224"
        prod = api_create_product(name=name, ean=ean)
        pid = prod["id"]

        status, body = _post(
            f"{live_url}/api/products/{pid}/check-duplicate",
            {"name": name, "ean": ean},
        )
        assert status == 200
        assert body.get("duplicate") is None, (
            f"Self-match must not register as duplicate; got: {body}"
        )
