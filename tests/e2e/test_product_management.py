"""Test product editing and deletion."""

import pytest
from playwright.sync_api import expect


def test_product_row_expandable(page, api_create_product):
    """Clicking a product row should expand it to show details."""
    api_create_product(name="ExpandTestProd")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click the product row to expand
    row = page.locator(".table-row", has_text="ExpandTestProd")
    row.first.click()
    page.wait_for_timeout(300)

    # Expanded section should be visible
    expanded = page.locator(".expanded")
    expect(expanded.first).to_be_visible(timeout=3000)


def test_edit_product(page, api_create_product):
    """Editing a product should update its data."""
    api_create_product(name="EditOriginalName")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click product to expand
    row = page.locator(".table-row", has_text="EditOriginalName")
    row.first.click()
    page.wait_for_timeout(300)

    # Click edit button
    edit_btn = page.locator("[data-action='start-edit']").first
    edit_btn.click()
    page.wait_for_timeout(500)

    # The edit form should be visible
    edit_name = page.locator("#ed-name")
    expect(edit_name).to_be_visible(timeout=3000)

    # Change the name
    edit_name.fill("EditUpdatedName")

    # Save
    save_btn = page.locator("[data-action='save-product']").first
    save_btn.click()

    # Should show success toast
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_delete_product(page, api_create_product):
    """Deleting a product should remove it from the list."""
    api_create_product(name="DeleteMeProd")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Click product to expand
    row = page.locator(".table-row", has_text="DeleteMeProd")
    row.first.click()
    page.wait_for_timeout(300)

    # Click delete button
    delete_btn = page.locator("[data-action='delete']").first
    delete_btn.click()
    page.wait_for_timeout(300)

    # Click confirm in the custom modal
    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # Should show success toast
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)

    # Product should eventually disappear after reload
    page.wait_for_timeout(500)
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )
    expect(page.locator("#results-container")).not_to_contain_text("DeleteMeProd")
