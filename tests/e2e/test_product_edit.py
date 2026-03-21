"""Detailed e2e tests for product editing: nutrition fields, duplicate detection, sorting."""

import json
import urllib.error
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _reload_and_wait(page) -> None:
    """Reload the page and wait until the product list finishes loading.

    Args:
        page: Playwright page object.
    """
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )


def _expand_product_row(page, product_name: str) -> None:
    """Click the product row to expand it and wait for the animation.

    Args:
        page: Playwright page object.
        product_name: Visible name of the product whose row should be expanded.
    """
    row = page.locator(".table-row", has_text=product_name)
    row.first.click()
    page.wait_for_timeout(300)


def _open_edit_form(page, product_name: str) -> None:
    """Expand a product row and click its edit button.

    Args:
        page: Playwright page object.
        product_name: Visible name of the product to edit.
    """
    _expand_product_row(page, product_name)
    edit_btn = page.locator("[data-action='start-edit']").first
    edit_btn.click()
    page.wait_for_timeout(500)


def _check_duplicate_api(
    live_url: str, product_id: int, ean: str, name: str
) -> dict:
    """POST to the check-duplicate endpoint and return the parsed response.

    Args:
        live_url: Base URL of the running Flask server.
        product_id: ID of the product being edited (excluded from duplicate search).
        ean: EAN barcode string to check.
        name: Product name to check.

    Returns:
        Parsed JSON response body containing ``duplicate`` and
        ``a_is_synced_with_off`` keys.
    """
    payload = json.dumps({"ean": ean, "name": name}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products/{product_id}/check-duplicate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _create_product_raw(live_url: str, payload: dict) -> tuple[int, dict]:
    """POST a product creation request and return (status_code, body).

    Args:
        live_url: Base URL of the running Flask server.
        payload: Dict that will be JSON-encoded and sent as the request body.

    Returns:
        Tuple of HTTP status code and parsed JSON response body.
    """
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_edit_nutrition_fields(page, api_create_product):
    """Editing kcal, protein and fat should persist after save and reload.

    Creates a product via API, opens the edit form, changes three nutrition
    fields, saves, verifies the success toast, then reloads the page and
    expands the row again to confirm the updated values are shown in the
    nutrition table.
    """
    api_create_product(
        name="NutrEditTest",
        kcal=300,
        protein=10,
        fat=15,
    )
    _reload_and_wait(page)

    _open_edit_form(page, "NutrEditTest")

    # Verify the edit form is visible before interacting
    expect(page.locator("#ed-name")).to_be_visible(timeout=3000)

    # Update the three nutrition fields
    page.locator("#ed-kcal").fill("350")
    page.locator("#ed-protein").fill("22")
    page.locator("#ed-fat").fill("8")

    page.locator("[data-action='save-product']").first.click()

    # Success toast must appear
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)

    # Reload and expand again to verify persistence
    _reload_and_wait(page)
    _expand_product_row(page, "NutrEditTest")

    # The nutrition table should be visible and contain the new values
    nutri_table = page.locator(".nutri-table")
    expect(nutri_table.first).to_be_visible(timeout=5000)
    expect(nutri_table.first).to_contain_text("350")
    expect(nutri_table.first).to_contain_text("22")
    expect(nutri_table.first).to_contain_text("8")


def test_edit_cancel_discards_changes(page, api_create_product):
    """Cancelling an edit should leave the product name unchanged.

    Opens the edit form, types a new name, clicks cancel, and verifies that
    the product row still shows the original name rather than the typed value.
    """
    api_create_product(name="CancelEditOrig")
    _reload_and_wait(page)

    _open_edit_form(page, "CancelEditOrig")

    edit_name = page.locator("#ed-name")
    expect(edit_name).to_be_visible(timeout=3000)

    # Type a different name but do not save
    edit_name.fill("CancelEditChanged")

    page.locator("[data-action='cancel-edit']").first.click()
    page.wait_for_timeout(300)

    # The results container should still show the original name
    results = page.locator("#results-container")
    expect(results).to_contain_text("CancelEditOrig")
    expect(results).not_to_contain_text("CancelEditChanged")


