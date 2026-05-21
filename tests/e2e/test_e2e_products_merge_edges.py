"""End-to-end merge edge-case tests for ``POST /api/products/<id>/merge``.

Phase 2B of the LSO-1352 audit: closes merge-endpoint gaps. Notable:

- **Self-merge is now rejected with 400.** Prior to this PR the service
  would silently delete the product because the final ``DELETE FROM
  products WHERE id = source_id`` runs on the same row as the target.
  A guard was added in ``services/product_duplicate.merge_products`` and
  is asserted by ``TestMergeSelf``.
- Non-existent source / target ⇒ 404.
- Source ``source_id`` must be a positive integer ⇒ 400.
- Cross-product EAN already attached: ``INSERT OR IGNORE`` keeps merge
  idempotent; documented here so the behaviour cannot regress.
- After a successful merge with conflicting field values, the target's
  field reflects the user's choice (verified via GET).
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


# ===========================================================================
# Self-merge (target == source) — rejected with 400, target preserved
# ===========================================================================


class TestMergeSelf:
    """Self-merge MUST be rejected with 400 (LSO-1352 regression guard).

    Without the guard added in ``merge_products``, the service would
    happily run ``DELETE FROM products WHERE id = source_id`` and remove
    the product entirely while reporting 200 OK. That is the textbook
    "passes coverage, breaks production" antipattern Rule 18 was written
    to catch.
    """

    def test_self_merge_returns_400(
        self, live_url, api_create_product, unique_name
    ):
        prod = api_create_product(name=unique_name("SelfMerge"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/merge",
            {"source_id": pid, "choices": {}},
        )
        assert status == 400, (
            f"Self-merge must be rejected with 400, got {status}: {body}"
        )
        assert "error" in body
        assert "itself" in body["error"].lower(), (
            f"Error must mention 'itself': {body['error']!r}"
        )

    def test_self_merge_does_not_delete_product(
        self, live_url, api_create_product, unique_name
    ):
        """Critical: the product must still exist after a rejected self-merge."""
        prod = api_create_product(name=unique_name("SelfNoDelete"))
        pid = prod["id"]
        _post(
            f"{live_url}/api/products/{pid}/merge",
            {"source_id": pid, "choices": {}},
        )
        status, body = _get(f"{live_url}/api/products/{pid}")
        assert status == 200, (
            f"Product must still exist after rejected self-merge; "
            f"got {status}: {body}"
        )
        assert body["id"] == pid


# ===========================================================================
# Missing target / source — 404 contract
# ===========================================================================


class TestMergeMissingProducts:
    """Missing target or source must return 404 (not 500)."""

    def test_target_not_found_returns_404(self, live_url, api_create_product):
        """Unknown pid in URL returns 404."""
        source = api_create_product(name="MergeSrcOnly")
        status, body = _post(
            f"{live_url}/api/products/999999/merge",
            {"source_id": source["id"], "choices": {}},
        )
        assert status == 404, (
            f"Unknown target must return 404, got {status}: {body}"
        )
        assert "not found" in body.get("error", "").lower()

    def test_source_not_found_returns_404(
        self, live_url, api_create_product, unique_name
    ):
        """Unknown ``source_id`` in body returns 404."""
        target = api_create_product(name=unique_name("MergeTgtOnly"))
        tid = target["id"]
        status, body = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": 999999, "choices": {}},
        )
        assert status == 404
        assert "source" in body.get("error", "").lower()
        assert "not found" in body.get("error", "").lower()


# ===========================================================================
# Bad source_id payloads — 400 contract
# ===========================================================================


class TestMergeBadSourcePayload:
    """``source_id`` must be a positive integer; everything else ⇒ 400."""

    def test_missing_source_id_returns_400(
        self, live_url, api_create_product, unique_name
    ):
        prod = api_create_product(name=unique_name("MergeMissingSrc"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/merge", {}
        )
        assert status == 400
        assert "source_id" in body.get("error", "").lower()

    def test_string_source_id_returns_400(
        self, live_url, api_create_product, unique_name
    ):
        prod = api_create_product(name=unique_name("MergeStrSrc"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/merge",
            {"source_id": "not_an_int"},
        )
        assert status == 400
        assert "source_id" in body.get("error", "").lower()
        assert "integer" in body.get("error", "").lower()

    def test_null_source_id_returns_400(
        self, live_url, api_create_product, unique_name
    ):
        prod = api_create_product(name=unique_name("MergeNullSrc"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/merge",
            {"source_id": None},
        )
        assert status == 400

    def test_zero_source_id_returns_400(
        self, live_url, api_create_product, unique_name
    ):
        """0 is falsy so the route's ``not source_id`` guard rejects it."""
        prod = api_create_product(name=unique_name("MergeZeroSrc"))
        pid = prod["id"]
        status, body = _post(
            f"{live_url}/api/products/{pid}/merge",
            {"source_id": 0},
        )
        assert status == 400


# ===========================================================================
# Successful merge — verify post-state
# ===========================================================================


