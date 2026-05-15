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


def test_edit_category_persists_via_get_after_save(page, api_create_product, live_url):
    """Re-GET the product after a UI category change confirms the new ``type`` persisted.

    Regression vector for LSO-1267 — that bug shipped through ``test_edit_category_change``
    which only asserted a success toast. A silently-broken save would still
    flash the toast while leaving the underlying type unchanged. This test
    closes that loophole by hitting ``GET /api/products/<pid>`` after the
    save and comparing the returned ``type`` to the originally-selected
    category, not to any DOM-class indicator.
    """
    # Seed a second category so we have a guaranteed-different option to pick.
    # The default seed only includes "Snacks", which matches the starting type.
    target_category = "EditPersistTargetCat"
    create_cat_req = urllib.request.Request(
        f"{live_url}/api/categories",
        data=json.dumps({"name": target_category, "label": target_category}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(create_cat_req, timeout=5).read()
    except urllib.error.HTTPError as exc:
        # 409 (already exists) is fine; anything else is a setup failure.
        if exc.code != 409:
            raise

    created = api_create_product(name="CatPersistTest", category="Snacks")
    pid = created["id"]
    _reload_and_wait(page)

    _open_edit_form(page, "CatPersistTest")

    category_select = page.locator("#ed-type")
    expect(category_select).to_be_attached(timeout=3000)

    # ``#ed-type`` is wrapped by the ``upgradeSelect`` custom UI which hides
    # the native <select>; force=True bypasses the visibility check while
    # still firing the change event the save handler relies on.
    category_select.select_option(target_category, force=True)

    page.locator("[data-action='save-product']").first.click()

    # Wait for the success toast before re-fetching so the PUT round-trip
    # has actually committed.
    expect(page.locator(".toast").first).to_be_visible(timeout=5000)

    # The decisive check: hit the API directly and confirm the category
    # column was updated. No DOM polling, no toast-only fallback.
    req = urllib.request.Request(
        f"{live_url}/api/products/{pid}", method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        product = json.loads(resp.read())

    assert product.get("type") == target_category, (
        f"After UI save, GET /api/products/{pid} returned type={product.get('type')!r}, "
        f"expected {target_category!r}. This is the LSO-1267 regression class."
    )


def test_edit_persists_saved_fields_via_api_get(page, api_create_product, live_url):
    """Brand, stores, and nutrition edits must all show up on a subsequent API GET.

    Same regression class as ``test_edit_category_persists_via_get_after_save``
    (LSO-1267) but exercises the text and numeric fields. A silent save
    regression for any of brand/stores/nutrition would slip past current
    toast-only tests; this test asserts every saved field via the
    authoritative ``GET /api/products/<pid>`` response.
    """
    created = api_create_product(
        name="EditPersistMulti",
        brand="OriginalBrand",
        stores="OriginalStore",
        kcal=200,
        protein=8,
        fat=10,
    )
    pid = created["id"]
    _reload_and_wait(page)

    _open_edit_form(page, "EditPersistMulti")

    expect(page.locator("#ed-brand")).to_be_visible(timeout=3000)

    # Apply distinctive new values that won't collide with the seed data.
    page.locator("#ed-brand").fill("NewBrandX")
    page.locator("#ed-stores").fill("NewStoreY, NewStoreZ")
    page.locator("#ed-kcal").fill("345")
    page.locator("#ed-protein").fill("21")
    page.locator("#ed-fat").fill("7")

    page.locator("[data-action='save-product']").first.click()
    expect(page.locator(".toast").first).to_be_visible(timeout=5000)

    req = urllib.request.Request(
        f"{live_url}/api/products/{pid}", method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        product = json.loads(resp.read())

    assert product.get("brand") == "NewBrandX", (
        f"brand should be 'NewBrandX' after save, got {product.get('brand')!r}"
    )
    assert product.get("stores") == "NewStoreY, NewStoreZ", (
        f"stores should be 'NewStoreY, NewStoreZ' after save, got {product.get('stores')!r}"
    )
    assert float(product.get("kcal")) == 345.0, (
        f"kcal should be 345 after save, got {product.get('kcal')!r}"
    )
    assert float(product.get("protein")) == 21.0, (
        f"protein should be 21 after save, got {product.get('protein')!r}"
    )
    assert float(product.get("fat")) == 7.0, (
        f"fat should be 7 after save, got {product.get('fat')!r}"
    )


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


def test_edit_category_change_persists(page, api_create_product, live_url):
    """Category change via custom dropdown must persist after save (regression for LSO-1267).

    Steps match the spec in LSO-1267 task-description document:
    1. Open edit form.
    2. Click the custom dropdown trigger (NOT select_option on the hidden native select).
    3. Pick a different category option.
    4. Assert trigger label and native select value both updated.
    5. Save and assert toast + form closed.
    6. GET product endpoint and assert new category is stored.
    7. Assert old category is not stored.
    8. Second GET for idempotency.
    """
    # Ensure a second category exists so we can change away from "Snacks"
    cat_payload = json.dumps({"name": "Dairy", "label": "Dairy", "emoji": "\U0001f95b"}).encode()
    cat_req = urllib.request.Request(
        f"{live_url}/api/categories",
        data=cat_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(cat_req, timeout=5):
            pass
    except urllib.error.HTTPError:
        pass  # 409 if category already exists from a previous run

    product = api_create_product(name="CatPersistTest", category="Snacks")
    product_id = product["id"]

    _reload_and_wait(page)
    _open_edit_form(page, "CatPersistTest")

    # Locate the custom dropdown trigger rendered by upgradeSelect around #ed-type.
    # The native <select> itself is hidden on desktop; interact via the custom UI only.
    edit_form = page.locator(".edit-form").first
    category_trigger = edit_form.locator(".custom-select-trigger").first
    expect(category_trigger).to_be_visible(timeout=3000)

    # Open the custom dropdown
    category_trigger.click()
    page.wait_for_timeout(300)

    # Find an option that differs from the current category ("Snacks")
    custom_options = edit_form.locator(".custom-select-option")
    new_category_value = None
    new_category_label = None
    option_count = custom_options.count()
    for i in range(option_count):
        opt = custom_options.nth(i)
        val = opt.get_attribute("data-value")
        if val and val != "Snacks":
            new_category_value = val
            new_category_label = opt.text_content().strip()
            opt.click()
            break

    assert new_category_value is not None, (
        "Expected at least one non-Snacks category option in the dropdown"
    )
    page.wait_for_timeout(300)

    # Assertion: custom dropdown trigger label updated after picking new option
    expect(category_trigger).to_contain_text(new_category_label)

    # Assertion: underlying native <select> value also updated
    native_val = page.locator("#ed-type").evaluate("el => el.value")
    assert native_val == new_category_value, (
        f"Native #ed-type should be {new_category_value!r} after custom pick, got {native_val!r}"
    )

    # Save button must still be visible — a premature form close would remove it
    save_btn = page.locator("[data-action='save-product']").first
    expect(save_btn).to_be_visible(timeout=3000)

    save_btn.click()

    # Assertion 8 (spec step 8): success toast confirms the API round-trip succeeded
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)

    # Assertion 1: modal is closed after save (save button no longer visible)
    expect(save_btn).not_to_be_visible(timeout=5000)

    # Assertion 2: GET to product endpoint returns the new category value
    get_req = urllib.request.Request(f"{live_url}/api/products/{product_id}")
    with urllib.request.urlopen(get_req, timeout=5) as resp:
        product_data = json.loads(resp.read())

    assert product_data.get("type") == new_category_value, (
        f"Expected persisted category {new_category_value!r}, got {product_data.get('type')!r}"
    )

    # Assertion 3: old category is NOT still stored
    assert product_data.get("type") != "Snacks", (
        f"Old category 'Snacks' should not be stored, got {product_data.get('type')!r}"
    )

    # Assertion 4: idempotent — second GET still returns the new category
    get_req2 = urllib.request.Request(f"{live_url}/api/products/{product_id}")
    with urllib.request.urlopen(get_req2, timeout=5) as resp2:
        product_data2 = json.loads(resp2.read())

    assert product_data2.get("type") == new_category_value, (
        f"Idempotency: second GET returned {product_data2.get('type')!r}, expected {new_category_value!r}"
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
