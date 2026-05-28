"""E2E validation tests for ``POST/DELETE /api/categories`` and
``GET /api/categories/<name>/weights``.

Phase 2D-2 of LSO-1352 (audit items 23–25).

- Item 23 — ``POST /api/categories`` 400 boundary set:
  * empty ``name`` -> ``name and label are required``
  * empty ``label`` -> ``name and label are required``
  * name longer than ``_MAX_CATEGORY_NAME_LEN`` -> ``Invalid category name``
  * name containing a control char -> ``Invalid category name``
  * label longer than ``_PQ_MAX_LABEL_LEN`` — pin the *actual* contract
    (today ``add_category`` does **not** length-check the label; it is
    only validated on PUT). The audit asks for oversized-label coverage,
    so we explicitly assert the current behaviour as a regression guard.
- Item 24 — ``DELETE /api/categories/<name>``:
  * invalid path-encoded name -> 400
  * ``move_to`` equal to ``name`` -> 400 ``Cannot move products to the
    same category``
  * ``move_to`` referring to a non-existent category -> 400
    ``Target category does not exist``
- Item 25 — ``GET /api/categories/<name>/weights``:
  * invalid name -> 400 from ``_validate_category_name``
  * unknown name -> 404 ``Category not found``
"""

import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

from config import _MAX_CATEGORY_NAME_LEN, _PQ_MAX_LABEL_LEN


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


def _enc(name):
    """Path-encode a category name segment (keeps ``/`` safe so a literal slash
    in the name is rejected by the route rather than re-routed)."""
    return urllib.parse.quote(name, safe="")


# ===========================================================================
# Item 23 — POST /api/categories 400 boundary set
# ===========================================================================


class TestPostCategoryValidation:
    """``POST /api/categories`` boundary validation."""

    def test_empty_name_returns_400(self, live_url):
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": "", "label": "Some Label", "emoji": "\U0001f4e6"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "name and label are required"}

    def test_whitespace_only_name_returns_400(self, live_url):
        """``name`` is ``.strip()``-ed in the blueprint so all-whitespace ->
        empty -> same 400."""
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": "   \t  ", "label": "Foo", "emoji": "\U0001f4e6"},
        )
        assert status == 400
        assert body == {"error": "name and label are required"}

    def test_empty_label_returns_400(self, live_url, unique_name):
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": unique_name("cat"), "label": "", "emoji": "\U0001f4e6"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "name and label are required"}

    def test_name_over_max_length_returns_400(self, live_url):
        """``_validate_category_name`` rejects names longer than
        ``_MAX_CATEGORY_NAME_LEN`` with ``Invalid category name``."""
        long_name = "n" * (_MAX_CATEGORY_NAME_LEN + 1)
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": long_name, "label": "OK", "emoji": "\U0001f4e6"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid category name"}

    def test_name_at_max_length_succeeds(self, live_url):
        """Name exactly at the limit is accepted (boundary)."""
        # Use a random tail so this is fresh across test runs.
        from uuid import uuid4
        tail = uuid4().hex[:8]
        at_limit = ("a" * (_MAX_CATEGORY_NAME_LEN - len(tail))) + tail
        assert len(at_limit) == _MAX_CATEGORY_NAME_LEN
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": at_limit, "label": "Boundary", "emoji": "\U0001f4e6"},
        )
        assert status == 201, f"At-limit name should be accepted: {status} {body}"

    def test_name_with_control_char_returns_400(self, live_url):
        """``_CATEGORY_NAME_RE`` rejects any control character (``\\x00-\\x1f``,
        ``\\x7f``) -> 400 ``Invalid category name``."""
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": "bad\x01name", "label": "OK", "emoji": "\U0001f4e6"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid category name"}

    def test_oversized_label_is_accepted_today(self, live_url, unique_name):
        """``add_category`` does *not* length-check ``label`` (only ``update_category``
        does). Pin the actual contract so a future change is a deliberate
        breaking change rather than a silent regression.

        Maps to audit item 23 ('oversized label'): documented + asserted, not
        silently passing."""
        long_label = "L" * (_PQ_MAX_LABEL_LEN + 1)
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={
                "name": unique_name("oversize"),
                "label": long_label,
                "emoji": "\U0001f4e6",
            },
        )
        assert status == 201, (
            "POST currently accepts oversized labels — pin contract. If this "
            f"changes, update audit item 23. Got {status}: {body}"
        )


