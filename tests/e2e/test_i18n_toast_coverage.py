"""i18n toast coverage tests — verify toasts and labels in all 3 languages.

For each language (no, en, se): switch language, trigger representative toasts,
and assert text matches translations/{lang}.json.
"""

import json
import os
import re

import pytest
from playwright.sync_api import expect

LANGUAGES = ["no", "en", "se"]

TOAST_KEYS_TO_TEST = [
    "toast_product_added",
    "toast_product_deleted",
    "toast_category_added",
    "toast_product_name_required",
    "toast_invalid_ean",
    "toast_invalid_file",
    "toast_image_too_large",
]


def _load_translations(lang="no"):
    """Load translations from the translation JSON files."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def _change_language(page, lang_code):
    """Change language via JS."""
    page.evaluate(f"() => window.changeLanguage('{lang_code}')")
    page.wait_for_timeout(500)


def _go_to_register(page):
    """Navigate to register view."""
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _go_to_settings(page):
    """Navigate to settings view."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _go_to_search(page):
    """Navigate to search view."""
    page.locator("button[data-view='search']").click()
    page.wait_for_timeout(300)


def _open_settings_section(page, i18n_key):
    """Open a specific settings section."""
    toggle = page.locator(
        f".settings-toggle:has(span[data-i18n='{i18n_key}'])"
    ).first
    toggle.click()
    page.wait_for_timeout(300)


def _wait_for_toast(page, expected_text, timeout=5000):
    """Wait for toast and assert it contains expected text."""
    toast = page.locator("#toast.show")
    expect(toast).to_be_visible(timeout=timeout)
    expect(toast).to_contain_text(expected_text, timeout=timeout)


def _dismiss_toast(page):
    """Dismiss toast if visible."""
    toast = page.locator("#toast.show")
    if toast.is_visible():
        close_btn = toast.locator(".toast-close")
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(200)


def _dismiss_modal(page):
    """Dismiss any open confirm modal."""
    cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
    if cancel.is_visible():
        cancel.click()
        page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# Toast Tests in All Languages
# ---------------------------------------------------------------------------


class TestI18nProductNameRequired:
    """Test toast_product_name_required in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_product_name_required_toast(self, page, lang):
        """Submit without name shows localized error toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_register(page)
        page.locator("#f-kcal").fill("100")
        page.locator("#btn-submit").click()
        _wait_for_toast(page, t["toast_product_name_required"])


class TestI18nInvalidEan:
    """Test toast_invalid_ean in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_invalid_ean_toast(self, page, lang):
        """Invalid EAN shows localized error toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_register(page)
        page.locator("#f-name").fill("EanI18nTest")
        page.locator("#f-ean").fill("bad")
        page.locator("#btn-submit").click()
        _wait_for_toast(page, t["toast_invalid_ean"])


class TestI18nProductAdded:
    """Test toast_product_added in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_product_added_toast(self, page, lang):
        """Registering a product shows localized success toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_register(page)
        product_name = f"I18n{lang.upper()}Product"
        page.locator("#f-name").fill(product_name)
        page.locator("#f-kcal").fill("150")
        page.locator("#f-protein").fill("10")
        page.locator("#f-fat").fill("5")
        page.locator("#f-carbs").fill("20")
        page.locator("#f-sugar").fill("3")
        page.locator("#f-salt").fill("0.5")
        page.locator("#f-smak").fill("4")
        page.locator("#btn-submit").click()
        page.wait_for_timeout(500)
        _dismiss_modal(page)
        expected = t["toast_product_added"].replace("{name}", product_name)
        _wait_for_toast(page, expected)


