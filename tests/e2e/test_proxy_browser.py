"""Browser-based e2e tests for image proxy UI behavior.

Covers product image display using the proxy route
and image-related interactions in the product view.
"""

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _open_edit_form(page, name):
    row = page.locator(f".table-row:has-text('{name}')").first
    row.click()
    # Clicking the row expands it; wait for the expanded area to render.
    expect(page.locator(".expanded").first).to_be_visible(timeout=5000)
    # The [data-action='start-edit'] button lives in the sibling .expanded div,
    # not inside .table-row, so use a page-scoped locator.
    edit_btn = page.locator("[data-action='start-edit']").first
    expect(edit_btn).to_be_visible(timeout=3000)
    edit_btn.click()
    # Entering edit mode re-renders the expanded row with the edit form.
    expect(page.locator("#ed-name")).to_be_visible(timeout=5000)


class TestImageUploadBrowser:
    """Test image upload/capture UI in registration and edit forms."""

    def test_image_button_in_register(self, page):
        """The registration form should have a photo/image button."""
        _go_to_register(page)
        btn = page.locator("#f-image-btn")
        expect(btn).to_be_visible()

    def test_image_preview_hidden_initially(self, page):
        """The image preview should be hidden when no image is set."""
        _go_to_register(page)
        preview = page.locator("#f-image-preview")
        expect(preview).to_be_hidden()

    def test_image_controls_in_expanded_row(self, page, api_create_product):
        """The expanded product row must show an image upload control.

        The button lives in the sibling ``.expanded`` div (see render.js),
        not inside ``.table-row`` — a row-scoped locator never matches, which
        is why the old guarded version silently passed without asserting.
        """
        product = api_create_product(name="ImgEditProd")
        _reload_and_wait(page)
        row = page.locator(".table-row:has-text('ImgEditProd')").first
        row.click()

        # Product has no image → render.js emits the upload button with
        # data-action='change-image' in the expanded area. The auto-waiting
        # expect also covers the row-expansion render.
        img_btn = page.locator(
            f"[data-action='change-image'][data-id='{product['id']}']"
        )
        expect(img_btn.first).to_be_visible(timeout=5000)


class TestImageDisplayBrowser:
    """Test image display in product rows."""

    def test_product_without_image_shows_placeholder(self, page, api_create_product):
        """A product without an image should not crash the display."""
        api_create_product(name="NoImgProd")
        _reload_and_wait(page)

        row = page.locator(f".table-row:has-text('NoImgProd')").first
        expect(row).to_be_visible()
