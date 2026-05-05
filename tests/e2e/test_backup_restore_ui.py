"""E2E tests for backup restore UI — file upload and drop zone (P0 gap #3).

Tests the browser-based backup/restore flow including the drag-and-drop zone,
file picker, confirmation modal, and the resulting data state after restore.

The restore flow:
1. User clicks the drop zone (or #restore-file input).
2. A confirmation modal appears.
3. On confirm, the file is read and POST /api/restore is called.
4. A success toast is shown and the product list refreshes.

We use page.route() to intercept /api/restore so the test is hermetic and
does not mutate the shared e2e database.  For the UI element visibility tests
we simply navigate to the settings section.
"""

import json
import tempfile
import os
import urllib.request

from playwright.sync_api import expect, Route, Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    """Navigate to the settings view and wait for the content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_database_section(page):
    """Open the collapsible database/backup section in settings."""
    toggle = page.locator(
        ".settings-toggle:has(span[data-i18n='settings_database_title'])"
    ).first
    toggle.click()
    page.wait_for_timeout(400)


def _reload_and_wait(page):
    """Reload the page and wait for the initial product list to settle."""
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _get_backup_json(live_url: str) -> dict:
    """Fetch a backup snapshot from the live server API."""
    req = urllib.request.Request(
        f"{live_url}/api/backup",
        headers={"X-API-Key": "e2e-testing-secret"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _write_temp_json(data: dict) -> str:
    """Serialise *data* to a temporary JSON file and return the path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as fh:
        json.dump(data, fh)
        return fh.name


# ---------------------------------------------------------------------------
# Visibility / structural tests
# ---------------------------------------------------------------------------


def test_backup_section_visible_in_settings(page):
    """The database/backup section should be reachable in settings."""
    _go_to_settings(page)
    _open_database_section(page)

    download_btn = page.locator("[data-i18n='btn_download_backup']").first
    expect(download_btn).to_be_visible(timeout=3000)


def test_restore_drop_zone_visible(page):
    """The #restore-drop drop zone should be visible in the database section."""
    _go_to_settings(page)
    _open_database_section(page)

    drop_zone = page.locator("#restore-drop")
    expect(drop_zone).to_be_visible(timeout=3000)


def test_restore_warning_text_visible(page):
    """A restore warning element should be displayed near the drop zone."""
    _go_to_settings(page)
    _open_database_section(page)

    # The warning may use either a class or a data-i18n attribute
    warning = page.locator(
        ".restore-warning, [data-i18n='restore_warning']"
    ).first
    expect(warning).to_be_visible(timeout=3000)


def test_import_button_visible(page):
    """The import button should be visible in the database settings section."""
    _go_to_settings(page)
    _open_database_section(page)

    import_btn = page.locator("[data-i18n='btn_import']").first
    expect(import_btn).to_be_visible(timeout=3000)


def test_backup_download_button_enabled(page):
    """The download backup button should be present and enabled."""
    _go_to_settings(page)
    _open_database_section(page)

    download_btn = page.locator("[data-i18n='btn_download_backup']").first
    expect(download_btn).to_be_visible(timeout=3000)
    expect(download_btn).to_be_enabled()


def test_backup_note_text_visible(page):
    """The backup explanation note should be displayed in the section."""
    _go_to_settings(page)
    _open_database_section(page)

    note = page.locator("[data-i18n='backup_note']").first
    expect(note).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Restore flow test
# ---------------------------------------------------------------------------


def test_restore_via_file_input_shows_confirm_modal(page, live_url, api_create_product):
    """Selecting a backup file via the restore input should open a confirm modal."""
    api_create_product(name="RestoreConfirmUITest")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _write_temp_json(backup_data)
    try:
        # The drop zone click triggers document.getElementById('restore-file').click()
        # which opens a file chooser we can intercept.
        with page.expect_file_chooser(timeout=5000) as fc_info:
            page.locator("#restore-drop").click()

        file_chooser = fc_info.value
        file_chooser.set_files(tmp_path)
        page.wait_for_timeout(500)

        # The JS reads the file and immediately shows a confirmation modal
        confirm_modal = page.locator(".scan-modal-bg[role='dialog']")
        expect(confirm_modal).to_be_visible(timeout=5000)

        # The modal must contain a confirmation button
        confirm_btn = page.locator(".confirm-yes")
        expect(confirm_btn).to_be_visible(timeout=3000)
    finally:
        os.unlink(tmp_path)


def test_restore_cancel_does_not_restore(page, live_url, api_create_product):
    """Cancelling the restore confirmation modal must leave the DB unchanged."""
    api_create_product(name="RestoreCancelUITest")
    backup_data = _get_backup_json(live_url)

    # Add a second product after the snapshot
    api_create_product(name="RestoreCancelShouldRemain")

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _write_temp_json(backup_data)
    try:
        with page.expect_file_chooser(timeout=5000) as fc_info:
            page.locator("#restore-drop").click()

        fc_info.value.set_files(tmp_path)
        page.wait_for_timeout(500)

        confirm_modal = page.locator(".scan-modal-bg[role='dialog']")
        expect(confirm_modal).to_be_visible(timeout=5000)

        # Cancel instead of confirming
        cancel_btn = page.locator(".confirm-no")
        expect(cancel_btn).to_be_visible(timeout=3000)
        cancel_btn.click()
        page.wait_for_timeout(500)

        # Modal must close and no restore occurred
        expect(confirm_modal).to_be_hidden(timeout=3000)

        # The product added after the snapshot must still be present
        page.locator("button[data-view='search']").click()
        _reload_and_wait(page)
        expect(page.locator("#results-container")).to_contain_text(
            "RestoreCancelShouldRemain"
        )
    finally:
        os.unlink(tmp_path)


def test_restore_via_file_input_calls_api_and_shows_toast(
    page, live_url, api_create_product
):
    """Confirming restore should POST to /api/restore and show a success toast."""
    api_create_product(name="RestoreAPICallTest")
    backup_data = _get_backup_json(live_url)

    # Intercept /api/restore with a mocked success response so we don't
    # mutate the shared session database.
    restore_called = []

    def _handle_restore(route: Route, request: Request) -> None:
        restore_called.append(request.post_data)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"message": "Restore successful"}),
        )

    page.route("**/api/restore", _handle_restore)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _write_temp_json(backup_data)
    try:
        with page.expect_file_chooser(timeout=5000) as fc_info:
            page.locator("#restore-drop").click()

        fc_info.value.set_files(tmp_path)
        page.wait_for_timeout(500)

        # Confirm the restore
        confirm_btn = page.locator(".confirm-yes")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()

        # The API must have been called
        page.wait_for_timeout(1000)
        assert len(restore_called) == 1, (
            "Expected exactly one POST to /api/restore after confirming restore"
        )

        # A success toast should appear
        toast = page.locator(".toast.show")
        expect(toast).to_be_visible(timeout=5000)
    finally:
        os.unlink(tmp_path)
        page.unroute("**/api/restore")
