"""End-to-end EAN-management edge-case tests for product CRUD.

Phase 2B of the LSO-1352 audit: closes the gaps identified for
``POST /api/products/<id>/eans``, ``DELETE /api/products/<id>/eans/<ean_id>``,
``PATCH /api/products/<id>/eans/<ean_id>/set-primary`` and
``POST /api/products/<id>/eans/<ean_id>/unsync``.

Covers:
- EAN format violations: non-digits, too short, too long, mixed.
- Duplicate-on-same-product 409 (idempotent reject).
- Adding an EAN that belongs to a *different* product is allowed (the
  ``UNIQUE`` constraint is ``(product_id, ean)``, not ``ean`` alone).
- Delete: cannot delete the only EAN, cannot delete a synced EAN.
- Set-primary on unknown ean_id / pid returns 404.
- Unsync of a non-existent EAN returns 404.

Asserts persisted state where applicable so a half-completed mutation
cannot pass as success (Rule 18).
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
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _get(url):
    return _request("GET", url)


def _post(url, payload):
    return _request("POST", url, payload=payload)


def _delete(url):
    return _request("DELETE", url)


def _patch(url, payload):
    return _request("PATCH", url, payload=payload)


# ===========================================================================
# POST /api/products/<id>/eans — format violations
# ===========================================================================


class TestAddEanFormatViolations:
    """``add_ean`` rejects any string not matching ``^\\d{8,13}$``."""

    def test_too_short_ean_rejected_with_specific_error(
        self, live_url, api_create_product, unique_name
    ):
        """7-digit EAN is rejected with 400 and an EAN-specific message."""
        prod = api_create_product(name=unique_name("EanShort"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": "1234567"}
        )
        assert status == 400, f"Expected 400 for 7-digit EAN: {status} {body}"
        assert "error" in body
        assert "EAN" in body["error"], (
            f"Error must mention 'EAN': {body['error']!r}"
        )
        assert "8-13" in body["error"] or "digit" in body["error"].lower(), (
            f"Error must explain the format constraint: {body['error']!r}"
        )

    def test_too_long_ean_rejected(
        self, live_url, api_create_product, unique_name
    ):
        """14-digit EAN is rejected with 400."""
        prod = api_create_product(name=unique_name("EanLong"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": "1" * 14}
        )
        assert status == 400, f"Expected 400 for 14-digit EAN: {body}"
        assert "EAN" in body.get("error", "")

    def test_non_digit_ean_rejected(
        self, live_url, api_create_product, unique_name
    ):
        """An EAN with letters is rejected even at a valid length."""
        prod = api_create_product(name=unique_name("EanAlpha"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": "12345abc6789"}
        )
        assert status == 400
        assert "EAN" in body.get("error", "")

    def test_empty_ean_rejected(
        self, live_url, api_create_product, unique_name
    ):
        """An empty EAN string is rejected (regex requires ≥ 8 digits)."""
        prod = api_create_product(name=unique_name("EanEmpty"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": ""}
        )
        assert status == 400, f"Expected 400 for empty EAN: {body}"
        assert "EAN" in body.get("error", "")

    def test_whitespace_only_ean_rejected(
        self, live_url, api_create_product, unique_name
    ):
        """Whitespace-only ean strips to empty and is rejected."""
        prod = api_create_product(name=unique_name("EanWhitespace"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": "   \t"}
        )
        assert status == 400
        assert "EAN" in body.get("error", "")

    def test_format_violation_does_not_persist(
        self, live_url, api_create_product, unique_name
    ):
        """A rejected add_ean does not appear in subsequent list_eans call."""
        prod = api_create_product(
            name=unique_name("EanNoPersist"), ean="1000000000001"
        )
        pid = prod["id"]
        _, before = _get(f"{live_url}/api/products/{pid}/eans")
        before_ids = {e["id"] for e in before}

        status, _ = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": "BADFORMAT"}
        )
        assert status == 400

        _, after = _get(f"{live_url}/api/products/{pid}/eans")
        after_ids = {e["id"] for e in after}
        assert before_ids == after_ids, (
            f"Rejected add_ean must not insert a row; before={before_ids}, "
            f"after={after_ids}"
        )


# ===========================================================================
# POST /api/products/<id>/eans — duplicate scenarios
# ===========================================================================


class TestAddEanDuplicateScenarios:
    """409 vs 201 contract for duplicate / cross-product EAN adds."""

    def test_same_ean_same_product_returns_409(
        self, live_url, api_create_product, unique_name
    ):
        """Re-adding the same EAN to the same product returns 409 with the
        canonical ``ean_already_exists`` error string."""
        prod = api_create_product(name=unique_name("DupSame"))
        pid = prod["id"]
        ean = "8800001110001"
        first, first_body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": ean}
        )
        assert first == 201, f"First add must succeed: {first_body}"

        status, body = _post(
            f"{live_url}/api/products/{pid}/eans", {"ean": ean}
        )
        assert status == 409, f"Re-add must return 409: {status} {body}"
        assert body.get("error") == "ean_already_exists", (
            f"Expected canonical error 'ean_already_exists', got: {body}"
        )

    def test_same_ean_different_product_is_allowed(
        self, live_url, api_create_product, unique_name
    ):
        """Adding the same EAN to a *different* product is allowed (the
        UNIQUE constraint is ``(product_id, ean)``).

        Documented to lock in current contract; if this changes in the
        future the duplicate-detection layer needs to evolve in step.
        """
        ean = "8800002220002"
        a = api_create_product(name=unique_name("ProdA"), ean=ean)
        b = api_create_product(name=unique_name("ProdB"), ean="8800002220003")
        b_id = b["id"]

        status, body = _post(
            f"{live_url}/api/products/{b_id}/eans", {"ean": ean}
        )
        assert status == 201, (
            f"Cross-product EAN add should succeed: {status} {body}"
        )
        assert body["ean"] == ean

        # Both products now reference the same EAN string in their lists.
        _, a_eans = _get(f"{live_url}/api/products/{a['id']}/eans")
        _, b_eans = _get(f"{live_url}/api/products/{b_id}/eans")
        assert ean in [e["ean"] for e in a_eans]
        assert ean in [e["ean"] for e in b_eans]

    def test_unknown_product_id_returns_404(self, live_url):
        """Adding an EAN to a non-existent product returns 404."""
        status, body = _post(
            f"{live_url}/api/products/999999/eans", {"ean": "1234567890123"}
        )
        assert status == 404, f"Expected 404: {status} {body}"
        assert "error" in body
        assert "not found" in body["error"].lower()


# ===========================================================================
# DELETE /api/products/<id>/eans/<ean_id> — protection edges
# ===========================================================================


class TestDeleteEanProtection:
    """``delete_ean`` enforces 'cannot delete only EAN' and 'cannot delete
    synced EAN' contracts via 400 responses."""

    def test_cannot_delete_only_ean(
        self, live_url, api_create_product, unique_name
    ):
        """If a product has exactly one EAN, deleting it returns 400."""
        prod = api_create_product(
            name=unique_name("OnlyEan"), ean="7700001110001"
        )
        pid = prod["id"]
        _, eans = _get(f"{live_url}/api/products/{pid}/eans")
        assert len(eans) == 1, "Precondition: product must have exactly 1 EAN"
        only_id = eans[0]["id"]

        status, body = _delete(
            f"{live_url}/api/products/{pid}/eans/{only_id}"
        )
        assert status == 400, f"Expected 400 for sole-EAN delete: {body}"
        assert body.get("error") == "cannot_delete_only_ean", (
            f"Expected 'cannot_delete_only_ean', got: {body}"
        )

        # EAN must still be present afterwards.
        _, eans_after = _get(f"{live_url}/api/products/{pid}/eans")
        assert only_id in [e["id"] for e in eans_after], (
            "EAN must remain after rejected delete"
        )

    def test_delete_unknown_ean_id_returns_404(
        self, live_url, api_create_product, unique_name
    ):
        """A non-existent ean_id on an existing product returns 404."""
        prod = api_create_product(name=unique_name("DelUnknownEan"))
        pid = prod["id"]
        status, body = _delete(
            f"{live_url}/api/products/{pid}/eans/999999"
        )
        assert status == 404
        assert "not found" in body.get("error", "").lower()

    def test_delete_ean_on_unknown_product_returns_404(self, live_url):
        """Unknown pid returns 404, not 500."""
        status, body = _delete(f"{live_url}/api/products/999999/eans/1")
        assert status == 404
        assert "not found" in body.get("error", "").lower()


