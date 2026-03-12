"""Test the settings view sections."""

from playwright.sync_api import expect


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    """Open a settings section by its data-i18n key."""
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


def test_settings_loads(page):
    """Settings view should load and show its content."""
    _go_to_settings(page)
    expect(page.locator("#settings-content")).to_be_visible()


def test_weight_section_toggle(page):
    """Clicking the weights section header should expand it."""
    _go_to_settings(page)
    _open_section(page, "settings_weights_title")
    expect(page.locator("#weight-items")).to_be_visible()


def test_category_section_toggle(page):
    """Clicking the categories section header should expand it."""
    _go_to_settings(page)
    _open_section(page, "settings_categories_title")
    expect(page.locator("#cat-list")).to_be_visible()


def test_add_category(page):
    """Adding a new category should work."""
    _go_to_settings(page)
    _open_section(page, "settings_categories_title")

    page.locator("#cat-name").fill("e2ecat")
    page.locator("#cat-label").fill("E2E Category")

    page.locator("button[data-i18n='btn_add_category']").first.click()

    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_flags_section_toggle(page):
    """Clicking the flags section header should expand it."""
    _go_to_settings(page)
    _open_section(page, "settings_flags_title")
    expect(page.locator("#flag-list")).to_be_visible()


def test_add_flag(page):
    """Adding a new flag should work."""
    _go_to_settings(page)
    _open_section(page, "settings_flags_title")

    page.locator("#flag-add-name").fill("e2e_flag")
    page.locator("#flag-add-label").fill("E2E Flag")

    page.locator("button[data-i18n='btn_add_flag']").first.click()

    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_protein_quality_section_toggle(page):
    """Clicking the PQ section header should expand it."""
    _go_to_settings(page)
    _open_section(page, "settings_pq_title")
    expect(page.locator("#pq-list")).to_be_visible()


def test_database_section_toggle(page):
    """Clicking the database section header should expand it."""
    _go_to_settings(page)
    _open_section(page, "settings_database_title")
    expect(page.locator("button[data-i18n='btn_download_backup']")).to_be_visible()
