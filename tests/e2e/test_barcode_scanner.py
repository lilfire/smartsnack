"""E2E tests for the barcode scanner module (P0 gap #8).

The actual camera cannot be used in a headless browser environment, so these
tests focus on:
  - Verifying scanner-related UI elements exist on both the register and
    search views.
  - Confirming the scanner JS module is loaded and exposes the expected
    window-level functions.
  - Verifying scan button attributes (title/tooltip).
  - Testing post-scan flows by invoking scanner.js exported functions directly
    via page.evaluate() with dynamic import(), bypassing unavailable hardware:
      * showScanNotFoundModal — the "not found" modal when a scanned EAN is
        not in the local database.
      * showScanOffConfirm — the "fetch from OFF?" confirm after assigning
        an EAN to an existing product.
      * showScanProductPicker — lets the user pick a local product to assign
        the scanned EAN to.

Note: showScanNotFoundModal, showScanProductPicker, and showScanOffConfirm are
not exported to window by app.js, so they are invoked via dynamic import().
Functions that ARE on window (openScanner, openSearchScanner, scanRegisterNew,
scanUpdateExisting, closeScanModal, etc.) are called directly.
"""

import json

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _go_to_search(page):
    page.locator("button[data-view='search']").click()
    expect(page.locator("#view-search")).to_be_visible()


def _call_scanner_fn(page, fn_name, *args):
    """Invoke a named export from scanner.js via dynamic import.

    Uses the module URL that the app already has loaded to avoid a second
    fetch.  Falls back to the window global if it happens to be present.
    """
    args_js = ", ".join(json.dumps(a) for a in args)
    page.evaluate(f"""async () => {{
        if (typeof window['{fn_name}'] === 'function') {{
            window['{fn_name}']({args_js});
            return;
        }}
        const mod = await import('/static/js/scanner.js');
        if (typeof mod.{fn_name} === 'function') {{
            mod.{fn_name}({args_js});
        }}
    }}""")


# ---------------------------------------------------------------------------
# Tests: scanner button presence
# ---------------------------------------------------------------------------


def test_scan_button_exists_on_register(page):
    """The scan barcode button must be present on the register form DOM."""
    _go_to_register(page)
    scan_btn = page.locator("[data-i18n-title='btn_scan_title']")
    expect(scan_btn).to_be_attached()


def test_scan_button_exists_on_search(page):
    """The scan barcode button must be present on the search view DOM."""
    _go_to_search(page)
    scan_btn = page.locator("[data-i18n-title='search_scan_title']")
    expect(scan_btn).to_be_attached()


def test_scan_button_register_has_title_attribute(page):
    """The register-view scan button must carry a data-i18n-title attribute
    so the i18n system can set a meaningful tooltip."""
    _go_to_register(page)
    scan_btn = page.locator("[data-i18n-title='btn_scan_title']")
    expect(scan_btn).to_be_attached()

    i18n_title = scan_btn.get_attribute("data-i18n-title")
    title = scan_btn.get_attribute("title")
    assert (i18n_title is not None) or (title is not None), (
        "Scan button must have a data-i18n-title or title attribute for accessibility"
    )


def test_scan_button_search_has_title_attribute(page):
    """The search-view scan button must carry a data-i18n-title attribute."""
    _go_to_search(page)
    scan_btn = page.locator("[data-i18n-title='search_scan_title']")
    expect(scan_btn).to_be_attached()

    i18n_title = scan_btn.get_attribute("data-i18n-title")
    title = scan_btn.get_attribute("title")
    assert (i18n_title is not None) or (title is not None), (
        "Search scan button must have a data-i18n-title or title attribute"
    )


# ---------------------------------------------------------------------------
# Tests: scanner JS module is loaded (window-exposed functions)
# ---------------------------------------------------------------------------


def test_scanner_module_exposes_open_scanner(page):
    """app.js assigns openScanner to window; it must be a callable function
    after the module loads."""
    has_fn = page.evaluate("() => typeof window.openScanner === 'function'")
    assert has_fn, "window.openScanner must be a function after the app loads"


