"""E2E tests for backup, restore, and import API endpoints.

These tests exercise the three HTTP endpoints exposed by the backup blueprint:

- GET  /api/backup  — export the full database as a JSON snapshot
- POST /api/restore — replace the database contents with a snapshot
- POST /api/import  — merge a list of products into the existing database

All requests use ``urllib.request`` to call the live Flask server directly;
no browser interaction is required for these API-level tests.
"""

import json
import urllib.error
import urllib.request

from playwright.sync_api import expect

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_API_KEY_HEADER = {"X-API-Key": "e2e-testing-secret"}


def _get_backup(live_url: str) -> dict:
    """GET /api/backup and return the parsed JSON body.

    Args:
        live_url: Base URL of the running Flask server.

    Returns:
        Parsed backup dictionary containing at least a ``products`` key.
    """
    req = urllib.request.Request(
        f"{live_url}/api/backup",
        headers=_API_KEY_HEADER,
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _post_restore(live_url: str, backup: dict) -> dict:
    """POST /api/restore with a backup payload and return the parsed JSON response.

    Args:
        live_url: Base URL of the running Flask server.
        backup: Full backup dictionary as returned by ``_get_backup``.

    Returns:
        Parsed JSON response from the restore endpoint.
    """
    payload = json.dumps(backup).encode()
    headers = {"Content-Type": "application/json", **_API_KEY_HEADER}
    req = urllib.request.Request(
        f"{live_url}/api/restore",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _post_import(live_url: str, body: dict) -> dict:
    """POST /api/import with the given body and return the parsed JSON response.

    Args:
        live_url: Base URL of the running Flask server.
        body: Dictionary containing ``products`` and optional control keys
            (``match_criteria``, ``on_duplicate``, ``merge_priority``).

    Returns:
        Parsed JSON response from the import endpoint.
    """
    payload = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", **_API_KEY_HEADER}
    req = urllib.request.Request(
        f"{live_url}/api/import",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get_products(live_url: str) -> list:
    """GET /api/products and return the parsed list of product objects.

    Args:
        live_url: Base URL of the running Flask server.

    Returns:
        List of product dictionaries currently stored in the database.
    """
    req = urllib.request.Request(
        f"{live_url}/api/products",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["products"]


def _reload_and_wait(page) -> None:
    """Reload the Playwright page and wait until the product list has settled.

    Args:
        page: Playwright page object.
    """
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_backup_api_returns_json(live_url, api_create_product, unique_name):
    """GET /api/backup should return a JSON object that contains a 'products' list.

    Creating at least one product beforehand ensures the database is non-empty
    and that the endpoint exercises its real code path rather than returning a
    trivial empty snapshot.
    """
    api_create_product(name=unique_name("BackupApiJsonTest"))

    backup = _get_backup(live_url)

    assert isinstance(backup, dict), (
        f"Expected a dict from /api/backup, got {type(backup).__name__}"
    )
    assert "products" in backup, (
        f"'products' key missing from backup response; keys present: {list(backup.keys())}"
    )
    assert isinstance(backup["products"], list), (
        f"'products' should be a list, got {type(backup['products']).__name__}"
    )


def test_backup_contains_created_products(live_url, api_create_product, unique_name):
    """A product created via the API must appear by name in the backup snapshot.

    This verifies that ``create_backup`` reads committed database state and
    serialises the product name faithfully.
    """
    product_name = unique_name("BackupContainsThisProduct_E2E")
    api_create_product(name=product_name)

    backup = _get_backup(live_url)

    product_names = [p.get("name", "") for p in backup["products"]]
    assert product_name in product_names, (
        f"Expected {product_name!r} in backup products, found: {product_names}"
    )


def test_restore_api(live_url, api_create_product, page, unique_name):
    """POST /api/restore should replace database contents with the snapshot.

    Procedure:
    1. Create product A and capture a backup.
    2. Create product B (not in the backup).
    3. Restore the backup — product B should vanish.
    4. Verify via GET /api/products that B is absent and A is present.
    5. Reload the browser page to confirm the UI also reflects the restored state.
    """
    product_a_name = unique_name("RestoreKeepMe_E2E")
    product_b_name = unique_name("RestoreRemoveMe_E2E")

    api_create_product(name=product_a_name)

    # Capture the snapshot while only product A exists
    snapshot = _get_backup(live_url)

    # Ensure product A was captured
    snapshot_names = [p.get("name", "") for p in snapshot["products"]]
    assert product_a_name in snapshot_names, (
        f"Product A {product_a_name!r} missing from snapshot; names: {snapshot_names}"
    )

    # Add product B after the snapshot was taken
    api_create_product(name=product_b_name)

    # Restore the earlier snapshot — product B should be wiped out
    response = _post_restore(live_url, snapshot)
    assert response.get("ok") is True, (
        f"Restore returned ok=False or unexpected error: {response}"
    )

    # The database was rewritten; reload the page so Flask's connection is fresh
    _reload_and_wait(page)

    current_products = _get_products(live_url)
    current_names = [p.get("name", "") for p in current_products]

    assert product_b_name not in current_names, (
        f"Product B {product_b_name!r} should have been removed by restore; "
        f"current products: {current_names}"
    )
    assert product_a_name in current_names, (
        f"Product A {product_a_name!r} should still exist after restore; "
        f"current products: {current_names}"
    )


def test_import_api_adds_products(live_url, api_create_product, unique_name):
    """POST /api/import with on_duplicate='skip' should add new products.

    A backup is taken to obtain a well-formed product list, then that same
    list is imported back with ``on_duplicate='skip'``.  Because the products
    already exist in the database they will be skipped (not duplicated), but
    the endpoint must return a successful response with ``ok=True``.
    Afterwards the products must still be present via GET /api/products.
    """
    product_name = unique_name("ImportApiAddTest_E2E")
    api_create_product(name=product_name)

    # Build a minimal import body using the product we just created
    backup = _get_backup(live_url)
    products_to_import = [
        p for p in backup["products"] if p.get("name") == product_name
    ]
    assert products_to_import, (
        f"Could not find {product_name!r} in backup to use as import source"
    )

    import_body = {
        "products": products_to_import,
        "match_criteria": "both",
        "on_duplicate": "skip",
    }

    response = _post_import(live_url, import_body)
    assert response.get("ok") is True, (
        f"Import returned ok=False or unexpected error: {response}"
    )

    # Confirm the product is still present in the database
    current_products = _get_products(live_url)
    current_names = [p.get("name", "") for p in current_products]
    assert product_name in current_names, (
        f"Expected {product_name!r} to be present after import, "
        f"but current products are: {current_names}"
    )


def test_backup_restore_round_trips_image_data(live_url, api_create_product, unique_name):
    """Image bytes seeded on a product must survive a backup/wipe/restore cycle.

    Backup/restore is the primary data-loss surface in SmartSnack — images
    are stored as base64 data URIs in the SQLite ``image`` column and are
    not deduped or sharded, so a single dropped field silently loses the
    user's photo. The existing tests never seeded an image, so a regression
    in image (un)pickling would slip through. This test:

    1. Creates a product
    2. Attaches a distinctive base64 PNG via PUT /api/products/<pid>/image
    3. Takes a backup
    4. Wipes the product
    5. Restores from the snapshot
    6. Asserts ``GET /api/products/<pid>/image`` returns the *exact* bytes
    """
    name = unique_name("ImageRoundtripProd")
    created = api_create_product(name=name)
    pid = created["id"]

    # 1×1 transparent PNG, base64-encoded as a data URI so the value is
    # both unique and byte-identical to what the UI would upload.
    image_data_uri = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
    )

    set_image_req = urllib.request.Request(
        f"{live_url}/api/products/{pid}/image",
        data=json.dumps({"image": image_data_uri}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(set_image_req, timeout=5) as resp:
        body = json.loads(resp.read())
        assert body.get("ok") is True, f"Image PUT failed: {body}"

    # Capture the backup *after* the image is attached.
    backup = _get_backup(live_url)
    backed_up = next(
        (p for p in backup["products"] if p.get("name") == name), None,
    )
    assert backed_up is not None, (
        f"Product {name!r} missing from backup. Names: "
        f"{[p.get('name') for p in backup['products']]}"
    )
    assert backed_up.get("image") == image_data_uri, (
        f"Backup did not capture image data byte-identical. "
        f"Expected len={len(image_data_uri)}, got len="
        f"{len(backed_up.get('image') or '')}"
    )

    # Wipe the product so we can verify restore actually recreates it.
    delete_req = urllib.request.Request(
        f"{live_url}/api/products/{pid}", method="DELETE",
    )
    with urllib.request.urlopen(delete_req, timeout=5) as resp:
        del_body = json.loads(resp.read())
        assert del_body.get("ok") is True, f"Pre-restore delete failed: {del_body}"

    # Restore from the snapshot.
    response = _post_restore(live_url, backup)
    assert response.get("ok") is True, (
        f"Restore returned ok=False or unexpected error: {response}"
    )

    # The new product won't necessarily have the old id; look it up by name.
    products = _get_products(live_url)
    restored = next((p for p in products if p.get("name") == name), None)
    assert restored is not None, (
        f"Restored product {name!r} not found in /api/products. "
        f"Available: {[p.get('name') for p in products]}"
    )
    restored_pid = restored["id"]

    # Fetch the image via its dedicated endpoint and assert byte-identity.
    img_req = urllib.request.Request(
        f"{live_url}/api/products/{restored_pid}/image", method="GET",
    )
    with urllib.request.urlopen(img_req, timeout=5) as resp:
        img_body = json.loads(resp.read())
    assert img_body.get("image") == image_data_uri, (
        f"Restored image bytes do not match. "
        f"Expected len={len(image_data_uri)}, "
        f"got len={len(img_body.get('image') or '')}"
    )


def test_import_merge_mode_resolves_conflicts(live_url, api_create_product, unique_name):
    """POST /api/import with mode='merge' must honour the merge_priority resolution.

    The merge code path in ``import_service._merge_product`` decides whether
    the imported side or the existing side wins on a field-by-field basis,
    yet it had no direct e2e coverage. Without this test, the merge logic
    could silently regress (e.g. always keep existing, or always overwrite)
    and only get caught by users in production.

    Scenario: an existing unsynced product gets imported with overlapping
    fields under ``merge_priority='use_imported'``. The imported brand and
    nutrition values must replace the originals for the matched product.
    """
    name = unique_name("ImportMergeProd")
    created = api_create_product(
        name=name,
        category="Snacks",
        brand="OriginalBrand",
        stores="OriginalStore",
        kcal=100,
        protein=5,
        fat=3,
    )
    pid = created["id"]

    import_body = {
        "products": [
            {
                "type": "Snacks",
                "name": name,
                "brand": "ImportedBrand",
                "stores": "ImportedStore",
                "kcal": 250,
                "protein": 22,
                "fat": 11,
            }
        ],
        "match_criteria": "name",
        "on_duplicate": "merge",
        "merge_priority": "use_imported",
    }

    response = _post_import(live_url, import_body)
    assert response.get("ok") is True, (
        f"Merge import returned ok=False or error: {response}"
    )

    # Re-fetch the product directly and assert that the imported side won
    # for every overlapping field. We use the dedicated single-product
    # endpoint so the assertions are authoritative.
    with urllib.request.urlopen(
        f"{live_url}/api/products/{pid}", timeout=5,
    ) as resp:
        merged = json.loads(resp.read())

    assert merged.get("brand") == "ImportedBrand", (
        f"merge_priority=use_imported should overwrite brand, "
        f"got {merged.get('brand')!r}"
    )
    assert merged.get("stores") == "ImportedStore", (
        f"merge should overwrite stores, got {merged.get('stores')!r}"
    )
    assert float(merged.get("kcal")) == 250.0, (
        f"merge should overwrite kcal, got {merged.get('kcal')!r}"
    )
    assert float(merged.get("protein")) == 22.0, (
        f"merge should overwrite protein, got {merged.get('protein')!r}"
    )
    assert float(merged.get("fat")) == 11.0, (
        f"merge should overwrite fat, got {merged.get('fat')!r}"
    )

    # Also confirm the keep_existing branch: a separate product where the
    # imported side should *not* win. Brand has values on both sides and
    # neither is synced, so keep_existing must preserve the original.
    name_keep = unique_name("ImportMergeKeep")
    created_keep = api_create_product(
        name=name_keep,
        category="Snacks",
        brand="KeepThisBrand",
        kcal=150,
    )
    pid_keep = created_keep["id"]

    keep_body = {
        "products": [
            {
                "type": "Snacks",
                "name": name_keep,
                "brand": "WouldOverwrite",
                "kcal": 999,
            }
        ],
        "match_criteria": "name",
        "on_duplicate": "merge",
        "merge_priority": "keep_existing",
    }
    keep_resp = _post_import(live_url, keep_body)
    assert keep_resp.get("ok") is True, (
        f"keep_existing merge returned error: {keep_resp}"
    )

    with urllib.request.urlopen(
        f"{live_url}/api/products/{pid_keep}", timeout=5,
    ) as resp:
        kept = json.loads(resp.read())

    assert kept.get("brand") == "KeepThisBrand", (
        f"merge_priority=keep_existing should retain brand, "
        f"got {kept.get('brand')!r}"
    )
    assert float(kept.get("kcal")) == 150.0, (
        f"merge_priority=keep_existing should retain kcal, "
        f"got {kept.get('kcal')!r}"
    )


def test_import_api_new_product_is_added(live_url, api_create_product, unique_name):
    """POST /api/import should insert a product that does not yet exist in the DB.

    A completely new product dict (with a name absent from the live database)
    is posted to /api/import.  The endpoint must acknowledge it, and a
    subsequent GET /api/products must list the imported product.
    """
    new_product_name = unique_name("ImportBrandNewProduct_E2E")

    import_body = {
        "products": [
            {
                "type": "Snacks",
                "name": new_product_name,
                "kcal": 150,
                "protein": 5,
            }
        ],
        "match_criteria": "both",
        "on_duplicate": "skip",
    }

    response = _post_import(live_url, import_body)
    assert response.get("ok") is True, (
        f"Import of new product returned ok=False or error: {response}"
    )

    # The import message should not report the product as skipped when it is new
    message = response.get("message", "")

    after_products = _get_products(live_url)
    after_names = [p.get("name", "") for p in after_products]
    assert new_product_name in after_names, (
        f"Newly imported product {new_product_name!r} not found in GET /api/products. "
        f"Import message was: {message!r}. Current products: {after_names}"
    )
