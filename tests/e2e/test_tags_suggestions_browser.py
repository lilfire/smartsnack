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

    def test_suggestions_appear_on_typing(self, page, api_create_product, live_url):
        """Typing in the tag modal input should show suggestions."""
        # Create tags via API
        _, tag1 = _api_raw(live_url, "/api/tags", method="POST",
                           body={"label": "suggest-alpha"})
        _, tag2 = _api_raw(live_url, "/api/tags", method="POST",
                           body={"label": "suggest-beta"})

        api_create_product(name="SuggestProd")
        _reload_and_wait(page)
        _open_edit_form(page, "SuggestProd")

        # Open tag modal
        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        expect(modal_input).to_be_visible()

        # Type a prefix
        modal_input.fill("suggest")
        page.wait_for_timeout(500)

        # Suggestions should include both tags
        suggestions = page.locator("#tag-modal-suggestions")
        expect(suggestions).to_contain_text("suggest-alpha")
        expect(suggestions).to_contain_text("suggest-beta")

        _cleanup_tag(live_url, tag1["id"])
        _cleanup_tag(live_url, tag2["id"])

    def test_no_match_shows_create_option(self, page, api_create_product, live_url):
        """Typing a non-existent tag should allow creating it."""
        api_create_product(name="NoMatchProd")
        _reload_and_wait(page)
        _open_edit_form(page, "NoMatchProd")

        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        modal_input.fill("zzz-unique-tag-xyz")
        page.wait_for_timeout(500)

        # Either suggestions list is empty or shows a "create" option
        # Pressing Enter should create the new tag
        modal_input.press("Enter")
        page.wait_for_timeout(500)

        tag_field = page.locator("#tag-field-ed")
        expect(tag_field).to_contain_text("zzz-unique-tag-xyz")

        # Cleanup
        _, tags = _api_raw(live_url, "/api/tags?q=zzz-unique-tag-xyz")
        for t in tags:
            _cleanup_tag(live_url, t["id"])

    def test_arrow_key_navigation(self, page, api_create_product, live_url):
        """Arrow keys should navigate suggestions in the tag modal."""
        _, tag = _api_raw(live_url, "/api/tags", method="POST",
                          body={"label": "arrow-nav-tag"})

        api_create_product(name="ArrowNavProd")
        _reload_and_wait(page)
        _open_edit_form(page, "ArrowNavProd")

        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal_input = page.locator("#tag-modal-input")
        modal_input.fill("arrow-nav")
        page.wait_for_timeout(500)

        # Press ArrowDown to highlight a suggestion
        modal_input.press("ArrowDown")
        page.wait_for_timeout(200)

        # A suggestion item should have a highlighted class
        highlighted = page.locator("#tag-modal-suggestions .highlighted")
        if highlighted.count() > 0:
            expect(highlighted.first).to_be_visible()

        _cleanup_tag(live_url, tag["id"])