# ===========================================================================
# PATCH /api/products/<id>/eans/<ean_id>/set-primary
# ===========================================================================


class TestSetPrimaryEanEdges:
    """``set_primary`` 404s on unknown ean_id or pid; success swaps roles."""

    def test_set_primary_swaps_primary_role(
        self, live_url, api_create_product, unique_name
    ):
        """After PATCH the targeted EAN is primary and the previous one is not."""
        prod = api_create_product(
            name=unique_name("SwapPrim"), ean="6600001110001"
        )
        pid = prod["id"]
        _, second_body = _post(
            f"{live_url}/api/products/{pid}/eans",
            {"ean": "6600001110002"},
        )
        new_id = second_body["id"]

        status, body = _patch(
            f"{live_url}/api/products/{pid}/eans/{new_id}/set-primary", {}
        )
        assert status == 200, f"set-primary should succeed: {body}"

        _, eans = _get(f"{live_url}/api/products/{pid}/eans")
        primaries = [e for e in eans if e["is_primary"]]
        assert len(primaries) == 1, (
            f"Exactly one EAN must remain primary; got: {eans}"
        )
        assert primaries[0]["id"] == new_id, (
            f"New EAN {new_id} must be primary; primaries: {primaries}"
        )

    def test_set_primary_unknown_ean_returns_404(
        self, live_url, api_create_product, unique_name
    ):
        """Unknown ean_id on a known product returns 404."""
        prod = api_create_product(name=unique_name("SetPrimUnknown"))
        pid = prod["id"]
        status, body = _patch(
            f"{live_url}/api/products/{pid}/eans/999999/set-primary", {}
        )
        assert status == 404
        assert "not found" in body.get("error", "").lower()

    def test_set_primary_unknown_product_returns_404(self, live_url):
        """Unknown pid returns 404."""
        status, body = _patch(
            f"{live_url}/api/products/999999/eans/1/set-primary", {}
        )
        assert status == 404
        assert "not found" in body.get("error", "").lower()


