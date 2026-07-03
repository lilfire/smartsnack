"""Task 3: Validation error edge cases in the UI.

Tests browser-triggered validation errors for the register form,
settings (categories, flags, protein quality, weights), and EAN manager.
All expected strings loaded from translation files — no hardcoded text.
"""

import json
import os
import re
import urllib.error
import urllib.request

from playwright.sync_api import expect


def _load_translations(lang="no"):
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "translations", f"{lang}.json"
    )
    with open(path) as f:
        return json.load(f)


def _go_to_register(page):
    page.locator("button[data-view='register']").click()
    expect(page.locator("#view-register")).to_be_visible()


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, i18n_key):
    toggle = page.locator(
        f".settings-toggle:has(span[data-i18n='{i18n_key}'])"
    ).first
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true", timeout=5000)


# ---------------------------------------------------------------------------
# Register form validation
# ---------------------------------------------------------------------------


class TestRegisterValidation:
    """Validation error edge cases for the product registration form."""

    def test_empty_name_shows_toast(self, page):
        """Submit with empty name shows toast_product_name_required."""
        t = _load_translations()
        _go_to_register(page)

        page.locator("#f-name").fill("")
        page.locator("#f-kcal").fill("100")
        page.locator("#btn-submit").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_product_name_required"])

    def test_invalid_ean_shows_toast(self, page):
        """Submit with invalid EAN shows toast_invalid_ean."""
        t = _load_translations()
        _go_to_register(page)

        page.locator("#f-name").fill("ValidName")
        page.locator("#f-ean").fill("abc123")
        page.locator("#btn-submit").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_invalid_ean"])

    def test_long_name_rejected(self, page, live_url):
        """Name >200 chars is rejected: server returns 400, error toast
        shows the server message, and no product is created.

        Backend pins this via _TEXT_FIELD_LIMITS["name"] == 200 in
        services/product_crud.py (ValueError -> HTTP 400).
        """
        _go_to_register(page)

        long_name = "A" * 201
        page.locator("#f-name").fill(long_name)
        page.locator("#f-kcal").fill("100")
        page.locator("#f-protein").fill("5")
        page.locator("#f-fat").fill("3")
        page.locator("#f-carbs").fill("20")
        page.locator("#f-sugar").fill("2")
        page.locator("#f-salt").fill("0.1")
        page.locator("#btn-submit").click()

        # products.js surfaces the server error message in an error toast.
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text("exceeds max length")

        # The product must NOT have been persisted.
        req = urllib.request.Request(
            f"{live_url}/api/products?search={'A' * 30}",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["products"] == [], (
            "Product with >200-char name must be rejected, but was persisted"
        )

    def test_all_nutrition_zero_succeeds(self, page):
        """All nutrition fields at 0 (boundary min) should succeed."""
        t = _load_translations()
        _go_to_register(page)

        product_name = "ZeroNutritionProduct"
        page.locator("#f-name").fill(product_name)
        for field in ["kcal", "fat", "carbs", "sugar", "protein", "salt"]:
            page.locator(f"#f-{field}").fill("0")
        page.locator("#btn-submit").click()

        # Wait until the submit handler surfaces either the success toast or a
        # modal (duplicate/OFF prompt) — whichever the app shows first.
        page.wait_for_selector("#toast.show, .scan-modal-bg", state="visible", timeout=5000)
        # Dismiss OFF modal if it appears
        cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
        if cancel.is_visible():
            cancel.click()
            expect(cancel).to_be_hidden(timeout=3000)

        expected = t["toast_product_added"].replace("{name}", product_name)
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(expected)

    def test_negative_kcal_accepted_stored_verbatim(self, page, live_url):
        """Negative kcal is accepted and stored verbatim (no clamping).

        Pins current backend behavior: helpers._num applies no minimum
        bound, so -50 round-trips unchanged and registration succeeds
        with the standard success toast.
        """
        t = _load_translations()
        _go_to_register(page)

        product_name = "NegKcalProduct"
        page.locator("#f-name").fill(product_name)
        # fill() sets the value programmatically, bypassing the HTML min attr
        page.locator("#f-kcal").fill("-50")
        page.locator("#f-protein").fill("5")
        page.locator("#f-fat").fill("3")
        page.locator("#f-carbs").fill("20")
        page.locator("#f-sugar").fill("2")
        page.locator("#f-salt").fill("0.1")
        page.locator("#btn-submit").click()

        expected = t["toast_product_added"].replace("{name}", product_name)
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(expected)

        # The stored product must carry the negative value unchanged.
        req = urllib.request.Request(
            f"{live_url}/api/products?search={product_name}",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        matching = [p for p in data["products"] if p["name"] == product_name]
        assert len(matching) == 1, f"Expected 1 stored product, got {len(matching)}"
        assert matching[0]["kcal"] == -50.0


# ---------------------------------------------------------------------------
# Settings — Categories validation
# ---------------------------------------------------------------------------


class TestCategoryValidation:
    """Validation errors when adding/deleting categories."""

    def test_empty_name_and_label(self, page):
        """Add category with empty name and label shows toast_name_display_required."""
        t = _load_translations()
        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        page.locator("#cat-name").fill("")
        page.locator("#cat-label").fill("")
        page.locator("button[data-i18n='btn_add_category']").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_name_display_required"])

    def test_empty_display_name(self, page, live_url):
        """Update category display name to empty shows toast_display_name_empty."""
        t = _load_translations()

        # Create a test category via API
        cat_name = "valtest_cat"
        cat_label = "ValTestCat"
        try:
            data = json.dumps({"name": cat_name, "label": cat_label}).encode()
            req = urllib.request.Request(
                f"{live_url}/api/categories",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "SmartSnack",
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError:
            pass  # may already exist

        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        # Find the label input for our test category and clear it
        label_input = page.locator(
            f"input.cat-item-label-input[data-cat-name='{cat_name}']"
        )
        expect(label_input).to_be_visible(timeout=5000)
        label_input.fill("")
        label_input.dispatch_event("change")

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_display_name_empty"])

        # Cleanup
        try:
            req = urllib.request.Request(
                f"{live_url}/api/categories/{cat_name}",
                headers={"X-Requested-With": "SmartSnack"},
                method="DELETE",
            )
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError:
            pass

    def test_delete_only_category(self, page, live_url, api_create_product):
        """Deleting the last remaining category shows toast_cannot_delete_only_category.

        The JS delete path that shows this toast only fires when the category
        has products (count > 0) AND there are no other categories to move
        them to.  We seed one product via api_create_product so we hit that
        path.  reset_db guarantees exactly 1 category ("Snacks"), so
        ``others.length == 0`` and the toast fires without the cat-move modal.
        """
        t = _load_translations()

        # Seed one product so the category has count > 0.  The "has products"
        # delete path checks for other categories; finding none, it shows
        # toast_cannot_delete_only_category and returns without a modal.
        api_create_product(name="OnlyCategory_TestProduct")

        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        # reset_db guarantees exactly 1 category ("Snacks" seed).
        page.wait_for_selector("[data-action='delete-cat']", state="visible", timeout=5000)
        btn_count = page.locator("[data-action='delete-cat']").count()
        assert btn_count == 1, (
            f"Expected exactly 1 delete button (reset_db should guarantee the "
            f"seed state), got {btn_count}. Check that reset_db ran correctly."
        )

        delete_btn = page.locator("[data-action='delete-cat']").first
        delete_btn.click()
        # The toast signals the delete handler finished; only after it shows
        # can we assert the cat-move modal never appeared.
        expect(page.locator(".toast").last).to_be_visible(timeout=5000)

        # With only one category there is nowhere to move products — the
        # cat-move modal must NOT appear.  Use the unique .cat-move-modal-bg
        # class (not .scan-modal-bg, which is also used by confirm dialogs).
        cat_move_modal = page.locator(".cat-move-modal-bg")
        assert not cat_move_modal.is_visible(), (
            "cat-move modal appeared unexpectedly when deleting the only category"
        )

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_cannot_delete_only_category"])


# ---------------------------------------------------------------------------
# Settings — Flags validation
# ---------------------------------------------------------------------------


class TestFlagValidation:
    """Validation errors when adding flags."""

    def test_empty_flag_name(self, page):
        """Add flag with empty name shows toast_name_display_required."""
        t = _load_translations()
        _go_to_settings(page)
        _open_section(page, "settings_flags_title")

        page.locator("#flag-add-name").fill("")
        page.locator("#flag-add-label").fill("")
        page.locator("button[data-i18n='btn_add_flag']").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_name_display_required"])


# ---------------------------------------------------------------------------
# Settings — Protein Quality validation
# ---------------------------------------------------------------------------


class TestProteinQualityValidation:
    """Validation errors when adding protein quality sources."""

    def test_pq_no_keywords(self, page):
        """Add PQ source with no keywords shows toast_pq_keywords_required."""
        t = _load_translations()
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")

        page.locator("#pq-add-label").fill("TestSource")
        page.locator("#pq-add-kw").fill("")
        page.locator("#pq-add-pdcaas").fill("0.8")
        page.locator("#pq-add-diaas").fill("0.9")
        page.locator("button[data-i18n='btn_add_protein_source']").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_pq_keywords_required"])


# ---------------------------------------------------------------------------
# Settings — Weights: category overrides
# ---------------------------------------------------------------------------


class TestWeightOverrideValidation:
    """Validation for weight category override add/delete."""

    def test_no_categories_without_overrides(self, page, live_url):
        """When all categories have overrides, calling openAddOverridePicker
        shows toast_no_categories_without_overrides."""
        t = _load_translations()

        # Get all categories and add weight overrides to each via API
        req = urllib.request.Request(
            f"{live_url}/api/categories",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            categories = json.loads(resp.read())

        # Get global weights to use as override template
        req = urllib.request.Request(
            f"{live_url}/api/weights",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            weights = json.loads(resp.read())

        # Add overrides for every category
        for cat in categories:
            override_payload = [
                {
                    "field": w["field"],
                    "is_overridden": True,
                    "enabled": w.get("enabled", True),
                    "weight": w.get("weight", 100),
                    "direction": w.get("direction", "lower"),
                    "formula": w.get("formula", "minmax"),
                    "formula_min": w.get("formula_min", 0),
                    "formula_max": w.get("formula_max", 100),
                }
                for w in weights
            ]
            data = json.dumps(override_payload).encode()
            req = urllib.request.Request(
                f"{live_url}/api/categories/{cat['name']}/weights",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "SmartSnack",
                },
                method="PUT",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError:
                pass

        _go_to_settings(page)
        _open_section(page, "settings_weights_title")

        # Wait for weight items to load (async)
        page.wait_for_selector("#weight-items .weight-item", timeout=10000)
        # updateScopeButtons() hides the add button once it sees that all
        # categories have overrides — wait for that render to complete.
        expect(page.locator("#weight-scope-add")).to_be_hidden(timeout=5000)

        # The add button is hidden by JS when all categories have overrides.
        # Force it visible and click it to trigger openAddOverridePicker.
        page.evaluate(
            "() => document.getElementById('weight-scope-add').style.display = ''"
        )
        page.locator("#weight-scope-add").click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(
            t["toast_no_categories_without_overrides"]
        )

        # Cleanup: remove overrides
        for cat in categories:
            clear_payload = [
                {
                    "field": w["field"],
                    "is_overridden": False,
                    "enabled": w.get("enabled", True),
                    "weight": w.get("weight", 100),
                    "direction": w.get("direction", "lower"),
                    "formula": w.get("formula", "minmax"),
                    "formula_min": w.get("formula_min", 0),
                    "formula_max": w.get("formula_max", 100),
                }
                for w in weights
            ]
            data = json.dumps(clear_payload).encode()
            req = urllib.request.Request(
                f"{live_url}/api/categories/{cat['name']}/weights",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "SmartSnack",
                },
                method="PUT",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError:
                pass

    def test_delete_category_override(self, page, live_url):
        """Add then delete a category override shows toast_category_override_deleted."""
        t = _load_translations()

        # Ensure we have at least 2 categories so we can add an override
        cats_req = urllib.request.Request(
            f"{live_url}/api/categories",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(cats_req, timeout=5) as resp:
            categories = json.loads(resp.read())

        if len(categories) < 2:
            # Create a second category
            data = json.dumps({"name": "override_test", "label": "Override Test"}).encode()
            req = urllib.request.Request(
                f"{live_url}/api/categories",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "SmartSnack",
                },
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError:
                pass

        _go_to_settings(page)
        _open_section(page, "settings_weights_title")
        # Wait for weight items to load (async)
        page.wait_for_selector("#weight-items .weight-item", timeout=10000)

        # Add an override: pick a category in the picker modal and confirm
        add_btn = page.locator("#weight-scope-add")
        expect(add_btn).to_be_visible(timeout=5000)
        add_btn.click()

        modal = page.locator(".scan-modal-bg")
        expect(modal).to_be_visible(timeout=5000)
        modal.locator(".scan-modal-btn-register").click()
        expect(modal).to_be_hidden(timeout=5000)

        # Now delete the override
        delete_btn = page.locator("#weight-scope-delete")
        expect(delete_btn).to_be_visible(timeout=5000)
        delete_btn.click()

        # Confirm deletion in the confirm dialog
        confirm = page.locator(".confirm-yes")
        expect(confirm.first).to_be_visible(timeout=5000)
        confirm.first.click()

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_category_override_deleted"])


# ---------------------------------------------------------------------------
# EAN Manager validation
# ---------------------------------------------------------------------------


class TestEanManagerValidation:
    """Validation errors in the EAN manager (expanded product view)."""

    def test_invalid_ean_in_manager(self, page, api_create_product):
        """Adding an invalid EAN in the manager shows toast_invalid_ean."""
        t = _load_translations()

        # Create a product to expand
        product_name = "EanValTestProduct"
        result = api_create_product(name=product_name)
        product_id = result["id"]

        # Reload page to see the new product
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        # Click on the product row to expand it
        row = page.locator(".table-row", has_text=product_name).first
        row.click()

        # Click edit button to enter edit mode (which loads EAN manager)
        edit_btn = page.locator("[data-action='start-edit']").first
        expect(edit_btn).to_be_visible(timeout=5000)
        edit_btn.click()

        # Find the EAN add input and enter an invalid EAN
        ean_input = page.locator(f"#ean-add-input-{product_id}")
        expect(ean_input).to_be_visible(timeout=5000)
        ean_input.fill("abc123")
        ean_input.press("Enter")

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_invalid_ean"])
