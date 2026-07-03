"""Tests for helpers.py — request parsing and validation helpers."""

import pytest


class TestNum:
    def test_none_returns_none(self):
        from helpers import _num

        assert _num({}, "x") is None

    def test_empty_string_returns_none(self):
        from helpers import _num

        assert _num({"x": ""}, "x") is None

    def test_valid_float(self):
        from helpers import _num

        assert _num({"x": "3.14"}, "x") == pytest.approx(3.14)

    def test_valid_int(self):
        from helpers import _num

        assert _num({"x": 42}, "x") == 42.0

    def test_invalid_string_raises(self):
        from helpers import _num

        with pytest.raises(ValueError, match="Invalid numeric value"):
            _num({"x": "abc"}, "x")

    def test_infinity_raises(self):
        from helpers import _num

        with pytest.raises(ValueError, match="Invalid numeric value"):
            _num({"x": float("inf")}, "x")

    def test_nan_raises(self):
        from helpers import _num

        with pytest.raises(ValueError, match="Invalid numeric value"):
            _num({"x": float("nan")}, "x")

    def test_zero(self):
        from helpers import _num

        assert _num({"x": 0}, "x") == 0.0

    def test_negative(self):
        from helpers import _num

        assert _num({"x": -5.5}, "x") == -5.5


class TestStrField:
    """LSO-1371: ``_str_field`` must coerce JSON ``null`` to default.

    Before this helper existed, ``data.get("k", "").strip()`` returned
    ``None`` (not the default) when the key was present but set to
    ``null`` — crashing every blueprint that did so with a 500.
    """

    def test_absent_key_returns_default(self):
        from helpers import _str_field

        assert _str_field({}, "x") == ""

    def test_absent_key_with_custom_default(self):
        from helpers import _str_field

        assert _str_field({}, "x", "\U0001f4e6") == "\U0001f4e6"

    def test_present_string_returned_as_is(self):
        from helpers import _str_field

        assert _str_field({"x": "  hello  "}, "x") == "  hello  "

    def test_present_none_returns_default(self):
        """JSON ``null`` (Python ``None``) must map to the default."""
        from helpers import _str_field

        assert _str_field({"x": None}, "x") == ""

    def test_present_none_with_custom_default(self):
        from helpers import _str_field

        assert _str_field({"x": None}, "x", "fallback") == "fallback"

    def test_strip_after_str_field_does_not_crash_on_null(self):
        """The whole point of the helper: ``.strip()`` must be safe."""
        from helpers import _str_field

        # Pre-fix: ``data.get("x", "").strip()`` would crash here.
        assert _str_field({"x": None}, "x").strip() == ""

    def test_empty_string_preserved(self):
        from helpers import _str_field

        assert _str_field({"x": ""}, "x") == ""


class TestSafeFloat:
    def test_valid_conversion(self):
        from helpers import _safe_float

        assert _safe_float("3.14") == pytest.approx(3.14)

    def test_int_input(self):
        from helpers import _safe_float

        assert _safe_float(10) == 10.0

    def test_invalid_string(self):
        from helpers import _safe_float

        with pytest.raises(ValueError, match="Invalid numeric value"):
            _safe_float("abc", "test_field")

    def test_none_raises(self):
        from helpers import _safe_float

        with pytest.raises(ValueError):
            _safe_float(None)

    def test_infinity_raises(self):
        from helpers import _safe_float

        with pytest.raises(ValueError, match="Non-finite"):
            _safe_float(float("inf"), "test")

    def test_nan_raises(self):
        from helpers import _safe_float

        with pytest.raises(ValueError, match="Non-finite"):
            _safe_float(float("nan"), "test")


class TestValidateKeywords:
    def test_valid_list(self):
        from helpers import _validate_keywords

        kws, err = _validate_keywords(["milk", "cheese"])
        assert err is None
        assert kws == ["milk", "cheese"]

    def test_csv_string(self):
        from helpers import _validate_keywords

        kws, err = _validate_keywords("milk, cheese, yoghurt")
        assert err is None
        assert kws == ["milk", "cheese", "yoghurt"]

    def test_too_many_keywords(self):
        from helpers import _validate_keywords
        from config import _PQ_MAX_KEYWORDS

        kws, err = _validate_keywords(["kw"] * (_PQ_MAX_KEYWORDS + 1))
        assert kws is None
        assert "Too many" in err

    def test_keyword_too_long(self):
        from helpers import _validate_keywords
        from config import _PQ_MAX_KEYWORD_LEN

        kws, err = _validate_keywords(["x" * (_PQ_MAX_KEYWORD_LEN + 1)])
        assert kws is None
        assert "max" in err

    def test_non_string_keyword(self):
        from helpers import _validate_keywords

        kws, err = _validate_keywords([123])
        assert kws is None
        assert err is not None

    def test_not_list_or_string(self):
        from helpers import _validate_keywords

        kws, err = _validate_keywords(42)
        assert kws is None
        assert "must be a list" in err

    def test_empty_csv_items_stripped(self):
        from helpers import _validate_keywords

        kws, err = _validate_keywords("a,,b, ,c")
        assert err is None
        assert kws == ["a", "b", "c"]


