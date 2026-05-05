"""E2E tests for the OFF add-product review modal (P0 gap #6).

After a product is registered with a valid EAN the app calls showConfirmModal()
asking the user "Add to OpenFoodFacts?".  Clicking Yes opens the OFF review
modal (off-review.js / #off-add-review-bg) which shows a summary of the filled
and empty fields and a Submit button.

All calls to external APIs (/api/off/add-product) are intercepted with
page.route() so the tests are fully deterministic and do not require a real
OFF account.
"""

import json

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _fill_product_form(page, name="ReviewTestProd", ean="7310865004703"):
    """Fill the register form with the minimum data needed to pass validation."""
    page.locator("#f-name").fill(name)
    if ean:
        page.locator("#f-ean").fill(ean)
    page.locator("#f-kcal").fill("150")
    page.locator("#f-protein").fill("10")
    page.locator("#f-fat").fill("5")


def _intercept_off_add_product(page, response_body=None):
    """Route POST /api/off/add-product to return a controlled response."""
    body = response_body if response_body is not None else {"ok": True}

    def _handler(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/off/add-product", _handler)


def _register_and_accept_off_prompt(page):
    """Submit the register form and click Yes on the 'Add to OFF?' confirm
    modal.  Returns when the OFF review modal is expected to be visible."""
    # Intercept the add-product API so submit does not hit a real server.
    _intercept_off_add_product(page)

    page.locator("#btn-submit").click()

    # The confirm modal (showConfirmModal) uses .scan-modal-bg and
    # .confirm-yes / .confirm-no buttons.
    confirm_bg = page.locator(".scan-modal-bg[role='dialog']")
    expect(confirm_bg).to_be_visible(timeout=5000)

    yes_btn = page.locator(".confirm-yes")
    expect(yes_btn).to_be_visible(timeout=3000)
    yes_btn.click()


# ---------------------------------------------------------------------------
# Tests: OFF prompt appears after registration
# ---------------------------------------------------------------------------


def test_register_product_with_ean_shows_off_confirm_prompt(page):
    """After registering a product with a valid EAN the app must present a
    confirm modal asking whether to add the product to OpenFoodFacts."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFPromptTestProd", ean="7310865004703")

    page.locator("#btn-submit").click()

    # A confirm modal must appear
    confirm_bg = page.locator(".scan-modal-bg[role='dialog']")
    expect(confirm_bg).to_be_visible(timeout=5000)

    # It must contain both a confirm (Yes) and a cancel (No) button
    expect(page.locator(".confirm-yes")).to_be_visible(timeout=3000)
    expect(page.locator(".confirm-no")).to_be_visible(timeout=3000)


def test_register_product_without_ean_no_off_prompt(page):
    """Registering a product without an EAN must NOT show the OFF prompt
    because the product cannot be identified on OFF."""
    _go_to_register(page)
    _fill_product_form(page, name="NoEanProd", ean="")

    page.locator("#btn-submit").click()

    # The confirm modal must not appear (no EAN, no OFF prompt)
    confirm_bg = page.locator(".scan-modal-bg[role='dialog']")
    expect(confirm_bg).to_be_hidden(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: OFF review modal content
# ---------------------------------------------------------------------------


def test_off_review_modal_appears_after_yes(page):
    """Clicking Yes on the OFF prompt must open the OFF review modal."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFReviewProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)


def test_off_review_modal_shows_ean(page):
    """The review modal must display the EAN of the product being submitted."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFEanDisplayProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)
    expect(review_bg).to_contain_text("7310865004703", timeout=3000)


def test_off_review_modal_shows_filled_fields_section(page):
    """The review modal must display a 'filled' section listing at least
    the product name (which was provided)."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFFilledSectionProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)

    # The filled-fields section header is rendered from the t('off_review_filled')
    # translation key; the product name 'OFFFilledSectionProd' must appear in
    # the modal body regardless of the language string used for the header.
    expect(review_bg).to_contain_text("OFFFilledSectionProd", timeout=3000)


def test_off_review_modal_submit_button_present_when_name_filled(page):
    """When the product name is provided the submit button must be present and
    not visually disabled (pointer-events: none indicates disabled state)."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFSubmitEnabledProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)

    submit_btn = page.locator("#off-submit-btn")
    expect(submit_btn).to_be_visible(timeout=3000)

    # When a name is provided the button must NOT carry the disabled styling
    # (off-review.js sets pointer-events:none when hasName is false).
    pointer_events = submit_btn.evaluate(
        "el => window.getComputedStyle(el).pointerEvents"
    )
    assert pointer_events != "none", (
        f"Expected submit button to be interactive, but pointer-events is '{pointer_events}'"
    )


# ---------------------------------------------------------------------------
# Tests: OFF review modal cancel behaviour
# ---------------------------------------------------------------------------


def test_off_review_cancel_closes_modal(page):
    """Clicking the Cancel button in the review modal must remove the modal
    from the DOM."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFCancelProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)

    # The cancel button is a .btn-off element; its text comes from t('btn_cancel')
    cancel_btn = page.locator("#off-add-review-bg .btn-off")
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()

    expect(review_bg).to_be_hidden(timeout=3000)


def test_off_review_close_button_dismisses_modal(page):
    """Clicking the × close button at the top of the review modal must
    remove the modal from the DOM."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFCloseXProd", ean="7310865004703")
    _register_and_accept_off_prompt(page)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)

    close_btn = page.locator("#off-add-review-bg .off-modal-close")
    expect(close_btn).to_be_visible(timeout=3000)
    close_btn.click()

    expect(review_bg).to_be_hidden(timeout=3000)


def test_off_confirm_no_skips_review_modal(page):
    """Clicking No on the OFF confirm prompt must NOT open the review modal."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFDeclineProd", ean="7310865004703")

    page.locator("#btn-submit").click()

    confirm_bg = page.locator(".scan-modal-bg[role='dialog']")
    expect(confirm_bg).to_be_visible(timeout=5000)

    no_btn = page.locator(".confirm-no")
    expect(no_btn).to_be_visible(timeout=3000)
    no_btn.click()

    # Confirm modal must close
    expect(confirm_bg).to_be_hidden(timeout=3000)

    # Review modal must NOT appear
    expect(page.locator("#off-add-review-bg")).to_be_hidden(timeout=2000)


