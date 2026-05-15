"""E2E tests for the emoji picker popup.

Tests: trigger button visible, opening the popup, search input, emoji grid,
selecting an emoji updates the trigger, search filtering, no-results message,
close on Escape, close on outside click.

No unittest.mock.patch, no if .count() guards, no trivially-passing assertions.
"""

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    page.locator("button.nav-tab[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_categories_section(page):
    """Force the categories settings section open for deterministic state."""
    page.evaluate("""() => {
        const toggles = document.querySelectorAll('.settings-toggle');
        for (const t of toggles) {
            if (t.querySelector('[data-i18n="settings_categories_title"]')) {
                const body = t.nextElementSibling;
                if (body && body.classList.contains('settings-section-body')) {
                    body.style.display = '';
                    t.setAttribute('aria-expanded', 'true');
                }
            }
        }
    }""")
    page.wait_for_timeout(600)


def _open_picker(page):
    """Click the first cat-item emoji trigger and wait for the popup."""
    trigger = page.locator(".cat-item-emoji-edit").first
    expect(trigger).to_be_visible(timeout=5000)
    trigger.click()
    page.wait_for_timeout(300)
    popup = page.locator(".emoji-picker-popup")
    expect(popup).to_be_visible(timeout=3000)
    return trigger, popup


# ---------------------------------------------------------------------------
# Tests: add-category emoji trigger (in the add form)
# ---------------------------------------------------------------------------


def test_add_category_emoji_trigger_is_attached(page):
    """The #cat-emoji-trigger button for the add-category form must be
    attached to the DOM in the categories section."""
    _go_to_settings(page)
    _open_categories_section(page)

    trigger = page.locator("#cat-emoji-trigger")
    expect(trigger).to_be_attached()


def test_add_category_emoji_trigger_opens_popup(page):
    """Clicking #cat-emoji-trigger must open the emoji picker popup."""
    _go_to_settings(page)
    _open_categories_section(page)

    page.locator("#cat-emoji-trigger").click()
    page.wait_for_timeout(300)

    popup = page.locator(".emoji-picker-popup")
    expect(popup).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: category list emoji triggers
# ---------------------------------------------------------------------------


def test_category_emoji_triggers_exist_in_list(page):
    """At least one .cat-item-emoji-edit trigger must be present (seed
    categories always exist)."""
    _go_to_settings(page)
    _open_categories_section(page)

    triggers = page.locator(".cat-item-emoji-edit")
    count = triggers.count()
    assert count >= 1, f"Expected at least one emoji trigger, got {count}"


def test_emoji_picker_opens_on_category_trigger_click(page):
    """Clicking a .cat-item-emoji-edit button must open the emoji popup."""
    _go_to_settings(page)
    _open_categories_section(page)
    _open_picker(page)


# ---------------------------------------------------------------------------
# Tests: popup contents
# ---------------------------------------------------------------------------


def test_emoji_picker_has_search_input(page):
    """The emoji popup must contain a search input."""
    _go_to_settings(page)
    _open_categories_section(page)
    _, popup = _open_picker(page)

    search = popup.locator(".emoji-picker-search")
    expect(search).to_be_visible(timeout=3000)


def test_emoji_picker_has_emoji_grid(page):
    """The emoji popup must contain a grid of emoji buttons."""
    _go_to_settings(page)
    _open_categories_section(page)
    _, popup = _open_picker(page)

    grid = popup.locator(".emoji-picker-grid")
    expect(grid).to_be_visible(timeout=3000)


def test_emoji_picker_grid_has_items(page):
    """The emoji grid must contain at least one emoji button."""
    _go_to_settings(page)
    _open_categories_section(page)
    _open_picker(page)

    items = page.locator(".emoji-picker-item")
    count = items.count()
    assert count >= 1, f"Expected emoji items in the grid, got {count}"


# ---------------------------------------------------------------------------
# Tests: selecting an emoji
# ---------------------------------------------------------------------------


def test_selecting_emoji_closes_popup(page):
    """Clicking an emoji item must close the popup."""
    _go_to_settings(page)
    _open_categories_section(page)
    _, popup = _open_picker(page)

    first_emoji = page.locator(".emoji-picker-item").first
    expect(first_emoji).to_be_visible(timeout=3000)
    first_emoji.click()
    page.wait_for_timeout(300)

    expect(popup).to_be_hidden(timeout=3000)


def test_selecting_emoji_updates_trigger_text(page):
    """Clicking an emoji item must update the trigger button's text content."""
    _go_to_settings(page)
    _open_categories_section(page)
    trigger, _ = _open_picker(page)

    first_item = page.locator(".emoji-picker-item").first
    selected_emoji = first_item.inner_text()

    first_item.click()
    page.wait_for_timeout(300)

    trigger_text = trigger.inner_text().strip()
    assert trigger_text == selected_emoji.strip(), (
        f"Expected trigger to show '{selected_emoji.strip()}', got '{trigger_text}'"
    )


# ---------------------------------------------------------------------------
# Tests: search filtering
# ---------------------------------------------------------------------------


def test_search_reduces_visible_item_count(page):
    """Typing a specific term must reduce the number of visible emoji items
    compared to the unfiltered count."""
    _go_to_settings(page)
    _open_categories_section(page)
    _open_picker(page)

    items = page.locator(".emoji-picker-item")
    total_before = items.count()
    assert total_before >= 2, (
        f"Need at least 2 emoji items to test filtering, got {total_before}"
    )

    search = page.locator(".emoji-picker-search")
    search.fill("apple")
    page.wait_for_timeout(300)

    # Count visible (non-hidden) items after filtering.
    visible_after = page.evaluate(
        "() => [...document.querySelectorAll('.emoji-picker-item')]"
        ".filter(el => el.style.display !== 'none').length"
    )
    assert visible_after < total_before, (
        f"Expected fewer items after search filter "
        f"({visible_after} < {total_before})"
    )


def test_search_with_no_match_shows_empty_message(page):
    """Searching for a nonsense term must show the no-results message and
    hide the regular emoji items."""
    _go_to_settings(page)
    _open_categories_section(page)
    _open_picker(page)

    search = page.locator(".emoji-picker-search")
    search.fill("xyznonexistent99999")
    page.wait_for_timeout(300)

    empty_msg = page.locator(".emoji-picker-empty")
    expect(empty_msg).to_be_visible(timeout=3000)

    # No regular emoji items should be visible.
    visible_items = page.evaluate(
        "() => [...document.querySelectorAll('.emoji-picker-item')]"
        ".filter(el => !el.classList.contains('emoji-picker-empty') "
        "         && el.style.display !== 'none').length"
    )
    assert visible_items == 0, (
        f"Expected 0 visible emoji items for nonsense query, got {visible_items}"
    )


def test_clearing_search_restores_all_items(page):
    """Clearing the search input must restore the full emoji grid."""
    _go_to_settings(page)
    _open_categories_section(page)
    _open_picker(page)

    items = page.locator(".emoji-picker-item:not(.emoji-picker-empty)")
    total_before = items.count()

    search = page.locator(".emoji-picker-search")
    search.fill("apple")
    page.wait_for_timeout(200)

    search.fill("")
    page.wait_for_timeout(200)

    visible_after = page.evaluate(
        "() => [...document.querySelectorAll('.emoji-picker-item')]"
        ".filter(el => !el.classList.contains('emoji-picker-empty') "
        "         && el.style.display !== 'none').length"
    )
    assert visible_after == total_before, (
        f"Expected all {total_before} items visible after clearing search, "
        f"got {visible_after}"
    )


# ---------------------------------------------------------------------------
# Tests: closing the popup
# ---------------------------------------------------------------------------


def test_popup_closes_on_escape(page):
    """Pressing Escape must close the emoji picker popup."""
    _go_to_settings(page)
    _open_categories_section(page)
    _, popup = _open_picker(page)

    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    expect(popup).to_be_hidden(timeout=3000)


def test_popup_closes_on_outside_click(page):
    """Clicking outside the popup (on the page body far from the trigger) must
    close the popup."""
    _go_to_settings(page)
    _open_categories_section(page)
    _, popup = _open_picker(page)

    # Click a safe region at the top-left corner that is not inside the popup.
    page.locator("h1, #view-settings").first.click(position={"x": 5, "y": 5})
    page.wait_for_timeout(400)

    expect(popup).to_be_hidden(timeout=3000)


def test_clicking_trigger_again_closes_popup(page):
    """Clicking the same trigger button while the popup is open must close it
    (toggle behaviour)."""
    _go_to_settings(page)
    _open_categories_section(page)
    trigger, popup = _open_picker(page)

    # Click trigger a second time — should close.
    trigger.click()
    page.wait_for_timeout(300)

    expect(popup).to_be_hidden(timeout=3000)
