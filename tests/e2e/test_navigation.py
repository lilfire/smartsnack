"""Test navigation between the three main views."""

import re

from playwright.sync_api import expect


def test_search_view_is_default(page):
    """Search view should be visible by default."""
    search = page.locator("#view-search")
    expect(search).to_be_visible()
    expect(page.locator("#view-register")).to_be_hidden()
    expect(page.locator("#view-settings")).to_be_hidden()


def test_switch_to_register_view(page):
    """Clicking the Register tab shows the register form."""
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()
    expect(page.locator("#view-search")).to_be_hidden()
    # Register tab should be active
    expect(page.locator("button[data-view='register']")).to_have_class(
        re.compile("active")
    )


def test_switch_to_settings_view(page):
    """Clicking the Settings tab shows the settings view."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    expect(page.locator("#view-search")).to_be_hidden()


def test_switch_back_to_search(page):
    """Switching away and back to search works correctly."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()

    page.locator("button[data-view='search']").click()
    expect(page.locator("#view-search")).to_be_visible()
    expect(page.locator("#view-settings")).to_be_hidden()


def test_nav_tabs_highlight_active(page):
    """Only the active nav tab should have the 'active' class."""
    # Search is active by default
    expect(page.locator("button[data-view='search']")).to_have_class(
        re.compile("active")
    )

    # Switch to register
    page.locator("button[data-view='register']").click()
    expect(page.locator("button[data-view='register']")).to_have_class(
        re.compile("active")
    )
    expect(page.locator("button[data-view='search']")).not_to_have_class(
        re.compile("active")
    )

    # Switch to settings
    page.locator("button[data-view='settings']").click()
    expect(page.locator("button[data-view='settings']")).to_have_class(
        re.compile("active")
    )
    expect(page.locator("button[data-view='register']")).not_to_have_class(
        re.compile("active")
    )
