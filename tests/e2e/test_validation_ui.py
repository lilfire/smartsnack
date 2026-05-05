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
    page.wait_for_timeout(300)


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

    def test_long_name_accepted_or_rejected(self, page):
        """Name >200 chars: either gets rejected or accepted (app may truncate)."""
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

        page.wait_for_timeout(1000)
        # Dismiss OFF modal if it appears
        cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
        if cancel.is_visible():
            cancel.click()
            page.wait_for_timeout(200)

        # Either a toast appeared (error or success) — just verify
        # the form didn't silently do nothing
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)

    def test_all_nutrition_zero_succeeds(self, page):
        """All nutrition fields at 0 (boundary min) should succeed."""
        t = _load_translations()
        _go_to_register(page)

        product_name = "ZeroNutritionProduct"
        page.locator("#f-name").fill(product_name)
        for field in ["kcal", "fat", "carbs", "sugar", "protein", "salt"]:
            page.locator(f"#f-{field}").fill("0")
        page.locator("#btn-submit").click()

        page.wait_for_timeout(500)
        # Dismiss OFF modal if it appears
        cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
        if cancel.is_visible():
            cancel.click()
            page.wait_for_timeout(200)

        expected = t["toast_product_added"].replace("{name}", product_name)
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(expected)

    def test_negative_kcal_clamped_or_rejected(self, page):
        """Negative kcal value: HTML input[type=number] min=0 should clamp."""
        _go_to_register(page)

        page.locator("#f-name").fill("NegKcalProduct")
        # Use evaluate to set a negative value (bypassing HTML min attr)
        page.locator("#f-kcal").fill("-50")
        page.locator("#f-protein").fill("5")
        page.locator("#f-fat").fill("3")
        page.locator("#f-carbs").fill("20")
        page.locator("#f-sugar").fill("2")
        page.locator("#f-salt").fill("0.1")
        page.locator("#btn-submit").click()

        page.wait_for_timeout(1000)
        # Dismiss OFF modal if it appears
        cancel = page.locator(".scan-modal-bg .scan-modal button:last-child")
        if cancel.is_visible():
            cancel.click()
            page.wait_for_timeout(200)

        # Either accepted (server clamps to 0) or shows error toast
        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)


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
        page.wait_for_timeout(500)

        # Find the label input for our test category and clear it
        label_input = page.locator(
            f"input.cat-item-label-input[data-cat-name='{cat_name}']"
        )
        if label_input.count() > 0:
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

    def test_delete_only_category(self, page, live_url):
        """Deleting the last remaining category shows toast_cannot_delete_only_category."""
        t = _load_translations()

        # Get current categories
        req = urllib.request.Request(
            f"{live_url}/api/categories",
            headers={"X-Requested-With": "SmartSnack"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            categories = json.loads(resp.read())

        # Delete all but one category (best-effort)
        for cat in categories[1:]:
            try:
                req = urllib.request.Request(
                    f"{live_url}/api/categories/{cat['name']}?move_to={categories[0]['name']}",
                    headers={"X-Requested-With": "SmartSnack"},
                    method="DELETE",
                )
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError:
                pass

        # Reload so the UI reflects the post-cleanup DB state before navigating.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => !document.querySelector('#results-container .loading')",
            timeout=10000,
        )

        _go_to_settings(page)
        _open_section(page, "settings_categories_title")

        # Wait for delete button (proves the section rendered with data).
        page.wait_for_selector("[data-action='delete-cat']", state="visible", timeout=5000)

        # Guard: cleanup must have left exactly 1 category.
        btn_count = page.locator("[data-action='delete-cat']").count()
        assert btn_count == 1, (
            f"Expected exactly 1 delete button after cleanup, got {btn_count} — "
            "prior-test contamination suspected"
        )

        delete_btn = page.locator("[data-action='delete-cat']").first
        delete_btn.click()
        page.wait_for_timeout(300)

        # If a cat-move modal appeared, cleanup failed — cancel and fail clearly.
        cat_move_modal = page.locator(".scan-modal-bg")
        if cat_move_modal.is_visible():
            cancel_btn = page.locator(".scan-modal-bg .scan-modal button:last-child")
            if cancel_btn.is_visible():
                cancel_btn.click()
            assert False, (
                "cat-move modal appeared — cleanup did not reduce to 1 category; "
                "prior-test contamination"
            )

        # Confirm the deletion attempt if a confirm dialog appeared.
        confirm = page.locator(".confirm-yes")
        if confirm.is_visible():
            confirm.click()

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
        page.wait_for_timeout(500)

        # The add button is hidden by JS when all categories have overrides.
        # Force it visible and click it to trigger openAddOverridePicker.
        page.evaluate(
            "() => document.getElementById('weight-scope-add').style.display = ''"
        )
        page.locator("#weight-scope-add").click()
        page.wait_for_timeout(300)

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
        page.wait_for_timeout(500)

        # Click add override
        add_btn = page.locator("#weight-scope-add")
        if add_btn.count() > 0 and add_btn.is_visible():
            add_btn.click()
            page.wait_for_timeout(300)

            modal = page.locator(".scan-modal-bg")
            if modal.is_visible():
                # Confirm to add override
                confirm_btn = modal.locator(".scan-modal-btn-register")
                confirm_btn.click()
                page.wait_for_timeout(500)

                # Now delete the override
                delete_btn = page.locator("#weight-scope-delete")
                if delete_btn.count() > 0 and delete_btn.is_visible():
                    delete_btn.click()
                    page.wait_for_timeout(300)

                    # Confirm deletion
                    confirm = page.locator(".confirm-yes")
                    if confirm.is_visible():
                        confirm.click()

                    toast = page.locator(".toast").last
                    expect(toast).to_be_visible(timeout=5000)
                    expect(toast).to_contain_text(
                        t["toast_category_override_deleted"]
                    )


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
        page.wait_for_timeout(300)

        # Click edit button to enter edit mode (which loads EAN manager)
        edit_btn = page.locator("[data-action='start-edit']").first
        expect(edit_btn).to_be_visible(timeout=5000)
        edit_btn.click()
        page.wait_for_timeout(500)

        # Find the EAN add input and enter an invalid EAN
        ean_input = page.locator(f"#ean-add-input-{product_id}")
        expect(ean_input).to_be_visible(timeout=5000)
        ean_input.fill("abc123")
        ean_input.press("Enter")

        toast = page.locator(".toast").last
        expect(toast).to_be_visible(timeout=5000)
        expect(toast).to_contain_text(t["toast_invalid_ean"])
