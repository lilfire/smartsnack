"""Test empty state and no-results UX (Task 6).

Verifies that:
- A fresh database with no products shows the no_products_found translation
- Searching for a non-matching query shows the no-results message
- The "create product" button appears in no-results state when a search query is active
"""

from playwright.sync_api import expect


def test_empty_database_shows_no_products_message(browser, app_server):
    """Fresh database with no products shows 'no_products_found' translation text."""
    page = browser.new_page()
    try:
        page.route(
            "**/*",
            lambda route: (
                route.abort()
                if not route.request.url.startswith(app_server)
                else route.continue_()
            ),
        )
        page.goto(app_server, wait_until="domcontentloaded")
        page.wait_for_selector("#results-container", state="attached", timeout=10000)
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        results = page.locator("#results-container")
        # The empty state should show the Norwegian translation for "no products found"
        # which is "Ingen produkter funnet"
        expect(results.locator(".empty")).to_be_visible(timeout=5000)
        expect(results).to_contain_text("Ingen produkter funnet")
    finally:
        page.close()


def test_search_no_results_shows_message(page, api_create_product):
    """Searching for non-matching query shows no-results message."""
    # Ensure at least one product exists so the empty state isn't shown by default
    api_create_product(name="ExistingProduct")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    search = page.locator("#search-input")
    search.fill("ZZZNonExistentProductXYZ")
    page.wait_for_timeout(500)

    results = page.locator("#results-container")
    expect(results.locator(".empty")).to_be_visible(timeout=5000)
    expect(results).to_contain_text("Ingen produkter funnet")


def test_search_no_results_shows_create_button(page, api_create_product):
    """No-results state with a search query shows the 'create product' button."""
    api_create_product(name="AnotherProduct")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    search = page.locator("#search-input")
    search.fill("BrandNewNonExistentItem")
    page.wait_for_timeout(500)

    results = page.locator("#results-container")
    expect(results.locator(".empty")).to_be_visible(timeout=5000)

    # The "create product" button should be visible (Norwegian: "Opprett produkt")
    create_btn = results.locator("[data-action='create-from-search']")
    expect(create_btn).to_be_visible(timeout=3000)
    expect(create_btn).to_contain_text("Opprett produkt")


def test_create_from_search_navigates_to_register(page, api_create_product):
    """Clicking 'create product' in no-results state navigates to register view."""
    api_create_product(name="SomeProductForSearch")
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    search = page.locator("#search-input")
    search.fill("TotallyNewProduct")
    page.wait_for_timeout(500)

    results = page.locator("#results-container")
    expect(results.locator(".empty")).to_be_visible(timeout=5000)

    create_btn = results.locator("[data-action='create-from-search']")
    expect(create_btn).to_be_visible(timeout=3000)
    create_btn.click()

    # Should navigate to register view
    register_view = page.locator("#view-register")
    expect(register_view).to_be_visible(timeout=5000)
