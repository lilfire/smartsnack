"""E2E tests for assigning flags to products.

Settings-side flag CRUD (add/edit/delete a flag definition) is exercised in
``test_flag_crud.py``, but the other half — assigning an existing flag to a
product and confirming that the chip renders + persists across a reload —
had no coverage. Without this test, the link between a flag definition and
its appearance on a product list could silently regress.

These tests assign a freshly-created user flag via the product update API,
re-fetch via the canonical product GET, and then drive the UI to confirm
the chip is actually visible in the expanded product row after a reload.
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_json(live_url: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _put_json(live_url: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _get_json(live_url: str, path: str) -> dict:
    with urllib.request.urlopen(f"{live_url}{path}", timeout=5) as resp:
        return json.loads(resp.read())


def _find_in_list(live_url: str, pid: int) -> dict:
    """Look up a product in ``GET /api/products`` by id.

    Flags are attached to products by ``list_products`` but NOT by the
    single-product ``get_product``. The list endpoint is the canonical
    place to read a product's flags via the API.
    """
    listed = _get_json(live_url, "/api/products")["products"]
    match = next((p for p in listed if p.get("id") == pid), None)
    assert match is not None, (
        f"Product id={pid} missing from /api/products. "
        f"Available ids: {[p.get('id') for p in listed]}"
    )
    return match


def _reload_and_wait(page) -> None:
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_assign_flag_to_product_persists_in_list(page, live_url, api_create_product, unique_name):
    """Assigning a user flag must persist on the product and render a chip after reload.

    Flow:
    1. Define a user flag via POST /api/flags.
    2. Create a product, then PUT /api/products/<pid> with flags=[<name>].
    3. Confirm the product in GET /api/products reports the flag.
    4. Reload the page, expand the row, confirm the rendered flag chip
       (``.flag-badge.flag-user``) is visible and shows the flag's label.

    The list endpoint (not the single-product GET) is the canonical place
    to read a product's flags via the API — ``services.product_crud.list_products``
    attaches flags via ``_get_product_flags`` whereas the single
    ``get_product`` does not.
    """
    flag_name = "is_e2e_assign_flag"
    flag_label = "E2E AssignFlag Label"

    _post_json(
        live_url, "/api/flags", {"name": flag_name, "label": flag_label},
    )

    product_name = unique_name("FlagAssignProd")
    created = api_create_product(name=product_name)
    pid = created["id"]

    update_resp = _put_json(
        live_url, f"/api/products/{pid}", {"flags": [flag_name]},
    )
    assert update_resp.get("ok") is True, (
        f"PUT /api/products/{pid} with flags should return ok=True, got: {update_resp}"
    )

    fetched = _find_in_list(live_url, pid)
    assert flag_name in (fetched.get("flags") or []), (
        f"Flag {flag_name!r} missing from product after assignment. "
        f"flags={fetched.get('flags')!r}"
    )

    # 4. UI assertion — the flag chip must render after reload + expand.
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text=product_name)
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    # The chip is scoped to the row's expanded section. Scope the locator
    # to the product-flags container so we don't accidentally match the
    # settings list elsewhere on the page.
    flag_badge = page.locator(".product-flags .flag-badge.flag-user", has_text=flag_label)
    expect(flag_badge.first).to_be_visible(timeout=5000)

    # And the label text must match exactly — not a substring fallback.
    badge_text = flag_badge.first.inner_text()
    assert flag_label in badge_text, (
        f"Flag chip text should contain {flag_label!r}, got {badge_text!r}"
    )


def test_clear_flag_assignment_removes_chip(page, live_url, api_create_product, unique_name):
    """Clearing a previously-assigned flag must drop it from both the API and the chip render.

    Locks in the second half of the assign/clear cycle. A regression that
    silently dropped flag removals would let the chip linger across reloads
    without us noticing.
    """
    flag_name = "is_e2e_clear_flag"
    flag_label = "E2E ClearFlag Label"

    _post_json(live_url, "/api/flags", {"name": flag_name, "label": flag_label})

    product_name = unique_name("FlagClearProd")
    created = api_create_product(name=product_name)
    pid = created["id"]

    # Assign then immediately clear via the same update endpoint.
    _put_json(live_url, f"/api/products/{pid}", {"flags": [flag_name]})
    _put_json(live_url, f"/api/products/{pid}", {"flags": []})

    fetched = _find_in_list(live_url, pid)
    assert flag_name not in (fetched.get("flags") or []), (
        f"Flag {flag_name!r} should be cleared, but flags={fetched.get('flags')!r}"
    )

    _reload_and_wait(page)
    row = page.locator(".table-row", has_text=product_name)
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    # No chip with this label may remain inside the expanded row.
    chips = page.locator(".product-flags .flag-badge", has_text=flag_label)
    assert chips.count() == 0, (
        f"Expected no flag chips after clear, found {chips.count()}"
    )
