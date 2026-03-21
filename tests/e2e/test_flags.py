"""E2E tests for flag management via API and UI."""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Settings navigation helpers (same pattern as test_settings.py)
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
# API helper utilities
# ---------------------------------------------------------------------------


def _api_get(live_url, path):
    """Perform a GET request and return the parsed JSON body."""
    with urllib.request.urlopen(f"{live_url}{path}", timeout=5) as resp:
        return json.loads(resp.read())


def _api_post(live_url, path, payload):
    """Perform a POST request with a JSON body; return (status_code, body)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _api_put(live_url, path, payload):
    """Perform a PUT request with a JSON body; return (status_code, body)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _api_delete(live_url, path):
    """Perform a DELETE request; return (status_code, body)."""
    req = urllib.request.Request(
        f"{live_url}{path}",
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# API-only tests
# ---------------------------------------------------------------------------


def test_flags_api_list(live_url):
    """GET /api/flags should return a list of flag objects."""
    flags = _api_get(live_url, "/api/flags")

    assert isinstance(flags, list), "Response should be a list"
    assert len(flags) >= 1, "At least one seeded flag should exist"

    # Verify the shape of each entry
    for flag in flags:
        assert "name" in flag, "Flag entry must have a 'name' key"
        assert "label" in flag, "Flag entry must have a 'label' key"
        assert "type" in flag, "Flag entry must have a 'type' key"
        assert "count" in flag, "Flag entry must have a 'count' key"
        assert isinstance(flag["count"], int), "'count' must be an integer"


def test_flags_api_crud(live_url):
    """POST a new flag, verify it appears in the list, PUT to update, then DELETE."""
    flag_name = "is_e2e_crud_test"
    flag_label = "E2E CRUD Test"
    updated_label = "E2E CRUD Updated"

    # Clean up any leftover flag from a previous run so the test is idempotent
    _api_delete(live_url, f"/api/flags/{flag_name}")

    # POST — create the flag
    status, body = _api_post(live_url, "/api/flags", {"name": flag_name, "label": flag_label})
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert body.get("ok") is True

    # Verify the flag appears in the list
    flags = _api_get(live_url, "/api/flags")
    names = [f["name"] for f in flags]
    assert flag_name in names, f"Newly created flag '{flag_name}' not found in list"

    # PUT — update the label
    status, body = _api_put(live_url, f"/api/flags/{flag_name}", {"label": updated_label})
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body.get("ok") is True

    # DELETE the flag
    status, body = _api_delete(live_url, f"/api/flags/{flag_name}")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body.get("ok") is True

    # Verify the flag is gone from the list
    flags = _api_get(live_url, "/api/flags")
    names = [f["name"] for f in flags]
    assert flag_name not in names, f"Deleted flag '{flag_name}' still appears in list"


def test_flag_config_api(live_url):
    """GET /api/flag-config should return a dict containing system flag entries."""
    config = _api_get(live_url, "/api/flag-config")

    assert isinstance(config, dict), "Response should be a dict"
    assert len(config) >= 1, "At least one flag config entry should exist"

    # is_synced_with_off is a known system flag seeded by init_db
    assert "is_synced_with_off" in config, (
        "System flag 'is_synced_with_off' must appear in flag-config"
    )

    # Verify the shape of a config entry
    entry = config["is_synced_with_off"]
    assert "type" in entry, "Config entry must have a 'type' key"
    assert "labelKey" in entry, "Config entry must have a 'labelKey' key"
    assert "label" in entry, "Config entry must have a 'label' key"
    assert entry["type"] == "system", (
        "is_synced_with_off should have type 'system'"
    )


# ---------------------------------------------------------------------------
# UI tests
# ---------------------------------------------------------------------------


def test_flag_label_edit_via_ui(page, live_url):
    """Add a flag via API, navigate to settings, change the label, verify toast."""
    flag_name = "is_e2e_label_edit"
    flag_label = "E2E Label Edit"

    # Ensure clean state
    _api_delete(live_url, f"/api/flags/{flag_name}")
    status, body = _api_post(live_url, "/api/flags", {"name": flag_name, "label": flag_label})
    assert status == 201, f"Setup: expected 201, got {status}: {body}"

    try:
        _go_to_settings(page)
        _open_section(page, "settings_flags_title")

        # The flag list must be visible
        expect(page.locator("#flag-list")).to_be_visible(timeout=5000)

        # Locate the label input for the specific flag
        label_input = page.locator(f"input[data-flag-name='{flag_name}']").first
        expect(label_input).to_be_visible(timeout=5000)

        # Change the label value and fire a change event to trigger the save
        label_input.fill("E2E Label Edited")
        label_input.dispatch_event("change")

        # A toast should appear confirming the update
        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)
    finally:
        # Clean up regardless of test outcome
        _api_delete(live_url, f"/api/flags/{flag_name}")


def test_delete_flag_via_ui(page, live_url):
    """Add a flag via API, navigate to settings, delete via UI button, verify toast."""
    flag_name = "is_e2e_delete_ui"
    flag_label = "E2E Delete UI"

    # Ensure clean state
    _api_delete(live_url, f"/api/flags/{flag_name}")
    status, body = _api_post(live_url, "/api/flags", {"name": flag_name, "label": flag_label})
    assert status == 201, f"Setup: expected 201, got {status}: {body}"

    _go_to_settings(page)
    _open_section(page, "settings_flags_title")

    # The flag list must be visible
    expect(page.locator("#flag-list")).to_be_visible(timeout=5000)

    # Find the flag item for the specific flag and click its delete button
    flag_item = page.locator(f".flag-item:has(input[data-flag-name='{flag_name}'])").first
    expect(flag_item).to_be_visible(timeout=5000)

    delete_btn = flag_item.locator("[data-action='delete-flag']")
    expect(delete_btn).to_be_visible(timeout=3000)
    delete_btn.click()

    # Confirm the modal dialog
    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # A toast should appear confirming the deletion
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_system_flags_not_editable(page):
    """System flags should carry a type badge and have no delete button."""
    _go_to_settings(page)
    _open_section(page, "settings_flags_title")

    expect(page.locator("#flag-list")).to_be_visible(timeout=5000)

    # Collect all system flag items
    system_items = page.locator(".flag-item-system")
    count = system_items.count()
    assert count >= 1, (
        "At least one system flag item (.flag-item-system) should be present"
    )

    # Every system flag item must have the type badge and no delete button
    for i in range(count):
        item = system_items.nth(i)

        # Type badge must be present
        badge = item.locator(".flag-type-badge.flag-type-system")
        expect(badge).to_be_visible(timeout=3000)

        # Delete button must not exist inside a system flag item
        delete_btn = item.locator("[data-action='delete-flag']")
        assert delete_btn.count() == 0, (
            f"System flag item {i} should not have a delete button"
        )
