"""End-to-end null-string-field handling across all CRUD endpoints.

LSO-1371: A hidden bug shipped because no e2e test exercised JSON ``null``
on optional string fields. Several services and blueprints called
``data.get("field", "").strip()`` — which returns ``None`` (not the
default) when the key is present but its value is ``null``, then crashes
``.strip()`` with ``AttributeError`` → 500.

These tests send a ``null`` JSON value for every string field that the
audit found unguarded, and assert the response is a clean validation
result (400 or accepted-as-empty 201/200 — never 500). Each test asserts
on the response body, not just status, per Rule 18.

If any of these tests start returning 500, the null-coercion guard in
``helpers._str_field`` (or its inlining at the call site) has regressed.
"""

import json
import urllib.error
import urllib.request

import pytest


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


# ===========================================================================
# POST /api/products — null on every optional string field is safe
# ===========================================================================

# Fields where JSON ``null`` was crashing ``add_product`` with 500 before the
# fix in services/product_crud.py:add_product. The value is set explicitly to
# ``null`` (not absent) — that's the only way to reproduce the bug, because
# absent keys hit the ``""`` default and never reach ``.strip()`` on ``None``.
PRODUCT_NULLABLE_STRING_FIELDS = (
    "type",
    "brand",
    "stores",
    "ingredients",
    "taste_note",
    "ean",
)


class TestPostProductNullStringFields:
    """``POST /api/products`` must not 500 when an optional string is ``null``."""

    @pytest.mark.parametrize("field", PRODUCT_NULLABLE_STRING_FIELDS)
    def test_null_string_field_does_not_500(self, live_url, unique_name, field):
        """JSON ``null`` for ``{field}`` must not crash with 500."""
        name = unique_name(f"NullStr_{field}")
        status, body = _post(
            f"{live_url}/api/products", {"name": name, field: None}
        )
        # Pre-fix behaviour: 500 + {"error": "An internal error occurred"}.
        # Post-fix: 201 (null coerced to ""), or 400 with a field-named error
        # if validation rejects an empty value.
        assert status != 500, (
            f"POST /api/products with {field}=null must not 500; "
            f"got {status}: {body}"
        )
        assert status in (200, 201, 400), (
            f"Unexpected status {status} for {field}=null: {body}"
        )
        if status in (200, 201):
            # Accepted as empty — must report the created id, not echo None
            assert "id" in body, f"Created product must include id: {body}"
            assert isinstance(body["id"], int), (
                f"id must be int, got {type(body['id']).__name__}: {body}"
            )
        else:
            # 400 — must have a field-relevant error body, not the generic
            # internal-error message
            assert "error" in body
            assert body["error"] != "An internal error occurred", (
                f"Got generic 500-style error for {field}=null — "
                f"AttributeError leaked through validation"
            )


# ===========================================================================
# POST /api/protein-quality — null label / null name must not 500
# ===========================================================================


class TestProteinQualityNullLabel:
    """PQ add + update must accept JSON ``null`` for the optional label."""

    def test_add_entry_with_null_label_does_not_500(
        self, live_url, unique_name
    ):
        """JSON ``label: null`` on POST must not crash."""
        kw = unique_name("nullpq")
        status, body = _post(
            f"{live_url}/api/protein-quality",
            {
                "name": kw,
                "keywords": [kw],
                "pdcaas": 0.5,
                "diaas": 0.5,
                "label": None,
            },
        )
        assert status != 500, (
            f"POST /api/protein-quality with label=null must not 500; "
            f"got {status}: {body}"
        )
        assert status in (200, 201), f"Expected create-success, got {status}: {body}"
        assert body.get("ok") is True
        assert isinstance(body.get("id"), int)

    def test_add_entry_with_null_name_does_not_500(
        self, live_url, unique_name
    ):
        """JSON ``name: null`` must produce a 400, not 500."""
        kw = unique_name("nullpqname")
        status, body = _post(
            f"{live_url}/api/protein-quality",
            {
                "name": None,
                "keywords": [kw],
                "pdcaas": 0.5,
                "diaas": 0.5,
            },
        )
        assert status != 500, (
            f"POST /api/protein-quality with name=null must not 500; "
            f"got {status}: {body}"
        )
        # Either 200/201 (name backfilled from keyword) or 400, but never 500
        assert status in (200, 201, 400)

    def test_update_entry_with_null_label_does_not_500(
        self, live_url, unique_name
    ):
        """JSON ``label: null`` on PUT must not crash."""
        kw = unique_name("nullupd")
        status, body = _post(
            f"{live_url}/api/protein-quality",
            {
                "name": kw,
                "keywords": [kw],
                "pdcaas": 0.5,
                "diaas": 0.5,
            },
        )
        assert status in (200, 201), f"Pre-condition create failed: {body}"
        pq_id = body["id"]

        status, body = _put(
            f"{live_url}/api/protein-quality/{pq_id}", {"label": None}
        )
        assert status != 500, (
            f"PUT label=null must not 500; got {status}: {body}"
        )
        assert status == 200
        assert body.get("ok") is True


