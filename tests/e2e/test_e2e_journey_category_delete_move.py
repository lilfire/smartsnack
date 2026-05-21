"""End-to-end user-journey: category delete-with-move at API level.

Covers gap **E** from the LSO-1354 audit (LSO-1352 Phase 2D-3): when a
user deletes a category that still has products, they pick a
replacement category and the products are reassigned in a single
transaction.

Implementation note (and test-design note): the audit description
phrases the call as ``DELETE /api/categories/A?move_to=B`` (query
param), but the route at ``blueprints/categories.py::delete_category``
reads ``move_to`` from the JSON request body, not the query string.
The frontend (``static/js/categories-edit.js`` and similar) sends a
JSON body. This test uses the BODY form because that is the actual
contract — a behavioural test must exercise what the code does, not
what the audit prose loosely describes. If the route ever grows query-
param support, add a sibling test; don't change this one.

The chain asserted here:

1. Seed categories ``A`` and ``B``, plus N products in ``A``.
2. ``DELETE /api/categories/A`` with ``{"move_to": "B"}`` → response
   includes ``moved == N``.
3. ``GET /api/categories`` → ``A`` is gone, ``B`` survives, ``B`` shows
   the N products via its ``count``.
4. ``GET /api/products?type=B`` → all N products are now under ``B``.
5. ``GET /api/products?type=A`` → empty list (the route returns 200
   with an empty result, not 404; this is the actual contract).

Rules:
- 17 (deterministic): unique category names per test, no shared state.
- 18 (assertions of correctness): every step verifies persisted state
  via a DOWNSTREAM read, not just the DELETE response.
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


def _delete(url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="DELETE",
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


def _seed_category(live_url, name, label, emoji="\U0001f4e6"):
    status, body = _post(
        f"{live_url}/api/categories",
        {"name": name, "label": label, "emoji": emoji},
    )
    assert status in (201, 409), (
        f"Category seed must succeed (201) or already exist (409), "
        f"got {status}: {body}"
    )


def test_delete_category_with_move_reassigns_all_products(
    live_url, api_create_product, unique_name
):
    """Seed two categories A and B, put N products in A, delete A with
    ``move_to=B``. Verify all N rows moved, A is gone, and the listing
    routes reflect the move.
    """
    cat_a = unique_name("CatA")
    cat_b = unique_name("CatB")
    _seed_category(live_url, cat_a, "Category A")
    _seed_category(live_url, cat_b, "Category B")

    n = 3
    pids = []
    for i in range(n):
        created = api_create_product(
            name=unique_name(f"prodA-{i}"), category=cat_a
        )
        pids.append(created["id"])

    # Pre-state sanity: all N are listed under A, none under B.
    status, listing_a = _get(f"{live_url}/api/products?type={cat_a}&limit=1000")
    assert status == 200
    assert len(listing_a["products"]) == n, (
        f"Setup invariant: A must have {n} products, got "
        f"{len(listing_a['products'])}"
    )
    status, listing_b = _get(f"{live_url}/api/products?type={cat_b}&limit=1000")
    assert status == 200
    assert len(listing_b["products"]) == 0, (
        f"Setup invariant: B must be empty, got "
        f"{len(listing_b['products'])} products"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 2: DELETE A with move_to=B → response.moved == N.
    # ──────────────────────────────────────────────────────────────────
    status, body = _delete(
        f"{live_url}/api/categories/{cat_a}",
        {"move_to": cat_b},
    )
    assert status == 200, f"Delete-with-move must return 200, got {status}: {body}"
    assert body["ok"] is True
    assert body["moved"] == n, (
        f"Response.moved must equal the seeded count {n}, got {body.get('moved')}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 3: GET /api/categories — A is gone, B remains.
    # ──────────────────────────────────────────────────────────────────
    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    names = [c["name"] for c in cats]
    assert cat_a not in names, f"Deleted category must be absent, got {names}"
    assert cat_b in names, f"Target category must remain, got {names}"
    # ``count`` on the category listing reflects how many products now
    # reference it — proving the side-effect via a DIFFERENT route.
    b_row = next(c for c in cats if c["name"] == cat_b)
    assert b_row["count"] == n, (
        f"Target category count must reflect the moved products, "
        f"got {b_row.get('count')} expected {n}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 4: GET /api/products?type=B — all N moved products present.
    # ──────────────────────────────────────────────────────────────────
    status, listing_b = _get(f"{live_url}/api/products?type={cat_b}&limit=1000")
    assert status == 200
    moved_ids = {p["id"] for p in listing_b["products"]}
    assert moved_ids == set(pids), (
        f"All seeded products must now be under B. "
        f"Expected ids {sorted(pids)}, got {sorted(moved_ids)}"
    )
    for p in listing_b["products"]:
        assert p["type"] == cat_b, (
            f"Moved product must have type=={cat_b!r}, got {p['type']!r}"
        )

    # ──────────────────────────────────────────────────────────────────
    # Step 5: GET /api/products?type=A — empty. The route's contract is
    # 200 + empty list (NOT 404) for an unknown ``type`` filter.
    # ──────────────────────────────────────────────────────────────────
    status, listing_a = _get(f"{live_url}/api/products?type={cat_a}&limit=1000")
    assert status == 200, (
        f"Listing with deleted category filter must be 200 (empty), "
        f"got {status}: {listing_a}"
    )
    assert listing_a["products"] == [], (
        f"Deleted category's product list must be empty, got "
        f"{listing_a['products']!r}"
    )
    assert listing_a["total"] == 0


def test_delete_category_without_move_when_populated_returns_400(
    live_url, api_create_product, unique_name
):
    """If a category has products and the request omits ``move_to``, the
    service raises ValueError and the route returns 400 — the category
    must NOT be deleted in that case. This guards against accidental
    data loss.
    """
    cat = unique_name("PopulatedCat")
    _seed_category(live_url, cat, "Populated")
    api_create_product(name=unique_name("prod"), category=cat)

    status, body = _delete(f"{live_url}/api/categories/{cat}")
    assert status == 400, (
        f"Delete without move_to on populated category must be 400, "
        f"got {status}: {body}"
    )
    assert "products still use this category" in body.get("error", ""), (
        f"Error must explain the reason, got {body.get('error')!r}"
    )

    # Side-effect assertion: category MUST still exist, product MUST
    # still belong to it. This proves the failure was a no-op (Rule 18).
    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    names = [c["name"] for c in cats]
    assert cat in names, (
        f"Category must NOT be deleted on validation failure, "
        f"missing from listing: {names}"
    )
    status, listing = _get(f"{live_url}/api/products?type={cat}&limit=1000")
    assert status == 200
    assert listing["total"] == 1, (
        f"Product must still belong to category after rejected delete, "
        f"got total={listing['total']}"
    )


def test_delete_empty_category_without_move_succeeds(live_url, unique_name):
    """An empty category can be deleted without ``move_to``. We seed an
    empty category, delete it, and verify it's gone from the listing.
    """
    cat = unique_name("EmptyCat")
    _seed_category(live_url, cat, "Empty")

    status, body = _delete(f"{live_url}/api/categories/{cat}")
    assert status == 200, (
        f"Empty-category delete must succeed without move_to, "
        f"got {status}: {body}"
    )
    assert body["moved"] == 0

    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200
    names = [c["name"] for c in cats]
    assert cat not in names, (
        f"Deleted empty category must be gone, got {names}"
    )
