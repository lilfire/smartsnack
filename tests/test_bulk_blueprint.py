"""Tests for blueprints/bulk.py (route-level validation) and
selected unit tests for services/bulk_service.py helper functions.

Coverage targets
----------------
Blueprint (blueprints/bulk.py):
  - POST /api/bulk/refresh-off/start  — invalid min_certainty, valid request
  - GET  /api/bulk/refresh-off/status — basic response shape
  - POST /api/bulk/estimate-pq        — basic response shape

Service helpers (services/bulk_service.py):
  - _parse_off_nutriment  — present / missing / invalid values
  - _should_update        — None / empty string / zero-with-existing / valid
  - _map_off_product      — nutrition, name, brand, stores, ingredients, weight, portion
  - _fetch_off_image      — no-URL fast-path returns None
  - get_refresh_status    — returns dict with all expected keys
  - start_refresh_from_off — returns False when job is already running
"""

from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Blueprint-level tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRefreshOffStartEndpoint:
    """POST /api/bulk/refresh-off/start"""

    def test_invalid_min_certainty_string_returns_400(self, client):
        resp = client.post(
            "/api/bulk/refresh-off/start",
            json={"min_certainty": "not-a-number"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] == "Invalid numeric parameter"

    def test_invalid_min_completeness_string_returns_400(self, client):
        resp = client.post(
            "/api/bulk/refresh-off/start",
            json={"min_completeness": "bad"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "Invalid numeric parameter"

    def test_valid_request_starts_job_and_returns_ok(self, client):
        """A well-formed request should start the background job (mocked) and
        return HTTP 200 with {"ok": true}."""
        with patch("services.bulk_service.start_refresh_from_off", return_value=True):
            resp = client.post(
                "/api/bulk/refresh-off/start",
                json={
                    "search_missing": False,
                    "min_certainty": 70,
                    "min_completeness": 60,
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True

    def test_already_running_returns_409(self, client):
        """When the service reports a job is already running the endpoint
        must return HTTP 409 with error 'already_running'."""
        with patch("services.bulk_service.start_refresh_from_off", return_value=False):
            resp = client.post(
                "/api/bulk/refresh-off/start",
                json={"min_certainty": 50},
            )
        assert resp.status_code == 409
        data = resp.get_json()
        assert data.get("error") == "already_running"

    def test_min_certainty_clamped_at_100(self, client):
        """Values above 100 are clamped silently — still a valid request."""
        with patch("services.bulk_service.start_refresh_from_off", return_value=True):
            resp = client.post(
                "/api/bulk/refresh-off/start",
                json={"min_certainty": 999},
            )
        assert resp.status_code == 200

    def test_min_certainty_clamped_at_0(self, client):
        """Negative values are clamped to 0 — still a valid request."""
        with patch("services.bulk_service.start_refresh_from_off", return_value=True):
            resp = client.post(
                "/api/bulk/refresh-off/start",
                json={"min_certainty": -10},
            )
        assert resp.status_code == 200

    def test_empty_body_uses_defaults(self, client):
        """A POST with no body (or empty JSON) must not raise and must accept
        default parameter values."""
        with patch("services.bulk_service.start_refresh_from_off", return_value=True):
            resp = client.post("/api/bulk/refresh-off/start", json={})
        assert resp.status_code == 200


class TestRefreshOffStatusEndpoint:
    """GET /api/bulk/refresh-off/status"""

    def test_returns_200(self, client):
        resp = client.get("/api/bulk/refresh-off/status")
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get("/api/bulk/refresh-off/status")
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_response_contains_running_key(self, client):
        data = client.get("/api/bulk/refresh-off/status").get_json()
        assert "running" in data

    def test_response_contains_done_key(self, client):
        data = client.get("/api/bulk/refresh-off/status").get_json()
        assert "done" in data

    def test_response_contains_progress_keys(self, client):
        data = client.get("/api/bulk/refresh-off/status").get_json()
        assert "current" in data
        assert "total" in data

    def test_response_contains_counter_keys(self, client):
        data = client.get("/api/bulk/refresh-off/status").get_json()
        assert "updated" in data
        assert "skipped" in data
        assert "errors" in data


class TestEstimatePqEndpoint:
    """POST /api/bulk/estimate-pq"""

    def test_returns_200(self, client):
        resp = client.post("/api/bulk/estimate-pq")
        assert resp.status_code == 200

    def test_returns_json_dict(self, client):
        data = client.post("/api/bulk/estimate-pq").get_json()
        assert isinstance(data, dict)

    def test_response_has_total_key(self, client):
        data = client.post("/api/bulk/estimate-pq").get_json()
        assert "total" in data

    def test_response_has_updated_key(self, client):
        data = client.post("/api/bulk/estimate-pq").get_json()
        assert "updated" in data

    def test_response_has_skipped_key(self, client):
        data = client.post("/api/bulk/estimate-pq").get_json()
        assert "skipped" in data

    def test_total_non_negative(self, client):
        data = client.post("/api/bulk/estimate-pq").get_json()
        assert data["total"] >= 0

    def test_service_error_returns_500(self, client):
        """If estimate_all_pq raises, the blueprint must return HTTP 500."""
        with patch(
            "services.bulk_service.estimate_all_pq",
            side_effect=RuntimeError("db gone"),
        ):
            resp = client.post("/api/bulk/estimate-pq")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# _parse_off_nutriment
# ─────────────────────────────────────────────────────────────────────────────


class TestParseOffNutriment:
    """services.bulk_service._parse_off_nutriment"""

    def test_prefers_per_100g_key(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"protein_100g": 12.5, "protein": 6.0}, "protein")
        assert result == 12.5

    def test_falls_back_to_plain_key(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"fat": 8.3}, "fat")
        assert result == 8.3

    def test_missing_key_returns_none(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({}, "energy-kcal")
        assert result is None

    def test_none_value_returns_none(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"salt_100g": None}, "salt")
        assert result is None

    def test_string_number_is_coerced_to_float(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"carbohydrates_100g": "34.2"}, "carbohydrates")
        assert result == 34.2

    def test_non_numeric_string_returns_none(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"fiber_100g": "trace"}, "fiber")
        assert result is None

    def test_zero_value_returns_none_due_to_or_chaining(self):
        """The implementation uses ``or`` to chain the two dict lookups, so a
        stored integer 0 (falsy) is treated as absent and None is returned.
        This test documents that known edge-case behaviour."""
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"sugars_100g": 0}, "sugars")
        assert result is None

    def test_integer_value_is_coerced_to_float(self):
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment({"energy-kcal_100g": 250}, "energy-kcal")
        assert isinstance(result, float)
        assert result == 250.0

    def test_100g_key_takes_precedence_even_when_plain_is_higher(self):
        """The _100g variant must win regardless of relative magnitude."""
        from services.bulk_service import _parse_off_nutriment

        result = _parse_off_nutriment(
            {"saturated-fat_100g": 2.1, "saturated-fat": 99.9}, "saturated-fat"
        )
        assert result == 2.1


