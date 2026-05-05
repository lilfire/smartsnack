"""Browser-based e2e tests for Tags CRUD via the product edit UI.

Tags are managed via a modal tag picker in the product edit form.
This file tests creating, assigning, and removing tags through
browser interactions.
"""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# API helpers (for setup/cleanup)
# ---------------------------------------------------------------------------

def _api_raw(live_url, path, *, method="GET", body=None):
    """JSON API request returning (status_code, parsed_body)."""
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


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _expand_product_row(page, name):
    """Expand a product row by clicking it."""
    row = page.locator(f".table-row:has-text('{name}')").first
    row.click()
    page.wait_for_timeout(300)


def _open_edit_form(page, name):
    """Expand product row and click the edit button."""
    _expand_product_row(page, name)
    row = page.locator(f".table-row:has-text('{name}')").first
    edit_btn = row.locator("[data-action='start-edit']")
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(300)


# ===========================================================================
# Tag creation via API and browser display
# ===========================================================================


class TestTagDisplayInProduct:
    """Verify tags display correctly on product rows."""

    def test_product_shows_assigned_tags(self, page, api_create_product, live_url, unique_name):
        """A product with assigned tags should show tag pills."""
        # Create tag and product via API
        tag_label = unique_name("browser-display").lower()
        prod_name = unique_name("TagDisplayProd")
        _, tag = _api_raw(live_url, "/api/tags", method="POST",
                          body={"label": tag_label})
        product = api_create_product(name=prod_name)
        _api_raw(live_url, f"/api/products/{product['id']}",
                 method="PUT", body={"tagIds": [tag["id"]]})

        # Reload to see updated product
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        # Expand the product row
        _expand_product_row(page, prod_name)

        # Should see the tag somewhere in the expanded view
        row = page.locator(f".table-row:has-text('{prod_name}')").first
        expect(row).to_contain_text(tag_label)

        _cleanup_tag(live_url, tag["id"])


class TestTagEditModal:
    """Test tag editing through the product edit form modal."""

    def test_tag_field_visible_in_edit(self, page, api_create_product, live_url, unique_name):
        """The tag field should be visible when editing a product."""
        prod_name = unique_name("TagEditVisible")
        api_create_product(name=prod_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _open_edit_form(page, prod_name)
        tag_field = page.locator("#tag-field-ed")
        expect(tag_field).to_be_visible(timeout=5000)

    def test_tag_modal_opens_on_click(self, page, api_create_product, live_url, unique_name):
        """Clicking the tag field should open the tag modal."""
        prod_name = unique_name("TagModalOpen")
        api_create_product(name=prod_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _open_edit_form(page, prod_name)
        tag_field = page.locator("#tag-field-ed")
        tag_field.click()
        page.wait_for_timeout(300)

        # The tag modal overlay should appear
        modal = page.locator("#tag-modal-overlay")
        expect(modal).to_be_visible(timeout=3000)

    def test_tag_modal_search_input(self, page, api_create_product, live_url, unique_name):
        """The tag modal should have a search input."""
        # Pre-create a tag
        tag_label = unique_name("searchable-tag").lower()
        # The search prefix matches the literal "searchable" portion of the label
        # so it remains the user-facing query a real user would type.
        search_prefix = tag_label.split("-")[0]
        prod_name = unique_name("TagModalSearch")
        _, tag = _api_raw(live_url, "/api/tags", method="POST",
                          body={"label": tag_label})

        api_create_product(name=prod_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _open_edit_form(page, prod_name)
        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        # Search for the tag
        modal_input = page.locator("#tag-modal-input")
        expect(modal_input).to_be_visible()
        modal_input.fill(search_prefix)
        page.wait_for_timeout(500)

        # Suggestions should appear
        suggestions = page.locator("#tag-modal-suggestions")
        expect(suggestions).to_contain_text(tag_label)

        _cleanup_tag(live_url, tag["id"])

    def test_create_new_tag_via_modal(self, page, api_create_product, live_url, unique_name):
        """Typing a new tag name and confirming should create the tag."""
        prod_name = unique_name("TagModalCreate")
        new_tag_label = unique_name("new-browser-tag").lower()
        api_create_product(name=prod_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _open_edit_form(page, prod_name)
        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        # Type a new tag name
        modal_input = page.locator("#tag-modal-input")
        modal_input.fill(new_tag_label)
        page.wait_for_timeout(300)

        # Press Enter to create
        modal_input.press("Enter")
        page.wait_for_timeout(500)

        # Confirm the modal
        confirm = page.locator("#tag-modal-confirm")
        if confirm.is_visible():
            confirm.click()
            page.wait_for_timeout(300)

        # The tag pill should appear in the tag field
        tag_field = page.locator("#tag-field-ed")
        expect(tag_field).to_contain_text(new_tag_label)

        # Cleanup
        _, tags = _api_raw(live_url, f"/api/tags?q={new_tag_label}")
        for t in tags:
            _cleanup_tag(live_url, t["id"])

    def test_close_tag_modal_with_escape(self, page, api_create_product, live_url, unique_name):
        """Pressing Escape should close the tag modal."""
        prod_name = unique_name("TagModalEsc")
        api_create_product(name=prod_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _open_edit_form(page, prod_name)
        page.locator("#tag-field-ed").click()
        page.wait_for_timeout(300)

        modal = page.locator("#tag-modal-overlay")
        expect(modal).to_be_visible(timeout=3000)

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        expect(modal).to_be_hidden()
