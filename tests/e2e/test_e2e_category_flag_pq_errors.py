"""End-to-end error-path tests for category/flag/protein-quality endpoints.

Closes the remaining LSO-1282 audit gaps for these blueprints:

- ``PUT /api/categories/<name>`` — 404 on unknown category, label length
  rejected with 400, name length boundary.
- ``POST /api/categories`` — 409 on duplicate name (ConflictError surfaced).
- ``POST /api/flags`` — 409 on duplicate name.
- ``POST /api/protein-quality`` — 409 on duplicate entry.
- ``POST /api/estimate-protein-quality`` — 400 on empty ingredients and on
  the service raising ``ValueError`` (LLM/estimate failure path; the
  estimator is mocked to deterministically raise).
- ``DELETE /api/flags/<name>`` — rejecting system flag deletion and
  documenting the response when the flag does not exist.

LSO-1289 / LSO-1282 audit section 7c (Medium) and 7d.
"""

import json
import urllib.error
import urllib.request

import pytest

from config import _PQ_MAX_LABEL_LEN, _MAX_CATEGORY_NAME_LEN


# ---------------------------------------------------------------------------
# HTTP helpers (single-purpose; mirrors existing e2e patterns)
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


def _get(url, timeout=5):
    return _request("GET", url, timeout=timeout)


def _post(url, payload, timeout=5):
    return _request("POST", url, payload=payload, timeout=timeout)


def _put(url, payload, timeout=5):
    return _request("PUT", url, payload=payload, timeout=timeout)


def _delete(url, timeout=5):
    return _request("DELETE", url, timeout=timeout)


# ===========================================================================
# PUT /api/categories/<name> — error paths added in this PR (LSO-1289)
# ===========================================================================


