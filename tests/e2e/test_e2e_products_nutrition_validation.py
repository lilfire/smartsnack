"""End-to-end nutrition-field validation for product CRUD.

Phase 2B of the LSO-1352 audit: for every field in ``NUTRITION_FIELDS``,
assert that ``_safe_float`` validation rejects non-numeric inputs, NaN,
and infinity on both POST and PUT — with a 400 status and a useful,
field-named error message (Rule 18).

Negative numeric values and zero are intentionally **not** rejected by
the service (no lower-bound is enforced for nutrition fields). The
existing tests in ``test_validation_boundaries.py`` already cover that
contract; this file focuses on the type-validation edges identified by
the audit.

Test data is driven directly from ``config.NUTRITION_FIELDS`` so the
suite stays in lockstep with config changes (Rule 16).
"""

import json
import urllib.error
import urllib.request

import pytest

from config import NUTRITION_FIELDS


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload, allow_nan=True).encode() if payload is not None else None
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


# ===========================================================================
# POST /api/products — invalid nutrition values are rejected per field
# ===========================================================================


class TestPostNutritionInvalidValues:
    """``POST /api/products`` rejects NaN / +inf / -inf / strings per field."""

    @pytest.mark.parametrize("field", NUTRITION_FIELDS)
    def test_nan_rejected_per_field(self, live_url, unique_name, field):
        """NaN in any nutrition field returns 400 naming that field."""
        name = unique_name(f"NaN_{field}")
        status, body = _post(
            f"{live_url}/api/products",
            {"name": name, field: float("nan")},
        )
        assert status == 400, (
            f"NaN in {field} should be rejected, got {status}: {body}"
        )
        assert "error" in body
        msg = body["error"].lower()
        assert field in msg or "numeric" in msg, (
            f"Error should reference {field!r} or 'numeric'; "
            f"got: {body['error']!r}"
        )

    @pytest.mark.parametrize("field", NUTRITION_FIELDS)
    def test_positive_infinity_rejected_per_field(
        self, live_url, unique_name, field
    ):
        """+inf in any nutrition field returns 400."""
        name = unique_name(f"PInf_{field}")
        status, body = _post(
            f"{live_url}/api/products",
            {"name": name, field: float("inf")},
        )
        assert status == 400, (
            f"+inf in {field} should be rejected, got {status}: {body}"
        )
        assert "error" in body
        msg = body["error"].lower()
        assert field in msg or "numeric" in msg

    @pytest.mark.parametrize("field", NUTRITION_FIELDS)
    def test_negative_infinity_rejected_per_field(
        self, live_url, unique_name, field
    ):
        """-inf in any nutrition field returns 400."""
        name = unique_name(f"NInf_{field}")
        status, body = _post(
            f"{live_url}/api/products",
            {"name": name, field: float("-inf")},
        )
        assert status == 400, (
            f"-inf in {field} should be rejected, got {status}: {body}"
        )
        assert "error" in body

    @pytest.mark.parametrize("field", NUTRITION_FIELDS)
    def test_non_numeric_string_rejected_per_field(
        self, live_url, unique_name, field
    ):
        """A non-numeric string in any nutrition field returns 400."""
        name = unique_name(f"Str_{field}")
        status, body = _post(
            f"{live_url}/api/products",
            {"name": name, field: "notanumber"},
        )
        assert status == 400, (
            f"String in {field} should be rejected, got {status}: {body}"
        )
        assert "error" in body
        msg = body["error"].lower()
        assert field in msg or "numeric" in msg, (
            f"Error should reference {field!r} or 'numeric'; "
            f"got: {body['error']!r}"
        )

    @pytest.mark.parametrize("field", NUTRITION_FIELDS)
    def test_rejected_post_does_not_persist(
        self, live_url, unique_name, field
    ):
        """Rejected POST does not create the product (no half-write)."""
        name = unique_name(f"NotPersisted_{field}")
        status, _ = _post(
            f"{live_url}/api/products", {"name": name, field: "garbage"}
        )
        assert status == 400, "Precondition: invalid value must be rejected"

        _, list_body = _get(f"{live_url}/api/products?search={name}")
        names = [p["name"] for p in list_body.get("products", [])]
        assert name not in names, (
            f"Rejected POST must not have persisted {name!r}; "
            f"list contains: {names}"
        )


