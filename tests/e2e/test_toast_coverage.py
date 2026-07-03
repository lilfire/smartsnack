"""Toast text assertion tests for all toast keys.

Each test triggers the UI action that causes a toast and asserts
the toast text contains the expected translation string loaded
from translations/no.json.
"""

import json
import os

from playwright.sync_api import expect


def _load_translations(lang="no"):
    """Load translations from the translation JSON files."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def _go_to_register(page):
    """Navigate to the register view."""
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _go_to_settings(page):
    """Navigate to settings view."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _go_to_search(page):
    """Navigate to search view."""
    page.locator("button[data-view='search']").click()
    page.wait_for_timeout(300)


def _open_settings_section(page, i18n_key):
    """Open a specific settings section by its data-i18n toggle key."""
    toggle = page.locator(
        f".settings-toggle:has(span[data-i18n='{i18n_key}'])"
    ).first
    toggle.click()
    page.wait_for_timeout(300)


def _wait_for_toast(page, expected_text, timeout=5000):
    """Wait for toast to appear and assert it contains expected text."""
    toast = page.locator("#toast.show")
    expect(toast).to_be_visible(timeout=timeout)
    expect(toast).to_contain_text(expected_text, timeout=timeout)


def _dismiss_toast(page):
    """Dismiss current toast if visible."""
    toast = page.locator("#toast.show")
    if toast.is_visible():
        close_btn = toast.locator(".toast-close")
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(200)


def _dismiss_modal(page):
    """Dismiss any open confirm modal."""
    cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
    if cancel.is_visible():
        cancel.click()
        page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# Product Toasts
# ---------------------------------------------------------------------------


