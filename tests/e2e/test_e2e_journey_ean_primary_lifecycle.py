"""End-to-end user-journey: EAN add → set-primary → delete-old-primary.

Covers gap **G** from the LSO-1354 audit (LSO-1352 Phase 2D-3): the
multi-EAN flow where a user adds a second barcode to a product,
promotes the new one to primary, and deletes the original primary —
ensuring the system never strips the product of its last EAN and the
``products.ean`` denormalised column stays in sync with the
``product_eans`` table.

The chain asserted here:

1. Seed a product with one primary EAN ``E1``.
2. ``POST /api/products/<pid>/eans`` adds ``E2`` as non-primary.
3. ``PATCH /api/products/<pid>/eans/<E2-id>/set-primary`` promotes
   ``E2``; ``E1`` becomes non-primary.
4. ``GET /api/products/<pid>/eans`` — exactly one row has
   ``is_primary=True`` and it's ``E2``.
5. ``DELETE /api/products/<pid>/eans/<E1-id>`` removes the demoted
   former-primary EAN.
6. ``GET /api/products/<pid>/eans`` — exactly one EAN survives and it
   is primary (``E2``).
7. Cross-route check: ``GET /api/products/<pid>`` shows the
   denormalised ``ean`` column matches ``E2`` (the primary), proving
   the SQL `UPDATE products SET ean = ...` ran inside set-primary.

Rules:
- 17 (deterministic): no time-based waits; each route call is
  synchronous and ordered.
- 18 (assertions of correctness): every step verifies via a downstream
  read. Counts and ``is_primary`` flags are asserted, not just response
  codes.
"""

import json
import urllib.error
import urllib.request


def _post(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _patch(url, timeout=5):
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _delete(url, timeout=5):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}, method="DELETE"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(url, timeout=5):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


E1 = "7311111111111"  # original primary
E2 = "7311111111128"  # added, then promoted to primary


def _find_ean(rows, ean):
    """Return the row whose ``ean`` field matches, or raise."""
    matches = [r for r in rows if r["ean"] == ean]
    assert len(matches) == 1, (
        f"Expected exactly one row for EAN {ean!r}, got {len(matches)}: {rows!r}"
    )
    return matches[0]