# ===========================================================================
# POST /api/products — valid numeric edges that ARE accepted
# ===========================================================================


class TestPostNutritionAcceptedEdges:
    """Document the current contract: numeric edges that ARE accepted."""

    def test_zero_accepted_for_all_nutrition_fields(
        self, live_url, unique_name
    ):
        """Zero is a valid value for every nutrition field (boundary)."""
        payload = {"name": unique_name("AllZeros")}
        for f in NUTRITION_FIELDS:
            payload[f] = 0
        status, body = _post(f"{live_url}/api/products", payload)
        assert status == 201, (
            f"Zero values across all nutrition fields must be accepted; "
            f"got {status}: {body}"
        )

    def test_numeric_string_accepted(self, live_url, unique_name):
        """A string that parses as a float (e.g. ``"3.14"``) is accepted.

        The service's ``_safe_float`` calls ``float(v)`` directly, so well-
        formed numeric strings round-trip cleanly. Documented here as a
        regression guard against a future stricter check breaking the
        flexible JSON shape that the UI sends.
        """
        status, body = _post(
            f"{live_url}/api/products",
            {"name": unique_name("NumStr"), "kcal": "3.14", "protein": "8"},
        )
        assert status == 201, f"Numeric strings must be accepted: {body}"
        pid = body["id"]
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched["kcal"] == 3.14
        assert fetched["protein"] == 8.0


# ===========================================================================
# PUT /api/products/<id> — invalid nutrition values are rejected per field
# ===========================================================================


class TestPutNutritionInvalidValues:
    """``PUT /api/products/<id>`` enforces the same numeric validation."""

    @pytest.mark.parametrize(
        "field", ("kcal", "protein", "fat", "carbs", "salt")
    )
    def test_nan_rejected_on_update(
        self, live_url, api_create_product, unique_name, field
    ):
        """NaN on update returns 400 and does not mutate the field."""
        prod = api_create_product(
            name=unique_name(f"UpdNaN_{field}"), **{field: 42}
        )
        pid = prod["id"]
        status, body = _put(
            f"{live_url}/api/products/{pid}", {field: float("nan")}
        )
        assert status == 400, (
            f"NaN on update of {field} should be rejected, got {status}: "
            f"{body}"
        )
        assert "error" in body
        # Confirm the original value is unchanged
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched[field] == 42, (
            f"Original {field}=42 must be preserved after rejected PUT; "
            f"got {fetched[field]!r}"
        )

    @pytest.mark.parametrize(
        "field", ("kcal", "protein", "fat", "carbs", "salt")
    )
    def test_infinity_rejected_on_update(
        self, live_url, api_create_product, unique_name, field
    ):
        """+inf on update returns 400."""
        prod = api_create_product(
            name=unique_name(f"UpdInf_{field}"), **{field: 7}
        )
        pid = prod["id"]
        status, body = _put(
            f"{live_url}/api/products/{pid}", {field: float("inf")}
        )
        assert status == 400, (
            f"+inf on update of {field} should be rejected, got {status}: "
            f"{body}"
        )
        assert "error" in body

    @pytest.mark.parametrize(
        "field", ("kcal", "protein", "fat", "carbs", "salt")
    )
    def test_string_rejected_on_update(
        self, live_url, api_create_product, unique_name, field
    ):
        """A non-numeric string on update returns 400."""
        prod = api_create_product(
            name=unique_name(f"UpdStr_{field}"), **{field: 9}
        )
        pid = prod["id"]
        status, body = _put(
            f"{live_url}/api/products/{pid}", {field: "abc"}
        )
        assert status == 400
        assert "error" in body
        msg = body["error"].lower()
        assert field in msg or "numeric" in msg

    def test_update_null_clears_nutrition_field(
        self, live_url, api_create_product, unique_name
    ):
        """null on update clears the field to None (documented contract)."""
        prod = api_create_product(
            name=unique_name("ClearNutr"), kcal=200, protein=10
        )
        pid = prod["id"]
        status, body = _put(
            f"{live_url}/api/products/{pid}", {"kcal": None}
        )
        assert status == 200, f"PUT null kcal should succeed: {body}"
        _, fetched = _get(f"{live_url}/api/products/{pid}")
        assert fetched["kcal"] is None, (
            f"Expected kcal=None after null PUT; got {fetched['kcal']!r}"
        )
        # Other fields are untouched
        assert fetched["protein"] == 10.0