class TestMergeSuccessVerification:
    """Successful merges produce the documented post-state."""

    def test_merge_deletes_source_only(
        self, live_url, api_create_product, unique_name
    ):
        """Target survives, source is deleted."""
        target = api_create_product(name=unique_name("TgtSurv"))
        source = api_create_product(name=unique_name("SrcGone"))
        tid, sid = target["id"], source["id"]

        status, body = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {}},
        )
        assert status == 200, f"Merge should succeed: {body}"

        get_tid_status, _ = _get(f"{live_url}/api/products/{tid}")
        get_sid_status, _ = _get(f"{live_url}/api/products/{sid}")
        assert get_tid_status == 200, "Target must still exist"
        assert get_sid_status == 404, "Source must be deleted"

    def test_merge_fills_empty_target_fields_from_source(
        self, live_url, api_create_product, unique_name
    ):
        """Empty target fields are populated from non-empty source values."""
        # Target has no brand; source has a brand
        target = api_create_product(
            name=unique_name("TgtNoBrand"), brand=""
        )
        source = api_create_product(
            name=unique_name("SrcWithBrand"), brand="MergedBrand"
        )
        tid, sid = target["id"], source["id"]

        status, _ = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {}},
        )
        assert status == 200
        _, merged = _get(f"{live_url}/api/products/{tid}")
        assert merged["brand"] == "MergedBrand", (
            f"Empty target brand should pull from source; got: {merged['brand']!r}"
        )

    def test_merge_keeps_target_value_when_both_present(
        self, live_url, api_create_product, unique_name
    ):
        """When both products have a value and no ``choices`` is given, the
        target's value wins (source value is discarded)."""
        target = api_create_product(
            name=unique_name("TgtKeep"), brand="TargetBrand"
        )
        source = api_create_product(
            name=unique_name("SrcDiscard"), brand="SourceBrand"
        )
        tid, sid = target["id"], source["id"]

        status, _ = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {}},
        )
        assert status == 200
        _, merged = _get(f"{live_url}/api/products/{tid}")
        assert merged["brand"] == "TargetBrand", (
            f"Target brand must be preserved when both products had a value; "
            f"got: {merged['brand']!r}"
        )

    def test_merge_choices_override_conflict(
        self, live_url, api_create_product, unique_name
    ):
        """A user choice for a conflicting field takes effect on the target."""
        target = api_create_product(
            name=unique_name("TgtChoice"), brand="TargetBrand"
        )
        source = api_create_product(
            name=unique_name("SrcChoice"), brand="SourceBrand"
        )
        tid, sid = target["id"], source["id"]

        status, _ = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {"brand": "ChosenBrand"}},
        )
        assert status == 200
        _, merged = _get(f"{live_url}/api/products/{tid}")
        assert merged["brand"] == "ChosenBrand", (
            f"User choice must win over both target and source; "
            f"got: {merged['brand']!r}"
        )

    def test_merge_transfers_eans_from_source(
        self, live_url, api_create_product, unique_name
    ):
        """EANs on source are moved to target via INSERT OR IGNORE."""
        target = api_create_product(
            name=unique_name("TgtEan"), ean="4400001110001"
        )
        source = api_create_product(
            name=unique_name("SrcEan"), ean="4400001110002"
        )
        tid, sid = target["id"], source["id"]

        status, _ = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {}},
        )
        assert status == 200

        _, eans = _get(f"{live_url}/api/products/{tid}/eans")
        ean_strings = {e["ean"] for e in eans}
        assert "4400001110001" in ean_strings, "Target's own EAN must remain"
        assert "4400001110002" in ean_strings, (
            f"Source EAN must be transferred to target; got: {ean_strings}"
        )

    def test_merge_with_shared_ean_is_idempotent(
        self, live_url, api_create_product, unique_name
    ):
        """If target and source share an EAN, ``INSERT OR IGNORE`` no-ops and
        the merge succeeds (no UNIQUE-constraint exception bubbles up)."""
        shared = "4400001110010"
        target = api_create_product(
            name=unique_name("TgtShared"), ean=shared
        )
        source_payload = {
            "name": unique_name("SrcShared"),
            "ean": shared,
            "on_duplicate": "allow_duplicate",
        }
        status, source = _post(
            f"{live_url}/api/products", source_payload
        )
        assert status == 201, f"Could not create shared-EAN source: {source}"
        sid = source["id"]
        tid = target["id"]

        status, _ = _post(
            f"{live_url}/api/products/{tid}/merge",
            {"source_id": sid, "choices": {}},
        )
        assert status == 200, "Shared-EAN merge must not raise"

        _, eans = _get(f"{live_url}/api/products/{tid}/eans")
        # Target should still have exactly one row for the shared EAN
        rows_for_shared = [e for e in eans if e["ean"] == shared]
        assert len(rows_for_shared) == 1, (
            f"Shared EAN must collapse to one row on target via INSERT OR "
            f"IGNORE; got: {rows_for_shared}"
        )
