"""E2E tests for the OpenFoodFacts product search/picker modal (P0 gap #5).

The OFF picker modal is created dynamically by off-picker.js when:
  - The user types a product name (>= 2 chars) in the register form and clicks
    the OFF fetch button  -> name-based search via POST /api/off/search
  - The user types a valid EAN in the register form and clicks the OFF fetch
    button  -> EAN lookup via GET /api/off/product/<ean>, and on success the
    form fields are populated without showing the picker modal.

All external HTTP calls are intercepted with page.route() so the tests are
fully deterministic.
"""

import json

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Shared mock payloads
# ---------------------------------------------------------------------------

_MOCK_OFF_SEARCH_RESPONSE = {
    "products": [
        {
            "code": "7310865004703",
            "product_name": "Kvarg Naturell",
            "brands": "Lindahls",
            "completeness": 0.8,
            "nutriments": {
                "energy-kcal_100g": 60,
                "proteins_100g": 11,
                "fat_100g": 0.2,
                "carbohydrates_100g": 3.5,
            },
        },
        {
            "code": "7038010069307",
            "product_name": "Monster ProteinChips",
            "brands": "Monster",
            "completeness": 0.6,
            "nutriments": {
                "energy-kcal_100g": 450,
                "proteins_100g": 30,
                "fat_100g": 15,
                "carbohydrates_100g": 45,
            },
        },
    ],
    "count": 2,
}

_MOCK_OFF_PRODUCT_RESPONSE = {
    "status": 1,
    "product": {
        "code": "7310865004703",
        "product_name": "Kvarg Naturell",
        "brands": "Lindahls",
        "stores": "Rema 1000",
        "ingredients_text": "Skummet melk, bakteriekultur",
        "nutriments": {
            "energy-kcal_100g": 60,
            "fat_100g": 0.2,
            "saturated-fat_100g": 0.1,
            "carbohydrates_100g": 3.5,
            "sugars_100g": 3.5,
            "proteins_100g": 11,
            "fiber_100g": 0,
            "salt_100g": 0.1,
        },
        "completeness": 0.8,
    },
}

