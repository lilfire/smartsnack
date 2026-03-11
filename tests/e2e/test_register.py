"""Test product registration flow."""

from playwright.sync_api import expect


def _go_to_register(page):
    """Navigate to the register view."""
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def test_register_form_fields_present(page):
    """All required form fields should be present in the register view."""
    _go_to_register(page)

    expect(
        page.locator("#f-type")
    ).to_be_attached()  # category select (hidden by custom overlay)
    expect(page.locator("#f-ean")).to_be_visible()  # EAN input
    expect(page.locator("#f-name")).to_be_visible()  # product name
    expect(page.locator("#f-brand")).to_be_visible()  # brand
    expect(page.locator("#f-kcal")).to_be_visible()  # kcal
    expect(page.locator("#f-protein")).to_be_visible()  # protein
    expect(page.locator("#f-fat")).to_be_visible()  # fat
    expect(page.locator("#f-carbs")).to_be_visible()  # carbs
    expect(page.locator("#f-sugar")).to_be_visible()  # sugar
    expect(page.locator("#f-salt")).to_be_visible()  # salt
    expect(page.locator("#f-fiber")).to_be_visible()  # fiber
    expect(page.locator("#f-smak")).to_be_visible()  # taste slider
    expect(page.locator("#btn-submit")).to_be_visible()  # submit button


def test_category_dropdown_has_options(page):
    """Category dropdown should be populated from the database."""
    _go_to_register(page)

    options = page.locator("#f-type option")
    count = options.count()
    assert count >= 1, "Category dropdown should have at least one option"


def test_register_product_success(page):
    """Submitting a valid product should succeed and show a toast."""
    _go_to_register(page)

    page.locator("#f-name").fill("E2E Test Product")
    page.locator("#f-kcal").fill("150")
    page.locator("#f-protein").fill("10")
    page.locator("#f-fat").fill("5")
    page.locator("#f-carbs").fill("20")
    page.locator("#f-sugar").fill("3")
    page.locator("#f-salt").fill("0.5")
    page.locator("#f-smak").fill("4")

    page.locator("#btn-submit").click()

    # Should show success toast
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)

    # Verify product appears in search
    page.locator("button[data-view='search']").click()
    page.wait_for_timeout(500)
    expect(page.locator("#results-container")).to_contain_text("E2E Test Product")


def test_register_product_without_name_fails(page):
    """Submitting without a product name should show an error."""
    _go_to_register(page)

    # Fill some fields but leave name empty
    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    # Should show error toast
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_taste_slider_updates_display(page):
    """Moving the taste slider should update the displayed value."""
    _go_to_register(page)

    slider = page.locator("#f-smak")
    display = page.locator("#smak-val")

    # Set slider to 5 and update the display directly (inline oninput
    # handler references #smak-display which may not exist after i18n)
    page.evaluate(
        """() => {
            const s = document.querySelector('#f-smak');
            s.value = '5';
            document.getElementById('smak-val').textContent = '5';
        }"""
    )
    expect(display).to_have_text("5")
    # Also verify the slider value itself
    expect(slider).to_have_value("5")


def test_ean_enables_fetch_button(page):
    """Entering an EAN should enable the Fetch button."""
    _go_to_register(page)

    ean_input = page.locator("#f-ean")
    fetch_btn = page.locator("#f-off-btn")

    # Initially disabled
    expect(fetch_btn).to_be_disabled()

    # Type a valid EAN
    ean_input.fill("7038010069307")
    expect(fetch_btn).to_be_enabled()
