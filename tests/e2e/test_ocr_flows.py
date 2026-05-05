"""E2E tests for OCR ingredient and nutrition scan flows.

Tests the OCR buttons, file picker triggers, and mocked API result handling
for both ingredient extraction and nutrition label scanning.

All OCR API calls are intercepted via page.route() — never via
unittest.mock.patch, which does not work across process boundaries.
"""

import json

import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fake JPEG bytes for file uploads. The OCR API is mocked via page.route(),
# so the actual content does not need to be a valid image — only the JPEG
# SOI/EOI markers are included for realism.
_TINY_JPEG_BYTES = b"\xff\xd8\xff\xd9"


def _go_to_register(page):
    page.locator("button.nav-tab[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


# ---------------------------------------------------------------------------
# OCR button presence tests
# ---------------------------------------------------------------------------


def test_ocr_ingredient_button_exists_on_register(page):
    """The OCR ingredient scan button must be present on the register form."""
    _go_to_register(page)
    ocr_btn = page.locator("#f-ocr-btn")
    expect(ocr_btn).to_be_attached()


def test_ocr_nutrition_button_exists_on_register(page):
    """The OCR nutrition scan button must be present on the register form."""
    _go_to_register(page)
    ocr_nutri_btn = page.locator("#f-ocr-nutri-btn")
    expect(ocr_nutri_btn).to_be_attached()


def test_ocr_ingredient_button_exists_on_edit(page, api_create_product):
    """The OCR ingredient scan button must be present in the edit form."""
    api_create_product(name="OCREditBtnProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="OCREditBtnProd")
    row.first.click()
    page.wait_for_timeout(300)
    page.locator("[data-action='start-edit']").first.click()
    page.wait_for_timeout(400)

    expect(page.locator("#ed-ocr-btn")).to_be_attached()


def test_ocr_nutrition_button_exists_on_edit(page, api_create_product):
    """The OCR nutrition scan button must be present in the edit form."""
    api_create_product(name="OCRNutriEditProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="OCRNutriEditProd")
    row.first.click()
    page.wait_for_timeout(300)
    page.locator("[data-action='start-edit']").first.click()
    page.wait_for_timeout(400)

    expect(page.locator("#ed-ocr-nutri-btn")).to_be_attached()


# ---------------------------------------------------------------------------
# OCR ingredient scan: full mocked flow
# ---------------------------------------------------------------------------


def test_ocr_ingredients_scan_populates_ingredients_field(page, tmp_path):
    """Clicking OCR ingredient button, providing a file, and receiving a mocked
    API response should populate the ingredients textarea."""
    _go_to_register(page)

    # Route the OCR ingredients endpoint to return a controlled payload.
    def _handle_ingredients(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"text": "Skummet melk, bakteriekultur, løpe", "provider": "tesseract"}),
        )

    page.route("**/api/ocr/ingredients", _handle_ingredients)

    # Write a tiny JPEG so the file chooser has a real file to return.
    fake_image = tmp_path / "scan.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-btn").click()

    file_chooser = fc_info.value
    file_chooser.set_files(str(fake_image))

    # The ingredients textarea should receive the text from the mocked response.
    ingredients_field = page.locator("#f-ingredients")
    expect(ingredients_field).to_have_value("Skummet melk, bakteriekultur, løpe", timeout=5000)


def test_ocr_ingredients_scan_shows_success_toast(page, tmp_path):
    """A successful OCR ingredient scan should show a success toast."""
    _go_to_register(page)

    page.route(
        "**/api/ocr/ingredients",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"text": "Havre, vann, salt", "provider": "tesseract"}),
        ),
    )

    fake_image = tmp_path / "scan2.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-btn").click()
    fc_info.value.set_files(str(fake_image))

    # A success toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


def test_ocr_ingredients_error_toast_on_no_text(page, tmp_path):
    """When the OCR API returns an error_type of 'no_text', an error toast appears."""
    _go_to_register(page)

    page.route(
        "**/api/ocr/ingredients",
        lambda route: route.fulfill(
            status=400,
            content_type="application/json",
            body=json.dumps({"error": "No text found", "error_type": "no_text"}),
        ),
    )

    fake_image = tmp_path / "blank.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-btn").click()
    fc_info.value.set_files(str(fake_image))

    # An error toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)
    expect(page.locator("#toast.show")).to_have_class(lambda cls: "error" in cls, timeout=5000)


# ---------------------------------------------------------------------------
# OCR nutrition scan: full mocked flow
# ---------------------------------------------------------------------------


def test_ocr_nutrition_scan_fills_numeric_fields(page, tmp_path):
    """Clicking OCR nutrition button, providing a file, and receiving a mocked
    API response should fill the corresponding numeric input fields."""
    _go_to_register(page)

    page.route(
        "**/api/ocr/nutrition",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "values": {"kcal": 342, "protein": 12.5, "fat": 8.0},
                "provider": "openai",
            }),
        ),
    )

    fake_image = tmp_path / "nutri.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-nutri-btn").click()
    fc_info.value.set_files(str(fake_image))

    # The kcal field should have been populated (only fills blank fields).
    expect(page.locator("#f-kcal")).to_have_value("342", timeout=5000)


def test_ocr_nutrition_scan_shows_success_toast(page, tmp_path):
    """A successful OCR nutrition scan should show a toast."""
    _go_to_register(page)

    page.route(
        "**/api/ocr/nutrition",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "values": {"kcal": 200, "protein": 5.0},
                "provider": "tesseract",
            }),
        ),
    )

    fake_image = tmp_path / "nutri2.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-nutri-btn").click()
    fc_info.value.set_files(str(fake_image))

    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


def test_ocr_nutrition_scan_no_values_shows_warning(page, tmp_path):
    """When the OCR nutrition API returns no values, a warning toast is shown."""
    _go_to_register(page)

    page.route(
        "**/api/ocr/nutrition",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"values": {}, "error_type": "no_values", "provider": "tesseract"}),
        ),
    )

    fake_image = tmp_path / "empty_nutri.jpg"
    fake_image.write_bytes(_TINY_JPEG_BYTES)

    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-nutri-btn").click()
    fc_info.value.set_files(str(fake_image))

    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# OCR button triggers file picker (no file selected)
# ---------------------------------------------------------------------------


def test_ocr_ingredient_button_triggers_file_chooser(page):
    """Clicking the OCR ingredient button must open a file chooser."""
    _go_to_register(page)

    # Route to prevent any real network call from interfering.
    page.route("**/api/ocr/ingredients", lambda route: route.abort())

    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("#f-ocr-btn").click()

    assert fc_info.value is not None


def test_ocr_nutrition_button_triggers_file_chooser(page):
    """Clicking the OCR nutrition button must open a file chooser."""
    _go_to_register(page)

    page.route("**/api/ocr/nutrition", lambda route: route.abort())

    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("#f-ocr-nutri-btn").click()

    assert fc_info.value is not None