_MOCK_OFF_NOT_FOUND_RESPONSE = {"status": 0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _intercept_off_search(page, response_body=None):
    """Route POST /api/off/search to return a controlled payload."""
    body = response_body if response_body is not None else _MOCK_OFF_SEARCH_RESPONSE

    def _handler(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/off/search", _handler)


def _intercept_off_product(page, response_body=None):
    """Route GET /api/off/product/<ean> to return a controlled payload."""
    body = response_body if response_body is not None else _MOCK_OFF_PRODUCT_RESPONSE

    def _handler(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/off/product/*", _handler)


# ---------------------------------------------------------------------------
# Tests: register form elements
# ---------------------------------------------------------------------------


def test_off_fetch_button_exists_on_register(page):
    """The OFF fetch button must be present on the register form."""
    _go_to_register(page)
    fetch_btn = page.locator("#f-off-btn")
    expect(fetch_btn).to_be_attached()


def test_off_search_input_exists_in_modal(page):
    """After opening the picker via a name search, the search input must be
    present inside the OFF modal."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)
    expect(page.locator("#off-search-input")).to_be_visible(timeout=3000)


def test_off_modal_search_button_exists(page):
    """The OFF modal must contain a search/re-search button."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)
    expect(page.locator("#off-search-btn")).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: name-based search opens the picker and shows results
# ---------------------------------------------------------------------------


def test_off_modal_opens_on_name_search(page):
    """Typing a name >= 2 chars and clicking fetch must open the OFF picker
    and display the mocked search results."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    # The modal background must appear
    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)

    # The results body must contain the result rows returned by the mock
    results_body = page.locator("#off-results-body")
    expect(results_body).to_be_visible(timeout=5000)
    expect(results_body.locator(".off-result[data-action='off-select']")).to_have_count(
        2, timeout=5000
    )


def test_off_modal_shows_product_names(page):
    """Result rows in the picker must display the product names from the
    mocked search response."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)
    results_body = page.locator("#off-results-body")
    expect(results_body).to_contain_text("Kvarg Naturell", timeout=5000)
    expect(results_body).to_contain_text("Monster ProteinChips", timeout=5000)


def test_off_modal_search_input_pre_filled(page):
    """The search input inside the picker should be pre-filled with the
    name the user typed in the register form."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)
    expect(page.locator("#off-search-input")).to_have_value("Kvarg", timeout=3000)


# ---------------------------------------------------------------------------
# Tests: selecting a result populates the form
# ---------------------------------------------------------------------------


def test_selecting_off_result_fills_form_fields(page):
    """Clicking a result row must close the picker and populate the register
    form with the selected product's nutrition data.  The EAN field is filled
    by a subsequent GET /api/off/product/<ean> call (also mocked)."""
    _go_to_register(page)
    _intercept_off_search(page)
    _intercept_off_product(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)

    # Click the first result
    first_result = page.locator(".off-result[data-action='off-select']").first
    expect(first_result).to_be_visible(timeout=5000)
    first_result.click()

    # Picker must close after selection
    expect(page.locator("#off-modal-bg")).to_be_hidden(timeout=5000)

    # The kcal field must be populated from the mock product data (60 kcal)
    expect(page.locator("#f-kcal")).not_to_have_value("", timeout=5000)


def test_selecting_off_result_fills_ean(page):
    """After selecting a search result the EAN field must be set to the
    product's barcode (7310865004703) returned by the mock."""
    _go_to_register(page)
    _intercept_off_search(page)
    _intercept_off_product(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)

    first_result = page.locator(".off-result[data-action='off-select']").first
    expect(first_result).to_be_visible(timeout=5000)
    first_result.click()

    # EAN must be populated from the code returned by the mock
    expect(page.locator("#f-ean")).to_have_value("7310865004703", timeout=5000)


# ---------------------------------------------------------------------------
# Tests: EAN lookup auto-populates without showing the picker
# ---------------------------------------------------------------------------


def test_off_ean_lookup_fills_form_without_modal(page):
    """Entering a valid EAN and clicking fetch must NOT show the picker modal;
    it should populate the form fields directly from the mocked product data."""
    _go_to_register(page)
    _intercept_off_product(page)

    page.locator("#f-ean").fill("7310865004703")
    page.locator("#f-off-btn").click()

    # Picker must remain hidden — EAN lookup applies data and closes immediately
    expect(page.locator("#off-modal-bg")).to_be_hidden(timeout=5000)

    # Product name must be applied from mock
    expect(page.locator("#f-name")).not_to_have_value("", timeout=5000)


def test_off_ean_lookup_not_found_opens_modal(page):
    """When an EAN lookup returns status 0 (not found), the picker modal must
    open so the user can search manually."""
    _go_to_register(page)
    _intercept_off_product(page, response_body=_MOCK_OFF_NOT_FOUND_RESPONSE)

    page.locator("#f-name").fill("SomeName")
    page.locator("#f-ean").fill("7310865004703")
    page.locator("#f-off-btn").click()

    # When not found the picker opens (unless autoClose is set); the modal bg
    # must be visible
    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Tests: close behaviour
# ---------------------------------------------------------------------------


def test_off_modal_close_button_dismisses_modal(page):
    """Clicking the × close button inside the OFF modal must hide the modal."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)

    close_btn = page.locator("#off-modal-bg .off-modal-close")
    expect(close_btn).to_be_visible(timeout=3000)
    close_btn.click()

    expect(page.locator("#off-modal-bg")).to_be_hidden(timeout=3000)


def test_off_modal_closes_on_backdrop_click(page):
    """Clicking the modal backdrop (outside the inner panel) must close the
    OFF picker modal."""
    _go_to_register(page)
    _intercept_off_search(page)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()

    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)

    # Click the very top-left corner of the backdrop (outside the modal panel)
    page.locator("#off-modal-bg").click(position={"x": 5, "y": 5})

    expect(page.locator("#off-modal-bg")).to_be_hidden(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: in-modal search (re-search)
# ---------------------------------------------------------------------------


def test_off_modal_search_button_triggers_new_search(page):
    """Changing the text in the search input and clicking the search button
    must issue a new /api/off/search request and update the results."""
    _go_to_register(page)

    call_count = {"n": 0}
    second_response = {
        "products": [
            {
                "code": "1234567890128",
                "product_name": "Røros Rømme",
                "brands": "Røros",
                "completeness": 0.7,
                "nutriments": {
                    "energy-kcal_100g": 200,
                    "proteins_100g": 3,
                    "fat_100g": 18,
                    "carbohydrates_100g": 4,
                },
            }
        ],
        "count": 1,
    }

    def _handler(route):
        call_count["n"] += 1
        if call_count["n"] == 1:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_MOCK_OFF_SEARCH_RESPONSE),
            )
        else:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(second_response),
            )

    page.route("**/api/off/search", _handler)

    page.locator("#f-name").fill("Kvarg")
    page.locator("#f-off-btn").click()
    expect(page.locator("#off-modal-bg")).to_be_visible(timeout=5000)
    expect(
        page.locator(".off-result[data-action='off-select']")
    ).to_have_count(2, timeout=5000)

    # Change search term and re-search
    page.locator("#off-search-input").fill("Røros")
    page.locator("#off-search-btn").click()

    # Results must update to the second response (1 result)
    expect(
        page.locator(".off-result[data-action='off-select']")
    ).to_have_count(1, timeout=5000)
    expect(page.locator("#off-results-body")).to_contain_text(
        "Røros Rømme", timeout=5000
    )