class TestPutCategoryErrorPaths:
    """PUT /api/categories/<name> error scenarios identified by the audit."""

    def test_update_unknown_category_returns_404(self, live_url):
        """Updating a category that does not exist must return 404, not silently
        succeed (regression guard: this endpoint previously no-op'd on missing
        rows and was flagged by the LSO-1282 audit)."""
        status, body = _put(
            f"{live_url}/api/categories/__never_existed__",
            {"label": "Phantom", "emoji": "\U0001f47b"},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "error" in body
        assert "not found" in body["error"].lower()

    def test_update_with_label_too_long_returns_400(self, live_url, unique_name):
        """A label longer than ``_PQ_MAX_LABEL_LEN`` is rejected with 400."""
        name = unique_name("longlbl")
        _post(
            f"{live_url}/api/categories",
            {"name": name, "label": "Original", "emoji": "\U0001f4e6"},
        )

        oversized = "a" * (_PQ_MAX_LABEL_LEN + 1)
        status, body = _put(
            f"{live_url}/api/categories/{name}",
            {"label": oversized, "emoji": ""},
        )
        assert status == 400, f"Expected 400 for oversized label, got {status}: {body}"
        assert "error" in body
        assert (
            "max length" in body["error"].lower()
            or "exceeds" in body["error"].lower()
        )

        # The original label must still be intact (oversized PUT was rejected
        # *before* the translation write happened).
        cats = _get(f"{live_url}/api/categories")[1]
        cat = next(c for c in cats if c["name"] == name)
        assert cat["label"] == "Original", (
            "Original label must be preserved when PUT is rejected"
        )

    def test_update_with_label_at_limit_succeeds(self, live_url, unique_name):
        """Label exactly at the limit is accepted (boundary check)."""
        name = unique_name("atlimit")
        _post(
            f"{live_url}/api/categories",
            {"name": name, "label": "Init", "emoji": "\U0001f4e6"},
        )

        at_limit = "x" * _PQ_MAX_LABEL_LEN
        status, body = _put(
            f"{live_url}/api/categories/{name}",
            {"label": at_limit, "emoji": ""},
        )
        assert status == 200, f"Label at limit should be accepted: {status} {body}"

    def test_update_with_overlong_name_returns_400(self, live_url):
        """A path-encoded name longer than ``_MAX_CATEGORY_NAME_LEN`` is rejected
        with 400 by ``_validate_category_name`` before any DB lookup."""
        long_name = "n" * (_MAX_CATEGORY_NAME_LEN + 1)
        status, body = _put(
            f"{live_url}/api/categories/{long_name}",
            {"label": "Whatever", "emoji": "\U0001f4e6"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "category name" in body["error"].lower()


# ===========================================================================
# 409 conflict paths — categories / flags / protein-quality
# ===========================================================================


class TestPostConflict409:
    """The three POST endpoints surface ConflictError as 409, not 400/500."""

    def test_post_category_duplicate_returns_409(self, live_url, unique_name):
        """Inserting the same category name twice returns 409 on the second call."""
        name = unique_name("dupcat")
        first_status, _ = _post(
            f"{live_url}/api/categories",
            {"name": name, "label": "First", "emoji": "\U0001f4e6"},
        )
        assert first_status == 201

        status, body = _post(
            f"{live_url}/api/categories",
            {"name": name, "label": "Second", "emoji": "\U0001f4e6"},
        )
        assert status == 409, f"Expected 409 on duplicate, got {status}: {body}"
        assert "error" in body
        # ConflictError message includes 'already exists'.
        assert "already exists" in body["error"].lower()

    def test_post_flag_duplicate_returns_409(self, live_url, unique_name):
        """Inserting the same flag name twice returns 409 on the second call."""
        # Flag names must match ``^[a-z][a-z0-9_]*$`` so we slugify the unique name.
        raw = unique_name("dupflag")
        name = raw.replace("-", "_").lower()
        first_status, _ = _post(
            f"{live_url}/api/flags",
            {"name": name, "label": "First Flag"},
        )
        assert first_status == 201

        status, body = _post(
            f"{live_url}/api/flags",
            {"name": name, "label": "Second Flag"},
        )
        assert status == 409, f"Expected 409 on duplicate flag, got {status}: {body}"
        assert "error" in body
        assert "already exists" in body["error"].lower()

    def test_post_protein_quality_duplicate_returns_409(
        self, live_url, unique_name
    ):
        """Inserting the same PQ entry name twice returns 409 on the second call.

        ``add_entry`` slugifies ``name`` so we pass an already-slug-safe value.
        """
        # Use a string-with-underscores name guaranteed to slugify identically.
        # protein_quality_service normalises to ``re.sub(r"[^a-zA-Z0-9_]", "_", ...)``
        raw = unique_name("duppq").replace("-", "_").lower()
        payload = {
            "name": raw,
            "keywords": ["dupkw"],
            "pdcaas": 0.5,
            "diaas": 0.5,
        }
        first_status, _ = _post(
            f"{live_url}/api/protein-quality", payload
        )
        assert first_status == 201

        status, body = _post(
            f"{live_url}/api/protein-quality", payload
        )
        assert status == 409, f"Expected 409 on duplicate PQ entry, got {status}: {body}"
        assert "error" in body
        assert "already exists" in body["error"].lower()


# ===========================================================================
# POST /api/estimate-protein-quality — error paths
# ===========================================================================


@pytest.fixture()
def patch_estimate():
    """Swap ``services.protein_quality_service.estimate`` with a controllable
    mock that matches the real signature.

    The live Flask server runs in the same process, so module-level attribute
    patching is observed by the route handler.
    """
    from unittest.mock import create_autospec
    from services import protein_quality_service

    original = protein_quality_service.estimate

    def _apply(side_effect=None, return_value=None):
        mock = create_autospec(original, spec_set=False)
        if side_effect is not None:
            mock.side_effect = side_effect
        elif return_value is not None:
            mock.return_value = return_value
        else:
            mock.return_value = {
                "est_pdcaas": 0.5,
                "est_diaas": 0.5,
                "sources": [],
            }
        protein_quality_service.estimate = mock
        return mock

    yield _apply
    protein_quality_service.estimate = original


class TestEstimateProteinQualityErrors:
    """``/api/estimate-protein-quality`` 400 error paths."""

    def test_empty_ingredients_returns_400(self, live_url):
        """Empty ``ingredients`` field returns 400 with explanatory error."""
        status, body = _post(
            f"{live_url}/api/estimate-protein-quality",
            {"ingredients": ""},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "ingredients" in body["error"].lower()

    def test_whitespace_only_ingredients_returns_400(self, live_url):
        """Whitespace-only ``ingredients`` (stripped to empty) returns 400."""
        status, body = _post(
            f"{live_url}/api/estimate-protein-quality",
            {"ingredients": "   \t\n  "},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "ingredients" in body["error"].lower()

    def test_missing_ingredients_field_returns_400(self, live_url):
        """A body without the ``ingredients`` key returns 400."""
        status, body = _post(
            f"{live_url}/api/estimate-protein-quality", {}
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "ingredients" in body["error"].lower()

    def test_estimator_value_error_returns_400(self, live_url, patch_estimate):
        """When the estimator (the LLM/keyword path in the service) raises
        ``ValueError``, the route returns 400 and surfaces the error message.

        The estimator is mocked deterministically per wake guidance — no
        real network call is made."""
        mock = patch_estimate(side_effect=ValueError("LLM parse failed"))
        status, body = _post(
            f"{live_url}/api/estimate-protein-quality",
            {"ingredients": "milk, oats"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body.get("error") == "LLM parse failed"
        # The mock must actually have been invoked — no coverage theater.
        assert mock.call_count == 1
        called_with = mock.call_args[0][0]
        assert isinstance(called_with, str) and "milk" in called_with


# ===========================================================================
# DELETE /api/flags/<name> — error paths
# ===========================================================================


class TestDeleteFlagErrors:
    """``DELETE /api/flags/<name>`` rejects system flags and reports unknown."""

    def test_delete_system_flag_is_rejected(self, live_url):
        """System flags (e.g. ``is_synced_with_off``) must not be deletable.

        The service raises ``ValueError("Cannot delete system flags")`` which
        the blueprint surfaces as 400. The flag must remain in the list."""
        status, body = _delete(f"{live_url}/api/flags/is_synced_with_off")
        assert status == 400, f"Expected 400 for system-flag delete, got {status}: {body}"
        assert "error" in body
        assert "system" in body["error"].lower()

        # The system flag must still be present.
        status, flags = _get(f"{live_url}/api/flags")
        assert status == 200
        names = {f["name"] for f in flags}
        assert "is_synced_with_off" in names, (
            "System flag must not have been deleted by the rejected DELETE"
        )

    def test_delete_unknown_flag_returns_404(self, live_url):
        """Deleting a flag that does not exist returns 404 with 'Flag not found'.

        ``flag_service.delete_flag`` raises ``LookupError("Flag not found")``
        for missing names, which the blueprint surfaces as 404 (REST 'absent
        resource' contract). LSO-1357 (Phase 2C audit) made this explicit so
        a future refactor cannot silently change the response code."""
        status, body = _delete(f"{live_url}/api/flags/__nonexistent_user_flag__")
        assert status == 404, f"Expected 404 for unknown flag, got {status}: {body}"
        assert "error" in body
        assert "not found" in body["error"].lower()
