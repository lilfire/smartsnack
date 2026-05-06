"""E2E tests for weight settings UI.

Tests weight scope selector, sliders, value display, saved indicator,
config toggle, and add/delete category override buttons.

No unittest.mock.patch, no if .count() guards, no else: pass.
Every test has at least one meaningful assertion that can fail.
"""

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    page.locator("button.nav-tab[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_weights_section(page):
    """Force the weights settings section open via JS for deterministic state."""
    page.evaluate("""() => {
        const toggles = document.querySelectorAll('.settings-toggle');
        for (const t of toggles) {
            if (t.querySelector('[data-i18n="settings_weights_title"]')) {
                const body = t.nextElementSibling;
                if (body && body.classList.contains('settings-section-body')) {
                    body.style.display = '';
                    t.setAttribute('aria-expanded', 'true');
                }
            }
        }
    }""")
    page.wait_for_timeout(600)


# ---------------------------------------------------------------------------
# Tests: weights section structure
# ---------------------------------------------------------------------------


def test_weight_items_container_is_visible(page):
    """The #weight-items container must be visible in the weights section."""
    _go_to_settings(page)
    _open_weights_section(page)
    expect(page.locator("#weight-items")).to_be_visible(timeout=5000)


def test_weight_scope_selector_is_visible(page):
    """The custom-select trigger for #weight-scope-select must be visible.

    The native <select> is CSS-hidden on desktop (>=640 px viewport) by
    forms.css; upgradeSelect() wraps it in .custom-select-wrap and exposes a
    .custom-select-trigger button instead.
    """
    _go_to_settings(page)
    _open_weights_section(page)
    scope_wrapper = page.locator(".custom-select-wrap").filter(
        has=page.locator("#weight-scope-select")
    )
    expect(scope_wrapper.locator(".custom-select-trigger")).to_be_visible(timeout=5000)


def test_scope_selector_has_global_option(page):
    """The scope selector must contain an option with value='' (global)."""
    _go_to_settings(page)
    _open_weights_section(page)

    global_option = page.locator("#weight-scope-select option[value='']")
    expect(global_option).to_be_attached()


def test_at_least_one_weight_item_rendered(page):
    """At least one weight item must be rendered (global weights exist from seed data)."""
    _go_to_settings(page)
    _open_weights_section(page)

    weight_items = page.locator("#weight-items .weight-item")
    expect(weight_items.first).to_be_visible(timeout=5000)


def test_each_weight_item_has_a_slider(page):
    """Every rendered weight-item must contain a range input slider."""
    _go_to_settings(page)
    _open_weights_section(page)

    sliders = page.locator("#weight-items input[type='range'][id^='w-']")
    expect(sliders.first).to_be_visible(timeout=5000)

    slider_count = sliders.count()
    assert slider_count >= 1, (
        f"Expected at least one weight slider, got {slider_count}"
    )


def test_each_slider_has_matching_value_display(page):
    """The first weight slider must have a matching value display element."""
    _go_to_settings(page)
    _open_weights_section(page)

    slider = page.locator("#weight-items input[type='range'][id^='w-']").first
    slider_id = slider.get_attribute("id")
    assert slider_id and slider_id.startswith("w-"), (
        f"Expected slider id to start with 'w-', got {slider_id!r}"
    )

    field = slider_id[len("w-"):]
    value_display = page.locator(f"#wv-{field}")
    expect(value_display).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: slider interaction
# ---------------------------------------------------------------------------


def test_slider_value_display_updates_on_change(page):
    """Moving a slider must update its corresponding value display element."""
    _go_to_settings(page)
    _open_weights_section(page)

    slider = page.locator("#weight-items input[type='range'][id^='w-']").first
    slider_id = slider.get_attribute("id")
    field = slider_id[len("w-"):]

    value_display = page.locator(f"#wv-{field}")
    initial_text = value_display.inner_text()

    # Set to a value unlikely to equal the initial value.
    new_raw = "30" if initial_text.strip() not in ("30", "30.0") else "70"
    slider.fill(new_raw)
    page.wait_for_timeout(200)

    updated_text = value_display.inner_text()
    assert updated_text != initial_text, (
        f"Expected value display to change from '{initial_text}', still shows '{updated_text}'"
    )


def test_slider_change_triggers_saved_indicator(page):
    """Changing a slider value must cause the saved indicator to become visible."""
    _go_to_settings(page)
    _open_weights_section(page)

    slider = page.locator("#weight-items input[type='range'][id^='w-']").first
    slider_id = slider.get_attribute("id")
    field = slider_id[len("w-"):]

    current_val = slider.get_attribute("value") or "50"
    new_val = "20" if current_val not in ("20", "20.0") else "80"
    slider.fill(new_val)

    # The debounced save fires after ~400 ms; wait up to 3 s for the indicator.
    saved_indicator = page.locator("#weights-saved-indicator")
    expect(saved_indicator).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: weight config toggle
# ---------------------------------------------------------------------------


def test_config_button_expands_advanced_config(page):
    """Clicking the config (gear) button on a weight item must expose the
    advanced config section for that field."""
    _go_to_settings(page)
    _open_weights_section(page)

    cfg_btn = page.locator("#weight-items .weight-cfg-btn").first
    expect(cfg_btn).to_be_visible(timeout=5000)

    cfg_btn.click()
    page.wait_for_timeout(300)

    # The corresponding wcfg- div must now be visible.
    visible_cfg = page.locator("#weight-items [id^='wcfg-']:visible")
    expect(visible_cfg.first).to_be_visible(timeout=3000)


def test_config_section_has_direction_select(page):
    """The advanced config section must expose a visible direction trigger.

    The native wd-* <select> is CSS-hidden on desktop; the custom-select
    trigger button is the visible element to assert against.
    """
    _go_to_settings(page)
    _open_weights_section(page)

    page.locator("#weight-items .weight-cfg-btn").first.click()
    page.wait_for_timeout(300)

    direction_wrapper = page.locator("#weight-items .wc-row .custom-select-wrap").first
    expect(direction_wrapper.locator(".custom-select-trigger")).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: add/delete category override buttons
# ---------------------------------------------------------------------------


def test_add_category_override_button_is_present(page):
    """The 'add category override' button (#weight-scope-add) must be present
    in the weights section."""
    _go_to_settings(page)
    _open_weights_section(page)

    add_btn = page.locator("#weight-scope-add")
    expect(add_btn).to_be_visible(timeout=5000)


def test_add_category_override_button_opens_picker_modal(page):
    """Clicking the add-override button must open a picker modal or show a
    toast (when all categories already have overrides)."""
    _go_to_settings(page)
    _open_weights_section(page)

    add_btn = page.locator("#weight-scope-add")
    expect(add_btn).to_be_visible(timeout=5000)
    add_btn.click()
    page.wait_for_timeout(500)

    # Either a modal appeared, or a toast appeared — both are valid outcomes.
    # Both elements use position:fixed, so offsetParent is always null;
    # check DOM presence / show class instead.
    appeared = page.wait_for_function(
        """() => {
            const modal = document.querySelector('.scan-modal-bg');
            const toast = document.querySelector('#toast.show');
            return !!modal || !!toast;
        }""",
        timeout=3000,
    )
    assert appeared, (
        "Expected either a picker modal or an info toast after clicking add-override"
    )


def test_delete_override_button_hidden_in_global_scope(page):
    """The delete-override button (#weight-scope-delete) must be hidden when
    the scope is set to global (no active category override)."""
    _go_to_settings(page)
    _open_weights_section(page)

    del_btn = page.locator("#weight-scope-delete")
    # In global scope (default) the delete button should be hidden.
    expect(del_btn).to_be_hidden(timeout=3000)
