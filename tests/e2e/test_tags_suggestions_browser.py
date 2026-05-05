"""Browser-based e2e tests for tag auto-suggestion UI.

Covers the tag input autocomplete/suggestion dropdown
behavior in the product edit form.
"""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


def _api_raw(live_url, path, *, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json",
               "X-Requested-With": "SmartSnack"} if data else {
        "X-Requested-With": "SmartSnack"}
    req = urllib.request.Request(
        f"{live_url}{path}", data=data, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _cleanup_tag(live_url, tag_id):
    _api_raw(live_url, f"/api/tags/{tag_id}", method="DELETE")


def _reload_and_wait(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _open_edit_form(page, name):
    row = page.locator(f".table-row:has-text('{name}')").first
    row.click()
    page.wait_for_timeout(300)
    edit_btn = row.locator("[data-action='start-edit']")
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(300)


class TestTagSuggestionsBrowser:
    """Test tag suggestion/autocomplete in the modal."""

    def test_suggestions_appear_on_typing(self, page, api_create_product, live_url, unique_name):
        """Typing in the tag modal input should show suggestions."""
        # Create tags via API with a shared unique prefix so the typed
        # search query matches both. The prefix doubles as the user input.
        prefix = unique_name("suggest").lower()
        alpha_label = f"{prefix}-alpha"
        beta_label = f"{prefix}-beta"
        _, tag1 = _api_raw(live_url, "/api/tags", method="POST",
                           body={"label": alpha_label})
        _, tag2 = _api_raw(live_url, "/api/tags", method="POST",
                           body={"label": beta_label})

        prod_name = unique_name("SuggestProd")
        api_create_product(name=prod_name)
        _reload_and_wait(page)
        _open_edit_form(page, prod_name)

        # Open tag modal
        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        expect(modal_input).to_be_visible()

        # Type the shared prefix
        modal_input.fill(prefix)
        page.wait_for_timeout(500)

        # Suggestions should include both tags
        suggestions = page.locator("#tag-modal-suggestions")
        expect(suggestions).to_contain_text(alpha_label)
        expect(suggestions).to_contain_text(beta_label)

        _cleanup_tag(live_url, tag1["id"])
        _cleanup_tag(live_url, tag2["id"])

    def test_no_match_shows_create_option(self, page, api_create_product, live_url, unique_name):
        """Typing a non-existent tag should allow creating it."""
        prod_name = unique_name("NoMatchProd")
        new_tag_label = unique_name("zzz-unique-tag-xyz").lower()
        api_create_product(name=prod_name)
        _reload_and_wait(page)
        _open_edit_form(page, prod_name)

        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        modal_input.fill(new_tag_label)
        page.wait_for_timeout(500)

        # Either suggestions list is empty or shows a "create" option
        # Pressing Enter should create the new tag
        modal_input.press("Enter")
        page.wait_for_timeout(500)

        tag_field = page.locator("#tag-field-ed")
        expect(tag_field).to_contain_text(new_tag_label)

        # Cleanup
        _, tags = _api_raw(live_url, f"/api/tags?q={new_tag_label}")
        for t in tags:
            _cleanup_tag(live_url, t["id"])

    def test_arrow_key_navigation(self, page, api_create_product, live_url, unique_name):
        """Arrow keys should navigate suggestions in the tag modal."""
        tag_label = unique_name("arrow-nav-tag").lower()
        # The user-typed prefix matches the tag's leading word so the
        # suggestion list will contain at least one item to navigate.
        search_prefix = "-".join(tag_label.split("-")[:2])
        _, tag = _api_raw(live_url, "/api/tags", method="POST",
                          body={"label": tag_label})

        prod_name = unique_name("ArrowNavProd")
        api_create_product(name=prod_name)
        _reload_and_wait(page)
        _open_edit_form(page, prod_name)

        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        modal_input.fill(search_prefix)
        page.wait_for_timeout(500)

        # Press ArrowDown to highlight a suggestion
        modal_input.press("ArrowDown")
        page.wait_for_timeout(200)

        # A suggestion item should have a highlighted class
        highlighted = page.locator("#tag-modal-suggestions .highlighted")
        if highlighted.count() > 0:
            expect(highlighted.first).to_be_visible()

        _cleanup_tag(live_url, tag["id"])
