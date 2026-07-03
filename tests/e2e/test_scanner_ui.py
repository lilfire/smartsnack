"""Test scanner/barcode UI degraded states (Task 9).

Verifies that:
- When getUserMedia throws NotAllowedError, scanner shows error UI
- When getUserMedia throws NotFoundError, scanner shows error UI
- Scanner button exists in register view and is clickable
"""

import json
import os

from playwright.sync_api import expect


def _load_translations(lang="no"):
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def test_scanner_not_allowed_error(browser, app_server, api_create_product):
    """Mock getUserMedia with NotAllowedError shows scanner error toast and UI."""
    # Create a product so the page loads normally
    api_create_product(name="ScannerTestProd")

    page = browser.new_page()
    try:
        # Mock getUserMedia to throw NotAllowedError before page loads
        page.add_init_script("""
            navigator.mediaDevices = {
                getUserMedia: () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError')),
                enumerateDevices: () => Promise.resolve([])
            };
        """)

        page.route(
            "**/*",
            lambda route: (
                route.abort()
                if not route.request.url.startswith(app_server)
                else route.continue_()
            ),
        )
        page.goto(app_server, wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        # Navigate to register view to access the scanner button
        nav_register = page.locator("[data-view='register']")
        nav_register.click()
        page.wait_for_timeout(500)

        # Click the scanner button in the register form
        scan_btn = page.locator(".btn-scan")
        expect(scan_btn).to_be_visible(timeout=3000)
        scan_btn.click()

        # html5-qrcode is bundled locally (static/js/vendor), so the library
        # loads and Html5Qrcode.start() rejects on the mocked getUserMedia.
        # scanner.js's catch handler then shows BOTH the load-error toast and
        # the .scanner-error div with scan_camera_error — assert both.
        t = _load_translations()
        scanner_error = page.locator(".scanner-error")
        expect(scanner_error.first).to_be_visible(timeout=5000)
        expect(scanner_error.first).to_contain_text(t["scan_camera_error"])
        toast = page.locator(".toast").first
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_scanner_load_error"])
    finally:
        page.close()


def test_scanner_not_found_error(browser, app_server, api_create_product):
    """Mock getUserMedia with NotFoundError shows scanner error toast and UI."""
    api_create_product(name="ScannerTestProd2")

    page = browser.new_page()
    try:
        # Mock getUserMedia to throw NotFoundError
        page.add_init_script("""
            navigator.mediaDevices = {
                getUserMedia: () => Promise.reject(new DOMException('No camera found', 'NotFoundError')),
                enumerateDevices: () => Promise.resolve([])
            };
        """)

        page.route(
            "**/*",
            lambda route: (
                route.abort()
                if not route.request.url.startswith(app_server)
                else route.continue_()
            ),
        )
        page.goto(app_server, wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        # Navigate to register view
        nav_register = page.locator("[data-view='register']")
        nav_register.click()
        page.wait_for_timeout(500)

        # Click scanner button
        scan_btn = page.locator(".btn-scan")
        expect(scan_btn).to_be_visible(timeout=3000)
        scan_btn.click()

        # Same deterministic error path as the NotAllowedError test: the
        # local html5-qrcode lib loads, start() rejects on the mocked
        # getUserMedia, and scanner.js shows both the toast and error div.
        t = _load_translations()
        scanner_error = page.locator(".scanner-error")
        expect(scanner_error.first).to_be_visible(timeout=5000)
        expect(scanner_error.first).to_contain_text(t["scan_camera_error"])
        toast = page.locator(".toast").first
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_scanner_load_error"])
    finally:
        page.close()


def test_scanner_button_exists_in_register_view(page):
    """Scanner button exists in register view and is clickable."""
    # Navigate to register view
    nav_register = page.locator("[data-view='register']")
    nav_register.click()
    page.wait_for_timeout(500)

    # The scan button should be visible
    scan_btn = page.locator(".btn-scan")
    expect(scan_btn).to_be_visible(timeout=3000)
    expect(scan_btn).to_be_enabled()

    # Verify the button has the i18n aria-label key (translated at runtime)
    expect(scan_btn).to_have_attribute("data-i18n-aria-label", "btn_scan_title")


def test_search_scanner_button_exists(page):
    """Scanner button exists in search view and is clickable."""
    # The search scanner button should be visible on the search page
    scan_btn = page.locator(".btn-scan-search")
    expect(scan_btn).to_be_visible(timeout=3000)
    expect(scan_btn).to_be_enabled()
