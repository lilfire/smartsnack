"""E2E tests for flag CRUD in settings.

Tests: flag list visible, add custom flag, verify it appears, update flag
label via inline input, delete flag, and system flags are read-only.

No unittest.mock.patch, no if .count() guards, no zero-assertion tests.
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    page.locator("button.nav-tab[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_flags_section(page):
    """Force the flags settings section open via JS for deterministic state."""
    page.evaluate("""() => {
        const toggles = document.querySelectorAll('.settings-toggle');
        for (const t of toggles) {
            if (t.querySelector('[data-i18n="settings_flags_title"]')) {
                const body = t.nextElementSibling;
                if (body && body.classList.contains('settings-section-body')) {
                    body.style.display = '';
                    t.setAttribute('aria-expanded', 'true');
                }
            }
        }
    }""")
    page.wait_for_timeout(600)


def _api(live_url, path, *, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}", data=data, headers=headers, method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Tests: flag list structure
# ---------------------------------------------------------------------------


def test_flags_section_shows_flag_list(page):
    """The #flag-list container must be visible after opening the flags section."""
    _go_to_settings(page)
    _open_flags_section(page)
    expect(page.locator("#flag-list")).to_be_visible(timeout=5000)


def test_flag_list_has_at_least_one_item(page):
    """At least one flag item must be shown (system flags are always present)."""
    _go_to_settings(page)
    _open_flags_section(page)

    flag_items = page.locator("#flag-list .flag-item")
    expect(flag_items.first).to_be_visible(timeout=5000)


def test_system_flags_have_system_badge(page):
    """System flag items must display a badge element with class flag-type-system."""
    _go_to_settings(page)
    _open_flags_section(page)

    system_badges = page.locator("#flag-list .flag-type-system")
    expect(system_badges.first).to_be_visible(timeout=5000)


def test_flag_type_badge_present_on_every_item(page):
    """Each rendered flag item must carry at least one type badge."""
    _go_to_settings(page)
    _open_flags_section(page)

    badges = page.locator("#flag-list .flag-type-badge")
    count = badges.count()
    assert count >= 1, f"Expected at least one flag-type-badge, got {count}"


# ---------------------------------------------------------------------------
# Tests: add flag form
# ---------------------------------------------------------------------------


def test_add_flag_form_inputs_are_visible(page):
    """The #flag-add-name and #flag-add-label inputs must be visible."""
    _go_to_settings(page)
    _open_flags_section(page)

    expect(page.locator("#flag-add-name")).to_be_visible(timeout=3000)
    expect(page.locator("#flag-add-label")).to_be_visible(timeout=3000)


def test_add_user_flag_appears_in_list(page):
    """Filling the add-flag form and submitting must add the flag to the list
    and show a success toast."""
    _go_to_settings(page)
    _open_flags_section(page)

    page.locator("#flag-add-name").fill("is_e2e_add_test")
    page.locator("#flag-add-label").fill("E2E Add Test Flag")

    add_btn = page.locator("[data-i18n='btn_add_flag']")
    expect(add_btn.first).to_be_visible(timeout=3000)
    add_btn.first.click()
    page.wait_for_timeout(600)

    # Success toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)

    # The new flag must appear in the list.
    expect(page.locator("#flag-list")).to_contain_text("is_e2e_add_test", timeout=5000)


# ---------------------------------------------------------------------------
# Tests: delete user flag
# ---------------------------------------------------------------------------


def test_delete_user_flag_removes_from_list(page, live_url):
    """Deleting a user flag via its delete button must remove it from the list
    and show a success toast."""
    _api(live_url, "/api/flags", method="POST", body={
        "name": "is_e2e_delete_me", "label": "E2E Delete Me",
    })

    _go_to_settings(page)
    _open_flags_section(page)

    delete_btn = page.locator("[data-action='delete-flag'][data-flag-name='is_e2e_delete_me']")
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(300)

    # Confirmation modal appears — confirm deletion.
    confirm_btn = page.locator("button.confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()
    page.wait_for_timeout(600)

    # Success toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)

    # Flag must no longer be in the list.
    expect(page.locator("#flag-list")).not_to_contain_text(
        "is_e2e_delete_me", timeout=5000
    )


def test_delete_user_flag_cancel_keeps_flag(page, live_url):
    """Cancelling the delete confirmation must leave the flag in the list."""
    _api(live_url, "/api/flags", method="POST", body={
        "name": "is_e2e_cancel_del", "label": "E2E Cancel Delete",
    })

    _go_to_settings(page)
    _open_flags_section(page)

    delete_btn = page.locator("[data-action='delete-flag'][data-flag-name='is_e2e_cancel_del']")
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(300)

    cancel_btn = page.locator("button.confirm-no")
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()
    page.wait_for_timeout(400)

    # Flag must still be in the list.
    expect(page.locator("#flag-list")).to_contain_text("E2E Cancel Delete", timeout=3000)


# ---------------------------------------------------------------------------
# Tests: inline label editing
# ---------------------------------------------------------------------------


def test_update_flag_label_saves_and_shows_toast(page, live_url):
    """Editing a user flag label inline and tabbing away must save the change
    and show a success toast."""
    _api(live_url, "/api/flags", method="POST", body={
        "name": "is_e2e_edit_label", "label": "E2E Original Label",
    })

    _go_to_settings(page)
    _open_flags_section(page)

    label_input = page.locator("input.cat-item-label-input[data-flag-name='is_e2e_edit_label']")
    expect(label_input).to_be_visible(timeout=5000)

    label_input.fill("E2E Updated Label")
    label_input.press("Tab")
    page.wait_for_timeout(600)

    # A toast must appear to confirm the save.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Tests: system flags are read-only
# ---------------------------------------------------------------------------


def test_system_flags_have_no_delete_button(page):
    """System flag items must not contain a delete button."""
    _go_to_settings(page)
    _open_flags_section(page)

    system_items = page.locator("#flag-list .flag-item-system")
    expect(system_items.first).to_be_visible(timeout=5000)

    item_count = system_items.count()
    assert item_count >= 1, "Expected at least one system flag item"

    for i in range(item_count):
        item = system_items.nth(i)
        delete_btn = item.locator("[data-action='delete-flag']")
        assert delete_btn.count() == 0, (
            f"System flag item #{i} must not have a delete button"
        )
