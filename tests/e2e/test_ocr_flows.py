"""E2E tests for OCR ingredient scanning flows."""

import base64

from playwright.sync_api import expect

# Minimal valid 1x1 PNG (white pixel)
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


def test_ocr_ingredients_error_toast_on_no_text(page, live_url, tmp_path):
    """When the OCR endpoint returns no text, an error toast must appear."""
    # Create a minimal image file for the file chooser
    img_path = tmp_path / "test_ocr.png"
    img_path.write_bytes(_TINY_PNG)

    # Intercept the OCR request and return an empty-text response
    page.route(
        "**/api/ocr/ingredients",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"text": "", "error": "No text found in image"}',
        ),
    )

    # Navigate to the register form where #f-ocr-btn lives
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()
    page.wait_for_selector("#f-ocr-btn", state="visible", timeout=5000)

    # Click the OCR button and provide the fake image via the file chooser
    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-btn").click()
    fc_info.value.set_files(str(img_path))

    # The JS code calls showToast(t('toast_ocr_no_text'), 'error') when text is empty
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=8000)
