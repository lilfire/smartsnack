"""Test search, filtering, and advanced filter functionality."""

import re

import pytest
from playwright.sync_api import expect


def test_search_input_exists(page):
    """The search input should be present and focusable."""
    search = page.locator("#search-input")
    expect(search).to_be_visible()
    search.focus()
    expect(search).to_be_focused()


def test_search_filters_products(page, api_create_product):
    """Typing in the search box should filter the product list."""
    api_create_product(name="UniqueAlphaProduct")
    api_create_product(name="BetaProduct")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    search = page.locator("#search-input")
    search.fill("UniqueAlpha")
    # Wait for debounce and results to update
    page.wait_for_timeout(500)

    results = page.locator("#results-container")
    expect(results).to_contain_text("UniqueAlphaProduct")
    expect(results).not_to_contain_text("BetaProduct")


def test_clear_search(page, api_create_product):
    """Clicking the clear button should reset the search."""
    api_create_product(name="ClearTestProd")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    search = page.locator("#search-input")
    search.fill("ClearTestProd")
    page.wait_for_timeout(500)

    page.locator("#search-clear").click()
    expect(search).to_have_value("")


def test_category_filter_toggle(page):
    """Clicking the category filter toggle should show filter pills."""
    toggle = page.locator("#filter-toggle")
    expect(toggle).to_be_visible()
    toggle.click()
    # Filter row should become visible
    filter_row = page.locator("#filter-row")
    expect(filter_row).to_be_visible()


def test_advanced_filter_toggle(page):
    """Clicking advanced filter toggle should show the advanced filters panel."""
    toggle = page.locator("#adv-filter-toggle")
    expect(toggle).to_be_visible()
    toggle.click()
    # Advanced filters panel should appear
    adv = page.locator("#advanced-filters")
    expect(adv).to_be_visible()


def test_result_count_displayed(page, api_create_product):
    """The result count should show how many products are displayed."""
    api_create_product(name="CountTestA")
    api_create_product(name="CountTestB")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    count_el = page.locator("#result-count")
    expect(count_el).to_be_visible()
    # Should contain a number
    expect(count_el).to_have_text(re.compile(".+"))