# ─────────────────────────────────────────────────────────────────────────────
# _should_update
# ─────────────────────────────────────────────────────────────────────────────


class TestShouldUpdate:
    """services.bulk_service._should_update"""

    def test_none_off_value_returns_false(self):
        from services.bulk_service import _should_update

        assert _should_update(None, "existing") is False

    def test_empty_string_off_value_returns_false(self):
        from services.bulk_service import _should_update

        assert _should_update("", "existing") is False

    def test_whitespace_string_off_value_returns_false(self):
        from services.bulk_service import _should_update

        assert _should_update("   ", "existing") is False

    def test_zero_with_existing_non_zero_local_returns_false(self):
        from services.bulk_service import _should_update

        assert _should_update(0, 10.5) is False

    def test_zero_with_zero_local_returns_true(self):
        """Zero should update when local is also zero — both are equivalent."""
        from services.bulk_service import _should_update

        assert _should_update(0, 0) is True

    def test_zero_with_none_local_returns_true(self):
        """Zero is a valid value when local has no data at all."""
        from services.bulk_service import _should_update

        assert _should_update(0, None) is True

    def test_zero_with_empty_string_local_returns_true(self):
        from services.bulk_service import _should_update

        assert _should_update(0, "") is True

    def test_valid_float_updates(self):
        from services.bulk_service import _should_update

        assert _should_update(14.5, None) is True

    def test_valid_string_updates(self):
        from services.bulk_service import _should_update

        assert _should_update("Chips Brand", None) is True

    def test_valid_string_overwrites_existing_local(self):
        from services.bulk_service import _should_update

        assert _should_update("New Name", "Old Name") is True

    def test_non_zero_float_with_existing_local_updates(self):
        from services.bulk_service import _should_update

        assert _should_update(5.5, 3.0) is True


