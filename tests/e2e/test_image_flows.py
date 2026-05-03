"""E2E tests for image upload, capture, and full-screen viewer.

Tests image upload via file picker, pending-image preview in the register
form, and the full-screen image viewer modal (open, close button, Escape key).
"""

import json
import urllib.request

import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Minimal valid 1×1 JPEG as a data URI (base64-encoded).
# Used both for seeding images via the API and for verifying previews.
# ---------------------------------------------------------------------------
TINY_IMAGE = (
    "data:image/jpeg;base64,"
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIRAAAQQCAgMBAAAAAAAAAAAAAQID"
    "BAUREiExQf/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oA"
    "DAMBAAIRAxEAPwCwc52yqt2pJrK3lxb3Lf8AUk5YIr3wOpFftjf6oAA//9k="
)


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _go_to_register(page):
    page.locator("button.nav-tab[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _put_image(live_url, product_id, image=TINY_IMAGE):
    payload = json.dumps({"image": image}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/image",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Image capture button in register form
# ---------------------------------------------------------------------------


def test_image_capture_button_exists_on_register(page):
    """The register form must have an image capture/upload button."""
    _go_to_register(page)
    btn = page.locator("#f-image-btn")
    expect(btn).to_be_attached()


def test_image_capture_button_triggers_file_chooser(page):
    """Clicking the register image button must open a file chooser."""
    _go_to_register(page)

    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("#f-image-btn").click()

    assert fc_info.value is not None


def test_image_preview_appears_after_file_selected(page, tmp_path):
    """After selecting an image in the register form the preview element
    must become visible and show the chosen image."""
    _go_to_register(page)

    import base64

    raw = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
        "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAAB"
        "AAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIRAAAQQCAgMBAAAA"
        "AAAAAAAAAQIDBQURESIxQf/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAA"
        "AAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AsHOdsqrdqSayt5cW9y3/AFJOWEI97A6kV+"
        "2N/qgAP//Z"
    )
    fake_img = tmp_path / "preview_test.jpg"
    fake_img.write_bytes(raw)

    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("#f-image-btn").click()
    fc_info.value.set_files(str(fake_img))

    preview = page.locator("#f-image-preview")
    expect(preview).to_be_visible(timeout=5000)


def test_image_remove_button_hides_preview(page, tmp_path):
    """After selecting an image, clicking the remove button must hide the
    preview and the remove button itself."""
    _go_to_register(page)

    import base64

    raw = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
        "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAAB"
        "AAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIRAAAQQCAgMBAAAA"
        "AAAAAAAAAQIDBQURESIxQf/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAA"
        "AAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AsHOdsqrdqSayt5cW9y3/AFJOWEI97A6kV+"
        "2N/qgAP//Z"
    )
    fake_img = tmp_path / "remove_test.jpg"
    fake_img.write_bytes(raw)

    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("#f-image-btn").click()
    fc_info.value.set_files(str(fake_img))

    expect(page.locator("#f-image-preview")).to_be_visible(timeout=5000)

    page.locator("#f-image-remove").click()
    page.wait_for_timeout(300)

    expect(page.locator("#f-image-preview")).to_be_hidden()


# ---------------------------------------------------------------------------
# Image in product row (via API seed) and viewer
# ---------------------------------------------------------------------------


def test_image_visible_in_expanded_row(page, api_create_product, live_url):
    """After seeding an image via the API the product expanded view must
    show an <img> element with a non-empty src."""
    product = api_create_product(name="ImgPreviewProd")
    _put_image(live_url, product["id"])

    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ImgPreviewProd")
    row.first.click()
    page.wait_for_timeout(300)

    img = page.locator(f"#prod-img-{product['id']}")
    expect(img).to_be_visible(timeout=5000)

    src = img.get_attribute("src")
    assert src and src.startswith("data:image/"), (
        f"Expected a data URI in src, got: {src!r}"
    )


def test_image_viewer_opens_on_click(page, api_create_product, live_url):
    """Clicking a product image must open the full-screen viewer."""
    product = api_create_product(name="ImgViewerProd")
    _put_image(live_url, product["id"])

    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ImgViewerProd")
    row.first.click()
    page.wait_for_timeout(300)

    img = page.locator(f"#prod-img-{product['id']}")
    expect(img).to_be_visible(timeout=5000)
    img.click()

    viewer = page.locator(".img-viewer-bg")
    expect(viewer).to_be_visible(timeout=3000)


def test_image_viewer_close_button_dismisses(page, api_create_product, live_url):
    """The close button on the image viewer must remove the viewer from the DOM."""
    product = api_create_product(name="ImgViewerCloseProd")
    _put_image(live_url, product["id"])

    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ImgViewerCloseProd")
    row.first.click()
    page.wait_for_timeout(300)

    img = page.locator(f"#prod-img-{product['id']}")
    expect(img).to_be_visible(timeout=5000)
    img.click()

    viewer = page.locator(".img-viewer-bg")
    expect(viewer).to_be_visible(timeout=3000)

    page.locator(".img-viewer-close").click()

    expect(viewer).to_be_hidden(timeout=3000)


def test_image_viewer_closes_on_escape(page, api_create_product, live_url):
    """Pressing Escape must close the full-screen image viewer."""
    product = api_create_product(name="ImgViewerEscProd")
    _put_image(live_url, product["id"])

    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ImgViewerEscProd")
    row.first.click()
    page.wait_for_timeout(300)

    img = page.locator(f"#prod-img-{product['id']}")
    expect(img).to_be_visible(timeout=5000)
    img.click()

    viewer = page.locator(".img-viewer-bg")
    expect(viewer).to_be_visible(timeout=3000)

    page.keyboard.press("Escape")

    expect(viewer).to_be_hidden(timeout=3000)


def test_image_viewer_closes_on_backdrop_click(page, api_create_product, live_url):
    """Clicking the backdrop of the image viewer must close it."""
    product = api_create_product(name="ImgViewerBgProd")
    _put_image(live_url, product["id"])

    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="ImgViewerBgProd")
    row.first.click()
    page.wait_for_timeout(300)

    img = page.locator(f"#prod-img-{product['id']}")
    expect(img).to_be_visible(timeout=5000)
    img.click()

    viewer = page.locator(".img-viewer-bg")
    expect(viewer).to_be_visible(timeout=3000)

    # Click in the corner of the backdrop (well outside the inner <img>).
    viewer.click(position={"x": 5, "y": 5})

    expect(viewer).to_be_hidden(timeout=3000)


# ---------------------------------------------------------------------------
# Placeholder when no image is set
# ---------------------------------------------------------------------------


def test_placeholder_shown_when_no_image(page, api_create_product):
    """A product without an image must show a placeholder in the expanded view."""
    api_create_product(name="NoImgPlaceholderProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="NoImgPlaceholderProd")
    row.first.click()
    page.wait_for_timeout(300)

    placeholder = page.locator(".expanded-img-placeholder")
    expect(placeholder).to_be_visible(timeout=5000)
