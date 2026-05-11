"""Tests for OFF language priority API and field selection (LSO-569)."""

import json
import pytest


class TestGetOffLanguagePriority:
    def test_default_returns_current_language(self, app_ctx):
        from services.settings_service import get_off_language_priority

        result = get_off_language_priority()
        assert result == ["no"]  # default language is "no"

    def test_default_follows_current_language(self, app_ctx):
        from services.settings_service import set_language, get_off_language_priority

        set_language("en")
        result = get_off_language_priority()
        assert result == ["en"]

    def test_returns_stored_value(self, app_ctx):
        from services.settings_service import set_off_language_priority, get_off_language_priority

        set_off_language_priority(["en", "no", "fr"])
        result = get_off_language_priority()
        assert result == ["en", "no", "fr"]

    def test_handles_corrupted_json(self, app_ctx):
        from db import get_db
        from services.settings_service import get_off_language_priority, _OFF_LANGUAGE_PRIORITY_KEY

        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
            (_OFF_LANGUAGE_PRIORITY_KEY, "not-valid-json"),
        )
        conn.commit()
        # Falls back to current language
        result = get_off_language_priority()
        assert result == ["no"]


class TestSetOffLanguagePriority:
    def test_saves_and_retrieves(self, app_ctx):
        from services.settings_service import set_off_language_priority, get_off_language_priority

        set_off_language_priority(["sv", "da"])
        assert get_off_language_priority() == ["sv", "da"]

    def test_overwrites_existing(self, app_ctx):
        from services.settings_service import set_off_language_priority, get_off_language_priority

        set_off_language_priority(["en"])
        set_off_language_priority(["no", "sv"])
        assert get_off_language_priority() == ["no", "sv"]

    def test_single_language(self, app_ctx):
        from services.settings_service import set_off_language_priority, get_off_language_priority

        set_off_language_priority(["de"])
        assert get_off_language_priority() == ["de"]


class TestPickByPriority:
    def test_picks_first_available(self):
        from services.proxy_service import _pick_by_priority

        product = {"product_name_en": "Bread", "product_name_no": "Brod"}
        assert _pick_by_priority(product, "product_name", ["no", "en"]) == "Brod"

    def test_skips_empty_and_falls_through(self):
        from services.proxy_service import _pick_by_priority

        product = {"product_name_no": "", "product_name_en": "Bread"}
        assert _pick_by_priority(product, "product_name", ["no", "en"]) == "Bread"

    def test_falls_back_to_base_field(self):
        from services.proxy_service import _pick_by_priority

        product = {"product_name": "Generic Name"}
        assert _pick_by_priority(product, "product_name", ["no", "en"]) == "Generic Name"

    def test_returns_empty_when_nothing_found(self):
        from services.proxy_service import _pick_by_priority

        product = {}
        assert _pick_by_priority(product, "product_name", ["no", "en"]) == ""

    def test_strips_whitespace(self):
        from services.proxy_service import _pick_by_priority

        product = {"product_name_no": "  Brod  "}
        assert _pick_by_priority(product, "product_name", ["no"]) == "Brod"

    def test_skips_whitespace_only(self):
        from services.proxy_service import _pick_by_priority

        product = {"product_name_no": "   ", "product_name_en": "Bread"}
        assert _pick_by_priority(product, "product_name", ["no", "en"]) == "Bread"

    def test_works_for_ingredients_text(self):
        from services.proxy_service import _pick_by_priority

        product = {
            "ingredients_text_no": "Mel, vann",
            "ingredients_text_en": "Flour, water",
        }
        assert _pick_by_priority(product, "ingredients_text", ["en", "no"]) == "Flour, water"


class TestBuildSearchFields:
    def test_includes_priority_lang_fields(self):
        from services.proxy_service import _build_search_fields

        fields = _build_search_fields(["no", "en"])
        assert "product_name_no" in fields
        assert "product_name_en" in fields
        assert "ingredients_text_no" in fields
        assert "ingredients_text_en" in fields

    def test_includes_base_fields(self):
        from services.proxy_service import _build_search_fields

        fields = _build_search_fields(["no"])
        assert "code" in fields
        assert "product_name" in fields
        assert "ingredients_text" in fields
        assert "completeness" in fields

    def test_single_language(self):
        from services.proxy_service import _build_search_fields

        fields = _build_search_fields(["sv"])
        assert "product_name_sv" in fields
        assert "ingredients_text_sv" in fields


class TestOffLanguageRoutes:
    def test_get_off_languages(self, client):
        resp = client.get("/api/settings/off-languages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "languages" in data
        assert "no" in data["languages"]
        assert "en" in data["languages"]
        assert "de" in data["languages"]
        assert len(data["languages"]) >= 50

    def test_get_off_language_priority_default(self, client):
        resp = client.get("/api/settings/off-language-priority")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "priority" in data
        assert data["priority"] == ["no"]

    def test_put_off_language_priority_saves(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": ["en", "no"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["priority"] == ["en", "no"]

        # Verify persisted
        resp2 = client.get("/api/settings/off-language-priority")
        assert resp2.get_json()["priority"] == ["en", "no"]

    def test_put_deduplicates_preserving_order(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": ["no", "en", "no", "sv", "en"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["priority"] == ["no", "en", "sv"]

    def test_put_rejects_empty_list(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_put_rejects_non_list(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": "no"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_put_rejects_non_string_items(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": [1, 2]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_put_rejects_empty_string_items(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": ["no", ""]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_put_missing_priority_key(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_put_strips_whitespace_from_items(self, client):
        resp = client.put(
            "/api/settings/off-language-priority",
            data=json.dumps({"priority": [" no ", " en "]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["priority"] == ["no", "en"]
