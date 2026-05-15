"""E2E tests for product delete with undo toast (P0 gap #2).

The delete flow shows a toast with an 'Undo' button for 5 seconds.
Clicking undo should restore the product. If the timeout elapses,
the product is permanently deleted via DELETE API.

Key implementation detail: the actual HTTP DELETE is deferred 5 seconds
after the confirm modal is accepted.  Tests that verify the product is
gone must wait for the undo window to expire before reloading.
"""

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_and_wait(page):
    """Reload the page and wait for the initial product list to settle."""
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _open_delete_confirm(page, product_name: str) -> None:
    """Expand a product row and open the delete confirmation modal."""
    row = page.locator(".table-row[data-product-id]", has_text=product_name)
    expect(row.first).to_be_visible(timeout=5000)
    row.first.click()
    page.wait_for_timeout(300)

    delete_btn = page.locator("[data-action='delete']").first
    expect(delete_btn).to_be_visible(timeout=3000)
    delete_btn.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_delete_shows_toast_with_undo_button(page, api_create_product):
    """Deleting a product should show a toast that contains an Undo button."""
    api_create_product(name="UndoToastProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "UndoToastProd")

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # Toast with undo button must appear
    toast = page.locator(".toast.show")
    expect(toast).to_be_visible(timeout=5000)

    undo_btn = page.locator(".toast-undo")
    expect(undo_btn).to_be_visible(timeout=3000)


def test_delete_toast_contains_product_name(page, api_create_product):
    """The delete toast message should include the deleted product's name."""
    api_create_product(name="NameInToastProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "NameInToastProd")

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    toast = page.locator(".toast.show")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text()
    assert "NameInToastProd" in toast_text, (
        f"Expected product name in toast text, got: '{toast_text}'"
    )


def test_undo_restores_product(page, api_create_product):
    """Clicking the Undo button within the 5s window should restore the product."""
    api_create_product(name="UndoRestoreProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "UndoRestoreProd")

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # Click undo immediately before the 5s window elapses
    undo_btn = page.locator(".toast-undo")
    expect(undo_btn).to_be_visible(timeout=3000)
    undo_btn.click()

    page.wait_for_timeout(500)

    # After undo, reload and verify the product is still present
    _reload_and_wait(page)
    expect(page.locator("#results-container")).to_contain_text("UndoRestoreProd")


def test_delete_without_undo_removes_product(page, api_create_product):
    """If the undo window elapses without clicking Undo, the product is deleted."""
    api_create_product(name="NoUndoProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "NoUndoProd")

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # The product is removed from the UI immediately.  The actual HTTP DELETE
    # fires after 5 seconds.  We wait for the toast's undo window to expire
    # and the toast to disappear before reloading so the server has processed
    # the delete.
    toast = page.locator(".toast.show")
    expect(toast).to_be_visible(timeout=5000)

    # Wait for the undo toast to auto-dismiss (duration=5000ms) plus buffer
    expect(toast).to_be_hidden(timeout=8000)

    # Allow the deferred DELETE request to complete
    page.wait_for_timeout(1500)

    _reload_and_wait(page)
    expect(page.locator("#results-container")).not_to_contain_text("NoUndoProd")


def test_delete_confirmation_modal_shows_product_name(page, api_create_product):
    """The confirmation modal for delete should display the product's name."""
    api_create_product(name="ConfirmNameProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "ConfirmNameProd")

    modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(modal).to_be_visible(timeout=3000)

    modal_text = modal.inner_text()
    assert "ConfirmNameProd" in modal_text, (
        f"Expected product name in delete confirmation modal, got: '{modal_text}'"
    )


def test_delete_confirmation_cancel_keeps_product(page, api_create_product):
    """Cancelling the delete confirmation modal should leave the product intact."""
    api_create_product(name="CancelDeleteProd")
    _reload_and_wait(page)

    _open_delete_confirm(page, "CancelDeleteProd")

    cancel_btn = page.locator(".confirm-no")
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()

    page.wait_for_timeout(300)

    # Modal should be gone and product still visible
    expect(page.locator(".scan-modal-bg[role='dialog']")).to_be_hidden(timeout=3000)
    expect(page.locator("#results-container")).to_contain_text("CancelDeleteProd")
