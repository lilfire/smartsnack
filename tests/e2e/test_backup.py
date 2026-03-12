"""Test backup and restore functionality."""

from playwright.sync_api import expect


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_database_section(page):
    """Open the database section in settings."""
    _go_to_settings(page)
    db_toggle = page.locator(
        ".settings-toggle:has(span[data-i18n='settings_database_title'])"
    ).first
    db_toggle.click()
    page.wait_for_timeout(300)


def test_download_backup_button_exists(page):
    """The download backup button should be present."""
    _open_database_section(page)
    btn = page.locator("button[data-i18n='btn_download_backup']")
    expect(btn).to_be_visible()


def test_import_button_exists(page):
    """The import (merge) button should be present."""
    _open_database_section(page)
    btn = page.locator("button[data-i18n='btn_import']")
    expect(btn).to_be_visible()


def test_restore_drop_zone_exists(page):
    """The file drop zone for restore should be present."""
    _open_database_section(page)
    drop = page.locator("#restore-drop")
    expect(drop).to_be_visible()


def test_download_backup_triggers_download(page):
    """Clicking download backup should initiate a file download."""
    _open_database_section(page)

    with page.expect_download(timeout=10000) as download_info:
        page.locator("button[data-i18n='btn_download_backup']").click()

    download = download_info.value
    assert download.suggested_filename.endswith(".json")
