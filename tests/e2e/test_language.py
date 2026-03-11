"""Test language switching functionality."""

import re

from playwright.sync_api import expect


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_language_section(page):
    """Open the language section in settings."""
    lang_toggle = page.locator(
        ".settings-toggle:has(span[data-i18n='settings_language'])"
    ).first
    lang_toggle.click()
    page.wait_for_timeout(300)


def _change_language(page, lang_code):
    """Change language via JS (native select is hidden by custom overlay)."""
    page.evaluate(
        f"""() => {{
            const sel = document.querySelector('#language-select');
            sel.value = '{lang_code}';
            window.changeLanguage('{lang_code}');
        }}"""
    )
    page.wait_for_timeout(1000)


def test_language_dropdown_exists(page):
    """The language select should be present in settings."""
    _go_to_settings(page)
    _open_language_section(page)

    select = page.locator("#language-select")
    expect(select).to_be_attached()


def test_switch_to_english(page):
    """Switching language to English should update UI text."""
    _go_to_settings(page)
    _open_language_section(page)

    _change_language(page, "en")

    # Nav tabs should now show English text
    search_tab = page.locator("button[data-view='search']")
    expect(search_tab).to_contain_text(re.compile("Search", re.IGNORECASE))


def test_switch_to_norwegian(page):
    """Switching language to Norwegian should update UI text."""
    _go_to_settings(page)
    _open_language_section(page)

    _change_language(page, "no")

    # Nav should show Norwegian
    search_tab = page.locator("button[data-view='search']")
    expect(search_tab).to_contain_text(re.compile("Søk", re.IGNORECASE))


def test_language_persists_across_reload(page):
    """After switching language, reloading should keep the selection."""
    _go_to_settings(page)
    _open_language_section(page)

    _change_language(page, "en")

    page.reload(wait_until="domcontentloaded")
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Should still be English
    search_tab = page.locator("button[data-view='search']")
    expect(search_tab).to_contain_text(re.compile("Search", re.IGNORECASE))
