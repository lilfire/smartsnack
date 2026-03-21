"""E2E tests for product image operations via API and UI."""

import json
import urllib.error
import urllib.request

from playwright.sync_api import expect

# A minimal but structurally valid JPEG encoded as a data URI.
# This is small enough for fast test execution while still being accepted
# by the image service's format validation.
TINY_IMAGE = (
    "data:image/jpeg;base64,"
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////"
    "////////////////////////////2wBDAf///////////////////////////////////////////"
    "/////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/"
    "EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAA"
    "AAAAAAAAAAP/aAAwDAQACEQMRAD8AKwA//9k="
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _put_image(live_url: str, product_id: int, image: str) -> dict:
    """PUT an image to a product via the REST API.

    Args:
        live_url: Base URL of the running Flask server.
        product_id: ID of the target product.
        image: Base64 data URI string.

    Returns:
        Parsed JSON response body.
    """
    payload = json.dumps({"image": image}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/image",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _get_image(live_url: str, product_id: int) -> tuple[int, dict]:
    """GET a product image from the REST API.

    Args:
        live_url: Base URL of the running Flask server.
        product_id: ID of the target product.

    Returns:
        Tuple of (HTTP status code, parsed JSON response body).
    """
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/image",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _delete_image(live_url: str, product_id: int) -> dict:
    """DELETE a product image via the REST API.

    Args:
        live_url: Base URL of the running Flask server.
        product_id: ID of the target product.

    Returns:
        Parsed JSON response body.
    """
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/image",
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _reload_and_wait(page) -> None:
    """Reload the page and wait until the product list finishes loading.

    Args:
        page: Playwright page object.
    """
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _expand_product_row(page, product_name: str) -> None:
    """Click the product row to expand it and wait for the animation.

    Args:
        page: Playwright page object.
        product_name: Visible name of the product whose row should be expanded.
    """
    row = page.locator(".table-row", has_text=product_name)
    row.first.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_set_image_via_api(live_url, api_create_product):
    """PUT a base64 image, then GET it back and verify the round-trip.

    The returned image data must exactly match what was uploaded so that
    the browser can render the correct pixels.
    """
    product = api_create_product(name="ImgSetAPITest")
    product_id = product["id"]

    put_response = _put_image(live_url, product_id, TINY_IMAGE)
    assert put_response.get("ok") is True, f"PUT failed: {put_response}"

    status, get_response = _get_image(live_url, product_id)
    assert status == 200, f"Expected 200, got {status}: {get_response}"
    assert get_response.get("image") == TINY_IMAGE, (
        "Retrieved image does not match the uploaded image"
    )


def test_delete_image_via_api(live_url, api_create_product):
    """PUT an image then DELETE it; a subsequent GET must return 404.

    After deletion the image column should be cleared and the endpoint
    must signal that no image is stored for the product.
    """
    product = api_create_product(name="ImgDeleteAPITest")
    product_id = product["id"]

    _put_image(live_url, product_id, TINY_IMAGE)

    delete_response = _delete_image(live_url, product_id)
    assert delete_response.get("ok") is True, f"DELETE failed: {delete_response}"

    status, get_response = _get_image(live_url, product_id)
    assert status == 404, (
        f"Expected 404 after deletion, got {status}: {get_response}"
    )


def test_image_shown_in_expanded_view(page, live_url, api_create_product):
    """After uploading an image via API, the expanded product row must show an img element.

    The UI renders a product image as ``<img id="prod-img-{id}">`` inside the
    expanded section.  This test confirms that the element is present and
    visible when an image exists.
    """
    product = api_create_product(name="ImgUIShowTest")
    product_id = product["id"]

    _put_image(live_url, product_id, TINY_IMAGE)

    _reload_and_wait(page)
    _expand_product_row(page, "ImgUIShowTest")

    img = page.locator(f"#prod-img-{product_id}")
    expect(img).to_be_visible(timeout=5000)


def test_remove_image_button_visible(page, live_url, api_create_product):
    """When a product has an image, the expanded view must show a 'Remove image' button.

    The button carries ``data-action='remove-image'`` and is only rendered
    when there is an image stored for the product.
    """
    product = api_create_product(name="ImgRemoveBtnTest")
    product_id = product["id"]

    _put_image(live_url, product_id, TINY_IMAGE)

    _reload_and_wait(page)
    _expand_product_row(page, "ImgRemoveBtnTest")

    remove_btn = page.locator(f"[data-action='remove-image'][data-id='{product_id}']")
    expect(remove_btn).to_be_visible(timeout=5000)


def test_remove_image_via_ui(page, live_url, api_create_product):
    """Clicking the 'Remove image' button and confirming the modal removes the image.

    After the modal is confirmed the UI should swap the img element for the
    placeholder div (``.expanded-img-placeholder``).  The test reloads the
    page afterwards to ensure the placeholder persists from the database
    state, not merely from an optimistic DOM update.
    """
    product = api_create_product(name="ImgRemoveUITest")
    product_id = product["id"]

    _put_image(live_url, product_id, TINY_IMAGE)

    _reload_and_wait(page)
    _expand_product_row(page, "ImgRemoveUITest")

    # Verify the image is present before removal
    img = page.locator(f"#prod-img-{product_id}")
    expect(img).to_be_visible(timeout=5000)

    # Click the remove button
    remove_btn = page.locator(f"[data-action='remove-image'][data-id='{product_id}']")
    remove_btn.click()
    page.wait_for_timeout(300)

    # Confirm the modal dialog
    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()
    page.wait_for_timeout(500)

    # Reload to confirm the deletion is persisted in the database
    _reload_and_wait(page)
    _expand_product_row(page, "ImgRemoveUITest")

    placeholder = page.locator(".expanded-img-placeholder")
    expect(placeholder.first).to_be_visible(timeout=5000)