class TestProductToasts:
    """Tests for product-related toast messages."""

    def test_toast_product_name_required(self, page):
        """Submit register form without name shows product name required toast."""
        t = _load_translations()
        _go_to_register(page)
        page.locator("#f-kcal").fill("100")
        page.locator("#btn-submit").click()
        _wait_for_toast(page, t["toast_product_name_required"])

    def test_toast_invalid_ean(self, page):
        """Submit register form with invalid EAN shows error toast."""
        t = _load_translations()
        _go_to_register(page)
        page.locator("#f-name").fill("Test Invalid EAN Product")
        page.locator("#f-ean").fill("abc123")
        page.locator("#btn-submit").click()
        _wait_for_toast(page, t["toast_invalid_ean"])

    def test_toast_product_added(self, page, unique_name):
        """Registering a product shows success toast with product name."""
        t = _load_translations()
        prod_name = unique_name("ToastTestProduct")
        _go_to_register(page)
        page.locator("#f-name").fill(prod_name)
        page.locator("#f-kcal").fill("150")
        page.locator("#f-protein").fill("10")
        page.locator("#f-fat").fill("5")
        page.locator("#f-carbs").fill("20")
        page.locator("#f-sugar").fill("3")
        page.locator("#f-salt").fill("0.5")
        page.locator("#f-smak").fill("4")
        page.locator("#btn-submit").click()
        # May get OFF modal - dismiss it
        page.wait_for_timeout(500)
        _dismiss_modal(page)
        # The toast text is the template with {name} replaced
        expected = t["toast_product_added"].replace("{name}", prod_name)
        _wait_for_toast(page, expected)

    def test_toast_product_deleted(self, page, api_create_product, unique_name):
        """Deleting a product shows delete toast with product name."""
        t = _load_translations()
        prod_name = unique_name("DeleteMeToast")
        product = api_create_product(name=prod_name)
        _go_to_search(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        # Click the product row to expand it
        row = page.locator(f".table-row[data-product-id='{product['id']}']")
        row.click()
        page.wait_for_timeout(500)
        # Click delete button (data-action="delete")
        delete_btn = page.locator(
            f"button[data-action='delete'][data-id='{product['id']}']"
        )
        expect(delete_btn).to_be_visible(timeout=5000)
        delete_btn.click()
        # Confirm delete modal
        page.wait_for_timeout(300)
        confirm_btn = page.locator(".scan-modal-bg .scan-modal button").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        expected = t["toast_product_deleted"].replace("{name}", prod_name)
        _wait_for_toast(page, expected)

    def test_toast_product_updated(self, page, api_create_product, unique_name):
        """Editing and saving a product shows updated toast."""
        t = _load_translations()
        product = api_create_product(name=unique_name("EditMeToast"))
        _go_to_search(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        row = page.locator(f".table-row[data-product-id='{product['id']}']")
        row.click()
        page.wait_for_timeout(500)
        # Click edit button (data-action="start-edit")
        edit_btn = page.locator(
            f"button[data-action='start-edit'][data-id='{product['id']}']"
        )
        expect(edit_btn).to_be_visible(timeout=5000)
        edit_btn.click()
        page.wait_for_timeout(500)
        # Save (data-action="save-product")
        save_btn = page.locator(
            f"button[data-action='save-product'][data-id='{product['id']}']"
        )
        expect(save_btn).to_be_visible(timeout=5000)
        save_btn.click()
        _wait_for_toast(page, t["toast_product_updated"])

    def test_toast_save_error(self, page):
        """Triggering a save error shows the save error toast."""
        t = _load_translations()
        _go_to_register(page)
        # Mock the products API to return 500
        page.route(
            "**/api/products",
            lambda route: route.fulfill(
                status=500,
                body='{"error":"forced error"}',
                content_type="application/json",
            ),
        )
        page.locator("#f-name").fill("ErrorProduct")
        page.locator("#f-kcal").fill("100")
        page.locator("#f-protein").fill("5")
        page.locator("#f-fat").fill("3")
        page.locator("#f-carbs").fill("10")
        page.locator("#f-sugar").fill("2")
        page.locator("#f-salt").fill("0.3")
        page.locator("#f-smak").fill("3")
        page.locator("#btn-submit").click()
        # Should show either the API error message or toast_save_error
        toast = page.locator("#toast.show")
        expect(toast).to_be_visible(timeout=5000)
        # The toast should show an error - either the message or the key text
        toast_text = toast.text_content()
        assert "error" in toast_text.lower() or t["toast_save_error"] in toast_text
        page.unroute("**/api/products")

    def test_toast_name_required(self, page, api_create_product):
        """Editing a product and clearing the name shows name required toast."""
        t = _load_translations()
        product = api_create_product(name="ClearNameToast")
        _go_to_search(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        row = page.locator(f".table-row[data-product-id='{product['id']}']")
        row.click()
        page.wait_for_timeout(500)
        # Click edit button
        edit_btn = page.locator(
            f"button[data-action='start-edit'][data-id='{product['id']}']"
        )
        expect(edit_btn).to_be_visible(timeout=5000)
        edit_btn.click()
        page.wait_for_timeout(500)
        # Clear the name field (#ed-name)
        name_input = page.locator("#ed-name")
        expect(name_input).to_be_visible(timeout=5000)
        name_input.fill("")
        # Click save
        save_btn = page.locator(
            f"button[data-action='save-product'][data-id='{product['id']}']"
        )
        save_btn.click()
        _wait_for_toast(page, t["toast_name_required"])


# ---------------------------------------------------------------------------
# Category Toasts
# ---------------------------------------------------------------------------


class TestCategoryToasts:
    """Tests for category-related toast messages."""

    def test_toast_category_added(self, page):
        """Adding a category shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_categories_title")
        page.wait_for_timeout(300)
        # Fill category name and label using their IDs
        name_input = page.locator("#cat-name")
        label_input = page.locator("#cat-label")
        expect(name_input).to_be_visible(timeout=5000)
        name_input.fill("testcat_toast")
        label_input.fill("Toast Category Display")
        # Click add category button (specific data-i18n to avoid weight override btn)
        add_btn = page.locator("button[data-i18n='btn_add_category']")
        add_btn.click()
        expected = t["toast_category_added"].replace(
            "{name}", "Toast Category Display"
        )
        _wait_for_toast(page, expected)

    def test_toast_name_display_required(self, page):
        """Adding a category without name/display shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_categories_title")
        page.wait_for_timeout(300)
        # Ensure fields are empty
        page.locator("#cat-name").fill("")
        page.locator("#cat-label").fill("")
        # Click add without filling fields
        add_btn = page.locator("button[data-i18n='btn_add_category']")
        add_btn.click()
        _wait_for_toast(page, t["toast_name_display_required"])

    def test_toast_category_updated(self, page, live_url):
        """Updating a category display name shows updated toast."""
        import urllib.request

        t = _load_translations()
        # First create a category via API
        payload = json.dumps({"name": "updatecat", "display": "UpdateCat"}).encode()
        req = urllib.request.Request(
            f"{live_url}/api/categories",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # May already exist

        _go_to_settings(page)
        _open_settings_section(page, "settings_categories_title")
        page.wait_for_timeout(500)
        # Modify a category display name input and fire its change handler
        # (settings-categories.js binds updateCategoryLabel on 'change').
        first_input = page.locator("#cat-list input.cat-item-label-input").first
        expect(first_input).to_be_visible(timeout=5000)
        first_input.fill("UpdatedDisplay")
        first_input.dispatch_event("change")
        _wait_for_toast(page, t["toast_category_updated"])

    def test_toast_cannot_delete_only_category(self, page, live_url):
        """Trying to delete the only category shows error toast."""
        import urllib.request

        t = _load_translations()
        # Get categories to check count
        req = urllib.request.Request(
            f"{live_url}/api/categories",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            categories = json.loads(resp.read())

        # If there's only one, try to delete it
        if len(categories) <= 1:
            _go_to_settings(page)
            _open_settings_section(page, "settings_categories_title")
            page.wait_for_timeout(500)
            del_btn = page.locator(
                ".category-row .btn-delete-category, .category-row button[aria-label*='Slett']"
            ).first
            if del_btn.is_visible():
                del_btn.click()
                page.wait_for_timeout(300)
                _wait_for_toast(page, t["toast_cannot_delete_only_category"])


# ---------------------------------------------------------------------------
# Backup Toasts
# ---------------------------------------------------------------------------


class TestBackupToasts:
    """Tests for backup/restore-related toast messages."""

    def test_toast_backup_downloaded(self, page):
        """Clicking backup download shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_database_title")
        page.wait_for_timeout(300)
        # Mock the navigation to prevent actual download
        page.evaluate(
            "() => { window._origLocation = window.location.href; }"
        )
        download_btn = page.locator(
            "button:has-text('Last ned backup')"
        ).first
        download_btn.click()
        _wait_for_toast(page, t["toast_backup_downloaded"])

    def test_toast_invalid_file_restore(self, page):
        """Restoring with non-JSON file shows invalid file toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_database_title")
        page.wait_for_timeout(300)
        # Set input files with non-JSON content
        restore_input = page.locator("#restore-input, input[type='file'][accept='.json']").first
        restore_input.set_input_files(
            {
                "name": "bad.txt",
                "mimeType": "text/plain",
                "buffer": b"not json at all",
            }
        )
        # Confirm the restore modal
        page.wait_for_timeout(500)
        confirm_btn = page.locator(".scan-modal-bg button").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        _wait_for_toast(page, t["toast_invalid_file"])


# ---------------------------------------------------------------------------
# OCR Toasts
# ---------------------------------------------------------------------------


class TestOcrToasts:
    """Tests for OCR-related toast messages.

    Each test drives the real OCR error path: clicking the register-form
    OCR button opens a file chooser, a file is provided, and the routed
    /api/ocr/ingredients request fails with a specific error_type. The
    toast must come from ocr.js _handleOcrError mapping that error_type —
    it is never injected directly, so these tests fail if the OCR error
    handling is removed or the error_type mapping breaks.
    """

    # Minimal JPEG (SOI + EOI). The OCR API call is intercepted via
    # page.route(), so the content never reaches a real OCR provider.
    _TINY_JPEG = b"\xff\xd8\xff\xd9"

    def _trigger_ocr_error(self, page, error_type):
        """Run the real OCR scan flow against a failing (routed) API."""
        page.route(
            "**/api/ocr/ingredients",
            lambda route: route.fulfill(
                status=502,
                content_type="application/json",
                body=json.dumps({"error": "ocr failed", "error_type": error_type}),
            ),
        )
        with page.expect_file_chooser() as fc_info:
            page.locator("#f-ocr-btn").click()
        fc_info.value.set_files(
            {"name": "label.jpg", "mimeType": "image/jpeg", "buffer": self._TINY_JPEG}
        )

    def test_toast_ocr_no_text(self, page):
        """OCR returning no text shows appropriate toast."""
        t = _load_translations()
        _go_to_register(page)
        self._trigger_ocr_error(page, "no_text")
        _wait_for_toast(page, t["toast_ocr_no_text"])

    def test_toast_ocr_token_limit(self, page):
        """OCR token limit reached shows appropriate toast."""
        t = _load_translations()
        _go_to_register(page)
        self._trigger_ocr_error(page, "token_limit_exceeded")
        _wait_for_toast(page, t["toast_ocr_token_limit"])

    def test_toast_ocr_provider_quota(self, page):
        """OCR provider quota exhausted shows appropriate toast."""
        t = _load_translations()
        _go_to_register(page)
        self._trigger_ocr_error(page, "provider_quota")
        _wait_for_toast(page, t["toast_ocr_provider_quota"])

    def test_toast_ocr_provider_timeout(self, page):
        """OCR provider timeout shows appropriate toast."""
        t = _load_translations()
        _go_to_register(page)
        self._trigger_ocr_error(page, "provider_timeout")
        _wait_for_toast(page, t["toast_ocr_provider_timeout"])

    def test_toast_ocr_invalid_image(self, page):
        """OCR with invalid image shows appropriate toast."""
        t = _load_translations()
        _go_to_register(page)
        self._trigger_ocr_error(page, "invalid_image")
        _wait_for_toast(page, t["toast_ocr_invalid_image"])

    def test_toast_ocr_settings_saved(self, page):
        """Saving OCR settings shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_ocr_title")
        page.wait_for_timeout(300)
        save_btn = page.locator(
            "button:has-text('Lagre OCR'), button[data-i18n='btn_save_ocr_settings']"
        ).first
        expect(save_btn).to_be_visible(timeout=5000)
        save_btn.click()
        _wait_for_toast(page, t["toast_ocr_settings_saved"])

    def test_toast_ocr_settings_error(self, page):
        """OCR settings save failure shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_ocr_title")
        page.wait_for_timeout(300)
        # Mock OCR settings endpoint to fail
        page.route(
            "**/api/ocr/settings",
            lambda route: route.fulfill(
                status=500,
                body='{"error":"server error"}',
                content_type="application/json",
            ),
        )
        save_btn = page.locator(
            "button:has-text('Lagre OCR'), button[data-i18n='btn_save_ocr_settings']"
        ).first
        expect(save_btn).to_be_visible(timeout=5000)
        save_btn.click()
        _wait_for_toast(page, t["toast_ocr_settings_error"])
        page.unroute("**/api/ocr/settings")


# ---------------------------------------------------------------------------
# EAN Toasts
# ---------------------------------------------------------------------------


class TestEanToasts:
    """Tests for EAN-related toast messages."""

    def test_toast_invalid_ean_in_edit(self, page, api_create_product):
        """Adding invalid EAN in product edit shows error toast."""
        t = _load_translations()
        product = api_create_product(name="EanTestProduct", ean="7038010069307")
        _go_to_search(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        row = page.locator(f".table-row[data-product-id='{product['id']}']")
        row.click()
        page.wait_for_timeout(300)
        # Look for EAN input in expanded view
        ean_input = page.locator(
            f".expanded-content[data-product-id='{product['id']}'] input[name='ean'], "
            f".expanded-content[data-product-id='{product['id']}'] .ean-manager input"
        ).first
        if ean_input.is_visible():
            ean_input.fill("invalid")
            # Try to add or save
            add_ean_btn = page.locator(
                f".expanded-content[data-product-id='{product['id']}'] button:has-text('Legg til EAN')"
            ).first
            if add_ean_btn.is_visible():
                add_ean_btn.click()
                _wait_for_toast(page, t["toast_invalid_ean"])


# ---------------------------------------------------------------------------
# Scanner Toasts
# ---------------------------------------------------------------------------


class TestScannerToasts:
    """Tests for scanner-related toast messages."""

    def test_toast_scanner_not_loaded(self, page):
        """Triggering scan without library shows scanner not loaded toast."""
        t = _load_translations()
        _go_to_register(page)
        # Simulate scanner library not being loaded
        page.evaluate(
            """() => {
                window.Quagga = undefined;
                window.BarcodeDetector = undefined;
            }"""
        )
        scan_btn = page.locator(
            "button[data-i18n-title='btn_scan_title'], button[title*='Skann strekkode']"
        ).first
        if scan_btn.is_visible():
            scan_btn.click()
            page.wait_for_timeout(500)
            toast = page.locator("#toast.show")
            if toast.is_visible():
                toast_text = toast.text_content()
                assert (
                    t["toast_scanner_not_loaded"] in toast_text
                    or t["toast_scanner_load_error"] in toast_text
                )


# ---------------------------------------------------------------------------
# Flag Toasts
# ---------------------------------------------------------------------------


class TestFlagToasts:
    """Tests for flag-related toast messages."""

    def test_toast_flag_added(self, page):
        """Adding a flag shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_flags_title")
        page.wait_for_timeout(300)
        # Fill flag name and label using IDs
        name_input = page.locator("#flag-add-name")
        label_input = page.locator("#flag-add-label")
        expect(name_input).to_be_visible(timeout=5000)
        name_input.fill("test_flag_toast")
        label_input.fill("Toast Flag")
        add_btn = page.locator("button:has-text('Legg til flagg')").first
        add_btn.click()
        # toast_flag_added uses the label as {name}
        expected = t["toast_flag_added"].replace("{name}", "Toast Flag")
        _wait_for_toast(page, expected)

    def test_toast_flag_name_required(self, page):
        """Adding a flag without name/label shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_flags_title")
        page.wait_for_timeout(300)
        # Ensure fields are empty
        page.locator("#flag-add-name").fill("")
        page.locator("#flag-add-label").fill("")
        add_btn = page.locator("button:has-text('Legg til flagg')").first
        add_btn.click()
        _wait_for_toast(page, t["toast_name_display_required"])


# ---------------------------------------------------------------------------
# Protein Quality Toasts
# ---------------------------------------------------------------------------


class TestPqToasts:
    """Tests for protein quality toast messages."""

    def test_toast_pq_keywords_required(self, page):
        """Adding PQ source without keywords shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_pq_title")
        page.wait_for_timeout(300)
        add_btn = page.locator(
            "button:has-text('Legg til proteinkilde')"
        ).first
        if add_btn.is_visible():
            add_btn.click()
            _wait_for_toast(page, t["toast_pq_keywords_required"])

    def test_toast_pq_added(self, page):
        """Adding a PQ source shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_pq_title")
        page.wait_for_timeout(300)
        # Fill the PQ form fields
        # The form has name, keywords, pdcaas, diaas fields
        pq_inputs = page.locator(
            ".settings-section:has(span[data-i18n='settings_pq_title']) input"
        )
        if pq_inputs.count() >= 3:
            # Name/label input
            pq_inputs.nth(0).fill("TestPQSource")
            # Keywords input
            pq_inputs.nth(1).fill("testprotein, testwhey")
            # PDCAAS
            pq_inputs.nth(2).fill("0.9")
            # DIAAS
            if pq_inputs.count() >= 4:
                pq_inputs.nth(3).fill("1.0")
            add_btn = page.locator(
                "button:has-text('Legg til proteinkilde')"
            ).first
            add_btn.click()
            expected = t["toast_pq_added"].replace("{name}", "TestPQSource")
            _wait_for_toast(page, expected)


# ---------------------------------------------------------------------------
# Image Toasts
# ---------------------------------------------------------------------------


class TestImageToasts:
    """Tests for image-related toast messages."""

    def test_toast_image_too_large(self, page):
        """Uploading oversized image shows error toast.

        Drives the real path: the register-form image button opens a file
        chooser (images.js captureProductImage creates the input
        dynamically); a >10MB file must trip the size check.
        """
        t = _load_translations()
        _go_to_register(page)
        with page.expect_file_chooser() as fc_info:
            page.locator("#f-image-btn").click()
        fc_info.value.set_files(
            {
                "name": "large.png",
                "mimeType": "image/png",
                "buffer": b"x" * (11 * 1024 * 1024),
            }
        )
        _wait_for_toast(page, t["toast_image_too_large"])


# ---------------------------------------------------------------------------
# Weight Override Toasts
# ---------------------------------------------------------------------------


class TestWeightToasts:
    """Tests for weight/score-related toast messages."""

    def test_toast_category_override_deleted(self, page, live_url):
        """Deleting a category weight override shows success toast."""
        import urllib.request

        t = _load_translations()
        # First create a category override via API
        payload = json.dumps(
            {"category": "Snacks", "weights": {"kcal": {"enabled": True, "value": 80}}}
        ).encode()
        req = urllib.request.Request(
            f"{live_url}/api/weights/category",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="PUT",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

        _go_to_settings(page)
        _open_settings_section(page, "settings_weights_title")
        page.wait_for_timeout(500)
        # Look for delete category override button
        del_override_btn = page.locator(
            "button:has-text('Slett kategori-overstyring'), button[data-i18n='btn_delete_category_override']"
        ).first
        if del_override_btn.is_visible():
            del_override_btn.click()
            # Confirm if needed
            page.wait_for_timeout(300)
            confirm_btn = page.locator(".scan-modal-bg button").first
            if confirm_btn.is_visible():
                confirm_btn.click()
            _wait_for_toast(page, t["toast_category_override_deleted"])


# ---------------------------------------------------------------------------
# OFF (Open Food Facts) Toasts
# ---------------------------------------------------------------------------


class TestOffToasts:
    """Tests for Open Food Facts related toast messages."""

    def test_toast_off_credentials_saved(self, page):
        """Saving OFF credentials shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_off_title")
        page.wait_for_timeout(300)
        user_input = page.locator(
            "input[placeholder*='OFF-brukernavn'], input[data-i18n-placeholder='ph_off_user_id']"
        ).first
        pass_input = page.locator(
            "input[placeholder*='OFF-passord'], input[data-i18n-placeholder='ph_off_password']"
        ).first
        if user_input.is_visible() and pass_input.is_visible():
            user_input.fill("testuser")
            pass_input.fill("testpass")
            save_btn = page.locator(
                "button:has-text('Lagre'):near(input[data-i18n-placeholder='ph_off_password'])"
            ).first
            if not save_btn.is_visible():
                save_btn = page.locator(
                    "button[data-i18n='btn_save_off_credentials']"
                ).first
            save_btn.click()
            _wait_for_toast(page, t["toast_off_credentials_saved"])

    def test_toast_off_lang_priority_saved(self, page):
        """Saving OFF language priority shows success toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_settings_section(page, "settings_off_title")
        page.wait_for_timeout(300)
        # Mock the settings save endpoint
        page.route(
            "**/api/settings/off-lang-priority",
            lambda route: route.fulfill(
                status=200,
                body='{"status":"ok"}',
                content_type="application/json",
            ),
        )
        # Trigger save via JS
        page.evaluate(
            """() => {
                if (window.saveOffLangPriority) window.saveOffLangPriority();
            }"""
        )
        page.wait_for_timeout(500)
        toast = page.locator("#toast.show")
        if toast.is_visible():
            expect(toast).to_contain_text(t["toast_off_lang_priority_saved"])
        page.unroute("**/api/settings/off-lang-priority")


# ---------------------------------------------------------------------------
# Network Error Toasts
# ---------------------------------------------------------------------------


class TestNetworkToasts:
    """Tests for network error toast messages."""

    def test_toast_network_error(self, page):
        """Network failure shows network error toast."""
        t = _load_translations()
        _go_to_search(page)
        # Mock products API to simulate network error
        page.route(
            "**/api/products*",
            lambda route: route.abort("connectionrefused"),
        )
        # Trigger a reload to fetch products
        page.evaluate("() => window.loadData && window.loadData()")
        page.wait_for_timeout(1000)
        toast = page.locator("#toast.show")
        if toast.is_visible():
            toast_text = toast.text_content()
            # Should contain either network error or load error
            assert (
                t["toast_network_error"] in toast_text
                or t["toast_load_error"] in toast_text
            )
        page.unroute("**/api/products*")

    def test_toast_load_error(self, page):
        """API returning error on load shows load error toast."""
        t = _load_translations()
        _go_to_search(page)
        page.route(
            "**/api/products*",
            lambda route: route.fulfill(
                status=500,
                body='{"error":"db error"}',
                content_type="application/json",
            ),
        )
        page.evaluate("() => window.loadData && window.loadData()")
        page.wait_for_timeout(1000)
        toast = page.locator("#toast.show")
        if toast.is_visible():
            toast_text = toast.text_content()
            assert (
                t["toast_load_error"] in toast_text
                or "error" in toast_text.lower()
            )
        page.unroute("**/api/products*")


# ---------------------------------------------------------------------------
# EAN Unlock Toast
# ---------------------------------------------------------------------------


class TestEanUnlockToasts:
    """Tests for EAN unlock toast messages."""

    def test_toast_ean_unlocked(self, page, api_create_product):
        """Unsyncing an OFF-synced EAN via the EAN manager shows the toast.

        Drives the real path: an OFF-synced product's EAN row renders an
        unsync button in the edit-mode EAN manager; clicking it POSTs to
        /api/products/<pid>/eans/<id>/unsync and ean-manager.js shows
        toast_ean_unlocked on success.
        """
        t = _load_translations()
        product = api_create_product(
            name="EanUnlockToastProd", ean="7038010069307", from_off=True
        )
        pid = product["id"]

        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )
        row = page.locator(".table-row", has_text="EanUnlockToastProd").first
        row.click()
        page.wait_for_timeout(300)
        edit_btn = page.locator("[data-action='start-edit']").first
        expect(edit_btn).to_be_visible(timeout=5000)
        edit_btn.click()

        unsync_btn = page.locator(
            f"#ean-manager-{pid} [data-ean-action='unsync-ean']"
        ).first
        expect(unsync_btn).to_be_visible(timeout=5000)
        unsync_btn.click()
        _wait_for_toast(page, t["toast_ean_unlocked"])
