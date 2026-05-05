"""Test category management via API and UI."""

import json
import urllib.request
import urllib.error

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Navigation helpers (mirrors test_settings.py conventions)
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    """Open a settings section by its data-i18n key."""
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# API helper
# ---------------------------------------------------------------------------


def _api(live_url, path, *, method="GET", body=None):
    """Make a JSON API request and return the parsed response body.

    Args:
        live_url: Base URL of the running server.
        path: URL path, e.g. ``"/api/categories"``.
        method: HTTP method string.
        body: Optional dict that will be JSON-encoded as the request body.

    Returns:
        Parsed JSON response as a Python object.
    """
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _api_raw(live_url, path, *, method="GET", body=None):
    """Like ``_api`` but also returns the HTTP status code.

    Returns:
        Tuple of ``(status_code, parsed_body)``.
    """
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def test_categories_api_list(live_url):
    """GET /api/categories should return a list that includes seed categories.

    The seed data in db.py inserts a ``"Snacks"`` category, so at minimum
    that entry must appear in the response.
    """
    cats = _api(live_url, "/api/categories")

    assert isinstance(cats, list), "Response should be a list"
    assert len(cats) >= 1, "Should have at least one seed category"

    names = [c["name"] for c in cats]
    assert "Snacks" in names, "Seed category 'Snacks' should be present"

    # Verify the shape of each item
    for cat in cats:
        assert "name" in cat, "Each category should have a 'name' key"
        assert "label" in cat, "Each category should have a 'label' key"
        assert "emoji" in cat, "Each category should have an 'emoji' key"
        assert "count" in cat, "Each category should have a 'count' key"
        assert isinstance(cat["count"], int), "'count' should be an integer"


def test_categories_api_add_and_delete(live_url):
    """POST a new category, confirm it appears in GET, then DELETE it.

    Uses unique names per run to avoid state pollution from other tests.
    """
    cat_name = "e2eapitestcat"
    cat_label = "E2E API Test Cat"
    cat_emoji = "\U0001f9ea"  # test tube

    # Clean up any leftover from a previous run (best-effort)
    _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")

    # Create
    status, body = _api_raw(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": cat_name, "label": cat_label, "emoji": cat_emoji},
    )
    assert status == 201, f"Expected 201 Created, got {status}: {body}"
    assert body.get("ok") is True

    # Verify it appears in the list
    cats = _api(live_url, "/api/categories")
    names = [c["name"] for c in cats]
    assert cat_name in names, f"Newly created category '{cat_name}' not found in GET"

    # Delete it
    status, body = _api_raw(
        live_url,
        f"/api/categories/{cat_name}",
        method="DELETE",
    )
    assert status == 200, f"Expected 200 on DELETE, got {status}: {body}"
    assert body.get("ok") is True

    # Confirm it is gone
    cats = _api(live_url, "/api/categories")
    names = [c["name"] for c in cats]
    assert cat_name not in names, f"Deleted category '{cat_name}' still appears in GET"


# ---------------------------------------------------------------------------
# UI tests
# ---------------------------------------------------------------------------


def test_category_label_edit_via_ui(live_url, page):
    """Editing a category label input and triggering change should show a toast.

    Creates a fresh category via the API so the test is self-contained, then
    navigates to Settings > Categories and changes the label input.
    """
    cat_name = "e2elabeleditcat"
    cat_label = "Label Edit Cat"

    # Clean up any leftover, then create
    _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")
    _api_raw(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": cat_name, "label": cat_label, "emoji": "\U0001f4dd"},
    )

    try:
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        # Wait for loadCategories() to finish and populate items (the container
        # becomes visible before the async fetch completes)
        page.wait_for_selector("#cat-list .cat-item", state="visible", timeout=8000)

        # Find the label input for our category
        label_input = page.locator(
            f"input.cat-item-label-input[data-cat-name='{cat_name}']"
        )
        expect(label_input).to_be_visible(timeout=5000)

        # Change the value and trigger the change event
        label_input.fill("Label Edit Cat Updated")
        label_input.dispatch_event("change")

        # A success toast should appear
        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    finally:
        # Clean up
        _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")