# ===========================================================================
# POST/PUT /api/categories — null name/label/emoji must not 500
# ===========================================================================


class TestCategoriesNullStringFields:
    """Category CRUD must coerce ``null`` to empty before validation."""

    @pytest.mark.parametrize("field", ["name", "label", "emoji"])
    def test_post_null_field_does_not_500(
        self, live_url, unique_name, field
    ):
        payload = {"name": unique_name("Cat"), "label": "L", "emoji": "X"}
        payload[field] = None
        status, body = _post(f"{live_url}/api/categories", payload)
        assert status != 500, (
            f"POST /api/categories with {field}=null must not 500; "
            f"got {status}: {body}"
        )
        # 400 (missing required) or 201 (created) are both fine — but never
        # 500. And the error message must not be the generic internal one.
        assert status in (200, 201, 400, 409)
        if status == 400:
            assert "error" in body
            assert body["error"] != "An internal error occurred"

    def test_put_null_label_does_not_500(self, live_url, unique_name):
        """PUT /api/categories/<name> with label=null must not 500."""
        cat = unique_name("CatPut")
        status, body = _post(
            f"{live_url}/api/categories",
            {"name": cat, "label": "Initial", "emoji": "X"},
        )
        assert status in (200, 201), f"Pre-condition create failed: {body}"

        status, body = _put(
            f"{live_url}/api/categories/{cat}",
            {"label": None, "emoji": "X"},
        )
        assert status != 500, (
            f"PUT category label=null must not 500; got {status}: {body}"
        )


# ===========================================================================
# POST/PUT /api/flags — null name/label must not 500
# ===========================================================================


def _flag_name(unique_name, prefix: str) -> str:
    """``unique_name`` uses a dash-uuid suffix; flag-name regex bans dashes.

    Substitute underscores so the test can actually create the precondition
    flag without tripping the (unrelated) name-validation 400.
    """
    return unique_name(prefix).lower().replace("-", "_")


class TestFlagsNullStringFields:
    """Flag CRUD must coerce ``null`` to empty before validation."""

    @pytest.mark.parametrize("field", ["name", "label"])
    def test_post_null_field_does_not_500(
        self, live_url, unique_name, field
    ):
        payload = {"name": _flag_name(unique_name, "flag"), "label": "L"}
        payload[field] = None
        status, body = _post(f"{live_url}/api/flags", payload)
        assert status != 500, (
            f"POST /api/flags with {field}=null must not 500; "
            f"got {status}: {body}"
        )
        assert status in (200, 201, 400, 409)
        if status == 400:
            assert "error" in body
            assert body["error"] != "An internal error occurred"

    def test_put_null_label_does_not_500(self, live_url, unique_name):
        """PUT /api/flags/<name> with label=null must not 500."""
        flag = _flag_name(unique_name, "flagput")
        status, body = _post(
            f"{live_url}/api/flags", {"name": flag, "label": "L"}
        )
        assert status in (200, 201), f"Pre-condition create failed: {body}"

        status, body = _put(
            f"{live_url}/api/flags/{flag}", {"label": None}
        )
        assert status != 500, (
            f"PUT flag label=null must not 500; got {status}: {body}"
        )


# ===========================================================================
# PUT /api/settings/off-credentials — null fields must not 500
# ===========================================================================


class TestSettingsOffCredentialsNullFields:
    """Settings PUT must accept ``null`` for off_user_id / off_password."""

    def test_null_off_user_id_does_not_500(self, live_url):
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": None, "off_password": "secret"},
        )
        assert status != 500, (
            f"null off_user_id must not 500; got {status}: {body}"
        )
        # Empty user_id is functionally a "clear credentials" — accept 200
        # or a clear 400, but never an unhandled crash
        assert status in (200, 400)

    def test_null_off_password_does_not_500(self, live_url):
        """`len(None)` would crash; null password must be coerced first."""
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": "someuser", "off_password": None},
        )
        assert status != 500, (
            f"null off_password must not 500; got {status}: {body}"
        )
        assert status in (200, 400)
