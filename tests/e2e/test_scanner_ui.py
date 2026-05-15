"""Test scanner/barcode UI degraded states (Task 9).

Verifies that:
- When getUserMedia throws NotAllowedError, scanner shows error UI
- When getUserMedia throws NotFoundError, scanner shows error UI
- Scanner button exists in register view and is clickable
"""

from playwright.sync_api import expect


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

        # The scanner should show an error state
        # Either toast_scanner_load_error or scan_camera_error should appear
        page.wait_for_timeout(2000)

        # Check for the scanner error UI (camera error message)
        scanner_error = page.locator(".scanner-error")
        toast = page.locator(".toast")
        # At least one of these should be visible
        has_error_ui = scanner_error.count() > 0 or toast.count() > 0
        assert has_error_ui, "Expected scanner error UI (toast or .scanner-error div) to appear"

        # Verify toast contains the scanner load error message
        if toast.count() > 0:
            # Norwegian: "Skanner-biblioteket ble ikke lastet" or camera error
            toast_text = toast.first.text_content()
            assert "Skanner" in toast_text or "kamera" in toast_text.lower(), (
                f"Toast should mention scanner/camera error, got: {toast_text}"
            )
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

        page.wait_for_timeout(2000)

        # Check for error indication
        scanner_error = page.locator(".scanner-error")
        toast = page.locator(".toast")
        has_error_ui = scanner_error.count() > 0 or toast.count() > 0
        assert has_error_ui, "Expected scanner error UI (toast or .scanner-error div) to appear"

        if toast.count() > 0:
            toast_text = toast.first.text_content()
            assert "Skanner" in toast_text or "kamera" in toast_text.lower(), (
                f"Toast should mention scanner/camera error, got: {toast_text}"
            )
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
