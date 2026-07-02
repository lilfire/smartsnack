"""Tests for LSO-1698 medium-severity backend bug fixes (M1-M3, M6-M10, M16).

Each test class reproduces the original bug scenario and verifies the fix.
"""

import sys
import types

import pytest


def _add_product(client, name="TestProduct", ean=None, type_="Snacks", **fields):
    payload = {"type": type_, "name": name, **fields}
    if ean:
        payload["ean"] = ean
    resp = client.post("/api/products", json=payload)
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()["id"]


# ── M1: PUT /api/settings/language type validation ─────────────────────────


class TestM1LanguageTypeValidation:
    def test_null_language_returns_400(self, client):
        resp = client.put("/api/settings/language", json={"language": None})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "language must be a string"

    def test_numeric_language_returns_400(self, client):
        resp = client.put("/api/settings/language", json={"language": 42})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "language must be a string"

    def test_valid_language_still_works(self, client):
        resp = client.put("/api/settings/language", json={"language": "en"})
        assert resp.status_code == 200
        assert resp.get_json()["language"] == "en"


# ── M2: POST /api/products/<pid>/eans with null ean ────────────────────────


class TestM2EanNullValidation:
    def test_null_ean_returns_400(self, client):
        pid = _add_product(client, name="EanNullProduct")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": None})
        assert resp.status_code == 400

    def test_numeric_ean_returns_400(self, client):
        pid = _add_product(client, name="EanNumProduct")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": 12345678})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "ean must be a string"

    def test_valid_ean_still_works(self, client):
        pid = _add_product(client, name="EanOkProduct")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "12345678"})
        assert resp.status_code == 201


# ── M3: mixed OR filters (text + computed field) ───────────────────────────


class TestM3MixedOrFilters:
    def test_mixed_or_text_and_computed_no_400(self, client):
        _add_product(client, name="Chocolate Bar")
        _add_product(client, name="Apple Juice")
        filters = (
            '{"logic": "or", "children": ['
            '{"field": "name", "op": "contains", "value": "choc"},'
            '{"field": "total_score", "op": ">=", "value": "0"}]}'
        )
        resp = client.get("/api/products", query_string={"filters": filters})
        assert resp.status_code == 200, resp.get_json()
        names = [p["name"] for p in resp.get_json()["products"]]
        assert "Chocolate Bar" in names

    def test_mixed_or_text_equality(self, client):
        _add_product(client, name="Melkesjokolade")
        _add_product(client, name="Brunost")
        filters = (
            '{"logic": "or", "children": ['
            '{"field": "name", "op": "=", "value": "brunost"},'
            '{"field": "completeness", "op": ">", "value": "999"}]}'
        )
        resp = client.get("/api/products", query_string={"filters": filters})
        assert resp.status_code == 200, resp.get_json()
        names = [p["name"] for p in resp.get_json()["products"]]
        assert names == ["Brunost"]

    def test_condition_to_post_text_ops(self):
        from services.product_filters import _condition_to_post

        assert _condition_to_post("name", "contains", "Choc") == ("name", "contains", "choc")
        assert _condition_to_post("name", "=", "Bar") == ("name", "=", "bar")
        with pytest.raises(ValueError):
            _condition_to_post("name", ">", "abc")

    def test_evaluate_post_node_text(self):
        from services.product_filters import _evaluate_post_node

        product = {"name": "Chocolate Bar", "brand": None}
        assert _evaluate_post_node(
            {"field": "name", "op": "contains", "val": "choc"}, product
        )
        assert not _evaluate_post_node(
            {"field": "name", "op": "!contains", "val": "choc"}, product
        )
        assert _evaluate_post_node(
            {"field": "name", "op": "=", "val": "chocolate bar"}, product
        )
        assert _evaluate_post_node(
            {"field": "brand", "op": "!=", "val": "tine"}, product
        )


# ── M6: merge_products choices validation ──────────────────────────────────


class TestM6MergeChoicesValidation:
    def _two_products(self, client):
        target = _add_product(client, name="MergeTarget", kcal=100)
        source = _add_product(client, name="MergeSource", kcal=200)
        return target, source

    def test_non_numeric_choice_for_real_column_returns_400(self, client):
        target, source = self._two_products(client)
        resp = client.post(
            f"/api/products/{target}/merge",
            json={"source_id": source, "choices": {"kcal": "abc"}},
        )
        assert resp.status_code == 400

    def test_boolean_source_id_returns_400(self, client):
        target, _ = self._two_products(client)
        resp = client.post(
            f"/api/products/{target}/merge", json={"source_id": True}
        )
        assert resp.status_code == 400

    def test_non_string_choice_for_text_column_returns_400(self, client):
        target, source = self._two_products(client)
        resp = client.post(
            f"/api/products/{target}/merge",
            json={"source_id": source, "choices": {"brand": 123}},
        )
        assert resp.status_code == 400

    def test_unknown_choice_field_returns_400(self, client):
        target, source = self._two_products(client)
        resp = client.post(
            f"/api/products/{target}/merge",
            json={"source_id": source, "choices": {"evil_column": "x"}},
        )
        assert resp.status_code == 400

    def test_valid_numeric_string_choice_merges(self, client):
        target, source = self._two_products(client)
        resp = client.post(
            f"/api/products/{target}/merge",
            json={"source_id": source, "choices": {"kcal": "150.5"}},
        )
        assert resp.status_code == 200
        product = client.get(f"/api/products/{target}").get_json()
        assert product["kcal"] == 150.5

    def test_validate_choices_rejects_non_finite(self):
        from services.product_duplicate import _validate_choices

        with pytest.raises(ValueError):
            _validate_choices({"kcal": "inf"}, ["kcal"])
        with pytest.raises(ValueError):
            _validate_choices({"kcal": True}, ["kcal"])


