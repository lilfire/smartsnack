"""E2E tests for accessibility: keyboard navigation, ARIA attributes, and roles.

Tests:
- Nav tabs are reachable by Tab key and are focusable elements
- Settings toggles have aria-expanded with a valid value ('true' or 'false')
- The #toast element has role='status' and aria-live
- The tag modal has role='dialog'
- Product table rows have role='row' and aria-label
- #result-count has role='status' or aria-live
- aria-live regions exist on the page
- Register form has associated labels or aria-label for key inputs
- Keyboard navigation moves focus between register form fields
- Product rows respond to Enter key (keyboard expand)
"""

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible(timeout=5000)


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible(timeout=5000)
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


# ---------------------------------------------------------------------------
# Keyboard navigation tests
# ---------------------------------------------------------------------------


def test_tab_moves_focus_to_focusable_element(page):
    """Pressing Tab from the page body must focus a real interactive element."""
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)

    focused_tag = page.evaluate("document.activeElement?.tagName?.toUpperCase()")
    assert focused_tag in ("BUTTON", "INPUT", "A", "SELECT", "TEXTAREA", "[object HTMLElement]"), (
        f"Expected focus to land on an interactive element, got tag: '{focused_tag}'"
    )


def test_nav_tabs_are_keyboard_focusable(page):
    """Each nav tab button must be focusable (have tabindex >= 0 or be a button)."""
    nav_tabs = page.locator("button.nav-tab[data-view]")
    count = nav_tabs.count()
    assert count >= 3, f"Expected at least 3 nav tab buttons, got {count}"

    for i in range(count):
        btn = nav_tabs.nth(i)
        tag = btn.evaluate("el => el.tagName.toLowerCase()")
        # Native <button> elements are inherently focusable; tabindex must not be -1
        tabindex = btn.get_attribute("tabindex")
        assert tag == "button" or (tabindex is not None and int(tabindex) >= 0), (
            f"Nav tab {i} is not keyboard-focusable: tag={tag}, tabindex={tabindex}"
        )


def test_tab_navigates_register_form_fields(page):
    """Tab must move focus away from #f-name to the next form field."""
    _go_to_register(page)

    page.locator("#f-name").focus()
    page.keyboard.press("Tab")
    page.wait_for_timeout(150)

    focused_id = page.evaluate("document.activeElement?.id")
    assert focused_id is not None, "Expected a focused element after Tab"
    assert focused_id != "f-name", (
        f"Expected focus to move away from #f-name after Tab, but still focused: '{focused_id}'"
    )


