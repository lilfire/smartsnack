"""End-to-end user-journey: OFF search → local product creation chain.

This file covers gap **C** from the LSO-1354 audit matrix (LSO-1352
Phase 2D-3): the user searches Open Food Facts for a product by name or
barcode, picks a candidate from the result list, the modal pre-fills
local fields with the OFF data, and the user saves a new local product.

The "finalise" route in this app is ``POST /api/products`` — the
``/api/off/add-product`` route pushes data BACK to OFF after a local
product already exists, so it is NOT the creation step. The modal calls
``POST /api/products`` with ``from_off: True`` to persist the new row
(see ``static/js/products.js`` and ``static/js/off-utils.js``).

The chain asserted here:

1. ``POST /api/off/search`` returns mocked candidates with the expected
   ``products`` / ``count`` shape (``services.proxy_service.off_search``
   is patched so no real HTTP is made).
2. ``POST /api/products`` with the picked candidate's fields persists
   a real product row and returns ``201`` with the new id.
3. ``GET /api/products`` includes the new product with the EAN, name,
   and nutrition values as persisted.
4. ``GET /api/products/<pid>`` returns the full product including the
   ``is_synced_with_off`` flag because ``from_off: true`` was set.

Rule 18 (assert correctness): each step verifies persisted state via a
DOWNSTREAM route — not just response codes from the route we just hit.
Rule 17 (deterministic): no time-based waits; the patch is synchronous.
Rule 8 (mock shape): ``proxy_service.off_search`` is patched on the
module path. The patched function has the same signature as the real
one and returns the documented ``{"products": [...], "count": N}``
shape so consumers can't drift from the contract.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import patch


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
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"_raw": body.decode("utf-8", errors="replace")}


def _get(url, timeout=5):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# Representative OFF response shape: nutriments use OFF's per-100g keys,
# name/ingredients live under language-suffixed fields, and ``code`` is
# the EAN. See ``proxy_service._OFF_SEARCH_BASE_FIELDS``.
_OFF_CANDIDATE_EAN = "7310865004703"
_OFF_CANDIDATE = {
    "code": _OFF_CANDIDATE_EAN,
    "product_name": "Kvarg Naturell",
    "product_name_no": "Kvarg Naturell",
    "product_name_en": "Quark Plain",
    "brands": "Lindahls",
    "stores": "ICA",
    "ingredients_text": "Pasteurisert melk, melkesyrekultur",
    "ingredients_text_no": "Pasteurisert melk, melkesyrekultur",
    "nutriments": {
        "energy-kcal_100g": 60,
        "fat_100g": 0.2,
        "saturated-fat_100g": 0.1,
        "carbohydrates_100g": 4.0,
        "sugars_100g": 4.0,
        "proteins_100g": 11.0,
        "fiber_100g": 0.0,
        "salt_100g": 0.1,
    },
    "completeness": 0.95,
    "certainty": 95,
    "image_front_url": "https://images.openfoodfacts.org/x.jpg",
    "lang": "no",
}


def test_off_search_to_local_product_creation_chain(live_url, unique_name):
    """Full chain: search OFF, pick the top result, create a local product,
    then verify it appears in the list and detail routes.

    Each step gates the next: if search returns no products, the test
    fails before attempting creation (rather than silently succeeding
    with a hard-coded payload).
    """
    # Use unique name so this test never collides with seed data even
    # before reset_db runs.
    expected_name = unique_name("KvargE2E")
    candidate = {**_OFF_CANDIDATE, "product_name": expected_name,
                 "product_name_no": expected_name}
    category = "Meieri"

    # Seed the target category so add_product accepts the product type.
    status, _ = _post(
        f"{live_url}/api/categories",
        {"name": category, "label": category, "emoji": "\U0001f95b"},
    )
    assert status in (201, 409), (
        f"Category seed must succeed or already exist, got {status}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 1: OFF search — mocked at the service boundary.
    # ──────────────────────────────────────────────────────────────────
    search_response = {"products": [candidate], "count": 1}
    with patch(
        "services.proxy_service.off_search",
        return_value=search_response,
    ) as mock_search:
        status, body = _post(
            f"{live_url}/api/off/search",
            {"q": expected_name},
        )

    assert status == 200, f"Expected 200 from search, got {status}: {body}"
    assert body["count"] == 1, (
        f"Search must return our mocked candidate, got count={body.get('count')}"
    )
    assert body["products"], "Search must return our mocked candidate"
    picked = body["products"][0]
    assert picked["code"] == _OFF_CANDIDATE_EAN, (
        f"Returned candidate must have the expected EAN, got {picked.get('code')!r}"
    )
    # Service was called once with the query — confirms the route wired
    # the user input through unchanged.
    assert mock_search.call_count == 1, (
        f"off_search must be invoked exactly once, got {mock_search.call_count}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 2: persist locally via POST /api/products. This is the route
    # the modal uses to create the new local row from the picked OFF
    # candidate (see static/js/products.js#addProduct → /api/products).
    # ──────────────────────────────────────────────────────────────────
    nutriments = picked["nutriments"]
    create_payload = {
        "name": picked["product_name"],
        "ean": picked["code"],
        "brand": picked["brands"],
        "stores": picked["stores"],
        "ingredients": picked["ingredients_text"],
        "type": category,
        "kcal": nutriments["energy-kcal_100g"],
        "fat": nutriments["fat_100g"],
        "saturated_fat": nutriments["saturated-fat_100g"],
        "carbs": nutriments["carbohydrates_100g"],
        "sugar": nutriments["sugars_100g"],
        "protein": nutriments["proteins_100g"],
        "fiber": nutriments["fiber_100g"],
        "salt": nutriments["salt_100g"],
        "from_off": True,
    }
    status, body = _post(f"{live_url}/api/products", create_payload)
    assert status == 201, (
        f"Create must return 201 with the new product id, got {status}: {body}"
    )
    new_pid = body["id"]
    assert isinstance(new_pid, int) and new_pid > 0, (
        f"Returned id must be a positive int, got {new_pid!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 3: GET /api/products lists the newly-created product. Filter
    # by type to keep the assertion robust against seed data.
    # ──────────────────────────────────────────────────────────────────
    status, listing = _get(
        f"{live_url}/api/products?type={category}&limit=1000"
    )
    assert status == 200, f"Expected 200 from list, got {status}: {listing}"
    products = listing["products"]
    matching = [p for p in products if p["id"] == new_pid]
    assert len(matching) == 1, (
        f"Newly-created product must appear in list exactly once, "
        f"got {len(matching)} rows. listing={products!r}"
    )
    listed = matching[0]
    assert listed["name"] == expected_name, (
        f"Listed name must match what we persisted, "
        f"got {listed['name']!r} expected {expected_name!r}"
    )
    assert listed["ean"] == _OFF_CANDIDATE_EAN, (
        f"Listed EAN must match the OFF candidate, "
        f"got {listed.get('ean')!r}"
    )
    # Nutrition was persisted — sample protein (most distinctive value).
    assert float(listed["protein"]) == 11.0, (
        f"Listed protein must reflect persisted nutrition, "
        f"got {listed.get('protein')!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 4: GET /api/products/<pid> returns the full product as
    # persisted. Note: the detail endpoint returns the raw row only —
    # ``flags`` are attached by the LIST endpoint, so we assert the
    # is_synced_with_off side-effect via ``listed["flags"]`` (Step 3)
    # rather than via the detail row.
    # ──────────────────────────────────────────────────────────────────
    status, detail = _get(f"{live_url}/api/products/{new_pid}")
    assert status == 200, f"Expected 200 from detail, got {status}: {detail}"
    assert detail["id"] == new_pid
    assert detail["name"] == expected_name
    assert detail["brand"] == "Lindahls", (
        f"Brand must round-trip from OFF candidate, got {detail.get('brand')!r}"
    )
    assert detail["stores"] == "ICA"
    assert detail["ingredients"] == "Pasteurisert melk, melkesyrekultur"
    assert detail["type"] == category
    assert detail["ean"] == _OFF_CANDIDATE_EAN, (
        f"Detail EAN must come from product_eans primary row, "
        f"got {detail.get('ean')!r}"
    )
    # Numeric fields are normalised by the API (rounded/typed). The exact
    # value is what we sent, so direct equality is safe.
    assert float(detail["kcal"]) == 60.0
    assert float(detail["sugar"]) == 4.0
    assert float(detail["salt"]) == 0.1
    # from_off=True must have written the is_synced_with_off flag via
    # ``mark_product_synced_with_off``. The listing route's ``flags``
    # column is the canonical surface for this — assert there.
    assert "is_synced_with_off" in listed.get("flags", []), (
        f"from_off=True must set is_synced_with_off; "
        f"listed.flags={listed.get('flags')!r}"
    )


def test_off_search_empty_results_does_not_create_local_product(live_url):
    """Negative chain: if OFF search returns no candidates, the user has
    nothing to pick, and no local product is created. We verify the
    contract: search returns 200 with ``count=0``, and the products list
    remains empty.
    """
    with patch(
        "services.proxy_service.off_search",
        return_value={"products": [], "count": 0},
    ):
        status, body = _post(
            f"{live_url}/api/off/search",
            {"q": "nonexistent-product-xyz"},
        )

    assert status == 200, f"Empty results must still be 200, got {status}: {body}"
    assert body == {"products": [], "count": 0}, (
        f"Empty search must return the documented empty shape, got {body!r}"
    )

    # No product was created — assert via the listing route.
    status, listing = _get(f"{live_url}/api/products?limit=1000")
    assert status == 200
    assert listing["total"] == 0, (
        f"No products should exist after an empty search, "
        f"got total={listing['total']}"
    )


def test_off_search_to_create_persists_secondary_lookup_by_barcode(
    live_url, unique_name
):
    """Variant: after creating from OFF, the EAN-search filter (``search``
    query param) finds the product. This catches a regression where the
    primary EAN row in ``product_eans`` wouldn't be written and the
    barcode-search code path would silently return zero results even
    though the product detail page worked.
    """
    name = unique_name("BarcodeFind")
    ean = "7311111111119"
    candidate = {
        **_OFF_CANDIDATE,
        "code": ean,
        "product_name": name,
        "product_name_no": name,
    }

    # Use an existing seeded category so we don't depend on category seeding.
    status, cats = _get(f"{live_url}/api/categories")
    assert status == 200 and cats, "Expected seeded categories to exist"
    category = cats[0]["name"]

    with patch(
        "services.proxy_service.off_search",
        return_value={"products": [candidate], "count": 1},
    ):
        status, search_body = _post(
            f"{live_url}/api/off/search", {"q": name}
        )

    assert status == 200 and search_body["products"], "Search should return candidate"
    picked = search_body["products"][0]

    nutriments = picked["nutriments"]
    status, create_body = _post(
        f"{live_url}/api/products",
        {
            "name": picked["product_name"],
            "ean": picked["code"],
            "type": category,
            "kcal": nutriments["energy-kcal_100g"],
            "protein": nutriments["proteins_100g"],
            "from_off": True,
        },
    )
    assert status == 201, f"Create must return 201, got {status}: {create_body}"

    # The list route's ``search`` param matches EAN via product_eans —
    # if the EAN wasn't persisted in product_eans, this search returns 0.
    status, listing = _get(f"{live_url}/api/products?search={ean}")
    assert status == 200
    found = [p for p in listing["products"] if p["id"] == create_body["id"]]
    assert len(found) == 1, (
        f"Search by EAN must find the product (proves product_eans row "
        f"was written by add_product), got {len(found)} hits: {listing}"
    )
    assert found[0]["ean"] == ean