def test_ean_add_promote_delete_old_primary_lifecycle(live_url, api_create_product):
    """Full primary-EAN lifecycle: start with E1, add E2, promote E2,
    delete E1. Asserts persistence and denormalisation at every step.
    """
    # Step 1: seed product with E1 as primary.
    created = api_create_product(name="EAN-G-target", ean=E1)
    pid = created["id"]

    # Sanity: the seeded product has exactly one EAN, and it's primary.
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200, f"Initial EAN list must return 200, got {status}"
    assert len(eans) == 1, (
        f"Seeded product must start with one EAN, got {len(eans)}: {eans}"
    )
    e1_row = eans[0]
    assert e1_row["ean"] == E1
    assert e1_row["is_primary"] is True
    e1_id = e1_row["id"]

    # Sanity: products.ean (denormalised) == primary EAN.
    status, prod = _get(f"{live_url}/api/products/{pid}")
    assert status == 200 and prod["ean"] == E1, (
        f"products.ean must mirror the primary EAN at seed, got {prod.get('ean')!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 2: POST add E2.
    # ──────────────────────────────────────────────────────────────────
    status, add_body = _post(
        f"{live_url}/api/products/{pid}/eans", {"ean": E2}
    )
    assert status == 201, (
        f"POST EAN must return 201 with the new row, got {status}: {add_body}"
    )
    assert add_body["ean"] == E2
    # Newly-added secondary EAN must NOT auto-promote to primary.
    assert add_body["is_primary"] is False, (
        f"Adding a 2nd EAN to a product with a primary must not promote "
        f"the new one. Got is_primary={add_body['is_primary']!r}"
    )
    e2_id = add_body["id"]

    # Downstream read: both EANs present, E1 still primary.
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    assert len(eans) == 2, f"Expected 2 EANs after add, got {len(eans)}: {eans}"
    primary_rows = [r for r in eans if r["is_primary"]]
    assert len(primary_rows) == 1, (
        f"Exactly one EAN must be primary, got {len(primary_rows)}: {eans}"
    )
    assert primary_rows[0]["ean"] == E1, (
        f"E1 must remain primary after adding E2, primary={primary_rows[0]['ean']!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 3: PATCH /set-primary on E2.
    # ──────────────────────────────────────────────────────────────────
    status, body = _patch(
        f"{live_url}/api/products/{pid}/eans/{e2_id}/set-primary"
    )
    assert status == 200, f"set-primary must return 200, got {status}: {body}"

    # ──────────────────────────────────────────────────────────────────
    # Step 4: list-EAN shows E2.is_primary=True, E1.is_primary=False.
    # ──────────────────────────────────────────────────────────────────
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    e2_row = _find_ean(eans, E2)
    e1_row = _find_ean(eans, E1)
    assert e2_row["is_primary"] is True, (
        f"E2 must be primary after promote, got is_primary={e2_row['is_primary']!r}"
    )
    assert e1_row["is_primary"] is False, (
        f"E1 must be demoted after promote, got is_primary={e1_row['is_primary']!r}"
    )
    primary_rows = [r for r in eans if r["is_primary"]]
    assert len(primary_rows) == 1, (
        f"Exactly one EAN must be primary, got {len(primary_rows)}: {eans}"
    )

    # Denormalisation check: products.ean now mirrors E2.
    status, prod = _get(f"{live_url}/api/products/{pid}")
    assert status == 200 and prod["ean"] == E2, (
        f"products.ean must follow primary promotion to E2, got {prod.get('ean')!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 5: DELETE old (demoted) primary E1.
    # ──────────────────────────────────────────────────────────────────
    status, body = _delete(f"{live_url}/api/products/{pid}/eans/{e1_id}")
    assert status == 200, (
        f"Deleting the demoted EAN must succeed (it is no longer primary "
        f"and not synced-with-off), got {status}: {body}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 6: exactly one EAN survives, it is primary, and it is E2.
    # ──────────────────────────────────────────────────────────────────
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    assert len(eans) == 1, (
        f"Exactly one EAN must remain after E1 delete, got {len(eans)}: {eans}"
    )
    survivor = eans[0]
    assert survivor["ean"] == E2
    assert survivor["is_primary"] is True, (
        f"Surviving EAN must be primary, got {survivor!r}"
    )

    # Step 7: denormalised products.ean still points to E2.
    status, prod = _get(f"{live_url}/api/products/{pid}")
    assert status == 200 and prod["ean"] == E2, (
        f"products.ean must still mirror E2 after E1 deletion, got "
        f"{prod.get('ean')!r}"
    )


def test_cannot_delete_only_remaining_ean(live_url, api_create_product):
    """The "primary fallback" lifecycle relies on the invariant: a
    product cannot have zero EANs. If the user tries to delete the only
    EAN, the service raises ValueError → 400 and the EAN survives.

    This is the underlying guarantee that makes Journey G safe — without
    it, deleting the primary would leave the product unreachable from
    the EAN-search code path.
    """
    created = api_create_product(name="EAN-G-onlyean", ean=E1)
    pid = created["id"]

    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert len(eans) == 1
    only_id = eans[0]["id"]

    status, body = _delete(f"{live_url}/api/products/{pid}/eans/{only_id}")
    assert status == 400, (
        f"Deleting the only EAN must be rejected with 400, got {status}: {body}"
    )
    assert body["error"] == "cannot_delete_only_ean", (
        f"Error code must be 'cannot_delete_only_ean', got {body.get('error')!r}"
    )

    # Side-effect assertion: the EAN must still exist (Rule 18).
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    assert len(eans) == 1, (
        f"Failed delete must NOT have removed anything, got {len(eans)} EANs"
    )
    assert eans[0]["ean"] == E1


def test_set_primary_then_re_promote_old_primary_round_trips(
    live_url, api_create_product
):
    """A user who changes their mind and promotes the original EAN
    again must end up in the same denormalised state they started in.
    This guards against a state machine that only handles "first
    promotion" correctly.
    """
    created = api_create_product(name="EAN-G-roundtrip", ean=E1)
    pid = created["id"]

    # Add E2 and promote.
    status, e2_body = _post(
        f"{live_url}/api/products/{pid}/eans", {"ean": E2}
    )
    assert status == 201
    e2_id = e2_body["id"]
    status, _ = _patch(f"{live_url}/api/products/{pid}/eans/{e2_id}/set-primary")
    assert status == 200

    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    e1_id = _find_ean(eans, E1)["id"]

    # Promote E1 back.
    status, _ = _patch(f"{live_url}/api/products/{pid}/eans/{e1_id}/set-primary")
    assert status == 200

    # Round-trip: state matches the seed (E1 primary, E2 secondary).
    status, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    assert _find_ean(eans, E1)["is_primary"] is True
    assert _find_ean(eans, E2)["is_primary"] is False
    status, prod = _get(f"{live_url}/api/products/{pid}")
    assert status == 200 and prod["ean"] == E1
