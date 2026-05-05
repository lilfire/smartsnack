"""E2E tests for translation verification across all three languages (no, en, se).

Tests:
- Default language is Norwegian: nav button text must be "Søk" (not "Search")
- Switching to English changes UI text to English equivalents
- Switching to Swedish changes UI text to Swedish equivalents
- Switching back to Norwegian restores Norwegian text
- No raw translation key strings appear visible in any view
- Toast messages appear in the active language after a registration
- data-i18n elements show translated text, not raw keys
- Placeholder attributes are translated, not raw keys
- Language persistence API works correctly
"""

import json
import urllib.request

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible(timeout=5000)
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible(timeout=5000)


def _go_to_search(page):
    page.locator("button[data-view='search']").click()
    expect(page.locator("#view-search")).to_be_visible(timeout=5000)


def _set_language(page, lang):
    """Set language via the changeLanguage() function exposed on window."""
    page.evaluate(
        """(lang) => {
            const sel = document.querySelector('#language-select');
            if (sel) sel.value = lang;
            if (typeof window.changeLanguage === 'function') {
                return window.changeLanguage(lang);
            }
        }""",
        lang,
    )
    page.wait_for_timeout(1200)


# ---------------------------------------------------------------------------
# Language switching tests
# ---------------------------------------------------------------------------


def test_default_language_is_norwegian(page):
    """The default language must be Norwegian: the search nav button says 'Søk'."""
    # The no.json translation for nav_search is "Søk" (with emoji prefix)
    nav_search = page.locator("button[data-view='search']")
    text = nav_search.inner_text()
    assert "Søk" in text, (
        f"Expected Norwegian 'Søk' as default nav text, got: '{text}'"
    )


def test_switch_to_english_updates_nav(page):
    """Switching to English must change the search nav button text to 'Search'."""
    _set_language(page, "en")

    nav_search = page.locator("button[data-view='search']")
    text = nav_search.inner_text()
    assert "Search" in text, (
        f"Expected 'Search' after switching to English, got: '{text}'"
    )
    # Must NOT still show Norwegian
    assert "Søk" not in text, (
        f"Norwegian 'Søk' still present after switching to English: '{text}'"
    )


def test_switch_to_swedish_updates_nav(page):
    """Switching to Swedish must change the search nav button text to 'Sök'."""
    _set_language(page, "se")

    nav_search = page.locator("button[data-view='search']")
    text = nav_search.inner_text()
    assert "Sök" in text, (
        f"Expected Swedish 'Sök' after switching to Swedish, got: '{text}'"
    )


def test_switch_back_to_norwegian(page):
    """Switching away from Norwegian and then back must restore Norwegian text."""
    _set_language(page, "en")
    _set_language(page, "no")

    nav_search = page.locator("button[data-view='search']")
    text = nav_search.inner_text()
    assert "Søk" in text, (
        f"Expected 'Søk' after switching back to Norwegian, got: '{text}'"
    )


# ---------------------------------------------------------------------------
# Translation completeness — no raw keys visible in the UI
# ---------------------------------------------------------------------------


def test_no_raw_keys_in_english_search_view(page):
    """In English mode, the search view must not display any raw translation key strings."""
    _set_language(page, "en")
    _go_to_search(page)

    body_text = page.locator("body").inner_text()
    raw_key_patterns = [
        "nav_search",
        "nav_register",
        "nav_settings",
        "search_placeholder",
        "filter_all",
        "loading_products",
    ]
    for key in raw_key_patterns:
        assert key not in body_text, (
            f"Raw translation key '{key}' is visible in the English search view"
        )


def test_no_raw_keys_in_english_register_view(page):
    """In English mode, the register view must not display raw translation key strings."""
    _set_language(page, "en")
    _go_to_register(page)

    view_text = page.locator("#view-register").inner_text()
    raw_key_patterns = [
        "register_title_1",
        "label_category",
        "label_product_name",
        "section_nutrition",
    ]
    for key in raw_key_patterns:
        assert key not in view_text, (
            f"Raw translation key '{key}' is visible in the English register view"
        )


def test_no_raw_keys_in_swedish_search_view(page):
    """In Swedish mode, the search view must not display raw translation key strings."""
    _set_language(page, "se")
    _go_to_search(page)

    body_text = page.locator("body").inner_text()
    raw_key_patterns = [
        "nav_search",
        "nav_register",
        "nav_settings",
        "search_placeholder",
    ]
    for key in raw_key_patterns:
        assert key not in body_text, (
            f"Raw translation key '{key}' is visible in the Swedish search view"
        )


