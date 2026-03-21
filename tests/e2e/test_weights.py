"""E2E tests for weight/score configuration via API and UI."""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Settings navigation helpers (mirrored from test_settings.py)
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    """Open a settings section by its data-i18n key."""
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# Internal API helpers
# ---------------------------------------------------------------------------

_WEIGHTS_SECTION_KEY = "settings_weights_title"
_REQUIRED_FIELDS = {"field", "label", "weight", "enabled", "direction", "formula", "formula_min", "formula_max"}


def _get_weights(live_url: str) -> list:
    """Fetch the full list of weights from the API."""
    with urllib.request.urlopen(f"{live_url}/api/weights", timeout=5) as resp:
        return json.loads(resp.read())


def _put_weights(live_url: str, payload: list) -> dict:
    """Send a PUT request to /api/weights with *payload* and return the parsed response."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}/api/weights",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def test_weights_api_returns_list(live_url):
    """GET /api/weights must return a non-empty list with the expected fields on each item."""
    weights = _get_weights(live_url)

    assert isinstance(weights, list), "Response should be a list"
    assert len(weights) > 0, "At least one weight entry should be present"

    for item in weights:
        missing = _REQUIRED_FIELDS - item.keys()
        assert not missing, f"Weight item for '{item.get('field')}' is missing keys: {missing}"

        assert isinstance(item["field"], str) and item["field"], "field must be a non-empty string"
        assert isinstance(item["enabled"], bool), "enabled must be a boolean"
        assert isinstance(item["weight"], (int, float)), "weight must be numeric"
        assert item["direction"] in ("lower", "higher"), f"Unexpected direction: {item['direction']}"
        assert item["formula"] in ("minmax", "direct"), f"Unexpected formula: {item['formula']}"


def test_weights_api_update(live_url):
    """PUT /api/weights should persist a modified weight value and the change should be visible in GET."""
    original_weights = _get_weights(live_url)

    # Pick the first weight entry to modify.
    target = original_weights[0]
    field = target["field"]
    old_weight = target["weight"]
    new_weight = 42.0 if old_weight != 42.0 else 43.0

    update_payload = [
        {
            "field": field,
            "enabled": target["enabled"],
            "weight": new_weight,
            "direction": target["direction"],
            "formula": target["formula"],
            "formula_min": target["formula_min"],
            "formula_max": target["formula_max"],
        }
    ]

    response = _put_weights(live_url, update_payload)
    assert response.get("ok") is True, f"Expected ok=True, got: {response}"

    updated_weights = _get_weights(live_url)
    updated_item = next((w for w in updated_weights if w["field"] == field), None)
    assert updated_item is not None, f"Field '{field}' not found in GET response after PUT"
    assert updated_item["weight"] == new_weight, (
        f"Expected weight {new_weight} for '{field}', got {updated_item['weight']}"
    )

    # Restore the original weight so that other tests are not affected.
    restore_payload = [
        {
            "field": field,
            "enabled": target["enabled"],
            "weight": old_weight,
            "direction": target["direction"],
            "formula": target["formula"],
            "formula_min": target["formula_min"],
            "formula_max": target["formula_max"],
        }
    ]
    _put_weights(live_url, restore_payload)


# ---------------------------------------------------------------------------
# UI tests
# ---------------------------------------------------------------------------


def test_weight_items_displayed(page):
    """The weights section should expand and show at least one .weight-item child."""
    _go_to_settings(page)
    _open_section(page, _WEIGHTS_SECTION_KEY)

    weight_items_container = page.locator("#weight-items")
    expect(weight_items_container).to_be_visible()

    # At least one weight item should be rendered inside the container.
    items = weight_items_container.locator(".weight-item")
    expect(items.first).to_be_visible(timeout=5000)


def test_weight_slider_updates_value(page):
    """Changing a weight slider value via JS should update the paired display span."""
    _go_to_settings(page)
    _open_section(page, _WEIGHTS_SECTION_KEY)

    # Locate the first enabled weight item's slider.
    first_item = page.locator(".weight-item.enabled").first
    expect(first_item).to_be_visible(timeout=5000)

    # Extract the field name from the item's id attribute (format: wi-{field}).
    item_id = first_item.get_attribute("id")
    assert item_id and item_id.startswith("wi-"), f"Unexpected weight item id: {item_id!r}"
    field = item_id[len("wi-"):]

    slider_id = f"w-{field}"
    value_id = f"wv-{field}"

    slider = page.locator(f"#{slider_id}")
    expect(slider).to_be_attached()

    # Set a known value on the slider using JS and fire the input event so the
    # display span is updated by the UI's own event handler.
    target_value = "75"
    page.evaluate(
        """([sliderId, valueId, val]) => {
            const slider = document.getElementById(sliderId);
            if (!slider) throw new Error('Slider not found: ' + sliderId);
            slider.value = val;
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        [slider_id, value_id, target_value],
    )

    # The display span should now reflect the new value.
    value_display = page.locator(f"#{value_id}")
    # onWeightSlider formats with .toFixed(1), so 75 → "75.0"
    expect(value_display).to_have_text(f"{float(target_value):.1f}", timeout=3000)


def test_weight_advanced_config_toggle(page):
    """Clicking the advanced config button on a weight item should reveal the config section."""
    _go_to_settings(page)
    _open_section(page, _WEIGHTS_SECTION_KEY)

    # Work with the first enabled weight item.
    first_item = page.locator(".weight-item.enabled").first
    expect(first_item).to_be_visible(timeout=5000)

    item_id = first_item.get_attribute("id")
    assert item_id and item_id.startswith("wi-"), f"Unexpected weight item id: {item_id!r}"
    field = item_id[len("wi-"):]

    cfg_section_id = f"wcfg-{field}"

    # The config section should start hidden.
    cfg_section = page.locator(f"#{cfg_section_id}")
    expect(cfg_section).to_be_hidden()

    # Click the advanced config button inside the weight item.
    cfg_btn = first_item.locator(".weight-cfg-btn")
    expect(cfg_btn).to_be_visible()
    cfg_btn.click()

    # After clicking, the config section should become visible.
    expect(cfg_section).to_be_visible(timeout=3000)
