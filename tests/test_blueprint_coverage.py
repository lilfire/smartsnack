"""Additional blueprint coverage tests targeting missing lines in:
- blueprints/flags.py
- blueprints/proxy.py
- blueprints/settings.py
- blueprints/bulk.py
- blueprints/protein_quality.py
- blueprints/off.py
"""

from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/flags.py
# ─────────────────────────────────────────────────────────────────────────────


class TestGetFlagsEndpoint:
    """GET /api/flags"""

    def test_returns_200(self, client):
        resp = client.get("/api/flags")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/flags").get_json()
        assert isinstance(data, list)


class TestGetFlagConfigEndpoint:
    """GET /api/flag-config"""

    def test_returns_200(self, client):
        resp = client.get("/api/flag-config")
        assert resp.status_code == 200

    def test_returns_dict(self, client):
        data = client.get("/api/flag-config").get_json()
        assert isinstance(data, dict)


class TestAddFlagEndpoint:
    """POST /api/flags"""

    def test_add_flag_success_returns_201(self, client):
        resp = client.post(
            "/api/flags",
            json={"name": "test_flag_unique", "label": "Test Flag"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get("ok") is True

    def test_add_flag_missing_json_returns_400(self, client):
        resp = client.post("/api/flags", content_type="text/plain", data="not json")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_add_flag_missing_name_returns_400(self, client):
        # name is empty string — service raises ValueError
        resp = client.post("/api/flags", json={"name": "", "label": "Label"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_add_flag_missing_label_returns_400(self, client):
        resp = client.post("/api/flags", json={"name": "valid_flag", "label": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_add_duplicate_flag_returns_409(self, client):
        # Add once successfully
        client.post(
            "/api/flags",
            json={"name": "dupe_flag_abc", "label": "Dupe Flag"},
        )
        # Adding again must produce a conflict
        resp = client.post(
            "/api/flags",
            json={"name": "dupe_flag_abc", "label": "Dupe Flag"},
        )
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_add_flag_invalid_name_pattern_returns_400(self, client):
        # Flag names must match ^[a-z][a-z0-9_]*$ — uppercase invalid
        resp = client.post(
            "/api/flags",
            json={"name": "InvalidName", "label": "Label"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestUpdateFlagEndpoint:
    """PUT /api/flags/<name>"""

    def _create_flag(self, client, name="upd_flag_xyz"):
        client.post("/api/flags", json={"name": name, "label": "Original Label"})
        return name

    def test_update_flag_label_success(self, client):
        name = self._create_flag(client)
        resp = client.put(f"/api/flags/{name}", json={"label": "Updated Label"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True

    def test_update_flag_empty_label_returns_400(self, client):
        name = self._create_flag(client, "upd_flag_empty_lbl")
        resp = client.put(f"/api/flags/{name}", json={"label": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_nonexistent_flag_returns_400(self, client):
        resp = client.put("/api/flags/does_not_exist", json={"label": "Label"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_missing_json_returns_400(self, client):
        name = self._create_flag(client, "upd_flag_no_json")
        resp = client.put(
            f"/api/flags/{name}", content_type="text/plain", data="bad"
        )
        assert resp.status_code == 400


class TestDeleteFlagEndpoint:
    """DELETE /api/flags/<name>"""

    def _create_flag(self, client, name="del_flag_xyz"):
        client.post("/api/flags", json={"name": name, "label": "Delete Me"})
        return name

    def test_delete_flag_success(self, client):
        name = self._create_flag(client)
        resp = client.delete(f"/api/flags/{name}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert "removed_from" in data

    def test_delete_flag_returns_removed_from_count(self, client):
        name = self._create_flag(client, "del_flag_count")
        resp = client.delete(f"/api/flags/{name}")
        data = resp.get_json()
        # No products flagged, so count is 0
        assert data["removed_from"] == 0

    def test_delete_nonexistent_flag_returns_400(self, client):
        resp = client.delete("/api/flags/no_such_flag_ever")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_delete_system_flag_returns_400(self, client):
        # is_synced_with_off is a system flag — cannot be deleted
        resp = client.delete("/api/flags/is_synced_with_off")
        assert resp.status_code == 400
        assert "error" in resp.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/proxy.py
# ─────────────────────────────────────────────────────────────────────────────


class TestProxyImageEndpoint:
    """GET /api/proxy-image"""

    def test_valid_url_returns_image_response(self, client):
        fake_bytes = b"\xff\xd8\xff" + b"\x00" * 20
        with patch(
            "services.proxy_service.proxy_image",
            return_value=(fake_bytes, "image/jpeg"),
        ):
            resp = client.get(
                "/api/proxy-image?url=https://images.openfoodfacts.org/img.jpg"
            )
        assert resp.status_code == 200
        assert resp.content_type == "image/jpeg"
        assert resp.data == fake_bytes

    def test_valid_url_sets_cache_header(self, client):
        fake_bytes = b"\x89PNG\r\n"
        with patch(
            "services.proxy_service.proxy_image",
            return_value=(fake_bytes, "image/png"),
        ):
            resp = client.get(
                "/api/proxy-image?url=https://images.openfoodfacts.org/img.png"
            )
        assert "Cache-Control" in resp.headers

    def test_disallowed_domain_returns_403(self, client):
        with patch(
            "services.proxy_service.proxy_image",
            side_effect=PermissionError("Domain not allowed"),
        ):
            resp = client.get("/api/proxy-image?url=https://evil.com/img.jpg")
        assert resp.status_code == 403
        assert "error" in resp.get_json()

    def test_runtime_error_returns_502(self, client):
        with patch(
            "services.proxy_service.proxy_image",
            side_effect=RuntimeError("upstream failed"),
        ):
            resp = client.get(
                "/api/proxy-image?url=https://images.openfoodfacts.org/img.jpg"
            )
        assert resp.status_code == 502
        assert "error" in resp.get_json()

    def test_value_error_returns_400(self, client):
        with patch(
            "services.proxy_service.proxy_image",
            side_effect=ValueError("Empty URL"),
        ):
            resp = client.get("/api/proxy-image")
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestOffSearchEndpoint:
    """GET and POST /api/off/search"""

    def test_get_search_success(self, client):
        with patch(
            "services.proxy_service.off_search",
            return_value={"products": [], "count": 0},
        ):
            resp = client.get("/api/off/search?q=chips")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data

    def test_get_search_value_error_returns_400(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=ValueError("bad query"),
        ):
            resp = client.get("/api/off/search?q=")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_get_search_runtime_error_returns_502(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=RuntimeError("OFF unavailable"),
        ):
            resp = client.get("/api/off/search?q=chips")
        assert resp.status_code == 502
        assert "error" in resp.get_json()

    def test_get_search_generic_exception_returns_500(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=Exception("unexpected"),
        ):
            resp = client.get("/api/off/search?q=chips")
        assert resp.status_code == 500
        assert "error" in resp.get_json()

    def test_post_search_with_query_success(self, client):
        with patch(
            "services.proxy_service.off_search",
            return_value={"products": [{"id": "abc"}], "count": 1},
        ):
            resp = client.post("/api/off/search", json={"q": "popcorn"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data

    def test_post_search_with_nutrition_filter(self, client):
        with patch(
            "services.proxy_service.off_search",
            return_value={"products": [], "count": 0},
        ) as mock_search:
            resp = client.post(
                "/api/off/search",
                json={
                    "q": "chips",
                    "category": "Snacks",
                    "nutrition": {"protein": "10.5", "fat": "5.0"},
                },
            )
        assert resp.status_code == 200
        # Verify nutrition dict was parsed to floats and forwarded
        _, call_kwargs = mock_search.call_args_list[0][0], mock_search.call_args
        call_args = mock_search.call_args[0]
        nutrition_arg = call_args[1]
        assert isinstance(nutrition_arg, dict)
        assert nutrition_arg.get("protein") == 10.5
        assert nutrition_arg.get("fat") == 5.0

    def test_post_search_with_invalid_nutrition_values_ignored(self, client):
        with patch(
            "services.proxy_service.off_search",
            return_value={"products": [], "count": 0},
        ) as mock_search:
            client.post(
                "/api/off/search",
                json={
                    "q": "chips",
                    "nutrition": {"protein": "not-a-number", "fat": 5.0},
                },
            )
        # "not-a-number" is skipped; only fat survives
        call_args = mock_search.call_args[0]
        nutrition_arg = call_args[1]
        assert nutrition_arg is not None
        assert "protein" not in nutrition_arg
        assert nutrition_arg.get("fat") == 5.0

    def test_post_search_with_all_invalid_nutrition_passes_none(self, client):
        with patch(
            "services.proxy_service.off_search",
            return_value={"products": [], "count": 0},
        ) as mock_search:
            client.post(
                "/api/off/search",
                json={"q": "chips", "nutrition": {"protein": "bad", "fat": "also-bad"}},
            )
        call_args = mock_search.call_args[0]
        nutrition_arg = call_args[1]
        # All values invalid → nutrition collapses to None
        assert nutrition_arg is None

    def test_post_search_runtime_error_returns_502(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=RuntimeError("timeout"),
        ):
            resp = client.post("/api/off/search", json={"q": "chips"})
        assert resp.status_code == 502

    def test_post_search_generic_exception_returns_500(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=Exception("boom"),
        ):
            resp = client.post("/api/off/search", json={"q": "chips"})
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Search failed"

    def test_post_search_value_error_returns_400(self, client):
        with patch(
            "services.proxy_service.off_search",
            side_effect=ValueError("invalid query"),
        ):
            resp = client.post("/api/off/search", json={"q": ""})
        assert resp.status_code == 400


class TestOffProductEndpoint:
    """GET /api/off/product/<code>"""

    def test_product_found_returns_200(self, client):
        mock_data = {"code": "1234567890123", "product_name": "Test Chips"}
        with patch(
            "services.proxy_service.off_product",
            return_value=mock_data,
        ):
            resp = client.get("/api/off/product/1234567890123")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == "1234567890123"

    def test_product_value_error_returns_400(self, client):
        with patch(
            "services.proxy_service.off_product",
            side_effect=ValueError("Invalid barcode"),
        ):
            resp = client.get("/api/off/product/bad_code")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_product_runtime_error_returns_502(self, client):
        with patch(
            "services.proxy_service.off_product",
            side_effect=RuntimeError("OFF unreachable"),
        ):
            resp = client.get("/api/off/product/1234567890123")
        assert resp.status_code == 502
        assert "error" in resp.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/settings.py
# ─────────────────────────────────────────────────────────────────────────────


class TestGetLanguageEndpoint:
    """GET /api/settings/language"""

    def test_returns_200_with_language_key(self, client):
        resp = client.get("/api/settings/language")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "language" in data
        assert isinstance(data["language"], str)


class TestSetLanguageEndpoint:
    """PUT /api/settings/language"""

    def test_missing_language_key_returns_400(self, client):
        # Valid JSON but missing the "language" field
        resp = client.put("/api/settings/language", json={"lang": "en"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "language" in data["error"]

    def test_missing_json_body_returns_400(self, client):
        resp = client.put(
            "/api/settings/language", content_type="text/plain", data="no json"
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_valid_language_returns_200(self, client):
        resp = client.put("/api/settings/language", json={"language": "en"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert data.get("language") == "en"


class TestGetOffCredentialsEndpoint:
    """GET /api/settings/off-credentials (no API key set in tests)"""

    def test_returns_200_without_api_key_configured(self, client):
        # SMARTSNACK_API_KEY is not set in test env → access always allowed
        resp = client.get("/api/settings/off-credentials")
        assert resp.status_code == 200

    def test_response_contains_off_user_id(self, client):
        data = client.get("/api/settings/off-credentials").get_json()
        assert "off_user_id" in data

    def test_response_contains_has_password(self, client):
        data = client.get("/api/settings/off-credentials").get_json()
        assert "has_password" in data
        assert isinstance(data["has_password"], bool)


class TestSetOffCredentialsEndpoint:
    """PUT /api/settings/off-credentials"""

    def test_set_credentials_success(self, client):
        with patch("services.settings_service.set_off_credentials", return_value=None):
            resp = client.put(
                "/api/settings/off-credentials",
                json={"off_user_id": "myuser", "off_password": "secret"},
            )
        assert resp.status_code == 200
        assert resp.get_json().get("ok") is True

    def test_missing_json_returns_400(self, client):
        resp = client.put(
            "/api/settings/off-credentials",
            content_type="text/plain",
            data="not json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_password_too_long_returns_400(self, client):
        # _MAX_PASSWORD_LEN is 500 — send 501 chars
        resp = client.put(
            "/api/settings/off-credentials",
            json={"off_user_id": "user", "off_password": "x" * 501},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "Password" in data["error"] or "password" in data["error"].lower()

    def test_encryption_not_configured_returns_500(self, client):
        with patch(
            "services.settings_service.set_off_credentials",
            side_effect=RuntimeError("no key"),
        ):
            resp = client.put(
                "/api/settings/off-credentials",
                json={"off_user_id": "user", "off_password": "pass"},
            )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data.get("error") == "encryption_not_configured"

    def test_empty_json_object_uses_defaults(self, client):
        # Empty dict is valid JSON — user_id and password both default to ""
        with patch("services.settings_service.set_off_credentials", return_value=None):
            resp = client.put("/api/settings/off-credentials", json={})
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/bulk.py — missing: POST /api/bulk/refresh-off and stream endpoint
# ─────────────────────────────────────────────────────────────────────────────


class TestRefreshOffSyncEndpoint:
    """POST /api/bulk/refresh-off (sync, non-streaming version)"""

    def test_success_returns_200_with_result(self, client):
        mock_result = {"updated": 3, "skipped": 1, "errors": 0}
        with patch(
            "services.bulk_service.refresh_from_off",
            return_value=mock_result,
        ):
            resp = client.post("/api/bulk/refresh-off")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 3
        assert data["skipped"] == 1

    def test_service_exception_returns_500(self, client):
        with patch(
            "services.bulk_service.refresh_from_off",
            side_effect=RuntimeError("connection error"),
        ):
            resp = client.post("/api/bulk/refresh-off")
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data
        assert "connection error" in data["error"]


class TestRefreshOffStreamEndpoint:
    """GET /api/bulk/refresh-off/stream (SSE endpoint)"""

    def test_stream_returns_event_stream_content_type(self, client):
        # Mock get_refresh_status to return not-running so the generator exits
        not_running = {
            "running": False,
            "current": 0,
            "total": 0,
            "name": "",
            "ean": "",
            "status": "",
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "done": True,
        }
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=not_running,
        ):
            resp = client.get("/api/bulk/refresh-off/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type

    def test_stream_response_contains_data_line(self, client):
        not_running = {
            "running": False,
            "current": 0,
            "total": 0,
            "name": "",
            "ean": "",
            "status": "",
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "done": True,
        }
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=not_running,
        ):
            resp = client.get("/api/bulk/refresh-off/stream")
        body = resp.data.decode("utf-8")
        # SSE lines start with "data: "
        assert body.startswith("data: ")

    def test_stream_has_no_cache_header(self, client):
        not_running = {
            "running": False,
            "current": 0,
            "total": 0,
            "name": "",
            "ean": "",
            "status": "",
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "done": True,
        }
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=not_running,
        ):
            resp = client.get("/api/bulk/refresh-off/stream")
        assert resp.headers.get("Cache-Control") == "no-cache"


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/protein_quality.py — missing: update, delete, estimate paths
# ─────────────────────────────────────────────────────────────────────────────


class TestUpdateProteinQualityEndpoint:
    """PUT /api/protein-quality/<pid>"""

    def _get_existing_pid(self, client) -> int:
        entries = client.get("/api/protein-quality").get_json()
        assert entries, "Seed data must include at least one PQ entry"
        return entries[0]["id"]

    def test_update_existing_entry_success(self, client):
        pid = self._get_existing_pid(client)
        resp = client.put(
            f"/api/protein-quality/{pid}",
            json={"pdcaas": 0.95, "diaas": 0.90},
        )
        assert resp.status_code == 200
        assert resp.get_json().get("ok") is True

    def test_update_label_field(self, client):
        pid = self._get_existing_pid(client)
        resp = client.put(
            f"/api/protein-quality/{pid}",
            json={"label": "Updated Label"},
        )
        assert resp.status_code == 200
        assert resp.get_json().get("ok") is True

    def test_update_nonexistent_pid_returns_404(self, client):
        resp = client.put(
            "/api/protein-quality/999999",
            json={"pdcaas": 0.5},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_update_invalid_pdcaas_returns_400(self, client):
        pid = self._get_existing_pid(client)
        resp = client.put(
            f"/api/protein-quality/{pid}",
            json={"pdcaas": "not-a-float"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_missing_json_returns_400(self, client):
        pid = self._get_existing_pid(client)
        resp = client.put(
            f"/api/protein-quality/{pid}",
            content_type="text/plain",
            data="bad",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestDeleteProteinQualityEndpoint:
    """DELETE /api/protein-quality/<pid>"""

    def _add_entry(self, client, name: str) -> int:
        resp = client.post(
            "/api/protein-quality",
            json={
                "name": name,
                "keywords": [name.replace("_", " ")],
                "pdcaas": 0.70,
                "diaas": 0.65,
                "label": name.replace("_", " ").title(),
            },
        )
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()["id"]

    def test_delete_existing_entry_returns_200(self, client):
        pid = self._add_entry(client, "del_pq_test_a")
        resp = client.delete(f"/api/protein-quality/{pid}")
        assert resp.status_code == 200
        assert resp.get_json().get("ok") is True

    def test_deleted_entry_no_longer_listed(self, client):
        pid = self._add_entry(client, "del_pq_test_b")
        client.delete(f"/api/protein-quality/{pid}")
        entries = client.get("/api/protein-quality").get_json()
        ids = [e["id"] for e in entries]
        assert pid not in ids

    def test_delete_nonexistent_pid_returns_404(self, client):
        resp = client.delete("/api/protein-quality/999999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestAddProteinQualityEndpoint:
    """POST /api/protein-quality — error paths not covered elsewhere"""

    def test_add_missing_json_returns_400(self, client):
        resp = client.post(
            "/api/protein-quality",
            content_type="text/plain",
            data="not json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_add_missing_required_fields_returns_400(self, client):
        # Missing pdcaas and diaas
        resp = client.post(
            "/api/protein-quality",
            json={"name": "incomplete_pq", "keywords": ["incomplete"]},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestEstimateProteinQualityEndpoint:
    """POST /api/estimate-protein-quality — missing paths"""

    def test_valid_ingredients_returns_200(self, client):
        resp = client.post(
            "/api/estimate-protein-quality",
            json={"ingredients": "whey protein, oats, sugar"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "est_pdcaas" in data
        assert "est_diaas" in data
        assert "sources" in data

    def test_missing_json_returns_400(self, client):
        resp = client.post(
            "/api/estimate-protein-quality",
            content_type="text/plain",
            data="no json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_service_value_error_returns_400(self, client):
        with patch(
            "services.protein_quality_service.estimate",
            side_effect=ValueError("bad ingredients"),
        ):
            resp = client.post(
                "/api/estimate-protein-quality",
                json={"ingredients": "some ingredient text"},
            )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# blueprints/off.py
# ─────────────────────────────────────────────────────────────────────────────


class TestAddProductToOffEndpoint:
    """POST /api/off/add-product"""

    def test_success_returns_200_with_status_verbose(self, client):
        mock_result = {"status_verbose": "fields saved"}
        with patch(
            "services.off_service.add_product_to_off",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/off/add-product",
                json={"ean": "1234567890123", "name": "Test Product"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert data.get("status_verbose") == "fields saved"

    def test_success_uses_default_status_verbose_when_absent(self, client):
        # Service returns a result dict without "status_verbose"
        with patch(
            "services.off_service.add_product_to_off",
            return_value={},
        ):
            resp = client.post(
                "/api/off/add-product",
                json={"ean": "1234567890123"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status_verbose") == "fields saved"

    def test_value_error_returns_400(self, client):
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=ValueError("EAN required"),
        ):
            resp = client.post(
                "/api/off/add-product",
                json={"name": "No EAN"},
            )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "EAN" in data["error"]

    def test_runtime_error_returns_502(self, client):
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=RuntimeError("OFF API timeout"),
        ):
            resp = client.post(
                "/api/off/add-product",
                json={"ean": "1234567890123"},
            )
        assert resp.status_code == 502
        data = resp.get_json()
        assert "error" in data
        assert "timeout" in data["error"]
