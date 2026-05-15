"""Task 5: OCR UI error states.

Tests OCR ingredient scanning error paths by mocking the /api/ocr/ingredients
endpoint with various error payloads and asserting the correct toast text.
All expected strings loaded from translation files.
"""

import json
import os
import re

from playwright.sync_api import expect


def _load_translations(lang="no"):
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


# Minimal 1x1 PNG for file chooser
_FAKE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _trigger_ocr_with_mock(page, route_pattern, mock_status, mock_body):
    """Install a route mock for the OCR endpoint, trigger the OCR button,
    and return after the file chooser completes."""

    def _handler(route):
        route.fulfill(
            status=mock_status,
            content_type="application/json",
            body=json.dumps(mock_body),
        )

    page.route(route_pattern, _handler)

    # Trigger the OCR ingredients button — this opens a file picker
    with page.expect_file_chooser() as fc_info:
        page.locator("#f-ocr-btn").click()

    file_chooser = fc_info.value
    file_chooser.set_files(
        [{"name": "test.png", "mimeType": "image/png", "buffer": _FAKE_PNG}]
    )


class TestOcrNoText:
    """OCR returns no_text error."""

    def test_no_text_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            400,
            {"error": "no_text", "error_type": "no_text", "error_detail": "No text found"},
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_ocr_no_text"])

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrInvalidImage:
    """OCR returns invalid_image error."""

    def test_invalid_image_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            400,
            {
                "error": "invalid_image",
                "error_type": "invalid_image",
                "error_detail": "Invalid image format",
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_ocr_invalid_image"])

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrProviderTimeout:
    """OCR returns provider_timeout error."""

    def test_provider_timeout_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            503,
            {
                "error": "provider_timeout",
                "error_type": "provider_timeout",
                "error_detail": "Provider timed out",
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_ocr_provider_timeout"])

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrProviderQuota:
    """OCR returns provider_quota error."""

    def test_provider_quota_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            429,
            {
                "error": "provider_quota",
                "error_type": "provider_quota",
                "error_detail": "Rate limit exceeded",
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_ocr_provider_quota"])

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrTokenLimit:
    """OCR returns token_limit_exceeded error."""

    def test_token_limit_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            429,
            {
                "error": "token_limit",
                "error_type": "token_limit_exceeded",
                "error_detail": "No remaining tokens",
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_ocr_token_limit"])

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrGenericError:
    """OCR returns HTTP 500 generic error."""

    def test_generic_500_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        error_detail = "an unexpected error occurred"
        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            500,
            {
                "error": "generic",
                "error_type": "generic",
                "error_detail": error_detail,
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        # toast_ocr_generic_error contains {error_detail} param
        expected = t["toast_ocr_generic_error"].replace(
            "{error_detail}", error_detail
        )
        expect(toast).to_contain_text(expected)

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))


class TestOcrFallbackWarning:
    """OCR returns success with fallback warning."""

    def test_fallback_warning_toast(self, page):
        t = _load_translations()
        _go_to_register(page)

        _trigger_ocr_with_mock(
            page,
            re.compile(r".*/api/ocr/ingredients$"),
            200,
            {
                "text": "Some ingredient text",
                "provider": "gemini",
                "fallback": True,
                "error_detail": "primary provider unavailable",
            },
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        # toast_ocr_fallback contains {fallback_provider} and {reason} params
        expected_fragment = t["toast_ocr_fallback"].split("{")[0].strip()
        if expected_fragment:
            expect(toast).to_contain_text(expected_fragment)
        else:
            # Fallback: just check it contains the provider name
            expect(toast).to_contain_text("gemini")

        page.unroute(re.compile(r".*/api/ocr/ingredients$"))
