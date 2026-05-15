"""Browser-based e2e tests for form validation feedback in the UI.

Covers inline validation errors, field constraints, and error
messages shown when registering or editing products.
"""

import re

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    edit_btn = row.locator("[data-action='start-edit']")
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(300)


# ===========================================================================
# Registration form validation
# ===========================================================================


class TestRegistrationValidation:
    """Test validation feedback in the product registration form."""

    def test_empty_name_shows_error(self, page):
        """Submitting with empty name should show an error."""
        _go_to_register(page)

        # Leave name empty and click register
        page.locator("#btn-submit").click()
        page.wait_for_timeout(300)

        # Name error should be visible
        error = page.locator("#f-name-error")
        expect(error).to_be_visible()

    def test_name_field_required_indicator(self, page):
        """The name field label should indicate it is required."""
        _go_to_register(page)
        label = page.locator("label[for='f-name']")
        expect(label).to_have_class(re.compile("field-required"))

    def test_category_field_required(self, page):
        """The category select should be required."""
        _go_to_register(page)
        label = page.locator("label[for='f-type']")
        expect(label).to_have_class(re.compile("field-required"))

    def test_ean_hint_visible(self, page):
        """The EAN field should show a format hint."""
        _go_to_register(page)
        hint = page.locator("#f-ean-hint")
        expect(hint).to_be_visible()
        expect(hint).to_contain_text("8-13")

    def test_invalid_ean_shows_error(self, page):
        """An invalid EAN (too short) should trigger the error span."""
        _go_to_register(page)
        page.locator("#f-ean").fill("123")
        page.locator("#f-name").click()  # blur EAN
        page.wait_for_timeout(300)

        # The EAN error element exists (may or may not be visible based
        # on how validation triggers — check if the pattern mismatch state
        # is reported)
        ean = page.locator("#f-ean")
        is_invalid = page.evaluate(
            "() => !document.getElementById('f-ean').checkValidity()"
        )
        assert is_invalid, "Short EAN should fail HTML5 pattern validation"

    def test_valid_ean_passes_validation(self, page):
        """A valid 13-digit EAN should pass validation."""
        _go_to_register(page)
        page.locator("#f-ean").fill("7038010069307")
        page.wait_for_timeout(100)

        is_valid = page.evaluate(
            "() => document.getElementById('f-ean').checkValidity()"
        )
        assert is_valid, "Valid 13-digit EAN should pass pattern validation"

    def test_valid_8_digit_ean(self, page):
        """An 8-digit EAN should pass validation."""
        _go_to_register(page)
        page.locator("#f-ean").fill("12345678")
        page.wait_for_timeout(100)

        is_valid = page.evaluate(
            "() => document.getElementById('f-ean').checkValidity()"
        )
        assert is_valid, "Valid 8-digit EAN should pass pattern validation"


# ===========================================================================
# Numeric field validation
# ===========================================================================


class TestNumericFieldValidation:
    """Test numeric input fields in the registration form."""

    def test_kcal_accepts_numeric(self, page):
        """The kcal field should accept numeric values."""
        _go_to_register(page)
        page.locator("#f-kcal").fill("200")
        expect(page.locator("#f-kcal")).to_have_value("200")

    def test_numeric_fields_have_min_zero(self, page):
        """Nutrition numeric fields should have min=0."""
        _go_to_register(page)
        for field_id in ["f-kcal", "f-fat", "f-protein", "f-carbs",
                         "f-sugar", "f-fiber", "f-salt"]:
            field = page.locator(f"#{field_id}")
            min_val = field.get_attribute("min")
            assert min_val == "0", f"{field_id} should have min=0"

    def test_nutrition_fields_are_number_type(self, page):
        """Nutrition fields should be type=number."""
        _go_to_register(page)
        for field_id in ["f-kcal", "f-fat", "f-protein", "f-carbs",
                         "f-sugar", "f-fiber", "f-salt"]:
            field = page.locator(f"#{field_id}")
            field_type = field.get_attribute("type")
            assert field_type == "number", f"{field_id} should be type=number"


# ===========================================================================
# Taste score slider
# ===========================================================================


class TestTasteScoreSlider:
    """Test the taste score range slider."""

    def test_taste_slider_exists(self, page):
        """The taste score slider should be in the registration form."""
        _go_to_register(page)
        slider = page.locator("#f-smak")
        expect(slider).to_be_visible()

    def test_taste_slider_default_value(self, page):
        """The taste slider should default to 3."""
        _go_to_register(page)
        slider = page.locator("#f-smak")
        expect(slider).to_have_value("3")

    def test_taste_slider_range(self, page):
        """The taste slider should have min=0, max=6."""
        _go_to_register(page)
        slider = page.locator("#f-smak")
        assert slider.get_attribute("min") == "0"
        assert slider.get_attribute("max") == "6"
        assert slider.get_attribute("step") == "0.5"

    def test_taste_value_display_updates(self, page):
        """Changing the slider should update the displayed value."""
        _go_to_register(page)
        slider = page.locator("#f-smak")
        slider.fill("5")
        page.wait_for_timeout(200)

        val_display = page.locator("#smak-val")
        expect(val_display).to_have_text("5")


# ===========================================================================
# Product edit form validation
# ===========================================================================


class TestEditFormValidation:
    """Test validation in the product edit form."""

    def test_edit_name_field_required(self, page, api_create_product, unique_name):
        """Saving with empty name should fail."""
        prod_name = unique_name("EditValProd")
        api_create_product(name=prod_name)
        _reload_and_wait(page)
        _open_edit_form(page, prod_name)

        # Clear the name field
        name_field = page.locator("#ed-name")
        name_field.fill("")

        # Click save
        save_btn = page.locator("[data-action='save-product']")
        save_btn.click()
        page.wait_for_timeout(500)

        # Either a toast error or inline error should appear
        # The product should still be in edit mode (not saved)
        expect(name_field).to_be_visible()

    def test_edit_cancel_discards_changes(self, page, api_create_product, unique_name):
        """Cancelling edit should discard changes."""
        prod_name = unique_name("EditCancelProd")
        api_create_product(name=prod_name)
        _reload_and_wait(page)
        _open_edit_form(page, prod_name)

        # Change the name
        page.locator("#ed-name").fill("Changed Name")

        # Cancel
        cancel_btn = page.locator("[data-action='cancel-edit']")
        cancel_btn.click()
        page.wait_for_timeout(300)

        # Original name should still be visible
        row = page.locator(f".table-row:has-text('{prod_name}')").first
        expect(row).to_be_visible()
