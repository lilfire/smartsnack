"""Browser-based e2e tests for bulk operations UI.

Covers the bulk OFF refresh and bulk PQ estimation
buttons in the settings panel.
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


# ===========================================================================
# Bulk Refresh OFF — Browser UI tests
# ===========================================================================


class TestBulkRefreshOffBrowser:
    """Test the bulk OFF refresh from the settings UI."""

    def test_refresh_button_exists(self, page):
        """The refresh-all-from-OFF button should be in the OFF settings."""
        _go_to_settings(page)
        _open_section(page, "settings_off_title")
        btn = page.locator("#btn-refresh-all-off")
        expect(btn).to_be_visible()

    def test_refresh_shows_progress_bar(self, page, api_create_product):
        """Clicking refresh should display the progress indicator."""
        api_create_product(name="BulkRefreshProd", ean="9900000000011")

        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#btn-refresh-all-off").click()
        # Confirm the refresh options modal (button.confirm-yes = "Start" button)
        page.locator("button.confirm-yes").click()

        progress = page.locator("#refresh-off-progress")
        expect(progress).to_be_visible(timeout=5000)

    def test_refresh_shows_status_text(self, page, api_create_product):
        """During/after refresh, a status message should appear."""
        api_create_product(name="BulkStatusProd", ean="9900000000012")

        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#btn-refresh-all-off").click()
        # Confirm the refresh options modal
        page.locator("button.confirm-yes").click()
        status = page.locator("#refresh-off-status")
        expect(status).to_be_visible(timeout=10000)

    def test_progress_bar_fills(self, page, api_create_product):
        """The progress bar should fill during refresh."""
        api_create_product(name="BulkBarProd", ean="9900000000013")

        _go_to_settings(page)
        _open_section(page, "settings_off_title")

        page.locator("#btn-refresh-all-off").click()
        # Confirm the refresh options modal
        page.locator("button.confirm-yes").click()
        bar = page.locator("#refresh-off-bar")

        # Wait for bar to have some width (indicating progress started or completed)
        page.wait_for_function(
            """() => {
                const bar = document.getElementById('refresh-off-bar');
                return bar && bar.style.width && bar.style.width !== '0%';
            }""",
            timeout=30000,
        )


# ===========================================================================
# Bulk PQ Estimate — Browser UI tests
# ===========================================================================


class TestBulkPqEstimateBrowser:
    """Test the bulk PQ estimation from the settings UI."""

    def test_estimate_button_exists(self, page):
        """The estimate-all-PQ button should be in the PQ settings."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        btn = page.locator("#btn-estimate-all-pq")
        expect(btn).to_be_visible()

    def test_estimate_triggers_status(self, page, api_create_product):
        """Clicking estimate should show a status message."""
        api_create_product(
            name="PqEstimateBulk",
            ingredients="milk, whey protein, oats, soy",
        )

        _go_to_settings(page)
        _open_section(page, "settings_pq_title")

        page.locator("#btn-estimate-all-pq").click()
        status = page.locator("#estimate-pq-status")
        expect(status).to_be_visible(timeout=10000)
