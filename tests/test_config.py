"""Tests for config.py — constants and computed fields."""

import pytest


class TestComputedFields:
    def test_pct_protein_cal(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_protein_cal"]
        p = {"protein": 20.0, "kcal": 200.0, "fat": 5.0, "carbs": 10.0}
        assert fn(p) == pytest.approx(40.0)  # 20*4/200*100

    def test_pct_protein_cal_none_protein(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_protein_cal"]
        assert fn({"protein": None, "kcal": 200.0}) is None

    def test_pct_protein_cal_zero_kcal(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_protein_cal"]
        assert fn({"protein": 20.0, "kcal": 0}) is None

    def test_pct_fat_cal(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_fat_cal"]
        p = {"fat": 10.0, "kcal": 200.0, "protein": 5.0, "carbs": 10.0}
        assert fn(p) == pytest.approx(45.0)  # 10*9/200*100

    def test_pct_carb_cal(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_carb_cal"]
        p = {"carbs": 25.0, "kcal": 200.0, "fat": 5.0, "protein": 10.0}
        assert fn(p) == pytest.approx(50.0)  # 25*4/200*100

    def test_pct_fat_cal_none(self):
        from config import COMPUTED_FIELDS
        fn = COMPUTED_FIELDS["pct_fat_cal"]
        assert fn({"fat": None, "kcal": 200.0}) is None


class TestScoreConfig:
    def test_all_entries_have_required_keys(self):
        from config import SCORE_CONFIG
        required = {"field", "label_key", "desc_key", "direction", "formula", "formula_min", "formula_max"}
        for sc in SCORE_CONFIG:
            assert required.issubset(sc.keys()), f"Missing keys in {sc['field']}"

    def test_score_config_map_matches(self):
        from config import SCORE_CONFIG, SCORE_CONFIG_MAP
        assert len(SCORE_CONFIG_MAP) == len(SCORE_CONFIG)
        for sc in SCORE_CONFIG:
            assert sc["field"] in SCORE_CONFIG_MAP

    def test_directions_valid(self):
        from config import SCORE_CONFIG
        for sc in SCORE_CONFIG:
            assert sc["direction"] in ("lower", "higher")

    def test_formulas_valid(self):
        from config import SCORE_CONFIG
        for sc in SCORE_CONFIG:
            assert sc["formula"] in ("minmax", "direct")


class TestConstants:
    def test_insert_placeholders_count(self):
        from config import INSERT_FIELDS, INSERT_PLACEHOLDERS
        field_count = len(INSERT_FIELDS.split(","))
        placeholder_count = len(INSERT_PLACEHOLDERS.split(","))
        assert field_count == placeholder_count

    def test_valid_columns_superset(self):
        from config import ALL_PRODUCT_FIELDS, _VALID_COLUMNS
        for f in ALL_PRODUCT_FIELDS:
            assert f in _VALID_COLUMNS

    def test_text_field_limits_subset(self):
        from config import _TEXT_FIELD_LIMITS, ALL_PRODUCT_FIELDS
        for tf in _TEXT_FIELD_LIMITS:
            assert tf in ALL_PRODUCT_FIELDS