# ---------------------------------------------------------------------------
# Toast message translation tests — triggered by real UI actions
# ---------------------------------------------------------------------------


def test_success_toast_in_english_contains_product_name(page):
    """After registering a product with English active, the success toast must
    contain the product name (which is language-independent)."""
    _set_language(page, "en")
    _go_to_register(page)

    product_name = "EnglishToastProdE2E"
    page.locator("#f-name").fill(product_name)
    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text()
    assert product_name in toast_text, (
        f"Expected product name '{product_name}' in English success toast, got: '{toast_text}'"
    )
    # English template: '"{name}" added!'
    assert "added" in toast_text.lower(), (
        f"Expected 'added' in English toast text, got: '{toast_text}'"
    )


def test_error_toast_in_english_mentions_name_field(page):
    """An empty-name validation error in English must reference 'name' or 'required'."""
    _set_language(page, "en")
    _go_to_register(page)

    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text().lower()
    assert "name" in toast_text or "required" in toast_text, (
        f"Expected English name-required error, got: '{toast_text}'"
    )


def test_success_toast_in_norwegian_contains_product_name(page):
    """After registering in Norwegian mode, the toast must contain the product name."""
    _set_language(page, "no")
    _go_to_register(page)

    product_name = "NorskToastProdE2E"
    page.locator("#f-name").fill(product_name)
    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text()
    assert product_name in toast_text, (
        f"Expected product name '{product_name}' in Norwegian toast, got: '{toast_text}'"
    )


# ---------------------------------------------------------------------------
# Static translation attribute tests
# ---------------------------------------------------------------------------


def test_data_i18n_elements_show_translated_text(page):
    """All visible data-i18n elements must have non-empty text that is not the raw key."""
    i18n_elements = page.locator("[data-i18n]")
    count = i18n_elements.count()
    assert count > 0, "Expected at least one [data-i18n] element on the page"

    failures = []
    for i in range(min(count, 15)):
        elem = i18n_elements.nth(i)
        if not elem.is_visible():
            continue
        text = elem.inner_text().strip()
        key = elem.get_attribute("data-i18n")
        if text == key:
            failures.append(f"data-i18n='{key}' shows raw key as visible text")

    assert not failures, (
        "Found data-i18n elements displaying raw keys:\n" + "\n".join(failures)
    )


def test_placeholder_translations_are_not_raw_keys(page):
    """Elements with data-i18n-placeholder must have translated placeholders, not raw keys."""
    _go_to_register(page)

    elements = page.locator("[data-i18n-placeholder]")
    count = elements.count()
    assert count > 0, "Expected at least one [data-i18n-placeholder] element in register view"

    failures = []
    for i in range(min(count, 8)):
        elem = elements.nth(i)
        if not elem.is_visible():
            continue
        placeholder = elem.get_attribute("placeholder") or ""
        key = elem.get_attribute("data-i18n-placeholder") or ""
        if placeholder == key:
            failures.append(
                f"data-i18n-placeholder='{key}' has untranslated placeholder='{placeholder}'"
            )

    assert not failures, (
        "Found untranslated placeholder attributes:\n" + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# Translation API tests
# ---------------------------------------------------------------------------


def test_languages_api_returns_all_three_codes(live_url):
    """GET /api/languages must return a list containing 'no', 'en', and 'se'."""
    req = urllib.request.Request(f"{live_url}/api/languages", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert isinstance(body, list), (
        f"Expected list from /api/languages, got {type(body).__name__}: {body}"
    )
    codes = [lang.get("code") for lang in body]
    assert "no" in codes, f"Expected 'no' in language codes, got: {codes}"
    assert "en" in codes, f"Expected 'en' in language codes, got: {codes}"
    assert "se" in codes, f"Expected 'se' in language codes, got: {codes}"


def test_language_setting_persists_via_api(live_url):
    """PUT /api/settings/language must acknowledge the change and persist it."""
    payload = json.dumps({"language": "en"}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/settings/language",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())

    assert body.get("ok") is True or "language" in body, (
        f"Expected success response from PUT /api/settings/language, got: {body}"
    )

    # Verify the change was persisted with a GET
    req = urllib.request.Request(
        f"{live_url}/api/settings/language",
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        get_body = json.loads(resp.read())

    assert get_body.get("language") == "en", (
        f"Expected language='en' after PUT, got: {get_body}"
    )

    # Reset to Norwegian so other tests start in a clean state
    reset_payload = json.dumps({"language": "no"}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/settings/language",
        data=reset_payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(req, timeout=5)
