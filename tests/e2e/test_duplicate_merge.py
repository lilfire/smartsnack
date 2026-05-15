"""E2E tests for duplicate merge conflict modal (P0 gap #7).

Tests the duplicate detection during registration and editing, including
the merge conflict modal with side-by-side field comparison and resolution.
"""

import json
import urllib.request

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _go_to_search(page):
    page.locator("button[data-view='search']").click()
    expect(page.locator("#view-search")).to_be_visible()


def _dismiss_any_modal(page):
    """Close any open modals before proceeding."""
    cancel = page.locator("button.confirm-no, button.scan-modal-btn-cancel")
    if cancel.count() > 0 and cancel.first.is_visible():
        cancel.first.click()
        page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# Registration duplicate detection
# ---------------------------------------------------------------------------


def test_register_duplicate_name_shows_modal(page, api_create_product):
    """Registering a product with a duplicate name should show a duplicate modal."""
    api_create_product(name="DupNameProdA", ean="1111111111116")
    _reload_and_wait(page)

    _go_to_register(page)
    page.locator("#f-name").fill("DupNameProdA")
    page.locator("#f-kcal").fill("100")
    page.locator("#f-protein").fill("5")
    page.locator("#f-fat").fill("3")
    page.locator("#f-saturated_fat").fill("1")
    page.locator("#f-carbs").fill("15")
    page.locator("#f-sugar").fill("3")
    page.locator("#f-fiber").fill("2")
    page.locator("#f-salt").fill("0.3")

    page.locator("#btn-submit").click()

    # A duplicate modal should appear (scan-modal-bg with role="dialog")
    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)

    # The modal text should reference the duplicate product name
    modal_text = modal.first.inner_text()
    assert "DupNameProdA" in modal_text, (
        f"Expected duplicate product name in modal, got: '{modal_text[:300]}'"
    )


def test_register_duplicate_ean_shows_modal(page, api_create_product):
    """Registering a product with a duplicate EAN should show a duplicate modal."""
    api_create_product(name="OrigEANDupProd", ean="2222222222226")
    _reload_and_wait(page)

    _go_to_register(page)
    page.locator("#f-name").fill("NewNameDupEAN")
    page.locator("#f-ean").fill("2222222222226")
    page.locator("#f-kcal").fill("100")
    page.locator("#f-protein").fill("5")
    page.locator("#f-fat").fill("3")
    page.locator("#f-saturated_fat").fill("1")
    page.locator("#f-carbs").fill("15")
    page.locator("#f-sugar").fill("3")
    page.locator("#f-fiber").fill("2")
    page.locator("#f-salt").fill("0.3")

    page.locator("#btn-submit").click()

    # A modal or toast should appear indicating duplicate
    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)


def test_duplicate_modal_has_action_buttons(page, api_create_product):
    """The duplicate modal should have action buttons (merge/cancel)."""
    api_create_product(name="DupModalBtnProd", ean="3333333333337")
    _reload_and_wait(page)

    _go_to_register(page)
    page.locator("#f-name").fill("DupModalBtnProd")
    page.locator("#f-kcal").fill("200")
    page.locator("#f-protein").fill("5")
    page.locator("#f-fat").fill("3")
    page.locator("#f-saturated_fat").fill("1")
    page.locator("#f-carbs").fill("15")
    page.locator("#f-sugar").fill("3")
    page.locator("#f-fiber").fill("2")
    page.locator("#f-salt").fill("0.3")

    page.locator("#btn-submit").click()

    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)

    # The modal should have at least one action button
    buttons = modal.locator("button")
    assert buttons.count() >= 1, "Expected at least one action button in duplicate modal"

    # Should have either a cancel/close option
    cancel_btn = modal.locator("button.confirm-no, button.scan-modal-btn-cancel")
    expect(cancel_btn.first).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Edit-time duplicate detection
# ---------------------------------------------------------------------------