class TestValidateCategoryName:
    def test_valid_name(self):
        from helpers import _validate_category_name

        assert _validate_category_name("Snacks") is None

    def test_name_with_spaces_hyphens(self):
        from helpers import _validate_category_name

        assert _validate_category_name("Ice-Cream Bars") is None

    def test_empty_name(self):
        from helpers import _validate_category_name

        assert _validate_category_name("") == "Invalid category name"

    def test_too_long(self):
        from helpers import _validate_category_name
        from config import _MAX_CATEGORY_NAME_LEN

        assert (
            _validate_category_name("x" * (_MAX_CATEGORY_NAME_LEN + 1))
            == "Invalid category name"
        )

    def test_special_characters_allowed(self):
        from helpers import _validate_category_name

        assert _validate_category_name("Snacks!@#") is None
        assert _validate_category_name("Frukt & Grønt") is None
        assert _validate_category_name("Brød/Kaker") is None
        assert _validate_category_name("O'Brien's") is None

    def test_control_characters_rejected(self):
        from helpers import _validate_category_name

        assert _validate_category_name("Snacks\x00") == "Invalid category name"
        assert _validate_category_name("Snacks\n") == "Invalid category name"

    def test_whitespace_only_rejected(self):
        from helpers import _validate_category_name

        assert _validate_category_name("   ") == "Invalid category name"


class TestRequireJson:
    def test_valid_json(self, app):
        from helpers import _require_json

        with app.test_request_context(
            "/test",
            method="POST",
            content_type="application/json",
            data='{"key": "value"}',
        ):
            result = _require_json()
            assert result == {"key": "value"}

    def test_missing_json(self, app):
        from helpers import _require_json

        with app.test_request_context("/test", method="POST"):
            with pytest.raises(ValueError, match="Invalid or missing JSON"):
                _require_json()

    def test_invalid_json(self, app):
        from helpers import _require_json

        with app.test_request_context(
            "/test",
            method="POST",
            content_type="application/json",
            data="not json",
        ):
            with pytest.raises(ValueError, match="Invalid or missing JSON"):
                _require_json()


class TestCheckApiKey:
    def test_no_key_configured(self, app, monkeypatch):
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "")
        with app.test_request_context("/test"):
            result = helpers._check_api_key()
            assert result is None

    def test_valid_key_in_header(self, app, monkeypatch):
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_request_context("/test", headers={"X-API-Key": "secret123"}):
            result = helpers._check_api_key()
            assert result is None

    def test_invalid_key(self, app, monkeypatch):
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_request_context("/test", headers={"X-API-Key": "wrong"}):
            result = helpers._check_api_key()
            assert result is not None
            response, status = result
            assert status == 401

    def test_key_in_query_param_rejected(self, app, monkeypatch):
        """?api_key= query string must NOT be accepted — it gets logged in access logs."""
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_request_context("/test?api_key=secret123"):
            result = helpers._check_api_key()
            assert result is not None, "query-string api_key must be rejected"
            response, status = result
            assert status == 401


class TestRequireJsonBodyType:
    """LSO-1672 H1: ``_require_json`` must reject non-dict JSON bodies.

    Every POST/PUT handler calls ``.get()``/``.pop()`` on the parsed body;
    a valid-JSON string/array/number body used to flow through and crash
    with ``AttributeError`` → 500. It must raise ``ValueError`` → 400.
    """

    def _ctx(self, app, body):
        return app.test_request_context(
            "/test",
            method="POST",
            content_type="application/json",
            data=body,
        )

    def test_require_json_rejects_string_body(self, app):
        from helpers import _require_json

        with self._ctx(app, '"hello"'):
            with pytest.raises(ValueError, match="must be a JSON object"):
                _require_json()

    def test_require_json_rejects_array_body(self, app):
        from helpers import _require_json

        with self._ctx(app, "[1, 2, 3]"):
            with pytest.raises(ValueError, match="must be a JSON object"):
                _require_json()

    def test_require_json_rejects_number_body(self, app):
        from helpers import _require_json

        with self._ctx(app, "42"):
            with pytest.raises(ValueError, match="must be a JSON object"):
                _require_json()

    def test_require_json_rejects_boolean_body(self, app):
        from helpers import _require_json

        with self._ctx(app, "true"):
            with pytest.raises(ValueError, match="must be a JSON object"):
                _require_json()

    def test_require_json_accepts_object(self, app):
        from helpers import _require_json

        with self._ctx(app, "{}"):
            assert _require_json() == {}

    def test_post_string_body_returns_400_not_500(self, client):
        """A real POST handler must map the ValueError to HTTP 400."""
        resp = client.post(
            "/api/products", data='"hello"', content_type="application/json"
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Request body must be a JSON object"

    def test_post_array_body_returns_400_not_500(self, client):
        resp = client.post(
            "/api/products", data="[1, 2, 3]", content_type="application/json"
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Request body must be a JSON object"

    def test_post_number_body_returns_400_not_500(self, client):
        resp = client.post(
            "/api/products", data="42", content_type="application/json"
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Request body must be a JSON object"


class TestStrFieldCoercion:
    """LSO-1672 H2: ``_str_field`` must coerce non-string JSON values.

    A numeric field value (e.g. ``{"ean": 7038010009457}``) used to be
    returned raw and crash downstream ``.strip()`` calls with
    ``AttributeError`` → 500.
    """

    def test_str_field_coerces_integer(self):
        from helpers import _str_field

        assert _str_field({"ean": 7038010009457}, "ean") == "7038010009457"

    def test_str_field_coerces_float(self):
        from helpers import _str_field

        assert _str_field({"v": 1.5}, "v") == "1.5"

    def test_str_field_coerces_boolean(self):
        from helpers import _str_field

        assert _str_field({"x": True}, "x") == "True"

    def test_str_field_null_returns_default(self):
        from helpers import _str_field

        assert _str_field({"x": None}, "x") == ""

    def test_str_field_string_passthrough(self):
        from helpers import _str_field

        assert _str_field({"x": "hi"}, "x") == "hi"

    def test_str_field_coerced_value_strips_safely(self):
        """The whole point: downstream ``.strip()`` must never crash."""
        from helpers import _str_field

        assert _str_field({"ean": 123}, "ean").strip() == "123"
