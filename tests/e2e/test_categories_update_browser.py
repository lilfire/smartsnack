"""Browser-based e2e tests for category management in settings UI.

Covers adding, editing display names, and verifying category
list interactions.
"""

import json
import os
import urllib.request

from playwright.sync_api import expect


def _load_translations(lang="no"):
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    # toggleSettingsSection sets aria-expanded when the section body is shown.
    expect(toggle).to_have_attribute("aria-expanded", "true", timeout=5000)


class TestCategoryListBrowser:
    """Test category list display in the settings UI."""

    def test_category_section_shows_list(self, page):
        """The categories section should show the category list."""
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")
        expect(page.locator("#cat-list")).to_be_visible()

    def test_category_list_has_items(self, page):
        """The category list should contain at least one category."""
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")
        cat_list = page.locator("#cat-list")
        # Default categories should be present (e.g., Snacks)
        expect(cat_list).not_to_be_empty()

    def test_add_category_form_fields(self, page):
        """The add-category form should have name and label fields."""
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")
        expect(page.locator("#cat-name")).to_be_visible()
        expect(page.locator("#cat-label")).to_be_visible()


class TestCategoryAddBrowser:
    """Test adding a new category via the settings UI."""

    def test_add_category_success(self, page):
        """Adding a valid category should show a success toast."""
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        page.locator("#cat-name").fill("e2e_browser_cat")
        page.locator("#cat-label").fill("E2E Browser Category")
        page.locator("button[data-i18n='btn_add_category']").first.click()

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_add_category_persists(self, page):
        """A newly added category should appear in the category list."""
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        page.locator("#cat-name").fill("e2e_persist_cat")
        page.locator("#cat-label").fill("Persist Category")
        with page.expect_response(
            lambda r: "/api/categories" in r.url and r.request.method == "POST"
        ):
            page.locator("button[data-i18n='btn_add_category']").first.click()

        cat_list = page.locator("#cat-list")
        expect(cat_list).to_contain_text("Persist Category", timeout=5000)

    def test_category_available_in_register(self, page):
        """An added category should be selectable in the registration form."""
        # First add the category
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")
        page.locator("#cat-name").fill("e2e_reg_cat")
        page.locator("#cat-label").fill("Register Category")
        with page.expect_response(
            lambda r: "/api/categories" in r.url and r.request.method == "POST"
        ):
            page.locator("button[data-i18n='btn_add_category']").first.click()

        # Now go to register and check
        page.locator("button[data-view='register']").click()
        expect(page.locator("#view-register")).to_be_visible()

        # Wait for loadData() to complete — it calls buildTypeSelect() which
        # rebuilds #f-type with the latest categories from the API.
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=5000,
        )

        category_select = page.locator("#f-type")
        options_text = category_select.inner_text()
        assert "Register Category" in options_text or "e2e_reg_cat" in options_text


class TestCategoryEditBrowser:
    """Test editing category display names in the settings UI."""

    def test_edit_category_label(self, page):
        """Editing a category label via its inline input shows the toast.

        The real UI (loadCategories in settings-categories.js) renders one
        ``input.cat-item-label-input`` per category whose ``change`` event
        PUTs the new label and shows toast_category_updated. The selectors
        this test previously guarded on ([data-action='edit-category'],
        input.settings-item-edit-input) never existed, so it asserted
        nothing.
        """
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        # Seed data guarantees the 'Snacks' category exists.
        label_input = page.locator(
            "#cat-list input.cat-item-label-input[data-cat-name='Snacks']"
        )
        expect(label_input).to_be_attached(timeout=5000)
        label_input.fill("Updated Label")
        label_input.dispatch_event("change")

        toast = page.locator("#toast.show")
        expect(toast).to_be_visible(timeout=5000)
        t = _load_translations()
        expect(toast).to_contain_text(t["toast_category_updated"])
        # The list re-renders from the API — the new label must round-trip.
        expect(
            page.locator(
                "#cat-list input.cat-item-label-input[data-cat-name='Snacks']"
            )
        ).to_have_value("Updated Label", timeout=5000)
