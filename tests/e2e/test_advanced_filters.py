"""E2E tests for the advanced filter panel.

The advanced filter panel is toggled by ``#adv-filter-toggle``.  When open,
the panel element ``#advanced-filters`` gains the CSS class ``open`` and the
normal ``#search-input`` is disabled.  Each condition is represented by an
``.adv-row`` containing field/operator/value controls.

Because ``upgradeSelect`` (in ``state.js``) replaces native ``<select>``
elements with a custom dropdown at viewport widths >= 640 px, all select
interactions in these tests go through the custom UI:

1. Click the ``.custom-select-trigger`` button to open the dropdown.
2. Click the ``.custom-select-option[data-value='<value>']`` div to pick a value.

The value input (``.adv-value-input``) remains a native ``<input>`` and is
filled with ``locator.fill()``.

After changing a filter value the tests wait 500 ms to allow the 300 ms input
debounce plus the subsequent async ``loadData`` call to complete.
"""

import re

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _open_advanced_filters(page) -> None:
    """Click the toggle to open the advanced filter panel and wait for it.

    Args:
        page: Playwright page object.
    """
    page.locator("#adv-filter-toggle").click()
    # The panel opens via requestAnimationFrame; give it a moment.
    page.wait_for_timeout(150)


def _close_advanced_filters(page) -> None:
    """Click the toggle again to close the advanced filter panel.

    Args:
        page: Playwright page object.
    """
    page.locator("#adv-filter-toggle").click()
    page.wait_for_timeout(150)


def _reload_and_wait(page) -> None:
    """Reload the page and wait until the product list finishes loading.

    Args:
        page: Playwright page object.
    """
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _select_custom_option(page, trigger_locator, data_value: str) -> None:
    """Open a custom select dropdown and pick a specific option by data-value.

    The ``upgradeSelect`` helper in ``state.js`` wraps native ``<select>``
    elements with a ``.custom-select-wrap`` div that contains a trigger
    button and a panel of ``.custom-select-option`` divs.  Native
    ``select_option()`` does not work once the select is inside the wrapper,
    so this helper clicks through the custom UI instead.

    Args:
        page: Playwright page object.
        trigger_locator: Playwright locator for the ``.custom-select-trigger``
            button belonging to the select that should be changed.
        data_value: The ``data-value`` attribute of the desired option div.
    """
    trigger_locator.click()
    page.wait_for_timeout(100)
    # The option panel is a sibling of the trigger inside .custom-select-wrap.
    # Use a CSS attribute selector to find the correct option regardless of
    # how many custom selects are present on the page.
    option = page.locator(
        f".custom-select-wrap.open .custom-select-option[data-value='{data_value}']"
    )
    option.click()
    page.wait_for_timeout(100)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_advanced_filters_open_close(page):
    """Toggle opens the panel (adds 'open' class) and toggle again closes it.

    The ``#advanced-filters`` element must have the class ``open`` immediately
    after the first click, and must not have it after the second click.
    """
    adv_panel = page.locator("#advanced-filters")

    _open_advanced_filters(page)
    expect(adv_panel).to_have_class(re.compile(r"\bopen\b"), timeout=2000)

    _close_advanced_filters(page)
    # After close the element stays in the DOM but without 'open'.
    expect(adv_panel).not_to_have_class(re.compile(r"\bopen\b"), timeout=2000)


def test_advanced_filters_disables_search(page):
    """Opening advanced filters must disable the normal search input.

    The ``toggleAdvancedFilters`` function in ``advanced-filters.js`` sets
    ``searchInput.disabled = true`` when entering advanced mode.
    """
    search_input = page.locator("#search-input")
    expect(search_input).to_be_enabled()

    _open_advanced_filters(page)
    expect(search_input).to_be_disabled()


def test_advanced_filters_initial_condition_row(page):
    """Opening advanced filters creates exactly one condition row with all controls.

    The panel must contain one ``.adv-row`` with a field select trigger, an
    operator select trigger, and a value input.
    """
    _open_advanced_filters(page)

    rows = page.locator(".adv-row")
    expect(rows).to_have_count(1)

    first_row = rows.first
    # Field select is wrapped by upgradeSelect — verify the trigger is present.
    expect(first_row.locator(".custom-select-trigger").first).to_be_visible()
    # Value input is a plain <input>.
    expect(first_row.locator(".adv-value-input")).to_be_visible()


