"""E2E tests for import with duplicate resolution modal (P0 gap #4).

Tests the import flow including:
- File selection via the #import-file hidden input
- Appearance of the duplicate resolution modal (.scan-modal.import-dup-modal)
- Match criteria radio options (ean / name / both)
- Duplicate action radio options (skip / overwrite / merge / allow_duplicate)
- Cancel closes the modal without importing
- Starting an import with 'skip' calls /api/import and shows a success toast

All assertions use expect() and are unconditional.
File selection uses page.expect_file_chooser() + file_chooser.set_files().
"""

import json
import os
import tempfile
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


def _open_import_modal(page, backup_data: dict) -> str:
    """Select a backup file for import and wait for the modal to appear.

    Returns the path to the temporary file (caller must delete it).
    """
    tmp_path = _write_temp_json(backup_data)

    # The import button triggers document.getElementById('import-file').click()
    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator("[data-i18n='btn_import']").first.click()

    fc_info.value.set_files(tmp_path)
    page.wait_for_timeout(600)

    # The import duplicate resolution modal must appear
    modal = page.locator(".scan-modal.import-dup-modal")
    expect(modal).to_be_visible(timeout=5000)

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_import_modal_opens_on_file_select(page, live_url, api_create_product):
    """Selecting an import file should show the duplicate resolution modal."""
    api_create_product(name="ImportModalTestProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")
        expect(modal).to_be_visible(timeout=5000)
    finally:
        os.unlink(tmp_path)


def test_import_modal_has_match_criteria_radios(page, live_url, api_create_product):
    """The import modal must have match criteria radio buttons (ean/name/both)."""
    api_create_product(name="ImportMatchProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")

        # All three match-criteria radio inputs must be present
        ean_radio = modal.locator("input[name='match_criteria'][value='ean']")
        name_radio = modal.locator("input[name='match_criteria'][value='name']")
        both_radio = modal.locator("input[name='match_criteria'][value='both']")

        expect(ean_radio).to_be_attached()
        expect(name_radio).to_be_attached()
        expect(both_radio).to_be_attached()

        # 'both' should be the default selection
        expect(both_radio).to_be_checked()
    finally:
        os.unlink(tmp_path)


def test_import_modal_has_duplicate_action_radios(
    page, live_url, api_create_product
):
    """The import modal must have all four on_duplicate radio options."""
    api_create_product(name="ImportActionProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")

        for value in ("skip", "overwrite", "merge", "allow_duplicate"):
            radio = modal.locator(f"input[name='on_duplicate'][value='{value}']")
            expect(radio).to_be_attached()

        # 'skip' should be the default selection
        skip_radio = modal.locator("input[name='on_duplicate'][value='skip']")
        expect(skip_radio).to_be_checked()
    finally:
        os.unlink(tmp_path)


def test_import_modal_has_start_button(page, live_url, api_create_product):
    """The import modal must have a start/confirm import button."""
    api_create_product(name="ImportStartBtnProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")
        start_btn = modal.locator("button.scan-modal-btn-register")
        expect(start_btn).to_be_visible(timeout=3000)
        expect(start_btn).to_be_enabled()
    finally:
        os.unlink(tmp_path)


def test_import_modal_cancel_closes(page, live_url, api_create_product):
    """Clicking the cancel button in the import modal must close it."""
    api_create_product(name="ImportCancelProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")
        expect(modal).to_be_visible(timeout=5000)

        cancel_btn = modal.locator("button.scan-modal-btn-cancel")
        expect(cancel_btn).to_be_visible(timeout=3000)
        cancel_btn.click()

        page.wait_for_timeout(400)
        expect(modal).to_be_hidden(timeout=3000)
    finally:
        os.unlink(tmp_path)


def test_import_skip_calls_api_and_shows_toast(page, live_url, api_create_product):
    """Importing with 'skip' should POST to /api/import and show a success toast."""
    api_create_product(name="ImportSkipProd")
    backup_data = _get_backup_json(live_url)

    # Intercept the import API to avoid mutating the shared DB
    import_calls: list[dict] = []

    def _handle_import(route: Route, request: Request) -> None:
        body = json.loads(request.post_data or "{}")
        import_calls.append(body)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {"message": "Import complete: 1 added, 0 skipped, 0 updated"}
            ),
        )

    page.route("**/api/import", _handle_import)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")

        # Ensure 'skip' is selected (it is the default, but be explicit)
        skip_radio = modal.locator("input[name='on_duplicate'][value='skip']")
        skip_radio.check()
        expect(skip_radio).to_be_checked()

        # Click the start button
        start_btn = modal.locator("button.scan-modal-btn-register")
        expect(start_btn).to_be_visible(timeout=3000)
        start_btn.click()

        # The API must be called
        page.wait_for_timeout(1000)
        assert len(import_calls) == 1, (
            f"Expected one POST to /api/import, got {len(import_calls)}"
        )
        assert import_calls[0].get("on_duplicate") == "skip", (
            f"Expected on_duplicate='skip' in POST body, got: {import_calls[0]}"
        )

        # A success toast must appear
        toast = page.locator(".toast.show")
        expect(toast).to_be_visible(timeout=5000)
    finally:
        os.unlink(tmp_path)
        page.unroute("**/api/import")


def test_import_merge_shows_merge_rules_section(page, live_url, api_create_product):
    """Selecting 'merge' in the import modal should reveal the merge rules section."""
    api_create_product(name="ImportMergeProd")
    backup_data = _get_backup_json(live_url)

    _go_to_settings(page)
    _open_database_section(page)

    tmp_path = _open_import_modal(page, backup_data)
    try:
        modal = page.locator(".scan-modal.import-dup-modal")

        merge_radio = modal.locator("input[name='on_duplicate'][value='merge']")
        merge_radio.check()
        page.wait_for_timeout(300)

        # The merge rules section should become visible
        merge_section = modal.locator(".import-dup-merge-rules")
        expect(merge_section).to_be_visible(timeout=3000)

        # The merge priority radios should also appear
        keep_radio = modal.locator("input[name='merge_priority'][value='keep_existing']")
        use_radio = modal.locator("input[name='merge_priority'][value='use_imported']")
        expect(keep_radio).to_be_attached()
        expect(use_radio).to_be_attached()
    finally:
        os.unlink(tmp_path)
