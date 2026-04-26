"""Unit tests for services/nutrition_parser.py."""
import pytest

from services.nutrition_parser import (
    parse_nutrition_response,
    parse_nutrition_text,
    _clean,
    _to_float,
    _strip_fences,
)


class TestJsonPath:
    def test_plain_json_object(self):
        text = '{"kcal": 250, "fat": 12.5, "protein": 8}'
        assert parse_nutrition_response(text) == {
            "kcal": 250.0,
            "fat": 12.5,
            "protein": 8.0,
        }

    def test_fenced_json(self):
        text = "```json\n{\"kcal\": 100, \"salt\": 0.5}\n```"
        assert parse_nutrition_response(text) == {"kcal": 100.0, "salt": 0.5}

    def test_fenced_json_no_language(self):
        text = "```\n{\"kcal\": 100}\n```"
        assert parse_nutrition_response(text) == {"kcal": 100.0}

    def test_pretty_printed_json(self):
        text = """
        {
            "kcal": 250,
            "energy_kj": 1045,
            "fat": 12.3,
            "saturated_fat": 4,
            "carbs": 30.1,
            "sugar": 5.0,
            "fiber": 3,
            "protein": 8.5,
            "salt": 0.8
        }
        """
        out = parse_nutrition_response(text)
        assert out == {
            "kcal": 250.0,
            "energy_kj": 1045.0,
            "fat": 12.3,
            "saturated_fat": 4.0,
            "carbs": 30.1,
            "sugar": 5.0,
            "fiber": 3.0,
            "protein": 8.5,
            "salt": 0.8,
        }

    def test_json_with_prose_wrapper(self):
        text = 'Here is the data: {"kcal": 100, "fat": 5} — extracted from the label.'
        assert parse_nutrition_response(text) == {"kcal": 100.0, "fat": 5.0}

    def test_json_with_string_values(self):
        text = '{"kcal": "250", "fat": "12,5", "salt": "0.8"}'
        assert parse_nutrition_response(text) == {
            "kcal": 250.0,
            "fat": 12.5,
            "salt": 0.8,
        }

    def test_json_unknown_keys_filtered(self):
        text = '{"kcal": 100, "vitamin_c": 50, "garbage": "nope", "protein": 8}'
        assert parse_nutrition_response(text) == {"kcal": 100.0, "protein": 8.0}

    def test_json_sanity_range_rejection(self):
        text = '{"kcal": 25000, "fat": 10, "salt": 999}'
        assert parse_nutrition_response(text) == {"fat": 10.0}

    def test_json_negative_values_rejected(self):
        text = '{"kcal": -50, "fat": 10}'
        assert parse_nutrition_response(text) == {"fat": 10.0}

    def test_json_null_values_ignored(self):
        text = '{"kcal": 100, "fat": null, "salt": null}'
        assert parse_nutrition_response(text) == {"kcal": 100.0}


class TestNorwegianLabel:
    def test_full_no_label_blob(self):
        text = (
            "N\u00e6ringsinnhold per 100 g\n"
            "Energi 1050 kJ / 250 kcal\n"
            "Fett 12 g\n"
            "herav mettede fettsyrer 4,0 g\n"
            "Karbohydrater 30 g\n"
            "herav sukkerarter 5 g\n"
            "Kostfiber 3 g\n"
            "Protein 8 g\n"
            "Salt 0,8 g"
        )
        out = parse_nutrition_response(text)
        assert out == {
            "kcal": 250.0,
            "energy_kj": 1050.0,
            "fat": 12.0,
            "saturated_fat": 4.0,
            "carbs": 30.0,
            "sugar": 5.0,
            "fiber": 3.0,
            "protein": 8.0,
            "salt": 0.8,
        }

    def test_no_label_with_decimal_comma(self):
        text = "Fett 12,5 g\nProtein 8,3 g\nSalt 0,85 g"
        out = parse_nutrition_text(text)
        assert out == {"fat": 12.5, "protein": 8.3, "salt": 0.85}

    def test_no_saturated_fat_not_confused_with_fat(self):
        text = "Fett 12 g\nherav mettede fettsyrer 4 g"
        out = parse_nutrition_text(text)
        assert out == {"fat": 12.0, "saturated_fat": 4.0}

    def test_no_sugar_not_confused_with_carbs(self):
        text = "Karbohydrater 30 g\nherav sukkerarter 5 g"
        out = parse_nutrition_text(text)
        assert out == {"carbs": 30.0, "sugar": 5.0}