class TestI18nProductDeleted:
    """Test toast_product_deleted in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_product_deleted_toast(self, page, api_create_product, lang):
        """Deleting a product shows localized delete toast."""
        t = _load_translations(lang)
        product_name = f"Del{lang.upper()}Prod"
        product = api_create_product(name=product_name)
        _change_language(page, lang)
        _go_to_search(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        # Re-apply language after reload
        _change_language(page, lang)
        row = page.locator(f".table-row[data-product-id='{product['id']}']")
        row.click()
        page.wait_for_timeout(500)
        # Click delete (data-action="delete")
        delete_btn = page.locator(
            f"button[data-action='delete'][data-id='{product['id']}']"
        )
        expect(delete_btn).to_be_visible(timeout=5000)
        delete_btn.click()
        page.wait_for_timeout(300)
        # Confirm modal
        confirm_btn = page.locator(".scan-modal-bg .scan-modal button").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        expected = t["toast_product_deleted"].replace("{name}", product_name)
        _wait_for_toast(page, expected)


class TestI18nCategoryAdded:
    """Test toast_category_added in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_category_added_toast(self, page, lang):
        """Adding a category shows localized success toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_settings(page)
        _open_settings_section(page, "settings_categories_title")
        page.wait_for_timeout(300)
        cat_name = f"i18ncat{lang}"
        display_name = f"I18n Cat {lang.upper()}"
        # Use IDs for the category form
        name_input = page.locator("#cat-name")
        label_input = page.locator("#cat-label")
        expect(name_input).to_be_visible(timeout=5000)
        name_input.fill(cat_name)
        label_input.fill(display_name)
        add_btn = page.locator(
            "button[data-i18n='btn_add_category']"
        ).first
        add_btn.click()
        expected = t["toast_category_added"].replace("{name}", display_name)
        _wait_for_toast(page, expected)


class TestI18nInvalidFile:
    """Test toast_invalid_file in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_invalid_file_toast(self, page, lang):
        """Restoring with invalid file shows localized error toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_settings(page)
        _open_settings_section(page, "settings_database_title")
        page.wait_for_timeout(300)
        restore_input = page.locator(
            "#restore-input, input[type='file'][accept='.json']"
        ).first
        restore_input.set_input_files(
            {
                "name": "bad.txt",
                "mimeType": "text/plain",
                "buffer": b"not json",
            }
        )
        page.wait_for_timeout(500)
        # Confirm restore modal
        confirm_btn = page.locator(".scan-modal-bg button").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        _wait_for_toast(page, t["toast_invalid_file"])


class TestI18nImageTooLarge:
    """Test toast_image_too_large in all languages."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_image_too_large_toast(self, page, lang):
        """Uploading oversized image shows localized error toast."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_register(page)
        image_input = page.locator(
            "input[type='file'][accept*='image']"
        ).first
        if image_input.count() > 0:
            large_buffer = b"x" * (11 * 1024 * 1024)
            image_input.set_input_files(
                {
                    "name": "large.png",
                    "mimeType": "image/png",
                    "buffer": large_buffer,
                }
            )
            _wait_for_toast(page, t["toast_image_too_large"])


# ---------------------------------------------------------------------------
# Static Label Tests in All Languages
# ---------------------------------------------------------------------------


class TestI18nStaticLabels:
    """Test that static data-i18n labels re-render on language change."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_nav_search_label(self, page, lang):
        """Nav search tab shows correct translated text."""
        t = _load_translations(lang)
        _change_language(page, lang)
        search_tab = page.locator("button[data-view='search']")
        # nav_search includes emoji prefix, check the text part
        nav_text = t["nav_search"]
        expect(search_tab).to_contain_text(
            re.compile(re.escape(nav_text.split(" ", 1)[-1]), re.IGNORECASE)
        )

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_nav_register_label(self, page, lang):
        """Nav register tab shows correct translated text."""
        t = _load_translations(lang)
        _change_language(page, lang)
        register_tab = page.locator("button[data-view='register']")
        nav_text = t["nav_register"]
        expect(register_tab).to_contain_text(
            re.compile(re.escape(nav_text.split(" ", 1)[-1]), re.IGNORECASE)
        )

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_nav_settings_label(self, page, lang):
        """Nav settings tab shows correct translated text."""
        t = _load_translations(lang)
        _change_language(page, lang)
        settings_tab = page.locator("button[data-view='settings']")
        nav_text = t["nav_settings"]
        expect(settings_tab).to_contain_text(
            re.compile(re.escape(nav_text.split(" ", 1)[-1]), re.IGNORECASE)
        )

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_register_title(self, page, lang):
        """Register view title shows correct translated text."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_register(page)
        title_el = page.locator(
            "#view-register h2, #view-register .view-title"
        ).first
        # The title spans two data-i18n elements; just check both parts present
        expect(title_el).to_contain_text(t["register_title_1"].strip())
        expect(title_el).to_contain_text(t["register_title_2"])

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_settings_section_headers(self, page, lang):
        """Settings section headers render in the correct language."""
        t = _load_translations(lang)
        _change_language(page, lang)
        _go_to_settings(page)
        # Check weights title
        weights_label = page.locator(
            "span[data-i18n='settings_weights_title']"
        ).first
        expect(weights_label).to_have_text(t["settings_weights_title"])
        # Check categories title
        categories_label = page.locator(
            "span[data-i18n='settings_categories_title']"
        ).first
        expect(categories_label).to_have_text(t["settings_categories_title"])
