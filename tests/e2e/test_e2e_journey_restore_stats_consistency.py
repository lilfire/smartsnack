"""End-to-end user-journey: restore → stats → product-list consistency.

Covers gap **I** from the LSO-1354 audit (LSO-1352 Phase 2D-3): after a
backup-restore round-trip, every read surface (``/api/stats``,
``/api/products``, ``/api/categories``) must report numbers consistent
with the restored payload — not the previous in-memory state, and not
a partial restore.

The chain asserted here:

1. ``GET /api/backup`` snapshots the seeded-empty initial state.
2. Seed N products + M *new* categories via the API.
3. ``GET /api/backup`` snapshots the populated state.
4. ``POST /api/restore`` with the empty snapshot.
5. ``GET /api/stats``, ``GET /api/products``, ``GET /api/categories``
   all reflect the restored empty state.
6. ``POST /api/restore`` with the populated snapshot.
7. Same three read surfaces reflect the populated state.

Implementation notes (what this test does NOT cover, and why):

- The audit prose mentions "T tags" but the backup payload at
  ``services/backup_core.py::create_backup`` does NOT include the
  ``tags`` table. ``restore_backup`` likewise does not delete or
  re-seed tags. Asserting tag counts across a restore would test a
  side-effect that the implementation does not promise. If tag
  persistence-through-restore is ever added, extend this test then.

Rules:
- 17 (deterministic): no time-based waits, no random state — fixed
  seed counts, fixed category names.
- 18 (assertions of correctness): every restore step is verified via
  THREE separate read surfaces, not just the restore response code.
- 16 (test data quality): we test with N=4 products and M=2 new
  categories — enough to distinguish "restored only categories" from
  "restored only products" failure modes.
"""

import json
import urllib.error
import urllib.request


def _post(url, payload, timeout=10):
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


def _get(url, timeout=10, raw=False):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload
            return resp.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _backup(live_url):
    """Fetch a backup payload as parsed JSON. The route returns the
    JSON inside an ``application/json`` body with a
    ``Content-Disposition: attachment`` header — the parsed dict is
    what ``POST /api/restore`` expects on the way back in."""
    status, body = _get(f"{live_url}/api/backup")
    assert status == 200, f"GET /api/backup must return 200, got {status}"
    return body


def _restore(live_url, payload):
    status, body = _post(f"{live_url}/api/restore", payload)
    assert status == 200, (
        f"POST /api/restore must return 200, got {status}: {body}"
    )
    return body


def _seed_category(live_url, name):
    status, body = _post(
        f"{live_url}/api/categories",
        {"name": name, "label": name, "emoji": "\U0001f4e6"},
    )
    assert status in (201, 409), (
        f"seed category must succeed (201) or exist (409), got "
        f"{status}: {body}"
    )


