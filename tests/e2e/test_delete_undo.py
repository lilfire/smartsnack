"""Test undo-delete flow (Task 7).

Verifies that:
- Deleting a product shows the toast_product_deleted text with undo button
- Clicking undo restores the product and shows toast_delete_undone
- Letting the undo window expire (>5s) permanently deletes the product
"""

from playwright.sync_api import expect


def test_delete_shows_toast_with_undo(page, api_create_product):
    """Deleting a product shows toast with deleted message and undo button."""
    api_create_product(name="UndoTestProduct")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click product to expand
    row = page.locator(".table-row", has_text="UndoTestProduct")
    row.first.click()
    page.wait_for_timeout(300)

    # Click delete button
    delete_btn = page.locator("[data-action='delete']").first
    delete_btn.click()
    page.wait_for_timeout(300)

    # Confirm deletion in the modal
    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # Should show success toast with product name (Norwegian: "X" slettet)
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)
    expect(toast.first).to_contain_text("slettet")

    # Undo button should be visible in the toast
    undo_btn = page.locator(".toast-undo")
    expect(undo_btn.first).to_be_visible(timeout=3000)


def test_undo_restores_product(page, api_create_product):
    """Clicking undo after delete restores the product and shows confirmation."""
    api_create_product(name="UndoRestoreProd")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click product to expand
    row = page.locator(".table-row", has_text="UndoRestoreProd")
    row.first.click()
    page.wait_for_timeout(300)

    # Delete
    delete_btn = page.locator("[data-action='delete']").first
    delete_btn.click()
    page.wait_for_timeout(300)

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # Wait for toast with undo button
    undo_btn = page.locator(".toast-undo")
    expect(undo_btn.first).to_be_visible(timeout=5000)

    # Click undo
    undo_btn.first.click()

    # Should show "Sletting angret" toast (toast_delete_undone)
    page.wait_for_timeout(500)
    toast_container = page.locator(".toast")
    expect(toast_container.last).to_contain_text("Sletting angret")

    # Product should reappear in results
    results = page.locator("#results-container")
    expect(results).to_contain_text("UndoRestoreProd")


def test_delete_permanent_after_undo_window(page, api_create_product):
    """After undo window expires (~5s), the product is permanently deleted."""
    api_create_product(name="PermanentDeleteProd")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click product to expand
    row = page.locator(".table-row", has_text="PermanentDeleteProd")
    row.first.click()
    page.wait_for_timeout(300)

    # Delete and confirm
    delete_btn = page.locator("[data-action='delete']").first
    delete_btn.click()
    page.wait_for_timeout(300)

    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)

    # Wait for the DELETE request to actually fire (5s undo window + network)
    with page.expect_response(
        lambda r: "/api/products/" in r.url and r.request.method == "DELETE",
        timeout=10000,
    ):
        confirm_btn.click()

    # Product should be gone after reload
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )
    expect(page.locator("#results-container")).not_to_contain_text("PermanentDeleteProd")