# ---------------------------------------------------------------------------
# Tests: submit flow via review modal
# ---------------------------------------------------------------------------


def test_off_review_submit_calls_api_and_closes_modal(page):
    """Clicking Submit in the review modal must POST to /api/off/add-product
    and then close both the review modal and the picker."""
    _go_to_register(page)
    _fill_product_form(page, name="OFFSubmitFlowProd", ean="7310865004703")

    submitted_payloads = []

    def _add_product_handler(route):
        submitted_payloads.append(json.loads(route.request.post_data))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"ok": True}),
        )

    # Open the review modal first; _register_and_accept_off_prompt also
    # installs a route handler for /api/off/add-product.  Register our
    # capturing handler AFTER it so that Playwright's LIFO route ordering
    # ensures our handler is invoked when Submit is clicked.
    _register_and_accept_off_prompt(page)
    page.route("**/api/off/add-product", _add_product_handler)

    review_bg = page.locator("#off-add-review-bg")
    expect(review_bg).to_be_visible(timeout=5000)

    submit_btn = page.locator("#off-submit-btn")
    expect(submit_btn).to_be_visible(timeout=3000)
    submit_btn.click()

    # Review modal must close after a successful submission
    expect(review_bg).to_be_hidden(timeout=5000)

    # The API must have been called with the EAN
    assert len(submitted_payloads) == 1, (
        f"Expected 1 POST to /api/off/add-product, got {len(submitted_payloads)}"
    )
    assert submitted_payloads[0].get("code") == "7310865004703", (
        f"Expected code=7310865004703 in payload, got: {submitted_payloads[0]}"
    )