def test_scanner_module_exposes_open_search_scanner(page):
    """app.js assigns openSearchScanner to window; it must be callable."""
    has_fn = page.evaluate("() => typeof window.openSearchScanner === 'function'")
    assert has_fn, "window.openSearchScanner must be a function after the app loads"


def test_scanner_module_exposes_close_scan_modal(page):
    """app.js assigns closeScanModal to window; it must be callable."""
    has_fn = page.evaluate("() => typeof window.closeScanModal === 'function'")
    assert has_fn, "window.closeScanModal must be a function after the app loads"


def test_scanner_module_exposes_scan_register_new(page):
    """app.js assigns scanRegisterNew to window; it must be callable."""
    has_fn = page.evaluate("() => typeof window.scanRegisterNew === 'function'")
    assert has_fn, "window.scanRegisterNew must be a function after the app loads"


def test_scanner_module_exposes_scan_update_existing(page):
    """app.js assigns scanUpdateExisting to window; it must be callable."""
    has_fn = page.evaluate("() => typeof window.scanUpdateExisting === 'function'")
    assert has_fn, "window.scanUpdateExisting must be a function after the app loads"


# ---------------------------------------------------------------------------
# Tests: post-scan "not found" modal (showScanNotFoundModal)
# ---------------------------------------------------------------------------


def test_scan_not_found_modal_appears(page):
    """showScanNotFoundModal('9999999999999') must create and display
    #scan-modal-bg in the DOM."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)


def test_scan_not_found_modal_shows_ean(page):
    """The not-found modal must display the scanned EAN so the user can
    confirm which barcode was detected."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)
    expect(scan_modal_bg).to_contain_text("9999999999999", timeout=2000)


def test_scan_not_found_modal_has_register_button(page):
    """The not-found modal must include a 'Register new' button."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)

    register_btn = page.locator("#scan-modal-bg .scan-modal-btn-register")
    expect(register_btn).to_be_visible(timeout=2000)


def test_scan_not_found_modal_has_cancel_button(page):
    """The not-found modal must include a Cancel button."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)

    cancel_btn = page.locator("#scan-modal-bg .scan-modal-btn-cancel")
    expect(cancel_btn).to_be_visible(timeout=2000)


def test_scan_not_found_modal_cancel_closes_it(page):
    """Clicking Cancel on the not-found modal must remove #scan-modal-bg
    from the DOM."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)

    page.locator("#scan-modal-bg .scan-modal-btn-cancel").click()

    expect(scan_modal_bg).to_be_hidden(timeout=3000)


def test_scan_not_found_modal_register_navigates_to_register_view(page):
    """Clicking 'Register new' on the not-found modal must navigate to the
    register view and pre-fill the EAN field with the scanned code."""
    _call_scanner_fn(page, "showScanNotFoundModal", "9999999999999")

    scan_modal_bg = page.locator("#scan-modal-bg")
    expect(scan_modal_bg).to_be_visible(timeout=3000)

    page.locator("#scan-modal-bg .scan-modal-btn-register").click()

    # scanRegisterNew calls switchView('register') and fills #f-ean
    expect(page.locator("#view-register")).to_be_visible(timeout=5000)
    expect(page.locator("#f-ean")).to_have_value("9999999999999", timeout=3000)


# ---------------------------------------------------------------------------
# Tests: scan-off-confirm modal (showScanOffConfirm)
# ---------------------------------------------------------------------------


def test_scan_off_confirm_modal_appears(page):
    """showScanOffConfirm must create and display #scan-off-confirm-bg."""
    _call_scanner_fn(page, "showScanOffConfirm", "7310865004703", 1)

    confirm_bg = page.locator("#scan-off-confirm-bg")
    expect(confirm_bg).to_be_visible(timeout=3000)


