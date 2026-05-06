"""Browser-based e2e tests for Settings UI panels.

Covers OFF language priority, OFF credentials, OCR settings,
and general settings interactions via the browser.
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _go_to_settings(page):
    """Navigate to settings view and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    """Open a settings section by its data-i18n key."""
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


def _api_put(live_url, path, payload):
    """PUT JSON to the API."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ===========================================================================
# OFF Language Priority — Browser UI tests
# ===========================================================================


class TestOffLanguagePriorityBrowser:
    """Test OFF language priority management in the settings UI."""

    def test_off_section_shows_language_priority(self, page):
        """The OFF section should display the language priority list."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        expect(page.locator("#off-lang-priority-list")).to_be_visible()
        expect(page.locator("#off-lang-add-select")).to_be_visible()
        expect(page.locator("#off-lang-add-btn")).to_be_visible()

    def test_add_language_to_priority(self, page, live_url):
        """Adding a language via the UI should update the priority list."""
        # Reset to known state
        _api_put(live_url, "/api/settings/off-language-priority", {"priority": ["no"]})

        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        # The add-select dropdown should have options
        add_select = page.locator("#off-lang-add-select")
        expect(add_select).to_be_visible()

        # Select 'en' from the dropdown and click add
        add_select.select_option("en")
        page.locator("#off-lang-add-btn").click()

        # Wait for the list to update
        page.wait_for_timeout(500)

        # Verify 'en' now appears in the priority list
        priority_list = page.locator("#off-lang-priority-list")
        expect(priority_list).to_contain_text("en")

    def test_remove_language_from_priority(self, page, live_url):
        """Removing a language via the UI should update the priority list."""
        # Set up two languages
        _api_put(live_url, "/api/settings/off-language-priority",
                 {"priority": ["no", "en"]})

        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        priority_list = page.locator("#off-lang-priority-list")
        expect(priority_list).to_contain_text("en")

        # Click the remove button for 'en'
        remove_btn = priority_list.locator("button[aria-label*='en']").first
        if remove_btn.is_visible():
            remove_btn.click()
            page.wait_for_timeout(500)
            expect(priority_list).not_to_contain_text("en")

    def test_language_priority_persists_after_reload(self, page, live_url):
        """Language priority should persist after page reload."""
        _api_put(live_url, "/api/settings/off-language-priority",
                 {"priority": ["de", "fr"]})

        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        priority_list = page.locator("#off-lang-priority-list")
        expect(priority_list).to_contain_text("de")
        expect(priority_list).to_contain_text("fr")

        # Reload page and verify persistence
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)

        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        priority_list = page.locator("#off-lang-priority-list")
        expect(priority_list).to_contain_text("de")
        expect(priority_list).to_contain_text("fr")


# ===========================================================================
# OFF Credentials — Browser UI tests
# ===========================================================================


class TestOffCredentialsBrowser:
    """Test OFF credentials form in the settings UI."""

    def test_credentials_form_visible(self, page):
        """The OFF section should show username and password fields."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        expect(page.locator("#off-user-id")).to_be_visible()
        expect(page.locator("#off-password")).to_be_visible()

    def test_save_credentials(self, page):
        """Saving OFF credentials should show a toast notification."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#off-user-id").fill("test-user")
        page.locator("#off-password").fill("test-pass")
        page.locator("button[data-i18n='btn_save_off_credentials']").click()

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_credentials_persist_after_reload(self, page):
        """After saving credentials and reloading, the username should persist."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#off-user-id").fill("persist-user")
        page.locator("#off-password").fill("persist-pass")
        page.locator("button[data-i18n='btn_save_off_credentials']").click()
        page.wait_for_timeout(500)

        # Reload
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)

        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        expect(page.locator("#off-user-id")).to_have_value("persist-user")


# ===========================================================================
# OCR Settings — Browser UI tests
# ===========================================================================


class TestOcrSettingsBrowser:
    """Test OCR settings panel in the browser."""

    def test_ocr_section_shows_provider_select(self, page):
        """The OCR section should show the provider dropdown."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        expect(page.locator("#ocr-provider-select")).to_be_visible()

    def test_tesseract_is_default_provider(self, page):
        """Tesseract should be the default OCR provider."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        provider = page.locator("#ocr-provider-select")
        expect(provider).to_have_value("tesseract")

    def test_save_ocr_settings(self, page):
        """Saving OCR settings should show a toast notification."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")

        page.locator("button[data-i18n='btn_save_ocr_settings']").click()

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_fallback_checkbox_visible(self, page):
        """The fallback checkbox should be visible in the OCR section."""
        _go_to_settings(page)
        _open_section(page, "settings_ocr_title")
        expect(page.locator("#ocr-fallback-checkbox")).to_be_visible()


# ===========================================================================
# Bulk Refresh OFF — Browser UI tests
# ===========================================================================


class TestBulkRefreshBrowser:
    """Test bulk refresh OFF button in the settings UI."""

    def test_refresh_button_visible(self, page):
        """The refresh-all-from-OFF button should be visible in settings."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        expect(page.locator("#btn-refresh-all-off")).to_be_visible()

    def test_refresh_button_starts_progress(self, page):
        """Clicking refresh should show the progress area."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#btn-refresh-all-off").click()
        page.locator("button.confirm-yes").click()
        # Progress container should become visible
        progress = page.locator("#refresh-off-progress")
        expect(progress).to_be_visible(timeout=5000)


# ===========================================================================
# PQ Estimate All — Browser UI tests
# ===========================================================================


class TestPqEstimateBrowser:
    """Test bulk PQ estimation button in the settings UI."""

    def test_estimate_button_visible(self, page):
        """The estimate-all-PQ button should be visible."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        expect(page.locator("#btn-estimate-all-pq")).to_be_visible()

    def test_estimate_shows_status(self, page, api_create_product):
        """Clicking estimate should show status feedback."""
        # Create a product with ingredients for PQ estimation
        api_create_product(
            name="PQ Browser Test",
            ingredients="milk, whey protein, oats",
        )

        _go_to_settings(page)
        _open_section(page, "settings_pq_title")

        page.locator("#btn-estimate-all-pq").click()
        # Status element should become visible
        status = page.locator("#estimate-pq-status")
        expect(status).to_be_visible(timeout=10000)