# ===========================================================================
# POST /api/products/<id>/eans/<ean_id>/unsync
# ===========================================================================


class TestUnsyncEanEdges:
    """``unsync_ean`` 404s on unknown ean_id."""

    def test_unsync_unknown_ean_returns_404(
        self, live_url, api_create_product, unique_name
    ):
        prod = api_create_product(name=unique_name("UnsyncUnknown"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/eans/999999/unsync", {}
        )
        assert status == 404
        assert "not found" in body.get("error", "").lower()

    def test_unsync_never_synced_ean_is_noop_and_returns_200(
        self, live_url, api_create_product, unique_name
    ):
        """Unsyncing an EAN that was never synced is a no-op (returns 200)."""
        prod = api_create_product(
            name=unique_name("UnsyncNever"), ean="5500001110001"
        )
        pid = prod["id"]
        _, eans = _get(f"{live_url}/api/products/{pid}/eans")
        ean_id = eans[0]["id"]
        assert eans[0]["synced_with_off"] is False, (
            "Precondition: EAN must not be synced"
        )

        status, body = _post(
            f"{live_url}/api/products/{pid}/eans/{ean_id}/unsync", {}
        )
        assert status == 200, f"Unsync no-op must return 200: {body}"
        assert body.get("ok") is True

        _, eans_after = _get(f"{live_url}/api/products/{pid}/eans")
        assert eans_after[0]["synced_with_off"] is False, (
            "EAN must remain unsynced after no-op unsync"
        )


# ===========================================================================
# POST /api/products/<id>/unsync — product-level unsync edges
# ===========================================================================


class TestProductUnsyncEdges:
    """``POST /api/products/<id>/unsync`` edge cases."""

    def test_unsync_never_synced_product_returns_200(
        self, live_url, api_create_product, unique_name
    ):
        """Unsyncing a product that was never synced is idempotent."""
        prod = api_create_product(name=unique_name("ProdNeverSync"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/unsync", {}
        )
        assert status == 200, f"Unsync never-synced must succeed: {body}"
        assert body.get("ok") is True

    def test_unsync_after_delete_returns_404(
        self, live_url, api_create_product, unique_name
    ):
        """Unsyncing a deleted product returns 404, not 500."""
        prod = api_create_product(name=unique_name("ProdDeleteUnsync"))
        pid = prod["id"]
        del_status, _ = _delete(f"{live_url}/api/products/{pid}")
        assert del_status == 200

        status, body = _post(f"{live_url}/api/products/{pid}/unsync", {})
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "not found" in body.get("error", "").lower()

    def test_unsync_nonexistent_returns_404(self, live_url):
        """Unknown pid returns 404."""
        status, body = _post(
            f"{live_url}/api/products/9999999/unsync", {}
        )
        assert status == 404
        assert "not found" in body.get("error", "").lower()