def test_backup_restore_round_trip_keeps_stats_and_listings_consistent(
    live_url, api_create_product, unique_name
):
    """Snapshot empty → seed → snapshot full → restore empty → restore
    full. After every restore, ``/api/stats``, ``/api/products``, and
    ``/api/categories`` must agree with the restored payload.
    """
    # ──────────────────────────────────────────────────────────────────
    # Step 1: snapshot the initial empty state. The conftest fixture
    # ``reset_db`` ensures there are 0 products before this test runs,
    # but the default seed leaves one category ("Snacks") — capture
    # that exactly.
    # ──────────────────────────────────────────────────────────────────
    empty_snapshot = _backup(live_url)
    initial_product_count = len(empty_snapshot["products"])
    initial_category_count = len(empty_snapshot["categories"])
    assert initial_product_count == 0, (
        f"reset_db must leave the DB with 0 products before this test, "
        f"got {initial_product_count}. Backup payload structure may have "
        f"changed."
    )
    assert initial_category_count >= 1, (
        f"Seed must leave at least one category, got "
        f"{initial_category_count}: {empty_snapshot['categories']!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 2: seed M=2 new categories and N=4 products spread across
    # them. Mixing distinct categories lets us assert ``type_counts``
    # post-restore — a single category wouldn't catch a "merged all
    # products into one type" bug.
    # ──────────────────────────────────────────────────────────────────
    cat_a = unique_name("RestoreCatA")
    cat_b = unique_name("RestoreCatB")
    _seed_category(live_url, cat_a)
    _seed_category(live_url, cat_b)

    seeded_pids: list[int] = []
    for i in range(2):
        c = api_create_product(name=unique_name(f"P-A{i}"), category=cat_a)
        seeded_pids.append(c["id"])
    for i in range(2):
        c = api_create_product(name=unique_name(f"P-B{i}"), category=cat_b)
        seeded_pids.append(c["id"])

    expected_total_products = len(seeded_pids)
    expected_total_categories = initial_category_count + 2

    # Sanity check intermediate state via stats — proves the seed worked
    # BEFORE we take the second snapshot. If the seed silently fails,
    # we don't want to record an "empty" snapshot here and confuse the
    # downstream assertions.
    status, stats = _get(f"{live_url}/api/stats")
    assert status == 200
    assert stats["total"] == expected_total_products, (
        f"Pre-snapshot stats must reflect seed: total={expected_total_products}, "
        f"got {stats['total']}. type_counts={stats.get('type_counts')!r}"
    )
    assert stats["types"] == expected_total_categories, (
        f"Pre-snapshot category count must be {expected_total_categories}, "
        f"got {stats['types']}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 3: snapshot the populated state. This is the payload we'll
    # restore back in step 6.
    # ──────────────────────────────────────────────────────────────────
    populated_snapshot = _backup(live_url)
    assert len(populated_snapshot["products"]) == expected_total_products
    populated_category_names = {c["name"] for c in populated_snapshot["categories"]}
    assert cat_a in populated_category_names
    assert cat_b in populated_category_names

    # ──────────────────────────────────────────────────────────────────
    # Step 4: restore the EMPTY snapshot. The DB should snap back to the
    # initial seed state (Snacks only, 0 products).
    # ──────────────────────────────────────────────────────────────────
    msg = _restore(live_url, empty_snapshot)
    assert "0" in msg["message"], (
        f"Restore message must report 0 products restored, got {msg!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 5: verify three read surfaces all reflect empty.
    # ──────────────────────────────────────────────────────────────────
    status, stats = _get(f"{live_url}/api/stats")
    assert status == 200
    assert stats["total"] == 0, (
        f"After empty restore, stats.total must be 0, got {stats['total']}"
    )
    assert stats["types"] == initial_category_count, (
        f"After empty restore, only initial categories must remain, "
        f"got types={stats['types']}, expected {initial_category_count}"
    )
    assert stats["type_counts"] == {}, (
        f"After empty restore, no category has any product, got "
        f"type_counts={stats['type_counts']!r}"
    )

    status, listing = _get(f"{live_url}/api/products?limit=1000")
    assert status == 200
    assert listing["total"] == 0
    assert listing["products"] == [], (
        f"After empty restore, product list must be empty, got "
        f"{listing['products']!r}"
    )

    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    assert len(cats) == initial_category_count, (
        f"After empty restore, category count must match initial, got "
        f"{len(cats)} vs expected {initial_category_count}"
    )
    cat_names = {c["name"] for c in cats}
    assert cat_a not in cat_names, (
        f"Seeded category {cat_a!r} must be gone after restore, "
        f"got {sorted(cat_names)}"
    )
    assert cat_b not in cat_names

    # ──────────────────────────────────────────────────────────────────
    # Step 6: restore the POPULATED snapshot. DB returns to N=4 products
    # across M+1=3 categories.
    # ──────────────────────────────────────────────────────────────────
    msg = _restore(live_url, populated_snapshot)
    assert str(expected_total_products) in msg["message"], (
        f"Restore message must report {expected_total_products} products, "
        f"got {msg!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 7: verify three read surfaces all reflect the populated state.
    # ──────────────────────────────────────────────────────────────────
    status, stats = _get(f"{live_url}/api/stats")
    assert status == 200
    assert stats["total"] == expected_total_products, (
        f"After populated restore, stats.total must be {expected_total_products}, "
        f"got {stats['total']}"
    )
    assert stats["types"] == expected_total_categories, (
        f"After populated restore, category count must be "
        f"{expected_total_categories}, got {stats['types']}"
    )
    # type_counts must show 2 products per seeded category.
    assert stats["type_counts"].get(cat_a) == 2, (
        f"After populated restore, cat_a must have 2 products, got "
        f"{stats['type_counts']!r}"
    )
    assert stats["type_counts"].get(cat_b) == 2, (
        f"After populated restore, cat_b must have 2 products, got "
        f"{stats['type_counts']!r}"
    )

    status, listing = _get(f"{live_url}/api/products?limit=1000")
    assert status == 200
    assert listing["total"] == expected_total_products
    listed_types = {p["type"] for p in listing["products"]}
    assert listed_types == {cat_a, cat_b}, (
        f"Restored products must keep their original categories, got "
        f"{sorted(listed_types)} vs expected {sorted([cat_a, cat_b])}"
    )

    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    cat_names = {c["name"] for c in cats}
    assert cat_a in cat_names, (
        f"Restored categories must include {cat_a!r}, got {sorted(cat_names)}"
    )
    assert cat_b in cat_names
    # The category's ``count`` field on /api/categories also reflects the
    # restored row count — another downstream surface (Rule 18).
    cat_a_row = next(c for c in cats if c["name"] == cat_a)
    assert cat_a_row["count"] == 2, (
        f"/api/categories must report cat_a count=2 after restore, got "
        f"{cat_a_row['count']!r}"
    )


def test_restore_replaces_categories_and_products_atomically(
    live_url, api_create_product, unique_name
):
    """A restore must REPLACE existing categories, not merge them. We
    pre-seed a category that is NOT in the snapshot, then restore an
    empty snapshot, and assert the pre-seeded category is gone.

    This catches a regression where restore_backup would leave stale
    categories in place if they happened not to appear in the payload —
    leading to an "I deleted this last week but it's still in my list"
    bug.
    """
    empty_snapshot = _backup(live_url)
    initial_categories = {c["name"] for c in empty_snapshot["categories"]}

    new_cat = unique_name("EphemeralCat")
    _seed_category(live_url, new_cat)
    # Confirm seed via category route.
    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    assert new_cat in {c["name"] for c in cats}

    _restore(live_url, empty_snapshot)

    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    after_names = {c["name"] for c in cats}
    assert new_cat not in after_names, (
        f"Categories not in the restored snapshot must be removed, "
        f"got {sorted(after_names)}"
    )
    assert after_names == initial_categories, (
        f"Category set after restore must exactly match the snapshot, "
        f"got {sorted(after_names)} vs expected {sorted(initial_categories)}"
    )


def test_restore_invalid_payload_returns_400(live_url):
    """A bad restore payload (missing ``products`` key) must be rejected
    with 400 — and the existing DB state must be untouched.

    This is Rule 18 applied to negative paths: a failed restore must
    NOT silently wipe the user's data.
    """
    # Pre-state: snapshot current DB so we can assert no change.
    before = _backup(live_url)

    status, body = _post(
        f"{live_url}/api/restore", {"version": "1.0"}  # no "products"
    )
    assert status == 400, (
        f"Invalid backup payload must return 400, got {status}: {body}"
    )
    assert body.get("error"), "400 response must carry an error message"

    # Post-state: snapshot again, structure must match the pre-state.
    after = _backup(live_url)
    assert len(after["products"]) == len(before["products"]), (
        f"Failed restore must not modify product count: "
        f"before={len(before['products'])}, after={len(after['products'])}"
    )
    assert len(after["categories"]) == len(before["categories"]), (
        f"Failed restore must not modify categories: "
        f"before={len(before['categories'])}, after={len(after['categories'])}"
    )