# ─────────────────────────────────────────────────────────────────────────────
# _map_off_product
# ─────────────────────────────────────────────────────────────────────────────


class TestMapOffProduct:
    """services.bulk_service._map_off_product"""

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _local(**kwargs):
        """Return a minimal local-row dict with all fields defaulting to None."""
        base = {
            "name": None,
            "brand": None,
            "stores": None,
            "ingredients": None,
            "kcal": None,
            "energy_kj": None,
            "fat": None,
            "saturated_fat": None,
            "carbs": None,
            "sugar": None,
            "protein": None,
            "fiber": None,
            "salt": None,
            "weight": None,
            "portion": None,
        }
        base.update(kwargs)
        return base

    # ── nutrition ─────────────────────────────────────────────────────────────

    def test_maps_kcal_from_nutriments(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"energy-kcal_100g": 450.7}}
        updates = _map_off_product(product, self._local())
        assert updates.get("kcal") == 451  # rounded to int

    def test_maps_energy_kj_rounded_to_int(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"energy-kj_100g": 1883.6}}
        updates = _map_off_product(product, self._local())
        assert updates.get("energy_kj") == 1884

    def test_maps_fat_to_one_decimal(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"fat_100g": 22.348}}
        updates = _map_off_product(product, self._local())
        assert updates.get("fat") == 22.3

    def test_maps_salt_to_two_decimals(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"salt_100g": 1.2345}}
        updates = _map_off_product(product, self._local())
        assert updates.get("salt") == 1.23

    def test_maps_protein_to_one_decimal(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"proteins_100g": 7.654}}
        updates = _map_off_product(product, self._local())
        assert updates.get("protein") == 7.7

    def test_zero_nutrition_with_existing_local_not_overwritten(self):
        """A zero OFF value must not overwrite an existing non-zero local value."""
        from services.bulk_service import _map_off_product

        product = {"nutriments": {"fat_100g": 0}}
        updates = _map_off_product(product, self._local(fat=12.0))
        assert "fat" not in updates

    def test_missing_nutriment_not_included(self):
        from services.bulk_service import _map_off_product

        product = {"nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert "kcal" not in updates
        assert "protein" not in updates

    # ── name ──────────────────────────────────────────────────────────────────

    def test_maps_norwegian_name_first(self):
        from services.bulk_service import _map_off_product

        product = {
            "product_name_no": "Norsk navn",
            "product_name": "English name",
            "nutriments": {},
        }
        updates = _map_off_product(product, self._local())
        assert updates.get("name") == "Norsk navn"

    def test_falls_back_to_product_name_when_no_norwegian(self):
        from services.bulk_service import _map_off_product

        product = {"product_name": "English name", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("name") == "English name"

    def test_name_is_stripped(self):
        from services.bulk_service import _map_off_product

        product = {"product_name": "  Chips  ", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates["name"] == "Chips"

    def test_empty_name_not_written(self):
        from services.bulk_service import _map_off_product

        product = {"product_name": "", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert "name" not in updates

    # ── brand ─────────────────────────────────────────────────────────────────

    def test_maps_brand(self):
        from services.bulk_service import _map_off_product

        product = {"brands": "Acme Co.", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("brand") == "Acme Co."

    def test_brand_not_overwritten_with_empty(self):
        from services.bulk_service import _map_off_product

        product = {"brands": "", "nutriments": {}}
        updates = _map_off_product(product, self._local(brand="Existing Brand"))
        assert "brand" not in updates

    # ── stores ────────────────────────────────────────────────────────────────

    def test_maps_stores_from_stores_field(self):
        from services.bulk_service import _map_off_product

        product = {"stores": "Rema 1000, Kiwi", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("stores") == "Rema 1000, Kiwi"

    def test_maps_stores_from_tags_when_stores_empty(self):
        from services.bulk_service import _map_off_product

        product = {
            "stores": "",
            "stores_tags": ["rema-1000", "kiwi"],
            "nutriments": {},
        }
        updates = _map_off_product(product, self._local())
        # Tags are title-cased with hyphens replaced by spaces
        assert "Rema 1000" in updates.get("stores", "")
        assert "Kiwi" in updates.get("stores", "")

    def test_stores_tags_ignored_when_stores_present(self):
        from services.bulk_service import _map_off_product

        product = {
            "stores": "Direct Store",
            "stores_tags": ["other-store"],
            "nutriments": {},
        }
        updates = _map_off_product(product, self._local())
        assert updates.get("stores") == "Direct Store"

    # ── ingredients ───────────────────────────────────────────────────────────

    def test_maps_norwegian_ingredients_first(self):
        from services.bulk_service import _map_off_product

        product = {
            "ingredients_text_no": "Mais, olje",
            "ingredients_text_en": "Corn, oil",
            "nutriments": {},
        }
        updates = _map_off_product(product, self._local())
        assert updates.get("ingredients") == "Mais, olje"

    def test_falls_back_to_english_ingredients(self):
        from services.bulk_service import _map_off_product

        product = {"ingredients_text_en": "Corn, oil", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("ingredients") == "Corn, oil"

    def test_falls_back_to_generic_ingredients_text(self):
        from services.bulk_service import _map_off_product

        product = {"ingredients_text": "Generic ingredients", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("ingredients") == "Generic ingredients"

    # ── weight ────────────────────────────────────────────────────────────────

    def test_maps_weight_from_product_quantity(self):
        from services.bulk_service import _map_off_product

        product = {"product_quantity": "150", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("weight") == 150

    def test_weight_is_rounded_integer(self):
        from services.bulk_service import _map_off_product

        product = {"product_quantity": "149.6", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("weight") == 150

    def test_invalid_weight_string_not_included(self):
        from services.bulk_service import _map_off_product

        product = {"product_quantity": "unknown", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert "weight" not in updates

    # ── portion ───────────────────────────────────────────────────────────────

    def test_maps_portion_from_serving_size_grams(self):
        from services.bulk_service import _map_off_product

        product = {"serving_size": "30g", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("portion") == 30

    def test_maps_portion_with_decimal_grams(self):
        from services.bulk_service import _map_off_product

        product = {"serving_size": "28.35 g", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert updates.get("portion") == 28

    def test_serving_size_without_grams_not_included(self):
        from services.bulk_service import _map_off_product

        product = {"serving_size": "1 piece", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert "portion" not in updates

    def test_empty_serving_size_not_included(self):
        from services.bulk_service import _map_off_product

        product = {"serving_size": "", "nutriments": {}}
        updates = _map_off_product(product, self._local())
        assert "portion" not in updates

    # ── empty product ─────────────────────────────────────────────────────────

    def test_empty_product_returns_empty_dict(self):
        from services.bulk_service import _map_off_product

        updates = _map_off_product({}, self._local())
        assert updates == {}


# ─────────────────────────────────────────────────────────────────────────────
# _fetch_off_image
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchOffImage:
    """services.bulk_service._fetch_off_image"""

    def test_no_image_url_returns_none(self):
        from services.bulk_service import _fetch_off_image

        # Product with no image fields at all — must return None without any
        # external call.
        result = _fetch_off_image({})
        assert result is None

    def test_all_image_fields_empty_returns_none(self):
        from services.bulk_service import _fetch_off_image

        product = {
            "image_front_url": "",
            "image_url": "",
            "image_front_small_url": "",
        }
        result = _fetch_off_image(product)
        assert result is None

    def test_image_fields_none_returns_none(self):
        from services.bulk_service import _fetch_off_image

        product = {
            "image_front_url": None,
            "image_url": None,
            "image_front_small_url": None,
        }
        result = _fetch_off_image(product)
        assert result is None

    def test_valid_url_calls_proxy_and_returns_data_uri(self):
        """When a URL is present, proxy_service.proxy_image is called and the
        result is encoded as a data URI."""
        from services.bulk_service import _fetch_off_image

        fake_image_bytes = b"\xff\xd8\xff" + b"\x00" * 10  # minimal JPEG-like
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(fake_image_bytes, "image/jpeg"),
        ):
            result = _fetch_off_image(
                {"image_front_url": "https://example.com/img.jpg"}
            )

        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_proxy_exception_returns_none(self):
        """If proxy_service.proxy_image raises, the function must return None
        instead of propagating the exception."""
        from services.bulk_service import _fetch_off_image

        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            side_effect=ConnectionError("unreachable"),
        ):
            result = _fetch_off_image(
                {"image_front_url": "https://example.com/img.jpg"}
            )

        assert result is None

    def test_oversized_image_returns_none(self):
        """Data URIs exceeding 2 MB must be discarded."""
        from services.bulk_service import _fetch_off_image

        # 2 MB of raw bytes will base64-expand to ~2.67 MB — over the limit.
        large_bytes = b"\x00" * (2 * 1024 * 1024)
        with patch(
            "services.bulk_service.proxy_service.proxy_image",
            return_value=(large_bytes, "image/jpeg"),
        ):
            result = _fetch_off_image(
                {"image_front_url": "https://example.com/large.jpg"}
            )

        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# get_refresh_status — consolidated key-presence test
# ─────────────────────────────────────────────────────────────────────────────


class TestGetRefreshStatusKeys:
    """Verify the full set of expected keys is always present.

    Detailed state tests (idle/not-done/report absence) live in
    test_bulk_service.py and are intentionally not duplicated here.
    """

    EXPECTED_KEYS = {
        "running",
        "current",
        "total",
        "name",
        "ean",
        "status",
        "updated",
        "skipped",
        "errors",
        "done",
    }

    def test_all_expected_keys_present(self, app_ctx):
        from services.bulk_service import get_refresh_status

        result = get_refresh_status()
        missing = self.EXPECTED_KEYS - result.keys()
        assert not missing, f"Missing keys from get_refresh_status(): {missing}"

    def test_returns_fresh_dict_each_call(self, app_ctx):
        from services.bulk_service import get_refresh_status

        r1 = get_refresh_status()
        r2 = get_refresh_status()
        assert r1 is not r2


# ─────────────────────────────────────────────────────────────────────────────
# start_refresh_from_off
# ─────────────────────────────────────────────────────────────────────────────


class TestStartRefreshFromOff:
    """services.bulk_service.start_refresh_from_off"""

    def test_returns_false_when_already_running(self, app_ctx):
        """If the in-memory job flag is already set, the function must return
        False immediately without spawning another thread."""
        import services.bulk_service as svc

        # Force the job into the 'running' state
        with svc._refresh_lock:
            svc._refresh_job["running"] = True
        try:
            result = svc.start_refresh_from_off()
        finally:
            # Always restore so later tests see an idle job
            with svc._refresh_lock:
                svc._refresh_job["running"] = False

        assert result is False

    def test_returns_true_when_not_running(self, app_ctx):
        """When the job is idle, start_refresh_from_off must return True and
        spawn a background thread (which we immediately stub out)."""
        import services.bulk_service as svc

        # Ensure idle state
        with svc._refresh_lock:
            svc._refresh_job["running"] = False

        with patch("services.bulk_service._run_refresh"):
            # Patch threading.Thread so no real thread is created
            mock_thread = MagicMock()
            with patch(
                "services.bulk_service.threading.Thread", return_value=mock_thread
            ):
                result = svc.start_refresh_from_off({"search_missing": False})

        # Restore state (thread was mocked so running is still True from the update)
        with svc._refresh_lock:
            svc._refresh_job["running"] = False

        assert result is True
        mock_thread.start.assert_called_once()

    def test_options_are_forwarded_to_run_refresh(self, app_ctx):
        """The options dict passed by the caller must be forwarded to _run_refresh."""
        import services.bulk_service as svc

        with svc._refresh_lock:
            svc._refresh_job["running"] = False

        captured_args = {}
        mock_thread = MagicMock()

        def capture_thread(**kwargs):
            captured_args.update(kwargs)
            return mock_thread

        with patch(
            "services.bulk_service.threading.Thread", side_effect=capture_thread
        ):
            svc.start_refresh_from_off({"min_certainty": 80})

        with svc._refresh_lock:
            svc._refresh_job["running"] = False

        assert captured_args.get("args") == ({"min_certainty": 80},)

    def test_job_state_reset_on_start(self, app_ctx):
        """Starting a fresh job must zero out counters from any previous run."""
        import services.bulk_service as svc

        with svc._refresh_lock:
            svc._refresh_job.update(
                running=False,
                updated=42,
                skipped=7,
                errors=3,
                done=True,
            )

        mock_thread = MagicMock()
        with patch("services.bulk_service.threading.Thread", return_value=mock_thread):
            svc.start_refresh_from_off()

        with svc._refresh_lock:
            assert svc._refresh_job["updated"] == 0
            assert svc._refresh_job["skipped"] == 0
            assert svc._refresh_job["errors"] == 0
            assert svc._refresh_job["done"] is False
            # Restore
            svc._refresh_job["running"] = False
