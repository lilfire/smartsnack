"""E2E regression tests for the H6/H7/H8 frontend flow fixes (LSO-1684).

H6: assigning a scanned EAN to an existing product must not 400 (the PUT
    used to echo the computed ``has_image`` column back to update_product).
H7: deleting a second product inside the first product's 5s undo window
    must flush the first DELETE instead of silently dropping it.
H8: cancelling the duplicate-merge modal (or a duplicate-check failure)
    must re-enable the Save button instead of leaving it stuck on
    "Saving...".
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _delete_product_via_ui(page, product_name):
    """Expand a product row, click delete, and accept the confirm modal."""
    row = page.locator(".table-row[data-product-id]", has_text=product_name)
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    delete_btn = page.locator("[data-action='delete']").first
    expect(delete_btn).to_be_visible(timeout=3000)
    delete_btn.click()

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()
    page.wait_for_timeout(200)


def _api_get_product(live_url, product_id):
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}",
        headers={"X-Requested-With": "SmartSnack"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# H6: scanner EAN assign to existing product
# ---------------------------------------------------------------------------


def test_scan_assign_ean_to_existing_product_persists(page, live_url, api_create_product):
    """Scan -> "Update existing" -> pick product must save the EAN without a 400.

    Regression: the PUT payload included the computed ``has_image`` field from
    the GET response, which ``update_product`` rejects as ``Invalid field``.
    """
    created = api_create_product(name="EanAssignTarget", category="Snacks")
    scanned_ean = "7310865004703"

    page.evaluate(f"() => window.scanUpdateExisting('{scanned_ean}')")
    expect(page.locator("#scan-picker-bg")).to_be_visible(timeout=3000)

    page.locator("#scan-picker-input").fill("EanAssignTarget")
    page.locator("#scan-picker-bg .off-modal-search button").click()

    result_row = page.locator("#scan-picker-body .off-result[data-action='pick']")
    expect(result_row.first).to_be_visible(timeout=5000)
    result_row.first.click()

    # Success path: the OFF fetch confirm modal appears and no error toast.
    expect(page.locator("#scan-off-confirm-bg")).to_be_visible(timeout=5000)
    expect(page.locator("#toast.error.show")).to_be_hidden(timeout=1000)

    # Dismiss the OFF confirm via the skip button.
    page.locator("#scan-off-confirm-bg .scan-modal-btn-cancel").click()
    expect(page.locator("#scan-off-confirm-bg")).to_be_hidden(timeout=3000)

    # The EAN must be persisted server-side.
    product = _api_get_product(live_url, created["id"])
    assert product["ean"] == scanned_ean, (
        f"Expected EAN {scanned_ean} persisted on product, got: {product['ean']!r}"
    )


# ---------------------------------------------------------------------------
# H7: rapid double delete inside the undo window
# ---------------------------------------------------------------------------


def test_rapid_double_delete_removes_both_products(page, live_url, api_create_product):
    """Deleting product B inside product A's 5s undo window must delete BOTH.

    Regression: the second delete cleared the first delete's timer without
    firing its DELETE request, so product A silently survived.
    """
    api_create_product(name="RapidDeleteA")
    api_create_product(name="RapidDeleteB")
    _reload_and_wait(page)

    _delete_product_via_ui(page, "RapidDeleteA")
    # Second delete immediately, well inside A's 5s undo window.
    _delete_product_via_ui(page, "RapidDeleteB")

    # Wait for B's undo window to expire and its deferred DELETE to complete.
    toast = page.locator(".toast.show")
    expect(toast).to_be_hidden(timeout=8000)
    page.wait_for_timeout(1500)

    _reload_and_wait(page)
    results = page.locator("#results-container")
    expect(results).not_to_contain_text("RapidDeleteA")
    expect(results).not_to_contain_text("RapidDeleteB")


# ---------------------------------------------------------------------------
# H8: save button recovery after duplicate-merge cancel
# ---------------------------------------------------------------------------


def test_save_button_reenabled_after_merge_modal_cancel(page, api_create_product):
    """Cancelling the duplicate-merge modal must re-enable the Save button.

    Regression: the early return on cancel skipped the button-reset block,
    leaving the button permanently disabled on "Saving...".

    Both products are created without EANs so that renaming the second to
    match the first triggers a name-based duplicate match on save (EAN
    matches take precedence in ``_find_duplicate``).
    """
    api_create_product(name="StuckSaveOrig")
    api_create_product(name="StuckSaveTarget")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="StuckSaveTarget")
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    edit_btn = page.locator("[data-action='start-edit']").first
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(500)

    edit_name = page.locator("#ed-name")
    expect(edit_name).to_be_visible(timeout=3000)
    edit_name.fill("StuckSaveOrig")

    save_btn = page.locator("[data-action='save-product']").first
    expect(save_btn).to_be_visible(timeout=3000)
    save_btn.click()

    # The duplicate-merge modal appears; cancel it.
    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal.first).to_be_visible(timeout=5000)
    cancel_btn = page.locator(".scan-modal-bg .confirm-no").first
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()
    expect(modal.first).to_be_hidden(timeout=3000)

    # The edit form must still be open and the Save button usable again.
    expect(edit_name).to_be_visible(timeout=3000)
    expect(save_btn).to_be_enabled(timeout=3000)
