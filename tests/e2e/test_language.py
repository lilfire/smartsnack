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


# ---------------------------------------------------------------------------
# Swedish language completeness (Task 8)
# ---------------------------------------------------------------------------

import json
import os


def _load_translations(lang="se"):
    """Load translations from the translation JSON files."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def test_switch_to_swedish(page):
    """Switching language to Swedish should update UI text."""
    t = _load_translations("se")
    _go_to_settings(page)
    _open_language_section(page)

    _change_language(page, "se")

    # Nav tabs should show Swedish text
    search_tab = page.locator("button[data-view='search']")
    nav_text = t["nav_search"].split(" ", 1)[-1]  # strip emoji prefix
    expect(search_tab).to_contain_text(re.compile(re.escape(nav_text), re.IGNORECASE))

    register_tab = page.locator("button[data-view='register']")
    reg_text = t["nav_register"].split(" ", 1)[-1]
    expect(register_tab).to_contain_text(
        re.compile(re.escape(reg_text), re.IGNORECASE)
    )

    settings_tab = page.locator("button[data-view='settings']")
    settings_text = t["nav_settings"].split(" ", 1)[-1]
    expect(settings_tab).to_contain_text(
        re.compile(re.escape(settings_text), re.IGNORECASE)
    )


def test_swedish_persists_across_reload(page):
    """Swedish language persists after page reload."""
    t = _load_translations("se")
    _go_to_settings(page)
    _open_language_section(page)

    _change_language(page, "se")

    page.reload(wait_until="domcontentloaded")
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Should still be Swedish
    search_tab = page.locator("button[data-view='search']")
    nav_text = t["nav_search"].split(" ", 1)[-1]
    expect(search_tab).to_contain_text(re.compile(re.escape(nav_text), re.IGNORECASE))


def test_register_product_in_swedish(page):
    """Registering a product in Swedish mode shows Swedish toast."""
    t = _load_translations("se")
    _go_to_settings(page)
    _open_language_section(page)
    _change_language(page, "se")

    # Navigate to register
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()

    product_name = "SwedishTestProduct"
    page.locator("#f-name").fill(product_name)
    page.locator("#f-kcal").fill("120")
    page.locator("#f-protein").fill("8")
    page.locator("#f-fat").fill("4")
    page.locator("#f-carbs").fill("15")
    page.locator("#f-sugar").fill("2")
    page.locator("#f-salt").fill("0.3")
    page.locator("#f-smak").fill("4")
    page.locator("#btn-submit").click()

    page.wait_for_timeout(500)
    # Dismiss OFF modal if it appears
    cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
    if cancel.is_visible():
        cancel.click()
        page.wait_for_timeout(200)

    expected = t["toast_product_added"].replace("{name}", product_name)
    toast = page.locator("#toast.show")
    expect(toast).to_be_visible(timeout=5000)
    expect(toast).to_contain_text(expected)


def test_switch_back_to_norwegian_from_swedish(page):
    """Switching from Swedish back to Norwegian reverts nav text."""
    t_se = _load_translations("se")
    t_no = _load_translations("no")
    _go_to_settings(page)
    _open_language_section(page)

    # First switch to Swedish
    _change_language(page, "se")
    search_tab = page.locator("button[data-view='search']")
    se_text = t_se["nav_search"].split(" ", 1)[-1]
    expect(search_tab).to_contain_text(re.compile(re.escape(se_text), re.IGNORECASE))

    # Now switch back to Norwegian
    _change_language(page, "no")
    no_text = t_no["nav_search"].split(" ", 1)[-1]
    expect(search_tab).to_contain_text(re.compile(re.escape(no_text), re.IGNORECASE))
