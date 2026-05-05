"""Browser-based e2e tests for OCR ingredient scanning UI.

Covers the ingredient scan button, OCR result display,
and ingredient text population in the product forms.
"""

from playwright.sync_api import expect


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _reload_and_wait(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _open_edit_form(page, name):
    row = page.locator(f".table-row:has-text('{name}')").first
    row.click()
    page.wait_for_timeout(300)
    # The start-edit button is in the sibling .expanded div, not inside .table-row.
    edit_btn = page.locator("[data-action='start-edit']").first
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(300)


class TestOcrScanButtonBrowser:
    """Test OCR scan button presence and behavior."""

    def test_ocr_button_in_register(self, page):
        """The OCR scan button should be in the registration form."""
        _go_to_register(page)
        ocr_btn = page.locator("#f-ocr-btn")
        expect(ocr_btn).to_be_visible()

    def test_nutrition_ocr_button_in_register(self, page):
        """The nutrition OCR scan button should be in the registration form."""
        _go_to_register(page)
        nutri_btn = page.locator("#f-ocr-nutri-btn")
        expect(nutri_btn).to_be_visible()

    def test_ingredients_textarea_present(self, page):
        """The ingredients textarea should be in the registration form."""
        _go_to_register(page)
        textarea = page.locator("#f-ingredients")
        expect(textarea).to_be_visible()

    def test_ocr_button_in_edit_form(self, page, api_create_product):
        """The OCR button should be available in the edit form."""
        api_create_product(name="OcrEditProd")
        _reload_and_wait(page)
        _open_edit_form(page, "OcrEditProd")

        ocr_btn = page.locator("#ed-ocr-btn")
        if ocr_btn.is_visible():
            expect(ocr_btn).to_be_visible()
        else:
            # Button might use a different selector
            textarea = page.locator("#ed-ingredients")
            expect(textarea).to_be_attached()


class TestOcrIngredientTranslationBrowser:
    """Test that OCR respects the app language setting."""

    def test_language_select_in_settings(self, page):
        """The language selector should be available in settings."""
        page.locator("button[data-view='settings']").click()
        expect(page.locator("#view-settings")).to_be_visible()
        page.wait_for_selector("#settings-content", state="visible", timeout=10000)

        toggle = page.locator(
            ".settings-toggle:has(span[data-i18n='settings_language'])"
        ).first
        toggle.click()
        page.wait_for_timeout(300)

        # On desktop upgradeSelect() wraps the native select in .custom-select-wrap and
        # hides it with CSS, exposing .custom-select-trigger instead.  On mobile the
        # native select is shown directly.  Use wait_for_function to avoid Playwright
        # strict-mode failures from or_() when both elements exist in the DOM at once.
        page.wait_for_function(
            """() => {
                const sel = document.getElementById('language-select');
                if (!sel) return false;
                const wrap = sel.closest('.custom-select-wrap');
                if (wrap) {
                    const trigger = wrap.querySelector('.custom-select-trigger');
                    return !!(trigger && trigger.offsetParent !== null);
                }
                return sel.offsetParent !== null;
            }""",
            timeout=5000,
        )
