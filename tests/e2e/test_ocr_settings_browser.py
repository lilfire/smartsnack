"""E2E tests for OCR settings UI in the settings view."""

from playwright.sync_api import expect


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


def test_provider_select_visible(page):
    """The OCR provider select should be visible after opening the OCR settings section."""
    _go_to_settings(page)
    _open_section(page, "settings_ocr_title")
    expect(page.locator("#ocr-provider")).to_be_visible()


def test_model_row_hidden_for_tesseract(page):
    """The model row should be hidden when 'tesseract' is selected as the provider."""
    _go_to_settings(page)
    _open_section(page, "settings_ocr_title")

    # Switch provider to tesseract — onOcrProviderChange() fires via onchange attribute
    page.locator("#ocr-provider").select_option("tesseract")
    page.wait_for_timeout(200)

    expect(page.locator("#ocr-model-row")).to_be_hidden()


def test_fallback_checkbox_toggleable(page):
    """The fallback checkbox should be togglable (check and uncheck)."""
    _go_to_settings(page)
    _open_section(page, "settings_ocr_title")

    cb = page.locator("#ocr-fallback")
    cb.check()
    expect(cb).to_be_checked()
    cb.uncheck()
    expect(cb).not_to_be_checked()