def test_delete_empty_category_via_ui(live_url, page):
    """Deleting a category with no products via the UI should show a toast.

    Creates an empty category via the API, navigates to Settings > Categories,
    clicks the delete button, confirms in the modal, and checks for a toast.
    """
    cat_name = "e2edelemptycat"
    cat_label = "Empty Delete Cat"

    # Clean up any leftover, then create
    _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")
    _api_raw(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": cat_name, "label": cat_label, "emoji": "\U0001f5d1"},
    )

    _go_to_settings(page)
    _open_section(page, "settings_categories_title")

    # Wait for the category list to render
    expect(page.locator("#cat-list")).to_be_visible()

    # Click the delete button for our category (count = 0, no reassign modal)
    delete_btn = page.locator(
        f"[data-action='delete-cat'][data-cat-name='{cat_name}']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()

    # Confirm in the generic confirmation modal
    confirm_btn = page.locator(".confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=5000)
    confirm_btn.click()

    # A success toast should appear
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_delete_category_with_products_shows_reassign(live_url, page, api_create_product):
    """Deleting a non-empty category should show the reassignment modal.

    Creates a product in a fresh category, then opens Settings > Categories
    and verifies that clicking delete surfaces ``.cat-move-modal`` instead of
    the plain confirm dialog.
    """
    cat_name = "e2ereassigncat"
    cat_label = "Reassign Cat"

    # Clean up, then create the category and a product inside it
    _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")
    _api_raw(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": cat_name, "label": cat_label, "emoji": "\U0001f4e6"},
    )
    api_create_product(name="ReassignTestProd", category=cat_name)

    _go_to_settings(page)
    _open_section(page, "settings_categories_title")

    # Wait for the category list to render
    expect(page.locator("#cat-list")).to_be_visible()

    # Click delete on the category that has products
    delete_btn = page.locator(
        f"[data-action='delete-cat'][data-cat-name='{cat_name}']"
    )
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()

    # The reassignment modal should appear (not the plain confirm modal)
    reassign_modal = page.locator(".cat-move-modal")
    expect(reassign_modal).to_be_visible(timeout=5000)


def test_category_filter_pills_filter_products(live_url, page, api_create_product):
    """Clicking a category filter pill should filter products to that category.

    Creates products in two different categories, opens the filter row,
    clicks the pill for one category, and verifies only its products remain.
    """
    cat_name = "e2epillcat"
    cat_label = "Pill Filter Cat"

    # Ensure category exists
    _api_raw(live_url, f"/api/categories/{cat_name}", method="DELETE")
    _api_raw(
        live_url,
        "/api/categories",
        method="POST",
        body={"name": cat_name, "label": cat_label, "emoji": "\U0001f48a"},
    )

    # Create one product in the custom category and one in the default
    api_create_product(name="PillCatProduct", category=cat_name)
    api_create_product(name="SnacksPillProduct", category="Snacks")

    # Reload the search view so the new products are listed
    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    # Open the filter row
    filter_toggle = page.locator("#filter-toggle")
    expect(filter_toggle).to_be_visible()
    filter_toggle.click()

    filter_row = page.locator("#filter-row")
    expect(filter_row).to_be_visible(timeout=5000)

    # Find and click the pill for our custom category
    # Pills are built as <button class="pill"> with the category label text
    pill = filter_row.locator("button.pill", has_text=cat_label)
    expect(pill).to_be_visible(timeout=5000)
    pill.click()

    # Wait for debounce / re-render
    page.wait_for_timeout(500)

    results = page.locator("#results-container")
    # Product in the filtered category should be visible
    expect(results).to_contain_text("PillCatProduct")
    # Product in a different category should not appear
    expect(results).not_to_contain_text("SnacksPillProduct")
