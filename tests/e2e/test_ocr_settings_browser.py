"""Browser-based e2e tests for OCR settings panel UI.

Covers OCR provider selection, model row visibility,
fallback checkbox, and save interactions.
"""

from playwright.sync_api import expect


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


class TestOcrProviderSelectBrowser:
    """Test OCR provider selection in the settings UI."""

    def test_provider_select_visible(self, page):
        """The OCR provider dropdown should be visible."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        expect(page.locator("#ocr-provider-select")).to_be_visible()

    def test_tesseract_is_default(self, page):
        """Tesseract should be selected by default."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        provider = page.locator("#ocr-provider-select")
        expect(provider).to_have_value("tesseract")

    def test_tesseract_always_available(self, page):
        """Tesseract option should always be available."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        options = page.locator("#ocr-provider-select option")
        texts = options.all_text_contents()
        assert any("Tesseract" in t or "tesseract" in t for t in texts)


class TestOcrModelRowBrowser:
    """Test the OCR model row visibility behavior."""

    def test_model_row_hidden_for_tesseract(self, page):
        """The model row should be hidden when Tesseract is selected."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        page.locator("#ocr-provider-select").select_option("tesseract")
        page.wait_for_timeout(300)
        model_row = page.locator("#ocr-model-row")
        expect(model_row).to_be_hidden()


class TestOcrFallbackBrowser:
    """Test the OCR fallback checkbox behavior."""

    def test_fallback_checkbox_visible(self, page):
        """The fallback checkbox should be visible in OCR settings."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        expect(page.locator("#ocr-fallback-checkbox")).to_be_visible()

    def test_fallback_checkbox_toggleable(self, page):
        """The fallback checkbox should be toggleable."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        cb = page.locator("#ocr-fallback-checkbox")

        # Check the initial state and toggle
        was_checked = cb.is_checked()
        cb.click()
        page.wait_for_timeout(200)

        if was_checked:
            expect(cb).not_to_be_checked()
        else:
            expect(cb).to_be_checked()


class TestOcrSaveBrowser:
    """Test saving OCR settings via the UI."""

    def test_save_button_visible(self, page):
        """The save OCR settings button should be visible."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        btn = page.locator("button[data-i18n='btn_save_ocr_settings']")
        expect(btn).to_be_visible()

    def test_save_shows_toast(self, page):
        """Saving OCR settings should show a toast notification."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        page.locator("button[data-i18n='btn_save_ocr_settings']").click()
        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_save_persists_after_reload(self, page):
        """Saved OCR settings should persist after page reload."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")

        # Save current settings
        page.locator("button[data-i18n='btn_save_ocr_settings']").click()
        page.wait_for_timeout(500)

        # Reload and verify
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)

        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        expect(page.locator("#ocr-provider-select")).to_have_value("tesseract")
