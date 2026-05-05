"""E2E tests for EAN management UI and API (P2 gap #23).

Tests:
- EAN list API returns the EAN created with the product
- EAN add via API
- EAN set-primary via API (unconditional — always asserts)
- EAN delete via API (unconditional — always asserts)
- EAN manager is visible in the edit form
- EAN value and primary badge are displayed
"""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _expand_and_edit(page, product_name):
    """Click a product row to expand it, then click the edit button."""
    row = page.locator(".table-row", has_text=product_name)
    row.first.click()
    page.wait_for_timeout(300)

    # [data-action='start-edit'] lives in the sibling .expanded div, not
    # inside .table-row, so use a page-scoped locator.
    edit_btn = page.locator("[data-action='start-edit']").first
    edit_btn.click()
    # Wait for the edit form to be present instead of a fixed delay.
    page.wait_for_selector(".edit-form", state="visible", timeout=5000)


def _post_json(live_url, path, payload):
    """POST JSON to the API and return the parsed response body."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# API tests — all assertions are unconditional
# ---------------------------------------------------------------------------


def test_ean_list_api_returns_list(live_url, api_create_product):
    """GET /api/products/{id}/eans returns a list containing the product's EAN."""
    product = api_create_product(name="EANListProd", ean="1234567890123")
    product_id = product["id"]

    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert isinstance(body, list), (
        f"Expected a JSON list from /eans, got {type(body).__name__}: {body}"
    )
    assert len(body) >= 1, (
        f"Expected at least one EAN in list (product was created with EAN), got: {body}"
    )
    ean_values = [item["ean"] for item in body]
    assert "1234567890123" in ean_values, (
        f"Expected EAN '1234567890123' in list, got: {ean_values}"
    )


def test_ean_add_api_returns_ean_object(live_url, api_create_product):
    """POST /api/products/{id}/eans adds a new EAN and returns it with id and ean fields."""
    product = api_create_product(name="EANAddProd")
    product_id = product["id"]

    body = _post_json(live_url, f"/api/products/{product_id}/eans", {"ean": "9876543210987"})

    assert "id" in body, f"Expected 'id' in EAN add response, got: {body}"
    assert "ean" in body, f"Expected 'ean' in EAN add response, got: {body}"
    assert body["ean"] == "9876543210987", (
        f"Expected ean='9876543210987' in response, got: {body['ean']!r}"
    )


def test_ean_set_primary_api(live_url, api_create_product):
    """PATCH /api/products/{id}/eans/{eanId}/set-primary sets the specified EAN as primary."""
    product = api_create_product(name="EANPrimaryProd", ean="1111111111111")
    product_id = product["id"]

    # Add a second EAN — this call must succeed for the test to be meaningful
    new_ean = _post_json(
        live_url,
        f"/api/products/{product_id}/eans",
        {"ean": "1111111111112"},
    )
    ean_id = new_ean["id"]

    # Set the second EAN as primary
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans/{ean_id}/set-primary",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert body.get("ok") is True, (
        f"Expected ok=True from set-primary, got: {body}"
    )

    # Verify the EAN list now reflects the new primary
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        eans = json.loads(resp.read())

    primary_eans = [e for e in eans if e.get("is_primary")]
    assert len(primary_eans) == 1, (
        f"Expected exactly one primary EAN after set-primary, got: {primary_eans}"
    )
    assert primary_eans[0]["id"] == ean_id, (
        f"Expected EAN id={ean_id} to be primary, got id={primary_eans[0]['id']}"
    )


def test_ean_delete_api(live_url, api_create_product):
    """DELETE /api/products/{id}/eans/{eanId} removes the specified non-primary EAN."""
    product = api_create_product(name="EANDeleteProd", ean="2222222222222")
    product_id = product["id"]

    # Add a second EAN so there is something to delete without removing the only EAN
    added_ean = _post_json(
        live_url,
        f"/api/products/{product_id}/eans",
        {"ean": "3333333333333"},
    )
    ean_to_delete = added_ean["id"]

    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans/{ean_to_delete}",
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert body.get("ok") is True, (
        f"Expected ok=True from EAN delete, got: {body}"
    )

    # Verify the EAN is actually gone
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        eans = json.loads(resp.read())

    remaining_ids = [e["id"] for e in eans]
    assert ean_to_delete not in remaining_ids, (
        f"Deleted EAN id={ean_to_delete} still appears in list: {remaining_ids}"
    )


def test_ean_delete_only_ean_returns_error(live_url, api_create_product):
    """DELETE on the only EAN should return a 4xx error, not silently succeed."""
    product = api_create_product(name="EANDeleteOnlyProd", ean="4444444444444")
    product_id = product["id"]

    # Get the EAN id for the single EAN
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        eans = json.loads(resp.read())

    only_ean_id = eans[0]["id"]

    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/eans/{only_ean_id}",
        method="DELETE",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError(
            "Expected an error when deleting the only EAN, but request succeeded"
        )
    except urllib.error.HTTPError as exc:
        assert exc.code in (400, 409), (
            f"Expected 400 or 409 when deleting only EAN, got {exc.code}"
        )
        body = json.loads(exc.read())
        assert "error" in body, (
            f"Expected 'error' key in response, got: {body}"
        )


# ---------------------------------------------------------------------------
# UI tests — all assertions are unconditional
# ---------------------------------------------------------------------------


def test_ean_manager_container_visible_in_edit(page, api_create_product):
    """The ean-manager-{id} container must be visible inside the edit form."""
    product = api_create_product(name="EANManagerUIProd", ean="5555555555555")
    product_id = product["id"]
    _reload_and_wait(page)

    _expand_and_edit(page, "EANManagerUIProd")

    ean_manager = page.locator(f"#ean-manager-{product_id}")
    expect(ean_manager).to_be_visible(timeout=5000)


def test_ean_value_displayed_in_manager(page, api_create_product):
    """The EAN value text must appear inside the EAN manager list."""
    api_create_product(name="EANValueProd", ean="6666666666666")
    _reload_and_wait(page)

    _expand_and_edit(page, "EANValueProd")

    # Wait for the EAN manager to load its async content
    page.wait_for_selector(".ean-value", state="visible", timeout=5000)

    ean_value = page.locator(".ean-value").first
    expect(ean_value).to_be_visible(timeout=5000)
    text = ean_value.inner_text()
    assert "6666666666666" in text, (
        f"Expected EAN '6666666666666' in .ean-value text, got: '{text}'"
    )


def test_ean_primary_badge_visible(page, api_create_product):
    """The primary EAN badge (.ean-badge-primary) must be visible in the edit form."""
    api_create_product(name="EANBadgeProd", ean="7777777777777")
    _reload_and_wait(page)

    _expand_and_edit(page, "EANBadgeProd")

    page.wait_for_selector(".ean-badge-primary", state="visible", timeout=5000)
    badge = page.locator(".ean-badge-primary").first
    expect(badge).to_be_visible(timeout=5000)


def test_ean_add_input_present_in_manager(page, api_create_product):
    """The EAN add-input field must be present in the EAN manager."""
    product = api_create_product(name="EANAddInputProd", ean="8888888888888")
    product_id = product["id"]
    _reload_and_wait(page)

    _expand_and_edit(page, "EANAddInputProd")

    add_input = page.locator(f"#ean-add-input-{product_id}")
    expect(add_input).to_be_visible(timeout=5000)