# ── M7: LLM translate fallback chain and timeouts ──────────────────────────


class TestM7TranslateFallbackChain:
    def test_next_backend_tried_after_exception(self, monkeypatch):
        from services import llm_translate_service as svc

        def _boom(prompt):
            raise RuntimeError("provider down")

        def _ok(prompt):
            return "oversatt tekst"

        monkeypatch.setattr(svc, "_BACKENDS", [_boom, _ok])
        assert svc.translate_ingredients("some text", "no") == "oversatt tekst"

    def test_all_backends_fail_returns_original(self, monkeypatch):
        from services import llm_translate_service as svc

        def _boom(prompt):
            raise RuntimeError("down")

        monkeypatch.setattr(svc, "_BACKENDS", [_boom, _boom])
        assert svc.translate_ingredients("original", "no") == "original"

    def test_claude_client_gets_timeout(self, monkeypatch):
        from services import llm_translate_service as svc

        captured = {}

        class _FakeAnthropic:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.messages = types.SimpleNamespace(
                    create=lambda **kw: types.SimpleNamespace(
                        content=[types.SimpleNamespace(text="ok")]
                    )
                )

        fake_mod = types.SimpleNamespace(Anthropic=_FakeAnthropic)
        monkeypatch.setitem(sys.modules, "anthropic", fake_mod)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        assert svc._try_claude("prompt") == "ok"
        assert captured["timeout"] == svc._LLM_TIMEOUT_SECONDS


# ── M8: dispatch_ocr_bytes respects fallback_to_tesseract ──────────────────


class TestM8OcrBytesFallbackSetting:
    _PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    def _patch_common(self, monkeypatch, fallback_enabled):
        from services import ocr_core, settings_service, ocr_settings_service

        monkeypatch.setattr(
            settings_service, "get_ocr_backend", lambda: "claude_vision"
        )
        monkeypatch.setattr(
            ocr_core,
            "get_available_backends",
            lambda: [
                {"id": "tesseract", "name": "Tesseract", "available": True},
                {"id": "claude_vision", "name": "Claude", "available": False},
            ],
        )
        monkeypatch.setattr(
            ocr_settings_service,
            "get_ocr_settings",
            lambda: {"fallback_to_tesseract": fallback_enabled},
        )
        return ocr_core

    def test_fallback_disabled_raises(self, monkeypatch):
        ocr_core = self._patch_common(monkeypatch, fallback_enabled=False)
        with pytest.raises(ValueError, match="fallback to tesseract is disabled"):
            ocr_core.dispatch_ocr_bytes(self._PNG)

    def test_fallback_enabled_switches_to_tesseract(self, monkeypatch):
        ocr_core = self._patch_common(monkeypatch, fallback_enabled=True)
        monkeypatch.setitem(
            ocr_core._PROVIDERS, "tesseract", lambda *a, **kw: "ocr text"
        )
        result = ocr_core.dispatch_ocr_bytes(self._PNG)
        assert result["fallback"] is True
        assert result["text"] == "ocr text"


# ── M9: bulk endpoints hide internal exception text ─────────────────────────


class TestM9BulkGenericErrors:
    def test_refresh_off_hides_internal_error(self, client, monkeypatch):
        from services import bulk_service

        def _boom():
            raise RuntimeError("secret internal path /data/db.sqlite")

        monkeypatch.setattr(bulk_service, "refresh_from_off", _boom)
        resp = client.post("/api/bulk/refresh-off")
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Internal error"
        assert "secret" not in resp.get_data(as_text=True)

    def test_estimate_pq_hides_internal_error(self, client, monkeypatch):
        from services import bulk_service

        def _boom():
            raise TypeError("secret column name")

        monkeypatch.setattr(bulk_service, "estimate_all_pq", _boom)
        resp = client.post("/api/bulk/estimate-pq")
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Internal error"
        assert "secret" not in resp.get_data(as_text=True)

    def test_refresh_off_value_error_surfaces_message(self, client, monkeypatch):
        from services import bulk_service

        def _bad():
            raise ValueError("nothing to refresh")

        monkeypatch.setattr(bulk_service, "refresh_from_off", _bad)
        resp = client.post("/api/bulk/refresh-off")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "nothing to refresh"