# ===========================================================================
# Item 24 — DELETE /api/categories/<name> validation
# ===========================================================================


@pytest.fixture()
def existing_categories(live_url, unique_name):
    """Create two real categories so move_to tests have valid targets."""
    src = unique_name("delsrc")
    dst = unique_name("deldst")
    for n in (src, dst):
        status, body = _request(
            "POST",
            f"{live_url}/api/categories",
            payload={"name": n, "label": n.upper(), "emoji": "\U0001f4e6"},
        )
        assert status == 201, f"Fixture setup failed for {n}: {status} {body}"
    return {"src": src, "dst": dst}


class TestDeleteCategoryValidation:
    """``DELETE /api/categories/<name>`` 400 paths."""

    def test_invalid_name_returns_400(self, live_url):
        """A path-encoded control character is rejected by
        ``_validate_category_name`` before any DB action."""
        status, body = _request(
            "DELETE", f"{live_url}/api/categories/{_enc('bad' + chr(2) + 'name')}"
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid category name"}

    def test_move_to_unknown_category_returns_400(
        self, live_url, existing_categories, api_create_product
    ):
        """Add a product under ``src`` so deletion requires ``move_to``; supply
        a target that does not exist -> 400 ``Target category does not exist``.
        """
        src = existing_categories["src"]
        api_create_product(name="MoveToUnknown", category=src)

        status, body = _request(
            "DELETE",
            f"{live_url}/api/categories/{_enc(src)}",
            payload={"move_to": "__never_existed_target__"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Target category does not exist"}

    def test_move_to_same_as_name_returns_400(
        self, live_url, existing_categories, api_create_product
    ):
        """``move_to == name`` is a no-op cycle and is rejected with a specific
        message so the caller knows the request, not the data, is wrong."""
        src = existing_categories["src"]
        api_create_product(name="MoveToSelf", category=src)

        status, body = _request(
            "DELETE",
            f"{live_url}/api/categories/{_enc(src)}",
            payload={"move_to": src},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Cannot move products to the same category"}

    def test_delete_with_products_no_move_to_returns_400(
        self, live_url, existing_categories, api_create_product
    ):
        """Without ``move_to``, deleting a category that still has products is
        rejected — pin the message so the count-template is testable."""
        src = existing_categories["src"]
        api_create_product(name="BlocksDelete", category=src)

        status, body = _request("DELETE", f"{live_url}/api/categories/{_enc(src)}")
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "Cannot delete" in body["error"]
        assert "1" in body["error"], "Error must include the product count"


# ===========================================================================
# Item 25 — GET /api/categories/<name>/weights
# ===========================================================================


class TestGetCategoryWeightsValidation:
    """``GET /api/categories/<name>/weights`` validates the path-name."""

    def test_invalid_name_returns_400(self, live_url):
        """Path-encoded control char rejected before any DB lookup."""
        status, body = _request(
            "GET", f"{live_url}/api/categories/{_enc('w' + chr(31) + 'x')}/weights"
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid category name"}

    def test_name_over_max_returns_400(self, live_url):
        long_name = "x" * (_MAX_CATEGORY_NAME_LEN + 1)
        status, body = _request(
            "GET", f"{live_url}/api/categories/{_enc(long_name)}/weights"
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid category name"}

    def test_unknown_name_returns_404(self, live_url):
        """A valid-format name that does not exist in the DB -> 404."""
        status, body = _request(
            "GET", f"{live_url}/api/categories/__never_existed_weights__/weights"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Category not found"}