def test_add_condition(page):
    """Clicking the 'add condition' button appends a second condition row.

    After the click the panel must contain exactly two ``.adv-row`` elements.
    """
    _open_advanced_filters(page)

    # The first .adv-add-condition-btn adds conditions (the second adds subgroups).
    page.locator(".adv-add-condition-btn").first.click()
    page.wait_for_timeout(150)

    rows = page.locator(".adv-row")
    expect(rows).to_have_count(2)


def test_logic_toggle_visible_with_two_conditions(page):
    """The AND/OR logic toggle button must become visible when 2+ conditions exist.

    The button starts with ``visibility: hidden`` and is set to
    ``visibility: visible`` by ``_updateVisibilityAll`` once a second child
    is added to the group.
    """
    _open_advanced_filters(page)

    # Add a second condition to make the logic toggle appear.
    page.locator(".adv-add-condition-btn").first.click()
    page.wait_for_timeout(150)

    logic_btn = page.locator(".adv-group-logic-btn").first
    # The button exists in the DOM — check its computed visibility style is
    # not 'hidden' (the JS sets style.visibility, not display).
    visibility = logic_btn.evaluate("el => window.getComputedStyle(el).visibility")
    assert visibility != "hidden", (
        f"Expected .adv-group-logic-btn to be visible with 2 conditions, "
        f"but got visibility='{visibility}'"
    )


def test_filter_by_numeric_field(page, api_create_product):
    """Filtering by kcal > 300 should show only the high-calorie product.

    Two products are created: one with kcal=100 and one with kcal=500.  After
    applying the filter only the 500 kcal product should appear in
    ``#results-container``.
    """
    api_create_product(name="LowKcalProduct", kcal=100)
    api_create_product(name="HighKcalProduct", kcal=500)

    _reload_and_wait(page)
    _open_advanced_filters(page)

    first_row = page.locator(".adv-row").first

    # --- Select field: kcal ---
    field_trigger = first_row.locator(".custom-select-trigger").first
    _select_custom_option(page, field_trigger, "kcal")

    # After changing the field, the op select is rebuilt.  Wait briefly for
    # the DOM update triggered by upgradeSelect's callback.
    page.wait_for_timeout(200)

    # --- Select operator: ">" ---
    # The operator select is the second custom-select-trigger in the row.
    op_trigger = first_row.locator(".custom-select-trigger").nth(1)
    _select_custom_option(page, op_trigger, ">")

    # --- Enter value ---
    value_input = first_row.locator(".adv-value-input")
    value_input.fill("300")

    # Wait for the 300 ms debounce + async loadData round-trip.
    page.wait_for_timeout(600)

    results = page.locator("#results-container")
    expect(results).to_contain_text("HighKcalProduct")
    expect(results).not_to_contain_text("LowKcalProduct")


def test_filter_by_text_field(page, api_create_product):
    """Filtering by name contains 'Zephyr' should show only the matching product.

    Two products are created with distinct names.  The advanced filter is
    configured as ``name contains Zephyr`` and only the matching product must
    appear in results.
    """
    api_create_product(name="ZephyrSnackBar")
    api_create_product(name="OrdinaryMuesli")

    _reload_and_wait(page)
    _open_advanced_filters(page)

    first_row = page.locator(".adv-row").first

    # --- Select field: name ---
    # 'name' is the default field, but select it explicitly for clarity.
    field_trigger = first_row.locator(".custom-select-trigger").first
    _select_custom_option(page, field_trigger, "name")

    page.wait_for_timeout(200)

    # --- Select operator: contains ---
    op_trigger = first_row.locator(".custom-select-trigger").nth(1)
    _select_custom_option(page, op_trigger, "contains")

    # --- Enter value ---
    value_input = first_row.locator(".adv-value-input")
    value_input.fill("Zephyr")

    # Wait for debounce + API.
    page.wait_for_timeout(600)

    results = page.locator("#results-container")
    expect(results).to_contain_text("ZephyrSnackBar")
    expect(results).not_to_contain_text("OrdinaryMuesli")


def test_close_advanced_filters_restores_search(page):
    """Closing the advanced filter panel must re-enable the search input.

    The ``toggleAdvancedFilters`` close branch sets
    ``searchInput.disabled = false``, restoring normal search behaviour.
    """
    search_input = page.locator("#search-input")

    _open_advanced_filters(page)
    expect(search_input).to_be_disabled()

    _close_advanced_filters(page)
    expect(search_input).to_be_enabled()
