"""End-to-end tests for the nutrition-label OCR auto-fill feature.

Intercepts /api/ocr/nutrition via Playwright route mocking so no real
provider is called. Verifies that:
  - The scan button populates empty nutrition inputs in the register form
  - The same button in the edit modal populates ed-* inputs
  - Pre-filled inputs are not overwritten
  - Zero-value and 429 error paths surface a toast
"""

import json
import re

from playwright.sync_api import expect


# A minimal 1x1 PNG for the <input type="file"> upload.
_FAKE_PNG_BYTES = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
    0x0D, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x62, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
    0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
])


def _install_mock_nutrition_route(page, payload, status=200):
    """Route-intercept /api/ocr/nutrition to return a fixed payload."""
    def _handler(route):
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        )

    page.route(re.compile(r".*/api/ocr/nutrition$"), _handler)


def _upload_file_via_picker(page, file_input_selector_opens):
    """Upload a fake PNG through the file chooser opened by clicking the button.

    file_input_selector_opens is a callable (page -> None) that triggers
    the file picker (i.e. clicks the scan button).
    """
    with page.expect_file_chooser() as fc_info:
        file_input_selector_opens(page)
    file_chooser = fc_info.value
    file_chooser.set_files(
        files=[{
            "name": "label.png",
            "mimeType": "image/png",
            "buffer": _FAKE_PNG_BYTES,
        }]
    )


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


class TestRegisterFormNutritionOcr:
    """The scan button on the register form populates empty nutrition inputs."""

    def test_scan_button_exists(self, page):
        _go_to_register(page)
        expect(page.locator("#f-ocr-nutri-btn")).to_be_visible()

    def test_populates_empty_nutrition_inputs(self, page):
        _install_mock_nutrition_route(page, {
            "values": {
                "kcal": 250,
                "energy_kj": 1050,
                "fat": 12.5,
                "saturated_fat": 4.0,
                "carbs": 30.0,
                "sugar": 5.0,
                "fiber": 3.0,
                "protein": 8.0,
                "salt": 0.8,
            },
            "count": 9,
            "provider": "Claude Vision",
            "fallback": False,
        })
        _go_to_register(page)

        _upload_file_via_picker(
            page, lambda p: p.locator("#f-ocr-nutri-btn").click()
        )

        # Wait for the scan to complete (button re-enabled).
        expect(page.locator("#f-ocr-nutri-btn")).to_be_enabled(timeout=5000)

        expect(page.locator("#f-kcal")).to_have_value("250")
        expect(page.locator("#f-energy_kj")).to_have_value("1050")
        expect(page.locator("#f-fat")).to_have_value("12.5")
        expect(page.locator("#f-saturated_fat")).to_have_value("4")
        expect(page.locator("#f-carbs")).to_have_value("30")
        expect(page.locator("#f-sugar")).to_have_value("5")
        expect(page.locator("#f-fiber")).to_have_value("3")
        expect(page.locator("#f-protein")).to_have_value("8")
        expect(page.locator("#f-salt")).to_have_value("0.8")

    def test_pre_filled_inputs_are_not_overwritten(self, page):
        _install_mock_nutrition_route(page, {
            "values": {"kcal": 250, "fat": 12.5, "protein": 8},
            "count": 3,
            "provider": "Claude Vision",
            "fallback": False,
        })
        _go_to_register(page)

        page.locator("#f-fat").fill("99")

        _upload_file_via_picker(
            page, lambda p: p.locator("#f-ocr-nutri-btn").click()
        )
        expect(page.locator("#f-ocr-nutri-btn")).to_be_enabled(timeout=5000)

        # fat was pre-filled, must remain unchanged
        expect(page.locator("#f-fat")).to_have_value("99")
        # other fields are populated from the mock
        expect(page.locator("#f-kcal")).to_have_value("250")
        expect(page.locator("#f-protein")).to_have_value("8")

    def test_no_values_shows_warning_toast(self, page):
        _install_mock_nutrition_route(page, {
            "values": {},
            "count": 0,
            "error_type": "no_values",
            "provider": "Tesseract (Local)",
            "fallback": False,
        })
        _go_to_register(page)

        _upload_file_via_picker(
            page, lambda p: p.locator("#f-ocr-nutri-btn").click()
        )

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_quota_error_shows_toast(self, page):
        _install_mock_nutrition_route(page, {
            "error": "OCR provider quota exceeded",
            "error_type": "provider_quota",
            "error_detail": "The selected OCR provider has reached its usage quota.",
        }, status=429)
        _go_to_register(page)

        _upload_file_via_picker(
            page, lambda p: p.locator("#f-ocr-nutri-btn").click()
        )

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)


class TestEditFormNutritionOcr:
    """The scan button in the edit modal populates ed-* nutrition inputs."""

    def test_edit_form_scan_button_populates_inputs(self, page, api_create_product):
        api_create_product(name="OCR Edit Target")

        _install_mock_nutrition_route(page, {
            "values": {
                "kcal": 333,
                "fat": 11.1,
                "protein": 9.9,
            },
            "count": 3,
            "provider": "Claude Vision",
            "fallback": False,
        })

        page.reload()
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        row = page.locator(".table-row", has_text="OCR Edit Target").first
        row.click()
        page.wait_for_timeout(300)

        edit_btn = page.locator("[data-action='start-edit']").first
        edit_btn.click()
        page.wait_for_timeout(300)

        scan_btn = page.locator("#ed-ocr-nutri-btn")
        expect(scan_btn).to_be_visible(timeout=5000)

        # Clear the existing values so our mocked values can populate them.
        for field in ("kcal", "fat", "protein"):
            page.locator(f"#ed-{field}").fill("")

        _upload_file_via_picker(page, lambda p: scan_btn.click())
        expect(scan_btn).to_be_enabled(timeout=5000)

        expect(page.locator("#ed-kcal")).to_have_value("333")
        expect(page.locator("#ed-fat")).to_have_value("11.1")
        expect(page.locator("#ed-protein")).to_have_value("9.9")
