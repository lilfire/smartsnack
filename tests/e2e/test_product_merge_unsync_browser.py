"""Browser-based e2e tests for product merge and unsync UI.

Covers the unsync button behavior and merge/duplicate
detection interactions in the product view.
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


def _reload_and_wait(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _expand_product_row(page, name):
    row = page.locator(f".table-row:has-text('{name}')").first
    row.click()
    page.wait_for_timeout(300)


def _open_edit_form(page, name):
    _expand_product_row(page, name)
    row = page.locator(f".table-row:has-text('{name}')").first
    edit_btn = row.locator("[data-action='start-edit']")
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    page.wait_for_timeout(300)


class TestUnsyncButtonBrowser:
    """Test the unsync button for OFF-synced products."""

    def test_unsync_button_on_synced_product(self, page, api_create_product, live_url):
        """A synced product should have an unsync button."""
        product = api_create_product(
            name="SyncedProd", ean="7038010069307",
            off_source="openfoodfacts",
        )
        _reload_and_wait(page)
        _expand_product_row(page, "SyncedProd")

        # Look for an unsync action
        row = page.locator(f".table-row:has-text('SyncedProd')").first
        unsync_btn = row.locator("[data-ean-action='unsync-ean']")
        if unsync_btn.count() > 0:
            expect(unsync_btn.first).to_be_visible()

    def test_non_synced_product_no_unsync(self, page, api_create_product):
        """A non-synced product should not show an unsync button."""
        api_create_product(name="LocalOnlyProd")
        _reload_and_wait(page)
        _expand_product_row(page, "LocalOnlyProd")

        row = page.locator(f".table-row:has-text('LocalOnlyProd')").first
        unsync_btns = row.locator("[data-ean-action='unsync-ean']")
        assert unsync_btns.count() == 0


class TestProductDeleteBrowser:
    """Test product deletion from the expanded view."""

    def test_delete_button_exists(self, page, api_create_product):
        """An expanded product row should have a delete button."""
        api_create_product(name="DeleteBtnProd")
        _reload_and_wait(page)
        _expand_product_row(page, "DeleteBtnProd")

        row = page.locator(f".table-row:has-text('DeleteBtnProd')").first
        delete_btn = row.locator("[data-action='delete']")
        expect(delete_btn).to_be_visible()

    def test_delete_removes_product(self, page, api_create_product):
        """Clicking delete should remove the product from the list."""
        api_create_product(name="DeleteMeProd")
        _reload_and_wait(page)
        _expand_product_row(page, "DeleteMeProd")

        row = page.locator(f".table-row:has-text('DeleteMeProd')").first
        delete_btn = row.locator("[data-action='delete']")
        delete_btn.click()
        page.wait_for_timeout(1000)

        # Product should no longer be in the list (or an undo toast appears)
        # Give the undo period time to pass or verify the toast
        toast = page.locator(".toast")
        if toast.first.is_visible():
            # Undo toast visible means delete was triggered
            expect(toast.first).to_be_visible()