class TestEnglishLabel:
    def test_full_en_label_blob(self):
        text = (
            "Nutrition per 100 g\n"
            "Energy 1050 kJ / 250 kcal\n"
            "Fat 12 g\n"
            "of which saturates 4 g\n"
            "Carbohydrate 30 g\n"
            "of which sugars 5 g\n"
            "Fibre 3 g\n"
            "Protein 8 g\n"
            "Salt 0.8 g"
        )
        out = parse_nutrition_response(text)
        assert out == {
            "kcal": 250.0,
            "energy_kj": 1050.0,
            "fat": 12.0,
            "saturated_fat": 4.0,
            "carbs": 30.0,
            "sugar": 5.0,
            "fiber": 3.0,
            "protein": 8.0,
            "salt": 0.8,
        }

    def test_en_saturated_fat_alternative(self):
        text = "Fat 15g\nSaturated fat 5g"
        out = parse_nutrition_text(text)
        assert out == {"fat": 15.0, "saturated_fat": 5.0}


class TestEdgeCases:
    def test_range_takes_lower_bound(self):
        text = '{"fat": "4-6", "protein": "8\u20139"}'
        assert parse_nutrition_response(text) == {"fat": 4.0, "protein": 8.0}

    def test_less_than_value(self):
        text = '{"salt": "<0.5", "sugar": "<1"}'
        assert parse_nutrition_response(text) == {"salt": 0.5, "sugar": 1.0}

    def test_approximately_value(self):
        text = '{"protein": "~8", "fat": "~12.5"}'
        assert parse_nutrition_response(text) == {"protein": 8.0, "fat": 12.5}

    def test_kj_only_label(self):
        text = "Energi 1050 kJ"
        assert parse_nutrition_text(text) == {"energy_kj": 1050.0}

    def test_kcal_only_label(self):
        text = "Energy 250 kcal per 100g"
        assert parse_nutrition_text(text) == {"kcal": 250.0}

    def test_empty_string(self):
        assert parse_nutrition_response("") == {}

    def test_none_input(self):
        assert parse_nutrition_response(None) == {}
        assert parse_nutrition_text(None) == {}

    def test_non_string_input(self):
        assert parse_nutrition_response(123) == {}
        assert parse_nutrition_text(["not", "a", "string"]) == {}

    def test_garbage_text(self):
        assert parse_nutrition_response("hello world, nothing numeric here") == {}

    def test_malformed_json_falls_back_to_regex(self):
        text = "{broken json but Fett 12 g and Protein 8 g}"
        assert parse_nutrition_response(text) == {"fat": 12.0, "protein": 8.0}

    def test_boolean_values_ignored(self):
        text = '{"kcal": true, "fat": false, "protein": 8}'
        assert parse_nutrition_response(text) == {"protein": 8.0}

    def test_json_list_not_object(self):
        text = '[1, 2, 3]'
        assert parse_nutrition_response(text) == {}


class TestToFloat:
    def test_int(self):
        assert _to_float(100) == 100.0

    def test_float(self):
        assert _to_float(12.5) == 12.5

    def test_comma_decimal(self):
        assert _to_float("0,8") == 0.8

    def test_string_with_unit(self):
        assert _to_float("12.5 g") == 12.5

    def test_leading_less_than(self):
        assert _to_float("<0.5") == 0.5

    def test_range(self):
        assert _to_float("4-6") == 4.0
        assert _to_float("4\u20136") == 4.0

    def test_none(self):
        assert _to_float(None) is None

    def test_bool_rejected(self):
        assert _to_float(True) is None
        assert _to_float(False) is None

    def test_empty_string(self):
        assert _to_float("") is None

    def test_non_numeric_string(self):
        assert _to_float("hello") is None


class TestClean:
    def test_empty_dict(self):
        assert _clean({}) == {}

    def test_none(self):
        assert _clean(None) == {}

    def test_filters_unknown_keys(self):
        assert _clean({"kcal": 100, "invalid_key": 50}) == {"kcal": 100.0}

    def test_drops_negative(self):
        assert _clean({"kcal": -1, "fat": 5}) == {"fat": 5.0}

    def test_drops_over_cap(self):
        assert _clean({"kcal": 1000, "fat": 10}) == {"fat": 10.0}

    def test_salt_cap(self):
        assert _clean({"salt": 100}) == {}
        assert _clean({"salt": 40}) == {"salt": 40.0}

    def test_energy_kj_cap(self):
        assert _clean({"energy_kj": 4000}) == {}
        assert _clean({"energy_kj": 1000}) == {"energy_kj": 1000.0}


class TestStripFences:
    def test_no_fence(self):
        assert _strip_fences("hello") == "hello"

    def test_empty(self):
        assert _strip_fences("") == ""
        assert _strip_fences(None) is None

    def test_json_fence(self):
        assert _strip_fences("```json\n{}\n```") == "{}"

    def test_bare_fence(self):
        assert _strip_fences("```\n{}\n```") == "{}"

    def test_uppercase_fence(self):
        assert _strip_fences("```JSON\n{}\n```") == "{}"
