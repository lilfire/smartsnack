"""E2E tests for error toasts, validation errors, and toast timing (P2 gaps #26-27).

Tests:
- Submitting the register form without a name shows an error toast
- The error toast has the 'error' CSS class applied
- A successful registration shows a toast with the 'success' CSS class
- Toasts auto-dismiss after the configured duration
- API returns JSON error body for missing required fields
- API returns 404 for nonexistent resources

None of these tests use window.showToast directly — all toasts are
triggered by real UI interactions.
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


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Validation error toast tests — triggered through real UI actions
# ---------------------------------------------------------------------------


def test_register_empty_name_shows_error_toast(page):
    """Submitting the register form without a name must show a visible error toast."""
    _go_to_register(page)

    # Leave name empty, fill only kcal, and submit
    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text()
    assert len(toast_text.strip()) > 0, (
        "Expected non-empty error toast text, got empty string"
    )


def test_register_empty_name_toast_has_error_class(page):
    """The toast shown for a missing name must have the 'error' CSS class."""
    _go_to_register(page)

    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    # state.js sets toast.className = 'toast ' + type + ' show'
    classes = toast.get_attribute("class") or ""
    assert "error" in classes, (
        f"Expected 'error' in toast class list, got: '{classes}'"
    )


def test_register_empty_name_toast_mentions_name(page):
    """The error toast for a missing name must reference the name field."""
    _go_to_register(page)

    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text().lower()
    # Norwegian: "Produktnavn er påkrevd", English: "Product name is required"
    assert "navn" in toast_text or "name" in toast_text or "required" in toast_text, (
        f"Expected name-related error in toast, got: '{toast_text}'"
    )


def test_successful_register_shows_success_toast(page):
    """A successful product registration must show a toast with the 'success' CSS class."""
    _go_to_register(page)

    page.locator("#f-name").fill("SuccessToastProdUnique")
    page.locator("#f-kcal").fill("150")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    classes = toast.get_attribute("class") or ""
    assert "success" in classes, (
        f"Expected 'success' in toast class list after registration, got: '{classes}'"
    )


def test_success_toast_contains_product_name(page):
    """The success toast after registration must contain the registered product name."""
    product_name = "ToastNameVerifyProd"
    _go_to_register(page)

    page.locator("#f-name").fill(product_name)
    page.locator("#f-kcal").fill("150")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    toast_text = toast.inner_text()
    assert product_name in toast_text, (
        f"Expected product name '{product_name}' in success toast, got: '{toast_text}'"
    )


def test_edit_empty_name_shows_error_toast(page, api_create_product):
    """Clearing the name field in edit mode and saving must show an error toast."""
    api_create_product(name="EditEmptyNameProd")
    _reload_and_wait(page)

    row = page.locator(".table-row", has_text="EditEmptyNameProd")
    row.first.click()
    page.wait_for_timeout(300)

    page.locator("[data-action='start-edit']").first.click()
    page.wait_for_timeout(500)

    page.locator("#ed-name").fill("")
    page.locator("[data-action='save-product']").first.click()
    page.wait_for_timeout(500)

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    classes = toast.get_attribute("class") or ""
    assert "error" in classes, (
        f"Expected 'error' class on toast for empty name save, got: '{classes}'"
    )


def test_toast_auto_dismiss_after_duration(page):
    """A toast triggered by a real action must disappear after its auto-dismiss timeout."""
    _go_to_register(page)

    page.locator("#f-name").fill("AutoDismissToastProd")
    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    # Confirm it appears first
    expect(toast).to_be_visible(timeout=5000)

    # state.js default duration is 3000ms; wait well beyond that
    page.wait_for_timeout(4500)

    # The toast must no longer have the 'show' class (auto-dismissed)
    classes = toast.get_attribute("class") or ""
    assert "show" not in classes, (
        f"Expected toast to be auto-dismissed after 4.5 s, but 'show' still in class: '{classes}'"
    )


def test_toast_has_aria_live_attribute(page):
    """The #toast element must have an aria-live attribute for screen readers."""
    _go_to_register(page)

    page.locator("#f-kcal").fill("100")
    page.locator("#btn-submit").click()

    toast = page.locator("#toast")
    expect(toast).to_be_visible(timeout=5000)

    # state.js sets aria-live='assertive' for errors, 'polite' for others
    aria_live = toast.get_attribute("aria-live")
    assert aria_live in ("assertive", "polite"), (
        f"Expected aria-live to be 'assertive' or 'polite', got: {aria_live!r}"
    )


# ---------------------------------------------------------------------------
# API error response tests
# ---------------------------------------------------------------------------


def test_api_missing_name_returns_400(live_url):
    """POST /api/products without a name must return HTTP 400 with a JSON error body."""
    payload = json.dumps({"kcal": 100}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/products",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("Expected a 400 error for missing name, but request succeeded")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400, f"Expected HTTP 400, got {exc.code}"
        body = json.loads(exc.read())
        assert "error" in body, (
            f"Expected 'error' key in 400 response body, got: {body}"
        )


def test_api_delete_nonexistent_product_returns_404(live_url):
    """DELETE /api/products/99999999 must return HTTP 404."""
    req = urllib.request.Request(
        f"{live_url}/api/products/99999999",
        method="DELETE",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("Expected 404 for nonexistent product, but request succeeded")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404, f"Expected HTTP 404, got {exc.code}"
