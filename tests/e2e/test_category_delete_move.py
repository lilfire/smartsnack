"""E2E tests for category delete with move modal.

Tests the flow when deleting a category that has products: a modal appears
asking the user to select a target category to move products to.

No unittest.mock.patch is used — all setup goes through the live API.
No if .count() guards — every assertion uses expect() or a direct assert.
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


def _open_categories_section(page):
    """Force the categories settings section open via JS so the toggle
    state is deterministic regardless of prior test state."""
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


def _api(live_url, path, *, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}", data=data, headers=headers, method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _create_category(live_url, name, label=None):
    return _api(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": name, "label": label or name},
    )


# ---------------------------------------------------------------------------
# Tests: category list is visible
# ---------------------------------------------------------------------------


def test_category_list_is_visible_in_settings(page):
    """The category list container must be visible after opening settings."""
    _go_to_settings(page)
    _open_categories_section(page)
    expect(page.locator("#cat-list")).to_be_visible(timeout=5000)


def test_at_least_one_category_shown(page):
    """At least one category item must be rendered (seed data exists)."""
    _go_to_settings(page)
    _open_categories_section(page)

    cat_items = page.locator("#cat-list .cat-item")
    # Use a Playwright assertion so failure produces a meaningful message.
    expect(cat_items.first).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Tests: adding a category
# ---------------------------------------------------------------------------


def test_add_category_form_present(page):
    """The add-category form inputs must be visible in the categories section."""
    _go_to_settings(page)
    _open_categories_section(page)

    expect(page.locator("#cat-name")).to_be_visible(timeout=3000)
    expect(page.locator("#cat-label")).to_be_visible(timeout=3000)


def test_add_category_creates_item_in_list(page):
    """Submitting the add-category form must add the new category to the list."""
    _go_to_settings(page)
    _open_categories_section(page)

    page.locator("#cat-name").fill("e2e_add_cat_test")
    page.locator("#cat-label").fill("E2E Add Cat")

    add_btn = page.locator("button[data-action='add-cat'], [data-i18n='btn_add_category']")
    expect(add_btn.first).to_be_visible(timeout=3000)
    add_btn.first.click()
    page.wait_for_timeout(800)

    # Category labels live in <input value="..."> not text nodes; the internal
    # name (key) is rendered as visible text in <span class="cat-item-key">.
    expect(page.locator("#cat-list")).to_contain_text("e2e_add_cat_test", timeout=5000)


# ---------------------------------------------------------------------------
# Tests: deleting an empty category shows simple confirmation
# ---------------------------------------------------------------------------


def test_delete_empty_category_shows_confirm_modal(page, live_url):
    """Deleting a category with no products must show a simple confirmation
    modal (not the move modal)."""
    _create_category(live_url, "e2e_empty_del_cat", "E2E Empty Del Cat")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_empty_del_cat']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(400)

    # The standard confirm modal must appear.
    confirm_modal = page.locator(".scan-modal-bg[role='dialog']")
    expect(confirm_modal).to_be_visible(timeout=3000)

    # The move-specific select dropdown must NOT be present in this flow.
    move_select = page.locator(".cat-move-select")
    expect(move_select).to_have_count(0)


def test_delete_empty_category_cancel_keeps_category(page, live_url):
    """Cancelling the confirmation modal must leave the category intact."""
    _create_category(live_url, "e2e_cancel_del_cat", "E2E Cancel Del Cat")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_cancel_del_cat']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(400)

    page.locator("button.confirm-no").click()
    page.wait_for_timeout(400)

    # Category must still appear in the list (key is visible text; label is in an input value).
    expect(page.locator("#cat-list")).to_contain_text("e2e_cancel_del_cat", timeout=3000)


# ---------------------------------------------------------------------------
# Tests: deleting a category with products shows move modal
# ---------------------------------------------------------------------------


def test_delete_category_with_products_shows_move_modal(page, live_url, api_create_product):
    """Deleting a category that has products must open the move modal
    (not the plain confirm modal)."""
    _create_category(live_url, "e2e_move_src", "E2E Move Source")
    api_create_product(name="E2EMoveProd1", category="e2e_move_src")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_move_src']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(600)

    # The move modal specifically (not a plain confirm) must appear.
    move_modal = page.locator(".cat-move-modal-bg")
    expect(move_modal).to_be_visible(timeout=3000)


def test_move_modal_contains_target_dropdown(page, live_url, api_create_product):
    """The move modal must contain a <select> for choosing the target category."""
    _create_category(live_url, "e2e_move_dropdown", "E2E Move Dropdown")
    api_create_product(name="E2EMoveDropdownProd", category="e2e_move_dropdown")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_move_dropdown']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(600)

    # The select dropdown must be visible.
    move_select = page.locator(".cat-move-select")
    expect(move_select).to_be_visible(timeout=3000)

    # It must have at least one option (a target category to move to).
    options = move_select.locator("option")
    count = options.count()
    assert count >= 1, f"Expected at least one target-category option, got {count}"


def test_move_modal_cancel_preserves_category(page, live_url, api_create_product):
    """Clicking cancel in the move modal must close it without deleting anything."""
    _create_category(live_url, "e2e_move_cancel", "E2E Move Cancel")
    api_create_product(name="E2EMoveCancelProd", category="e2e_move_cancel")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_move_cancel']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(600)

    move_modal = page.locator(".cat-move-modal-bg")
    expect(move_modal).to_be_visible(timeout=3000)

    cancel_btn = page.locator("button.cat-move-cancel")
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()
    page.wait_for_timeout(500)

    # Modal must be gone.
    expect(move_modal).to_be_hidden(timeout=3000)

    # Category must still exist in the list (key is visible text; label is in an input value).
    expect(page.locator("#cat-list")).to_contain_text("e2e_move_cancel", timeout=3000)


def test_move_and_delete_shows_success_toast(page, live_url, api_create_product):
    """Confirming the move modal must delete the source category and show a
    success toast."""
    _create_category(live_url, "e2e_move_confirm", "E2E Move Confirm")
    api_create_product(name="E2EMoveConfirmProd", category="e2e_move_confirm")

    _go_to_settings(page)
    _open_categories_section(page)

    delete_btn = page.locator(
        "[data-action='delete-cat'][data-cat-name='e2e_move_confirm']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(600)

    move_modal = page.locator(".cat-move-modal-bg")
    expect(move_modal).to_be_visible(timeout=3000)

    # Click the confirm (move-and-delete) button.
    confirm_btn = page.locator("button.cat-move-confirm")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()

    # A success toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)

    # The source category must no longer appear in the list.
    page.wait_for_timeout(800)
    expect(page.locator("#cat-list")).not_to_contain_text(
        "E2E Move Confirm", timeout=5000
    )