def test_product_row_responds_to_enter_key(page, api_create_product):
    """Pressing Enter on a focused product row must expand it."""
    api_create_product(name="KeyboardExpandProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="KeyboardExpandProd").first
    row.focus()
    page.wait_for_timeout(150)
    row.press("Enter")
    page.wait_for_timeout(400)

    expanded = page.locator(".expanded")
    expect(expanded.first).to_be_visible(timeout=3000)


def test_click_row_again_collapses_expanded(page, api_create_product):
    """Clicking an expanded product row again must collapse it."""
    api_create_product(name="ToggleCollapseProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ToggleCollapseProd").first
    row.click()
    page.wait_for_timeout(300)

    expanded = page.locator(".expanded").first
    expect(expanded).to_be_visible(timeout=3000)

    row.click()
    page.wait_for_timeout(300)

    expect(expanded).to_be_hidden(timeout=3000)


# ---------------------------------------------------------------------------
# ARIA attribute tests
# ---------------------------------------------------------------------------


def test_aria_live_regions_exist(page):
    """The page must have at least one element with an aria-live attribute."""
    live_regions = page.locator("[aria-live]")
    count = live_regions.count()
    assert count > 0, (
        f"Expected at least one [aria-live] region on the page, found {count}"
    )


def test_toast_has_role_status(page):
    """The #toast element must have role='status' as set in toast.html."""
    toast = page.locator("#toast")
    expect(toast).to_be_attached()
    role = toast.get_attribute("role")
    assert role == "status", (
        f"Expected #toast to have role='status', got: {role!r}"
    )


def test_toast_has_aria_live_attribute(page):
    """The #toast element must have an aria-live attribute (set in toast.html or via JS)."""
    # toast.html sets aria-live="polite" initially; state.js may override to "assertive"
    toast = page.locator("#toast")
    expect(toast).to_be_attached()
    aria_live = toast.get_attribute("aria-live")
    assert aria_live in ("polite", "assertive"), (
        f"Expected #toast aria-live to be 'polite' or 'assertive', got: {aria_live!r}"
    )


def test_settings_toggles_have_aria_expanded(page):
    """Every .settings-toggle must have aria-expanded set to 'true' or 'false'."""
    _go_to_settings(page)

    toggles = page.locator(".settings-toggle")
    count = toggles.count()
    assert count > 0, "Expected at least one .settings-toggle in settings view"

    for i in range(count):
        toggle = toggles.nth(i)
        aria_expanded = toggle.get_attribute("aria-expanded")
        assert aria_expanded in ("true", "false"), (
            f"Settings toggle #{i} has invalid aria-expanded='{aria_expanded}' "
            f"(expected 'true' or 'false')"
        )


def test_result_count_has_accessible_role(page, api_create_product):
    """#result-count must have role='status' or aria-live so screen readers announce it."""
    api_create_product(name="ResultCountARIAProd")
    _reload_and_wait(page)

    result_count = page.locator("#result-count")
    expect(result_count).to_be_attached()

    role = result_count.get_attribute("role")
    aria_live = result_count.get_attribute("aria-live")
    assert role == "status" or aria_live is not None, (
        f"#result-count must have role='status' or aria-live, "
        f"got role={role!r}, aria-live={aria_live!r}"
    )


def test_product_rows_have_role_row(page, api_create_product):
    """Product table rows must have role='row' for screen reader table semantics."""
    api_create_product(name="RowRoleProd")
    _reload_and_wait(page)

    rows = page.locator(".table-row[data-product-id]")
    count = rows.count()
    assert count >= 1, "Expected at least one product row"

    first_row = rows.first
    role = first_row.get_attribute("role")
    assert role == "row", (
        f"Expected product row to have role='row', got: {role!r}"
    )


def test_product_rows_have_aria_label(page, api_create_product):
    """Product table rows must have aria-label set to the product name."""
    product_name = "AriaLabelProd"
    api_create_product(name=product_name)
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text=product_name).first
    aria_label = row.get_attribute("aria-label")
    assert aria_label is not None and len(aria_label) > 0, (
        f"Expected product row to have a non-empty aria-label, got: {aria_label!r}"
    )
    assert product_name in aria_label, (
        f"Expected product name '{product_name}' in aria-label, got: '{aria_label}'"
    )


def test_tag_modal_has_role_dialog(page, api_create_product):
    """The tag modal overlay must carry role='dialog' when open."""
    api_create_product(name="TagARIAProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="TagARIAProd").first
    row.click()
    page.wait_for_timeout(300)

    page.locator("[data-action='start-edit']").first.click()
    page.wait_for_timeout(500)

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    modal = page.locator("#tag-modal-overlay")
    expect(modal).to_be_visible(timeout=3000)

    role = modal.get_attribute("role")
    assert role == "dialog", (
        f"Expected tag modal to have role='dialog', got: {role!r}"
    )


def test_register_form_name_field_has_label(page):
    """The #f-name input must have an associated <label> element in the register form."""
    _go_to_register(page)

    label = page.locator("label[for='f-name']")
    count = label.count()
    assert count >= 1, (
        "Expected a <label for='f-name'> element in the register form, found none"
    )
    expect(label.first).to_be_visible(timeout=3000)
