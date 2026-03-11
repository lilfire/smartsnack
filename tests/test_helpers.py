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

    def test_special_characters(self):
        from helpers import _validate_category_name

        assert _validate_category_name("Snacks!@#") == "Invalid category name"


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

    def test_key_in_query_param(self, app, monkeypatch):
        import helpers

        monkeypatch.setattr(helpers, "_API_KEY", "secret123")
        with app.test_request_context("/test?api_key=secret123"):
            result = helpers._check_api_key()
            assert result is None
