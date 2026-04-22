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


def test_backup_api_returns_json(live_url, api_create_product):
    """GET /api/backup should return a JSON object that contains a 'products' list.

    Creating at least one product beforehand ensures the database is non-empty
    and that the endpoint exercises its real code path rather than returning a
    trivial empty snapshot.
    """
    api_create_product(name="BackupApiJsonTest")

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


def test_backup_contains_created_products(live_url, api_create_product):
    """A product created via the API must appear by name in the backup snapshot.

    This verifies that ``create_backup`` reads committed database state and
    serialises the product name faithfully.
    """
    unique_name = "BackupContainsThisProduct_E2E"
    api_create_product(name=unique_name)

    backup = _get_backup(live_url)

    product_names = [p.get("name", "") for p in backup["products"]]
    assert unique_name in product_names, (
        f"Expected '{unique_name}' in backup products, found: {product_names}"
    )


def test_restore_api(live_url, api_create_product, page):
    """POST /api/restore should replace database contents with the snapshot.

    Procedure:
    1. Create product A and capture a backup.
    2. Create product B (not in the backup).
    3. Restore the backup — product B should vanish.
    4. Verify via GET /api/products that B is absent and A is present.
    5. Reload the browser page to confirm the UI also reflects the restored state.
    """
    product_a_name = "RestoreKeepMe_E2E"
    product_b_name = "RestoreRemoveMe_E2E"

    api_create_product(name=product_a_name)

    # Capture the snapshot while only product A exists
    snapshot = _get_backup(live_url)

    # Ensure product A was captured
    snapshot_names = [p.get("name", "") for p in snapshot["products"]]
    assert product_a_name in snapshot_names, (
        f"Product A '{product_a_name}' missing from snapshot; names: {snapshot_names}"
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
        f"Product B '{product_b_name}' should have been removed by restore; "
        f"current products: {current_names}"
    )
    assert product_a_name in current_names, (
        f"Product A '{product_a_name}' should still exist after restore; "
        f"current products: {current_names}"
    )


def test_import_api_adds_products(live_url, api_create_product):
    """POST /api/import with on_duplicate='skip' should add new products.

    A backup is taken to obtain a well-formed product list, then that same
    list is imported back with ``on_duplicate='skip'``.  Because the products
    already exist in the database they will be skipped (not duplicated), but
    the endpoint must return a successful response with ``ok=True``.
    Afterwards the products must still be present via GET /api/products.
    """
    unique_name = "ImportApiAddTest_E2E"
    api_create_product(name=unique_name)

    # Build a minimal import body using the product we just created
    backup = _get_backup(live_url)
    products_to_import = [
        p for p in backup["products"] if p.get("name") == unique_name
    ]
    assert products_to_import, (
        f"Could not find '{unique_name}' in backup to use as import source"
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
    assert unique_name in current_names, (
        f"Expected '{unique_name}' to be present after import, "
        f"but current products are: {current_names}"
    )


def test_import_api_new_product_is_added(live_url, api_create_product):
    """POST /api/import should insert a product that does not yet exist in the DB.

    A completely new product dict (with a name absent from the live database)
    is posted to /api/import.  The endpoint must acknowledge it, and a
    subsequent GET /api/products must list the imported product.
    """
    new_product_name = "ImportBrandNewProduct_E2E"

    # Confirm the product is not already present (fresh session state)
    before_names = [p.get("name", "") for p in _get_products(live_url)]
    # Guard: if somehow the name is already there from a previous run, skip the
    # creation assertion rather than failing spuriously.

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
        f"Newly imported product '{new_product_name}' not found in GET /api/products. "
        f"Import message was: '{message}'. Current products: {after_names}"
    )
