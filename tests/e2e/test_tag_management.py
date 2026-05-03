"""E2E tests for tag management UI and API (P2 gap #24).

Tests:
- Tag input widget and add-tag button exist in the edit form
- The tag modal opens, accepts input, and closes
- Adding a tag creates a .tag-pill in the edit form
- The tag remove button removes the pill (pill count strictly decreases)
- Tag suggestions appear when typing a known label
"""

import json
import urllib.request

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _expand_and_edit(page, product_name):
    """Click a product row to expand it, then open the edit form."""
    row = page.locator(".table-row", has_text=product_name)
    row.first.click()
    page.wait_for_timeout(300)
    page.locator("[data-action='start-edit']").first.click()
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Tag API tests
# ---------------------------------------------------------------------------


def test_tags_search_api_returns_list(live_url):
    """GET /api/tags?q=test must return a JSON list."""
    req = urllib.request.Request(f"{live_url}/api/tags?q=test", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert isinstance(body, list), (
        f"Expected list from /api/tags, got {type(body).__name__}: {body}"
    )


def test_tags_create_api_returns_tag_object(live_url):
    """POST /api/tags must return an object with both 'id' and 'label' fields."""
    payload = json.dumps({"label": "E2EAPITag"}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/tags",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert "id" in body, f"Expected 'id' in tag creation response, got: {body}"
    assert "label" in body, f"Expected 'label' in tag creation response, got: {body}"
    assert body["label"] == "E2EAPITag", (
        f"Expected label='E2EAPITag', got: {body['label']!r}"
    )


# ---------------------------------------------------------------------------
# Tag UI tests — all assertions unconditional
# ---------------------------------------------------------------------------


def test_tag_field_visible_in_edit(page, api_create_product):
    """The #tag-field-ed container must be visible in the product edit form."""
    api_create_product(name="TagFieldProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagFieldProd")

    tag_field = page.locator("#tag-field-ed")
    expect(tag_field).to_be_visible(timeout=5000)


def test_add_tag_button_exists_in_edit(page, api_create_product):
    """The #add-tag-btn button must be visible inside the edit form."""
    api_create_product(name="TagAddBtnProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagAddBtnProd")

    add_btn = page.locator("#add-tag-btn")
    expect(add_btn).to_be_visible(timeout=5000)


def test_tag_modal_opens_on_add_click(page, api_create_product):
    """Clicking #add-tag-btn must show the #tag-modal-overlay dialog."""
    api_create_product(name="TagModalProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagModalProd")

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    modal = page.locator("#tag-modal-overlay")
    expect(modal).to_be_visible(timeout=3000)


def test_tag_modal_has_role_dialog(page, api_create_product):
    """The tag modal overlay must have role='dialog' for accessibility."""
    api_create_product(name="TagRoleProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagRoleProd")

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    modal = page.locator("#tag-modal-overlay")
    expect(modal).to_be_visible(timeout=3000)
    role = modal.get_attribute("role")
    assert role == "dialog", (
        f"Expected tag modal to have role='dialog', got: {role!r}"
    )


def test_tag_modal_has_input_and_buttons(page, api_create_product):
    """The tag modal must have a text input, a confirm button, and a cancel button."""
    api_create_product(name="TagBtnsProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagBtnsProd")

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    expect(page.locator("#tag-modal-input")).to_be_visible(timeout=3000)
    expect(page.locator("#tag-modal-confirm")).to_be_visible(timeout=3000)
    expect(page.locator("#tag-modal-cancel")).to_be_visible(timeout=3000)


def test_tag_modal_cancel_closes_modal(page, api_create_product):
    """Clicking the cancel button must hide the tag modal."""
    api_create_product(name="TagCancelProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagCancelProd")

    page.locator("#add-tag-btn").click()
    modal = page.locator("#tag-modal-overlay")
    expect(modal).to_be_visible(timeout=3000)

    page.locator("#tag-modal-cancel").click()
    page.wait_for_timeout(300)

    expect(modal).to_be_hidden(timeout=3000)


def test_adding_tag_creates_pill(page, api_create_product):
    """Typing a tag name and confirming must add a .tag-pill inside #tag-field-ed."""
    api_create_product(name="TagNewProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagNewProd")

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    page.locator("#tag-modal-input").fill("TestTagPill")
    page.locator("#tag-modal-confirm").click()
    page.wait_for_timeout(600)

    pills = page.locator("#tag-field-ed .tag-pill")
    pill_count = pills.count()
    assert pill_count >= 1, (
        f"Expected at least one .tag-pill after adding a tag, got {pill_count}"
    )


def test_tag_remove_button_decreases_pill_count(page, api_create_product):
    """Clicking the .tag-remove button on a pill must remove exactly that pill."""
    api_create_product(name="TagRemoveProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagRemoveProd")

    # Add a tag so there is something to remove
    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)
    page.locator("#tag-modal-input").fill("RemoveThisTag")
    page.locator("#tag-modal-confirm").click()
    page.wait_for_timeout(600)

    pills_before = page.locator("#tag-field-ed .tag-pill").count()
    assert pills_before >= 1, (
        f"Pre-condition failed: expected at least one pill before removal, got {pills_before}"
    )

    # Click the remove button on the first pill
    page.locator("#tag-field-ed .tag-remove").first.click()
    page.wait_for_timeout(300)

    pills_after = page.locator("#tag-field-ed .tag-pill").count()
    assert pills_after < pills_before, (
        f"Expected fewer pills after removal: before={pills_before}, after={pills_after}"
    )


def test_tag_suggestions_appear_for_existing_tag(page, api_create_product, live_url):
    """Typing in the tag modal input must show matching suggestions for a known tag."""
    # Create a tag via API that the suggestion search can find
    payload = json.dumps({"label": "SuggestionTagE2E"}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/tags",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5)

    api_create_product(name="TagSuggestProd")
    _reload_and_wait(page)
    _expand_and_edit(page, "TagSuggestProd")

    page.locator("#add-tag-btn").click()
    page.wait_for_timeout(300)

    # Type the beginning of the known tag label
    page.locator("#tag-modal-input").fill("SuggestionTag")
    # Wait for the debounced fetch (200 ms) plus render time
    page.wait_for_timeout(700)

    suggestions = page.locator("#tag-modal-suggestions li")
    suggestion_count = suggestions.count()
    assert suggestion_count >= 1, (
        f"Expected at least one suggestion for 'SuggestionTag', got {suggestion_count}"
    )
    expect(suggestions.first).to_be_visible(timeout=3000)