def test_scan_off_confirm_modal_shows_ean(page):
    """The scan-off-confirm modal must display the EAN being confirmed."""
    _call_scanner_fn(page, "showScanOffConfirm", "7310865004703", 1)

    confirm_bg = page.locator("#scan-off-confirm-bg")
    expect(confirm_bg).to_be_visible(timeout=3000)
    expect(confirm_bg).to_contain_text("7310865004703", timeout=2000)


def test_scan_off_confirm_has_fetch_and_skip_buttons(page):
    """The scan-off-confirm modal must have both a Fetch and a Skip button."""
    _call_scanner_fn(page, "showScanOffConfirm", "7310865004703", 1)

    confirm_bg = page.locator("#scan-off-confirm-bg")
    expect(confirm_bg).to_be_visible(timeout=3000)

    # Fetch button uses .scan-modal-btn-register; Skip uses .scan-modal-btn-cancel
    expect(page.locator("#scan-off-confirm-bg .scan-modal-btn-register")).to_be_visible(
        timeout=2000
    )
    expect(page.locator("#scan-off-confirm-bg .scan-modal-btn-cancel")).to_be_visible(
        timeout=2000
    )


def test_scan_off_confirm_skip_closes_modal(page):
    """Clicking the Skip button on the scan-off-confirm modal must close it."""
    _call_scanner_fn(page, "showScanOffConfirm", "7310865004703", 1)

    confirm_bg = page.locator("#scan-off-confirm-bg")
    expect(confirm_bg).to_be_visible(timeout=3000)

    page.locator("#scan-off-confirm-bg .scan-modal-btn-cancel").click()

    expect(confirm_bg).to_be_hidden(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: scan product picker modal (via scanUpdateExisting on window)
# ---------------------------------------------------------------------------


def test_scan_product_picker_modal_appears(page):
    """scanUpdateExisting (on window) calls showScanProductPicker internally;
    #scan-picker-bg must appear."""
    page.evaluate("() => window.scanUpdateExisting('7310865004703')")

    picker_bg = page.locator("#scan-picker-bg")
    expect(picker_bg).to_be_visible(timeout=3000)


def test_scan_product_picker_has_search_input(page):
    """The scan product picker modal must contain a search input field
    (#scan-picker-input)."""
    page.evaluate("() => window.scanUpdateExisting('7310865004703')")

    picker_bg = page.locator("#scan-picker-bg")
    expect(picker_bg).to_be_visible(timeout=3000)

    search_input = page.locator("#scan-picker-input")
    expect(search_input).to_be_visible(timeout=2000)


def test_scan_product_picker_close_button_dismisses_it(page):
    """Clicking the × close button in the scan product picker must remove
    #scan-picker-bg from the DOM."""
    page.evaluate("() => window.scanUpdateExisting('7310865004703')")

    picker_bg = page.locator("#scan-picker-bg")
    expect(picker_bg).to_be_visible(timeout=3000)

    close_btn = page.locator("#scan-picker-bg .off-modal-close")
    expect(close_btn).to_be_visible(timeout=2000)
    close_btn.click()

    expect(picker_bg).to_be_hidden(timeout=3000)


def test_scan_product_picker_search_returns_results(page, api_create_product):
    """Searching for an existing product name in the scan picker must display
    matching result rows in #scan-picker-body."""
    api_create_product(name="ScanPickerFindMe", category="Snacks")

    page.evaluate("() => window.scanUpdateExisting('7310865004703')")

    picker_bg = page.locator("#scan-picker-bg")
    expect(picker_bg).to_be_visible(timeout=3000)

    page.locator("#scan-picker-input").fill("ScanPickerFindMe")

    # The search button text comes from t('off_search_btn') — click whichever
    # button is inside the picker modal's search area
    search_btn = page.locator("#scan-picker-bg .off-modal-search button")
    expect(search_btn).to_be_visible(timeout=2000)
    search_btn.click()

    result_row = page.locator("#scan-picker-body .off-result[data-action='pick']")
    expect(result_row.first).to_be_visible(timeout=5000)
    expect(page.locator("#scan-picker-body")).to_contain_text(
        "ScanPickerFindMe", timeout=5000
    )