# ── M10: OFF blueprint delegates to service layer ───────────────────────────


class TestM10OffServiceOrchestration:
    def test_route_returns_service_response(self, client, monkeypatch):
        from services import off_service

        monkeypatch.setattr(
            off_service,
            "add_and_sync_product",
            lambda data: {"ok": True, "status_verbose": "fields saved"},
        )
        resp = client.post("/api/off/add-product", json={"code": "123"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_route_maps_value_error_to_400(self, client, monkeypatch):
        from services import off_service

        def _bad(data):
            raise ValueError("off_err_no_ean")

        monkeypatch.setattr(off_service, "add_and_sync_product", _bad)
        resp = client.post("/api/off/add-product", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "off_err_no_ean"

    def test_route_maps_runtime_error_to_502(self, client, monkeypatch):
        from services import off_service

        def _down(data):
            raise RuntimeError("off_err_network")

        monkeypatch.setattr(off_service, "add_and_sync_product", _down)
        resp = client.post("/api/off/add-product", json={})
        assert resp.status_code == 502

    def test_service_uploads_image_and_sets_flag(self, app, monkeypatch):
        from services import off_service, image_service, product_crud

        monkeypatch.setattr(
            off_service, "add_product_to_off", lambda data: {"status_verbose": "saved"}
        )
        monkeypatch.setattr(
            image_service, "get_image", lambda pid: "data:image/jpeg;base64,abc"
        )
        uploads = []
        monkeypatch.setattr(
            off_service,
            "upload_image_to_off",
            lambda code, image: uploads.append((code, image)),
        )
        flags = []
        monkeypatch.setattr(
            product_crud,
            "mark_product_synced_with_off",
            lambda pid, code: flags.append((pid, code)),
        )
        result = off_service.add_and_sync_product(
            {"product_id": 7, "code": "5901234123457"}
        )
        assert result["image_uploaded"] is True
        assert result["synced_flag_set"] is True
        assert uploads == [("5901234123457", "data:image/jpeg;base64,abc")]
        assert flags == [(7, "5901234123457")]

    def test_service_ignores_boolean_product_id(self, monkeypatch):
        from services import off_service

        monkeypatch.setattr(
            off_service, "add_product_to_off", lambda data: {"status_verbose": "saved"}
        )
        result = off_service.add_and_sync_product({"product_id": True})
        assert result["image_uploaded"] is False
        assert result["synced_flag_set"] is False

    def test_flag_failure_reported_not_raised(self, monkeypatch):
        from services import off_service, image_service, product_crud

        monkeypatch.setattr(
            off_service, "add_product_to_off", lambda data: {"status_verbose": "saved"}
        )
        monkeypatch.setattr(image_service, "get_image", lambda pid: None)

        def _boom(pid, code):
            raise RuntimeError("db locked")

        monkeypatch.setattr(product_crud, "mark_product_synced_with_off", _boom)
        result = off_service.add_and_sync_product({"product_id": 3})
        assert result["ok"] is True
        assert result["synced_flag_set"] is False


# ── M16: translation writes use cross-process file locking ──────────────────


class TestM16CrossProcessLocking:
    def test_set_translation_key_acquires_flock(self, tmp_path, monkeypatch):
        import fcntl
        import json
        import translations

        monkeypatch.setattr(translations, "TRANSLATIONS_DIR", str(tmp_path))
        (tmp_path / "en.json").write_text('{"existing": "value"}', encoding="utf-8")

        flock_calls = []
        real_flock = fcntl.flock

        def _spy(fd, op):
            flock_calls.append(op)
            return real_flock(fd, op)

        monkeypatch.setattr(translations.fcntl, "flock", _spy)
        translations._set_translation_key("test_key", {"en": "Test Value"})

        assert fcntl.LOCK_EX in flock_calls
        assert fcntl.LOCK_UN in flock_calls
        data = json.loads((tmp_path / "en.json").read_text(encoding="utf-8"))
        assert data["test_key"] == "Test Value"
        assert data["existing"] == "value"
        assert (tmp_path / "en.json.lock").exists()

    def test_delete_translation_key_acquires_flock(self, tmp_path, monkeypatch):
        import fcntl
        import json
        import translations

        monkeypatch.setattr(translations, "TRANSLATIONS_DIR", str(tmp_path))
        for lang in ("no", "en", "se"):
            (tmp_path / f"{lang}.json").write_text(
                '{"doomed_key": "x", "kept": "y"}', encoding="utf-8"
            )

        flock_calls = []
        real_flock = fcntl.flock

        def _spy(fd, op):
            flock_calls.append(op)
            return real_flock(fd, op)

        monkeypatch.setattr(translations.fcntl, "flock", _spy)
        translations._delete_translation_key("doomed_key")

        assert flock_calls.count(fcntl.LOCK_EX) == 3
        for lang in ("no", "en", "se"):
            data = json.loads((tmp_path / f"{lang}.json").read_text(encoding="utf-8"))
            assert "doomed_key" not in data
            assert data["kept"] == "y"
