"""E2E tests for OCR-related UI elements in the ingredients area."""

from playwright.sync_api import expect


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


def test_language_select_in_settings(page):
    """The language select should be present and visible in the Language settings section."""
    _go_to_settings(page)
    _open_section(page, "settings_language")
    expect(page.locator("#language-select")).to_be_visible()


def test_ocr_button_in_edit_form(page, api_create_product):
    """The OCR button (#ed-ocr-btn) should be present when a product edit form is open."""
    api_create_product(name="OCR Button Test Product")

    # Start on the search view and wait for results
    page.locator("button[data-view='search']").click()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Expand the product row to reveal the edit button
    row = page.locator(".table-row", has_text="OCR Button Test Product")
    row.first.click()
    page.wait_for_timeout(300)

    # Click the edit button to open the edit form
    edit_btn = page.locator("[data-action='start-edit']").first
    edit_btn.click()
    page.wait_for_timeout(500)

    # The edit form should contain the OCR button
    expect(page.locator("#ed-ocr-btn")).to_be_visible()
