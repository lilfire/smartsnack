"""Task 4: Backup/Restore error paths.

Tests error toasts for restore with invalid files, malformed JSON,
server 500 errors, and success path for backup download.
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


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_database_section(page):
    toggle = page.locator(
        ".settings-toggle:has(span[data-i18n='settings_database_title'])"
    ).first
    toggle.click()
    page.wait_for_timeout(300)


class TestRestoreErrors:
    """Error paths for the restore flow."""

    def test_restore_non_json_file(self, page):
        """Restoring a non-JSON file shows toast_invalid_file."""
        t = _load_translations()
        _go_to_settings(page)
        _open_database_section(page)

        # Set a plain text file on the hidden restore input
        page.locator("#restore-file").set_input_files(
            {
                "name": "bad.txt",
                "mimeType": "text/plain",
                "buffer": b"this is not json at all",
            }
        )

        # The confirm modal should appear — confirm the restore
        confirm_btn = page.locator(".confirm-yes")
        if confirm_btn.is_visible(timeout=3000):
            confirm_btn.click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_invalid_file"])

    def test_restore_malformed_json(self, page):
        """Restoring valid JSON with wrong schema shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_database_section(page)

        # Valid JSON but wrong schema (no products key)
        malformed = json.dumps({"wrong_key": "value"}).encode()
        page.locator("#restore-file").set_input_files(
            {
                "name": "bad.json",
                "mimeType": "application/json",
                "buffer": malformed,
            }
        )

        # Confirm the restore
        confirm_btn = page.locator(".confirm-yes")
        if confirm_btn.is_visible(timeout=3000):
            confirm_btn.click()

        # Should show an error toast (server returns error for bad schema)
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        # The error message comes from the server — just verify a toast appeared
        # with some text content (not empty)
        toast_text = toast.text_content()
        assert len(toast_text.strip()) > 0, "Error toast should contain a message"

    def test_restore_server_500(self, page):
        """Mock restore endpoint returning 500 shows error toast."""
        t = _load_translations()
        _go_to_settings(page)
        _open_database_section(page)

        # Mock the restore endpoint to return 500
        page.route(
            "**/api/restore",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": "Restore failed"}),
            ),
        )

        # Provide valid-looking JSON
        backup = json.dumps({"products": [], "categories": []}).encode()
        page.locator("#restore-file").set_input_files(
            {
                "name": "backup.json",
                "mimeType": "application/json",
                "buffer": backup,
            }
        )

        # Confirm the restore
        confirm_btn = page.locator(".confirm-yes")
        if confirm_btn.is_visible(timeout=3000):
            confirm_btn.click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        toast_text = toast.text_content()
        assert len(toast_text.strip()) > 0, "Error toast should contain a message"

        # Clean up route
        page.unroute("**/api/restore")


class TestBackupDownloadSuccess:
    """Success path for backup download."""

    def test_backup_download_shows_toast(self, page):
        """Clicking download backup shows toast_backup_downloaded."""
        t = _load_translations()
        _go_to_settings(page)
        _open_database_section(page)

        # The download redirects via location.href, mock the endpoint
        page.route(
            "**/api/backup**",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                headers={"Content-Disposition": "attachment; filename=backup.json"},
                body=json.dumps({"products": [], "categories": []}),
            ),
        )

        # Click download button — the toast fires immediately before the download
        download_btn = page.locator("button[data-i18n='btn_download_backup']")
        download_btn.click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_backup_downloaded"])

        page.unroute("**/api/backup**")