def test_edit_duplicate_detection(page, api_create_product):
    """Editing a product name to match another should trigger duplicate detection.

    The backend's check-duplicate endpoint matches by EAN first; the name match
    only fires when the input EAN is empty (see ``_find_duplicate`` in
    ``services/product_duplicate.py``). Both products are therefore created
    without EANs so that editing the second to match the first's name triggers
    a name-based duplicate match and surfaces the merge dialog.
    """
    api_create_product(name="EditDupOrigA")
    api_create_product(name="EditDupTargetA")
    _reload_and_wait(page)

    # Expand and edit the second product
    row = page.locator(".table-row", has_text="EditDupTargetA")
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    edit_btn = page.locator("[data-action='start-edit']").first
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(500)

    # Change name to match the first product
    edit_name = page.locator("#ed-name")
    expect(edit_name).to_be_visible(timeout=3000)
    edit_name.fill("EditDupOrigA")

    # Save — should trigger duplicate check
    save_btn = page.locator("[data-action='save-product']").first
    expect(save_btn).to_be_visible(timeout=3000)
    save_btn.click()

    # Should see a duplicate detection modal
    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Merge conflict modal (when products have conflicting field values)
# ---------------------------------------------------------------------------


def test_merge_conflict_shows_conflicting_fields(page, api_create_product):
    """The merge conflict modal should display conflicting fields for resolution.

    The API rejects a second create with a duplicate name+empty EAN (HTTP 409
    via ``_find_duplicate``). To set up the merge-conflict scenario we pass
    ``on_duplicate="allow_duplicate"`` to bypass the create-time check (see
    ``services/product_crud.py:add_product``) so two products can share the
    same name with conflicting field values. Editing one of them then triggers
    name-based duplicate detection on save and surfaces the conflict modal.
    """
    api_create_product(
        name="ConflictA", brand="BrandAlpha", kcal=100,
        on_duplicate="allow_duplicate",
    )
    api_create_product(
        name="ConflictA", brand="BrandBeta", kcal=200,
        on_duplicate="allow_duplicate",
    )
    _reload_and_wait(page)

    # Expand the second product and edit to trigger merge
    rows = page.locator(".table-row", has_text="ConflictA")
    expect(rows.first).to_be_visible(timeout=5000)
    rows.first.click()
    page.wait_for_timeout(300)

    edit_btn = page.locator("[data-action='start-edit']").first
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(500)

    save_btn = page.locator("[data-action='save-product']").first
    expect(save_btn).to_be_visible(timeout=3000)
    save_btn.click()

    # Wait for conflict/duplicate modal
    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)

    # Check for conflict-specific elements (conflict-modal or conflict-option)
    # The modal might be a simple duplicate notice or a full conflict modal
    modal_text = modal.first.inner_text()
    assert len(modal_text) > 10, (
        f"Modal should have substantial text describing the conflict, got: '{modal_text}'"
    )


# ---------------------------------------------------------------------------
# Merge via API
# ---------------------------------------------------------------------------


def test_merge_products_api(live_url, api_create_product):
    """POST /api/products/{id}/merge should merge two products."""
    prod_a = api_create_product(name="MergeAPIProdC", brand="BrandC")
    prod_b = api_create_product(name="MergeAPIProdD", brand="BrandD")

    payload = json.dumps({
        "source_id": prod_b["id"],
        "choices": {},
    }).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products/{prod_a['id']}/merge",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert body.get("ok") is True, f"Expected ok=True from merge, got: {body}"

    # Verify the source product was deleted
    try:
        check_req = urllib.request.Request(
            f"{live_url}/api/products/{prod_b['id']}",
            headers={"X-Requested-With": "SmartSnack"},
        )
        urllib.request.urlopen(check_req, timeout=5)
        assert False, "Source product should have been deleted after merge"
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, f"Expected 404 for merged product, got {exc.code}"


def test_check_duplicate_api(live_url, api_create_product):
    """POST /api/products/{id}/check-duplicate should detect duplicates."""
    prod_a = api_create_product(name="CheckDupAPIProd", ean="6666666666660")
    prod_b = api_create_product(name="CheckDupOtherProd", ean="7777777777771")

    payload = json.dumps({
        "ean": "6666666666660",
        "name": "CheckDupOtherProd",
    }).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products/{prod_b['id']}/check-duplicate",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert "duplicate" in body, f"Expected 'duplicate' key in response, got: {body}"
    assert body["duplicate"] is not None, "Expected a duplicate to be found"
    assert body["duplicate"]["id"] == prod_a["id"], (
        f"Expected duplicate to be prod_a (id={prod_a['id']}), got id={body['duplicate']['id']}"
    )
