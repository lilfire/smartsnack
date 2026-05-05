"""E2E tests for infinite scroll / pagination (P0 gap #1).

Validates that products beyond the first page load correctly when the user
scrolls to the bottom, and that the scroll loader indicator behaves properly.

A single shared fixture creates 55 products once so that all scroll-related
assertions run against the same data set without re-creating products per
test (which is slow and causes accumulation across the shared-session DB).
"""

import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_and_wait(page):
    """Reload the page and wait for the initial product list to settle."""
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=15000,
    )


def _scroll_to_bottom(page):
    """Scroll the window to the very bottom."""
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


# ---------------------------------------------------------------------------
# Session-scoped product creation so all tests share one batch of products
# ---------------------------------------------------------------------------

# We use a module-level flag so the products are created once for the whole
# module.  We cannot use a session fixture here because api_create_product is
# function-scoped, so we create the data inside the first test that needs it
# via a module-level sentinel.

_SCROLL_PRODUCTS_CREATED = False
_SCROLL_PRODUCT_NAMES: list[str] = []


def _ensure_scroll_products(api_create_product) -> list[str]:
    """Create 55 uniquely-named products if not already done this session."""
    global _SCROLL_PRODUCTS_CREATED, _SCROLL_PRODUCT_NAMES
    if not _SCROLL_PRODUCTS_CREATED:
        names = [f"InfScroll_{i:03d}" for i in range(55)]
        for name in names:
            api_create_product(name=name)
        _SCROLL_PRODUCT_NAMES = names
        _SCROLL_PRODUCTS_CREATED = True
    return _SCROLL_PRODUCT_NAMES


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_load_limited_to_page_size(page, api_create_product):
    """Only the first page (≤50 products) should render on initial load."""
    _ensure_scroll_products(api_create_product)
    _reload_and_wait(page)

    row_count = page.locator(".table-row[data-product-id]").count()
    assert row_count <= 50, (
        f"Expected at most 50 rows on initial load, got {row_count}"
    )
    # There must be at least one row — the DB always has these products
    assert row_count > 0, "Expected at least one product row after seeding"


def test_scroll_loads_more_products(page, api_create_product):
    """Scrolling to the bottom should load additional products beyond page 1."""
    _ensure_scroll_products(api_create_product)
    _reload_and_wait(page)

    initial_count = page.locator(".table-row[data-product-id]").count()

    # Trigger infinite scroll
    _scroll_to_bottom(page)
    page.wait_for_function(
        f"() => document.querySelectorAll('.table-row[data-product-id]').length > {initial_count}",
        timeout=10000,
    )

    after_scroll_count = page.locator(".table-row[data-product-id]").count()
    assert after_scroll_count > initial_count, (
        f"Expected more products after scroll: before={initial_count}, "
        f"after={after_scroll_count}"
    )


def test_scroll_loader_present_in_dom(page, api_create_product):
    """The #scroll-loader element must be present in the DOM at all times."""
    _ensure_scroll_products(api_create_product)
    _reload_and_wait(page)

    loader = page.locator("#scroll-loader")
    expect(loader).to_be_attached()


def test_all_products_eventually_visible(page, api_create_product):
    """After repeated scrolling, all 55 seeded products should be visible."""
    names = _ensure_scroll_products(api_create_product)
    _reload_and_wait(page)

    # Scroll several times to load all pages
    for _ in range(6):
        _scroll_to_bottom(page)
        page.wait_for_timeout(800)

    container_text = page.locator("#results-container").inner_text()
    found = [n for n in names if n in container_text]

    # All 55 uniquely-named products should be present
    assert len(found) == len(names), (
        f"Expected all {len(names)} products after scrolling, "
        f"only found {len(found)}: missing={set(names) - set(found)}"
    )


def test_result_count_shows_numeric_value(page, api_create_product):
    """The result-count element must display a number reflecting the total."""
    _ensure_scroll_products(api_create_product)
    _reload_and_wait(page)

    result_count = page.locator("#result-count")
    expect(result_count).to_be_visible()

    count_text = result_count.inner_text()
    assert any(ch.isdigit() for ch in count_text), (
        f"Result count element must contain a digit, got: '{count_text}'"
    )
    # With 55 products the shown total should be at least 55
    digits = "".join(ch for ch in count_text if ch.isdigit() or ch == " ")
    numbers = [int(tok) for tok in digits.split() if tok.isdigit()]
    assert any(n >= 55 for n in numbers), (
        f"Result count should reflect at least 55 products, got: '{count_text}'"
    )