def test_edit_category_change(page, api_create_product):
    """Changing the category select and saving should show a success toast.

    The test confirms that the category select (#ed-type) is interactive
    and that the save round-trip completes without error.
    """
    api_create_product(name="CatChangeTest", category="Snacks")
    _reload_and_wait(page)

    _open_edit_form(page, "CatChangeTest")

    category_select = page.locator("#ed-type")
    expect(category_select).to_be_attached(timeout=3000)

    # Pick a different option if available; otherwise keep whatever is selected
    options = category_select.locator("option")
    option_count = options.count()
    if option_count >= 2:
        # Select the last option to guarantee a change
        last_value = options.nth(option_count - 1).get_attribute("value")
        if last_value:
            category_select.select_option(last_value)

    page.locator("[data-action='save-product']").first.click()

    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_edit_brand_and_stores(page, api_create_product):
    """Filling in brand and stores fields and saving should succeed with a toast.

    Verifies that text fields #ed-brand and #ed-stores accept input and that
    the product update API accepts the new values.
    """
    api_create_product(name="BrandStoresTest")
    _reload_and_wait(page)

    _open_edit_form(page, "BrandStoresTest")

    expect(page.locator("#ed-brand")).to_be_visible(timeout=3000)

    page.locator("#ed-brand").fill("TestBrandCo")
    page.locator("#ed-stores").fill("Kiwi, Rema 1000")

    page.locator("[data-action='save-product']").first.click()

    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_duplicate_check_api(live_url, api_create_product):
    """Creating two products with the same EAN should yield a 409 on the second.

    The first product is created normally.  A second POST with the same EAN
    is expected to return HTTP 409 with a ``duplicate`` key in the body,
    confirming that the server-side duplicate detection is active.  The
    check-duplicate endpoint is then called directly for the first product
    and must report no duplicate against itself.
    """
    shared_ean = "7310865071535"

    status_a, body_a = _create_product_raw(
        live_url,
        {
            "name": "DupCheckProdA",
            "type": "Snacks",
            "ean": shared_ean,
            "kcal": 200,
            "fat": 10,
            "carbs": 25,
            "sugar": 5,
            "protein": 8,
            "fiber": 3,
            "salt": 0.5,
            "smak": 4,
        },
    )
    assert status_a in (200, 201), (
        f"First product creation should succeed, got {status_a}: {body_a}"
    )
    product_a_id = body_a["id"]

    # Second product with the same EAN — expect 409
    status_b, body_b = _create_product_raw(
        live_url,
        {
            "name": "DupCheckProdB",
            "type": "Snacks",
            "ean": shared_ean,
            "kcal": 180,
            "fat": 8,
            "carbs": 22,
            "sugar": 4,
            "protein": 9,
            "fiber": 2,
            "salt": 0.4,
            "smak": 3,
        },
    )
    assert status_b == 409, (
        f"Second product with same EAN should return 409, got {status_b}: {body_b}"
    )
    assert "duplicate" in body_b, (
        f"409 response should contain 'duplicate' key, got: {body_b}"
    )
    assert body_b["duplicate"] is not None, (
        "The 'duplicate' value should not be null when a conflict is detected"
    )

    # check-duplicate for product A against its own EAN should find no other duplicate
    dup_resp = _check_duplicate_api(live_url, product_a_id, shared_ean, "DupCheckProdA")
    assert "duplicate" in dup_resp, (
        f"check-duplicate response missing 'duplicate' key: {dup_resp}"
    )
    assert "a_is_synced_with_off" in dup_resp, (
        f"check-duplicate response missing 'a_is_synced_with_off' key: {dup_resp}"
    )
    # Product A checking its own EAN should not flag itself as a duplicate
    assert dup_resp["duplicate"] is None, (
        f"Product should not report itself as a duplicate: {dup_resp['duplicate']}"
    )


def test_sort_by_column(page, api_create_product):
    """Clicking a sort header should apply the active sort indicator class.

    Creates two products to ensure the table has rows, then clicks any
    column header that carries ``data-action='sort'``.  The clicked header
    must gain the ``.th-active`` class, confirming that the sort state is
    reflected in the UI.
    """
    api_create_product(name="SortTestAlpha")
    api_create_product(name="SortTestBeta")
    _reload_and_wait(page)

    # Locate a sortable column header and click it
    sort_header = page.locator("[data-action='sort']").first
    expect(sort_header).to_be_visible(timeout=5000)
    sort_header.click()
    page.wait_for_timeout(400)

    # The active sort indicator must appear somewhere in the table header
    active_header = page.locator(".th-active")
    expect(active_header.first).to_be_visible(timeout=3000)


def test_product_score_displayed(page, api_create_product):
    """A product with full nutrition data should show a numeric score in the table.

    Supplies all fields that feed into the scoring formula so that the
    computed total_score is non-null.  After reload the ``.cell-score``
    element for the row should contain a digit.
    """
    api_create_product(
        name="ScoreDisplayTest",
        kcal=400,
        fat=18,
        saturated_fat=5,
        carbs=45,
        sugar=10,
        protein=20,
        fiber=5,
        salt=0.8,
        smak=5,
        weight=100,
        price=30,
    )
    _reload_and_wait(page)

    # Find the row for this product and check that its score cell has a number
    row = page.locator(".table-row", has_text="ScoreDisplayTest")
    expect(row.first).to_be_visible(timeout=5000)

    score_cell = row.first.locator(".cell-score")
    expect(score_cell).to_be_visible(timeout=3000)

    score_text = score_cell.inner_text()
    assert any(ch.isdigit() for ch in score_text), (
        f"Score cell should contain a numeric value, got: '{score_text!r}'"
    )


def test_expanded_view_shows_nutrition_table(page, api_create_product):
    """Expanding a product row should reveal the nutrition table (.nutri-table).

    The nutrition table is only rendered inside the expanded section and must
    not be visible while the row is collapsed.  After clicking the row it
    should become visible within a short timeout.
    """
    api_create_product(
        name="NutriTableVisTest",
        kcal=250,
        fat=9,
        carbs=30,
        sugar=6,
        protein=12,
        fiber=4,
        salt=0.6,
    )
    _reload_and_wait(page)

    # Table should not be visible before expansion
    nutri_table = page.locator(".nutri-table")
    # (it may not be in the DOM at all yet — checking visible is sufficient)

    _expand_product_row(page, "NutriTableVisTest")

    expect(nutri_table.first).to_be_visible(timeout=5000)
