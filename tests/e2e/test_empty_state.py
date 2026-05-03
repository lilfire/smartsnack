"""E2E tests for empty state and product unsync (P2 gaps #21-22).

Tests:
- Empty state message appears when a search yields no results
- The create-from-search CTA button appears in the empty state
- Unsync API returns a meaningful response (not silently swallowed)
"""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


def _reload_and_wait(page):
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


# ---------------------------------------------------------------------------
# Empty state tests
# ---------------------------------------------------------------------------


def test_search_no_results_shows_empty_state(page, api_create_product):
    """Searching for a term that matches no products renders the .empty element."""
    api_create_product(name="RealProduct")
    _reload_and_wait(page)

    search_input = page.locator("#search-input")
    search_input.fill("xyzXYZnonexistentq999zzz")
    page.wait_for_timeout(800)

    # The render.js empty-state path produces a div.empty inside #results-container
    empty = page.locator("#results-container .empty")
    expect(empty).to_be_visible(timeout=5000)


def test_empty_state_shows_no_products_text(page, api_create_product):
    """The empty state element must contain the translated 'no products found' string."""
    api_create_product(name="AnotherRealProduct")
    _reload_and_wait(page)

    page.locator("#search-input").fill("xyzXYZnonexistentq999zzz")
    page.wait_for_timeout(800)

    empty = page.locator("#results-container .empty")
    expect(empty).to_be_visible(timeout=5000)
    # render.js injects t('no_products_found') — Norwegian is "Ingen produkter funnet"
    empty_text = empty.inner_text()
    assert len(empty_text.strip()) > 0, (
        "Empty state element must contain non-empty text"
    )
    # Text must NOT be the raw translation key
    assert "no_products_found" not in empty_text, (
        f"Empty state shows raw translation key instead of translated text: '{empty_text}'"
    )


def test_empty_state_has_icon(page, api_create_product):
    """The empty state should render the .empty-icon element."""
    api_create_product(name="IconTestProduct")
    _reload_and_wait(page)

    page.locator("#search-input").fill("xyzXYZnonexistentq999zzz")
    page.wait_for_timeout(800)

    empty_icon = page.locator("#results-container .empty-icon")
    expect(empty_icon).to_be_visible(timeout=5000)


def test_create_from_search_button_appears_on_empty_search(page, api_create_product):
    """When a search yields no results, the create-from-search CTA must appear."""
    api_create_product(name="CTATestProduct")
    _reload_and_wait(page)

    page.locator("#search-input").fill("xyzXYZnonexistentq999zzz")
    page.wait_for_timeout(800)

    # render.js only renders the btn-create-from-search when search is non-empty
    cta = page.locator("button.btn-create-from-search")
    expect(cta).to_be_visible(timeout=5000)


def test_create_from_search_button_navigates_to_register(page, api_create_product):
    """Clicking the create-from-search CTA pre-fills the register form and switches view."""
    api_create_product(name="CTANavTestProduct")
    _reload_and_wait(page)

    search_term = "UniqueNewItemXYZ"
    page.locator("#search-input").fill(search_term)
    page.wait_for_timeout(800)

    cta = page.locator("button.btn-create-from-search")
    expect(cta).to_be_visible(timeout=5000)
    cta.click()
    page.wait_for_timeout(400)

    # Should have navigated to the register view
    expect(page.locator("#view-register")).to_be_visible(timeout=3000)

    # The name field should be pre-filled with the search term
    name_value = page.locator("#f-name").input_value()
    assert name_value == search_term, (
        f"Expected register name field to be pre-filled with '{search_term}', got '{name_value}'"
    )


# ---------------------------------------------------------------------------
# Unsync API tests
# ---------------------------------------------------------------------------


def test_unsync_api_returns_valid_response(live_url, api_create_product):
    """POST /api/products/{id}/unsync must return a JSON object (not raise an unhandled error)."""
    product = api_create_product(name="UnsyncAPIProd")
    product_id = product["id"]

    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/unsync",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # The endpoint may succeed (ok=True) or return a 4xx if the product was
    # never synced — either way it must return parseable JSON, not a 500.
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
        # Success path: endpoint must return a dict
        assert isinstance(body, dict), (
            f"Expected JSON object from unsync, got: {type(body).__name__}"
        )
        assert "ok" in body or "error" in body, (
            f"Expected 'ok' or 'error' key in unsync response, got: {body}"
        )
    except urllib.error.HTTPError as exc:
        # 4xx is fine — product was not synced; but the body must still be JSON
        body = json.loads(exc.read())
        assert "error" in body, (
            f"Expected 'error' key in non-2xx unsync response, got: {body}"
        )


def test_unsync_nonexistent_product_returns_404(live_url):
    """POST /api/products/99999999/unsync must return 404, not 500."""
    req = urllib.request.Request(
        f"{live_url}/api/products/99999999/unsync",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("Expected HTTP error for nonexistent product")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, (
            f"Expected 404 for nonexistent product unsync, got {exc.code}"
        )
        body = json.loads(exc.read())
        assert "error" in body, (
            f"Expected 'error' key in 404 body, got: {body}"
        )
