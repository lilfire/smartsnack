"""End-to-end tests for category weight override endpoints.

Tests GET and PUT /api/categories/<name>/weights against the live Flask
test server. Covers:

- GET returns inherited shape when no override exists
- GET returns stored override values after a PUT
- GET returns 404 for an unknown category
- PUT happy path persists overrides verified via follow-up GET
- PUT with invalid payload returns 400
- PUT with unknown category returns 404

LSO-1289 / LSO-1282 audit (gap 7c "Medium" rows for
`GET /api/categories/<name>/weights` and
`PUT /api/categories/<name>/weights`).
"""

import json
import urllib.error
import urllib.request

import pytest


# ---------------------------------------------------------------------------
# HTTP helpers (mirror existing e2e patterns; no shared module to follow
# conftest.py "do not introduce new fixture patterns" rule)
# ---------------------------------------------------------------------------


def _get(url, timeout=5):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _put(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seed_category(live_url, unique_name):
    """Create a fresh category via the API for override tests.

    Returns the category name. ``reset_db`` will remove it after the test,
    so no cleanup is required.
    """
    name = unique_name("cwcat")
    status, body = _post(
        f"{live_url}/api/categories",
        {"name": name, "label": "Category Weight Test", "emoji": "\U0001f9ea"},
    )
    assert status == 201, f"Setup failed to create category: {status} {body}"
    return name


# ===========================================================================
# GET /api/categories/<name>/weights
# ===========================================================================


class TestGetCategoryWeights:
    """GET returns inherited shape, override shape, or 404."""

    def test_no_override_returns_global_inherited_shape(
        self, live_url, seed_category
    ):
        """A fresh category with no override returns one entry per score field
        with ``is_overridden=False`` and ``weight`` matching the global value."""
        status, body = _get(
            f"{live_url}/api/categories/{seed_category}/weights"
        )
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert isinstance(body, list)
        assert len(body) > 0, "Score config produces a non-empty list"
        for item in body:
            assert set(item.keys()) >= {
                "field",
                "label",
                "desc",
                "enabled",
                "weight",
                "direction",
                "formula",
                "formula_min",
                "formula_max",
                "is_overridden",
            }
            assert item["is_overridden"] is False, (
                f"Field {item['field']!r} should not be overridden on a fresh category"
            )

        # The list of fields must match what /api/weights reports globally.
        global_status, global_body = _get(f"{live_url}/api/weights")
        assert global_status == 200
        global_fields = {w["field"] for w in global_body}
        category_fields = {item["field"] for item in body}
        assert (
            global_fields == category_fields
        ), "Inherited shape must contain the same fields as global /api/weights"

    def test_stored_override_returned_by_get(
        self, live_url, seed_category
    ):
        """After PUT-ing an override, GET reflects the override values + flag."""
        # PUT a single field override.
        override_payload = [
            {
                "field": "kcal",
                "enabled": True,
                "weight": 42.5,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
                "is_overridden": True,
            }
        ]
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            override_payload,
        )
        assert status == 200, f"PUT failed: {status} {body}"
        assert body.get("ok") is True

        # GET back must show the override.
        status, items = _get(
            f"{live_url}/api/categories/{seed_category}/weights"
        )
        assert status == 200, f"GET failed: {status} {items}"
        kcal = next((i for i in items if i["field"] == "kcal"), None)
        assert kcal is not None, "kcal field must be present in response"
        assert kcal["is_overridden"] is True, "kcal should now be flagged as overridden"
        assert kcal["weight"] == 42.5, f"Override weight not persisted: {kcal}"
        assert kcal["direction"] == "lower"
        assert kcal["formula"] == "minmax"

        # Other fields must remain non-overridden.
        for item in items:
            if item["field"] == "kcal":
                continue
            assert item["is_overridden"] is False, (
                f"Sibling field {item['field']!r} unexpectedly flagged as overridden"
            )

    def test_unknown_category_returns_404(self, live_url):
        """GET on a category that does not exist returns 404 with error body."""
        status, body = _get(
            f"{live_url}/api/categories/__no_such_cat__/weights"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "error" in body
        assert isinstance(body["error"], str) and body["error"]


# ===========================================================================
# PUT /api/categories/<name>/weights
# ===========================================================================


class TestPutCategoryWeights:
    """PUT persists overrides, rejects bad payloads, 404s unknown categories."""

    def test_happy_path_persists_via_subsequent_get(
        self, live_url, seed_category
    ):
        """PUT a valid payload, then GET back the override."""
        payload = [
            {
                "field": "protein",
                "enabled": True,
                "weight": 175.0,
                "direction": "higher",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
                "is_overridden": True,
            },
            {
                "field": "salt",
                "enabled": True,
                "weight": 80.0,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
                "is_overridden": True,
            },
        ]
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights", payload
        )
        assert status == 200, f"PUT failed: {status} {body}"
        assert body == {"ok": True}

        # Verify both fields persisted.
        status, items = _get(
            f"{live_url}/api/categories/{seed_category}/weights"
        )
        assert status == 200
        by_field = {i["field"]: i for i in items}
        assert by_field["protein"]["is_overridden"] is True
        assert by_field["protein"]["weight"] == 175.0
        assert by_field["protein"]["direction"] == "higher"
        assert by_field["salt"]["is_overridden"] is True
        assert by_field["salt"]["weight"] == 80.0
        assert by_field["salt"]["direction"] == "lower"

    def test_override_then_unset_removes_row(
        self, live_url, seed_category
    ):
        """Sending is_overridden=False after a prior override deletes the row."""
        # First, set an override.
        _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            [
                {
                    "field": "fat",
                    "enabled": True,
                    "weight": 50.0,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                    "is_overridden": True,
                }
            ],
        )
        # Sanity check the override took.
        _, items = _get(f"{live_url}/api/categories/{seed_category}/weights")
        fat = next(i for i in items if i["field"] == "fat")
        assert fat["is_overridden"] is True

        # Now unset it.
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            [
                {
                    "field": "fat",
                    "is_overridden": False,
                }
            ],
        )
        assert status == 200, f"PUT unset failed: {status} {body}"

        _, items = _get(f"{live_url}/api/categories/{seed_category}/weights")
        fat = next(i for i in items if i["field"] == "fat")
        assert fat["is_overridden"] is False, "Override row should be deleted"

    def test_non_list_payload_returns_400(self, live_url, seed_category):
        """A non-list JSON body is rejected by the service with 400."""
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            {"field": "kcal", "weight": 100},  # dict, not list
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "array" in body["error"].lower() or "list" in body["error"].lower()

    def test_invalid_field_returns_400(self, live_url, seed_category):
        """A list item with an unknown field is rejected with 400."""
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            [
                {
                    "field": "not_a_real_field",
                    "is_overridden": True,
                    "weight": 100,
                    "enabled": True,
                    "direction": "higher",
                    "formula": "direct",
                    "formula_min": 0,
                    "formula_max": 100,
                }
            ],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "not_a_real_field" in body["error"] or "field" in body["error"].lower()

    def test_invalid_direction_returns_400(self, live_url, seed_category):
        """A list item with a bogus direction value is rejected with 400."""
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            [
                {
                    "field": "kcal",
                    "is_overridden": True,
                    "weight": 100,
                    "enabled": True,
                    "direction": "sideways",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }
            ],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "direction" in body["error"].lower()

    def test_weight_out_of_range_returns_400(self, live_url, seed_category):
        """Weight outside 0-1000 is rejected with 400."""
        status, body = _put(
            f"{live_url}/api/categories/{seed_category}/weights",
            [
                {
                    "field": "kcal",
                    "is_overridden": True,
                    "weight": 5000,  # > 1000
                    "enabled": True,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }
            ],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "weight" in body["error"].lower()

    def test_unknown_category_returns_404(self, live_url):
        """PUT on a non-existent category returns 404."""
        status, body = _put(
            f"{live_url}/api/categories/__no_such_cat__/weights",
            [
                {
                    "field": "kcal",
                    "is_overridden": True,
                    "weight": 50,
                    "enabled": True,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }
            ],
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "error" in body
        assert "not found" in body["error"].lower()
