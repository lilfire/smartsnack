"""Advanced tests for services/product_service.py.

Covers: flag operations, completeness computation, advanced filter parsing,
condition SQL generation, post-filter evaluation, and integration tests for
list_products, add_product, and update_product with flags.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_product(db, name="Test Product", category="Snacks"):
    """Insert a minimal product and return its id."""
    cur = db.execute(
        "INSERT INTO products (type, name) VALUES (?, ?)", (category, name)
    )
    db.commit()
    return cur.lastrowid


def _get_flags_for(db, pid):
    """Return set of flag names for a product."""
    rows = db.execute(
        "SELECT flag FROM product_flags WHERE product_id = ?", (pid,)
    ).fetchall()
    return {r["flag"] for r in rows}


# ---------------------------------------------------------------------------
# _get_product_flags
# ---------------------------------------------------------------------------


class TestGetProductFlags:
    def test_empty_product_list_returns_empty_dict(self, db):
        from services.product_service import _get_product_flags

        result = _get_product_flags(db.cursor(), [])
        assert result == {}

    def test_product_with_no_flags_not_in_result(self, db, seed_product):
        from services.product_service import _get_product_flags

        result = _get_product_flags(db.cursor(), [seed_product])
        # key may be absent when no flags exist
        assert result.get(seed_product, []) == []

    def test_product_with_flags_returned(self, db, seed_product):
        from services.product_service import _get_product_flags

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        result = _get_product_flags(db.cursor(), [seed_product])
        assert "is_discontinued" in result[seed_product]

    def test_multiple_flags_for_one_product(self, db, seed_product):
        from services.product_service import _get_product_flags

        for flag in ("is_discontinued", "is_synced_with_off"):
            db.execute(
                "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
                (seed_product, flag),
            )
        db.commit()

        result = _get_product_flags(db.cursor(), [seed_product])
        assert set(result[seed_product]) == {"is_discontinued", "is_synced_with_off"}

    def test_flags_grouped_by_product_id(self, db, seed_category):
        from services.product_service import _get_product_flags

        pid1 = _insert_product(db, name="Product Alpha")
        pid2 = _insert_product(db, name="Product Beta")

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid1, "is_discontinued"),
        )
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid2, "is_synced_with_off"),
        )
        db.commit()

        result = _get_product_flags(db.cursor(), [pid1, pid2])
        assert "is_discontinued" in result[pid1]
        assert "is_synced_with_off" in result[pid2]

    def test_unknown_product_id_not_in_result(self, db):
        from services.product_service import _get_product_flags

        result = _get_product_flags(db.cursor(), [999999])
        assert result == {}


# ---------------------------------------------------------------------------
# _set_user_flags
# ---------------------------------------------------------------------------


class TestSetUserFlags:
    def test_set_valid_user_flag(self, db, seed_product):
        from services.product_service import _set_user_flags

        _set_user_flags(db, seed_product, ["is_discontinued"])
        db.commit()
        assert "is_discontinued" in _get_flags_for(db, seed_product)

    def test_unknown_flag_is_ignored(self, db, seed_product):
        from services.product_service import _set_user_flags

        _set_user_flags(db, seed_product, ["totally_made_up_flag"])
        db.commit()
        assert _get_flags_for(db, seed_product) == set()

    def test_system_flag_is_ignored(self, db, seed_product):
        from services.product_service import _set_user_flags

        _set_user_flags(db, seed_product, ["is_synced_with_off"])
        db.commit()
        assert "is_synced_with_off" not in _get_flags_for(db, seed_product)

    def test_replaces_existing_user_flags(self, db, seed_product):
        from services.product_service import _set_user_flags

        # Set is_discontinued first
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        # Now replace with empty list
        _set_user_flags(db, seed_product, [])
        db.commit()
        assert "is_discontinued" not in _get_flags_for(db, seed_product)

    def test_system_flag_preserved_when_clearing_user_flags(self, db, seed_product):
        from services.product_service import _set_user_flags

        # Place a system flag directly
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_synced_with_off"),
        )
        db.commit()

        # Clearing user flags must not remove the system flag
        _set_user_flags(db, seed_product, [])
        db.commit()
        assert "is_synced_with_off" in _get_flags_for(db, seed_product)

    def test_empty_flags_list_clears_user_flags(self, db, seed_product):
        from services.product_service import _set_user_flags

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        _set_user_flags(db, seed_product, [])
        db.commit()
        assert _get_flags_for(db, seed_product) == set()


# ---------------------------------------------------------------------------
# set_system_flag
# ---------------------------------------------------------------------------


class TestSetSystemFlag:
    def test_set_system_flag_true(self, app_ctx, seed_product):
        from services.product_service import set_system_flag
        from db import get_db

        set_system_flag(seed_product, "is_synced_with_off", True)
        row = (
            get_db()
            .execute(
                "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = ?",
                (seed_product, "is_synced_with_off"),
            )
            .fetchone()
        )
        assert row is not None

    def test_set_system_flag_false_clears_it(self, app_ctx, seed_product):
        from services.product_service import set_system_flag
        from db import get_db

        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_synced_with_off"),
        )
        db.commit()

        set_system_flag(seed_product, "is_synced_with_off", False)
        row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = ?",
            (seed_product, "is_synced_with_off"),
        ).fetchone()
        assert row is None

    def test_set_system_flag_idempotent(self, app_ctx, seed_product):
        from services.product_service import set_system_flag
        from db import get_db

        set_system_flag(seed_product, "is_synced_with_off", True)
        set_system_flag(seed_product, "is_synced_with_off", True)

        rows = (
            get_db()
            .execute(
                "SELECT COUNT(*) FROM product_flags WHERE product_id = ? AND flag = ?",
                (seed_product, "is_synced_with_off"),
            )
            .fetchone()[0]
        )
        assert rows == 1

    def test_unknown_flag_raises_value_error(self, app_ctx, seed_product):
        from services.product_service import set_system_flag

        with pytest.raises(ValueError, match="Unknown flag"):
            set_system_flag(seed_product, "not_a_real_flag", True)

    def test_user_flag_name_raises_value_error(self, app_ctx, seed_product):
        """set_system_flag should also reject flags not in flag_definitions."""
        from services.product_service import set_system_flag

        with pytest.raises(ValueError, match="Unknown flag"):
            set_system_flag(seed_product, "completely_absent", True)


# ---------------------------------------------------------------------------
# _compute_completeness
# ---------------------------------------------------------------------------


class TestComputeCompleteness:
    def test_fully_filled_product_scores_100(self):
        from services.product_service import _compute_completeness
        from config import COMPLETENESS_FIELDS

        p = {f: 1.0 for f in COMPLETENESS_FIELDS if f != "image"}
        p["has_image"] = True
        # Also fill "image" placeholder via has_image; remove raw "image" key if present
        p.pop("image", None)
        assert _compute_completeness(p) == 100

    def test_empty_product_scores_0(self):
        from services.product_service import _compute_completeness

        p = {}
        assert _compute_completeness(p) == 0

    def test_partial_product_between_0_and_100(self):
        from services.product_service import _compute_completeness
        from config import COMPLETENESS_FIELDS

        # Fill exactly half the non-image fields
        non_image = [f for f in COMPLETENESS_FIELDS if f != "image"]
        half = non_image[: len(non_image) // 2]
        p = {f: 1.0 for f in half}
        score = _compute_completeness(p)
        assert 0 < score < 100

    def test_image_counted_via_has_image_true(self):
        from services.product_service import _compute_completeness

        p_with = {"has_image": True}
        p_without = {"has_image": False}
        assert _compute_completeness(p_with) > _compute_completeness(p_without)

    def test_empty_string_not_counted(self):
        from services.product_service import _compute_completeness

        p_empty = {"brand": ""}
        p_filled = {"brand": "TestBrand"}
        assert _compute_completeness(p_empty) < _compute_completeness(p_filled)

    def test_none_value_not_counted(self):
        from services.product_service import _compute_completeness

        p_none = {"kcal": None}
        p_filled = {"kcal": 400.0}
        assert _compute_completeness(p_none) < _compute_completeness(p_filled)


# ---------------------------------------------------------------------------
# _parse_condition
# ---------------------------------------------------------------------------


class TestParseCondition:
    def test_valid_numeric_condition(self, app_ctx):
        from services.product_service import _parse_condition

        field, op, value, sql_op = _parse_condition(
            {"field": "kcal", "op": ">=", "value": "400"}
        )
        assert field == "kcal"
        assert op == ">="
        assert value == "400"
        assert sql_op == ">="

    def test_valid_text_condition(self, app_ctx):
        from services.product_service import _parse_condition

        field, op, value, sql_op = _parse_condition(
            {"field": "name", "op": "contains", "value": "popcorn"}
        )
        assert field == "name"
        assert op == "contains"
        assert sql_op == "LIKE"

    def test_invalid_field_raises(self, app_ctx):
        from services.product_service import _parse_condition

        with pytest.raises(ValueError, match="Invalid filter field"):
            _parse_condition({"field": "nonexistent", "op": "=", "value": "x"})

    def test_invalid_operator_raises(self, app_ctx):
        from services.product_service import _parse_condition

        with pytest.raises(ValueError, match="Invalid filter operator"):
            _parse_condition({"field": "kcal", "op": "~~", "value": "100"})

    def test_empty_value_raises(self, app_ctx):
        from services.product_service import _parse_condition

        with pytest.raises(ValueError, match="Filter value required"):
            _parse_condition({"field": "kcal", "op": "=", "value": ""})

    def test_flag_condition_true(self, app_ctx):
        from services.product_service import _parse_condition

        field, op, value, sql_op = _parse_condition(
            {"field": "flag:is_discontinued", "op": "=", "value": "true"}
        )
        assert field == "flag:is_discontinued"
        assert value == "true"
        assert sql_op == "="

    def test_flag_condition_false(self, app_ctx):
        from services.product_service import _parse_condition

        field, op, value, sql_op = _parse_condition(
            {"field": "flag:is_discontinued", "op": "=", "value": "false"}
        )
        assert value == "false"

    def test_flag_invalid_operator_raises(self, app_ctx):
        from services.product_service import _parse_condition

        with pytest.raises(ValueError, match="not valid for flag field"):
            _parse_condition(
                {"field": "flag:is_discontinued", "op": "!=", "value": "true"}
            )

    def test_flag_invalid_value_raises(self, app_ctx):
        from services.product_service import _parse_condition

        with pytest.raises(ValueError, match="Flag value must be"):
            _parse_condition(
                {"field": "flag:is_discontinued", "op": "=", "value": "yes"}
            )

    def test_post_query_field_accepted(self, app_ctx):
        from services.product_service import _parse_condition

        field, op, value, sql_op = _parse_condition(
            {"field": "total_score", "op": ">=", "value": "0.5"}
        )
        assert field == "total_score"


# ---------------------------------------------------------------------------
# _condition_to_sql
# ---------------------------------------------------------------------------


class TestConditionToSql:
    def test_text_field_contains(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("name", "contains", "popcorn", "LIKE")
        assert "LIKE" in sql
        assert "%popcorn%" in param

    def test_text_field_contains_escapes_percent(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("name", "contains", "100%corn", "LIKE")
        assert "\\%" in param

    def test_text_field_equals(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("name", "=", "Chips", "=")
        assert "LOWER" in sql
        assert param == "Chips"

    def test_numeric_field_greater_than(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("kcal", ">", "300", ">")
        assert "kcal >" in sql
        assert param == 300.0

    def test_numeric_field_less_than_or_equal(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("protein", "<=", "20.5", "<=")
        assert "protein <=" in sql
        assert param == pytest.approx(20.5)

    def test_flag_field_true_produces_exists(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("flag:is_discontinued", "=", "true", "=")
        assert "EXISTS" in sql
        assert "NOT" not in sql
        assert param == "is_discontinued"

    def test_flag_field_false_produces_not_exists(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("flag:is_discontinued", "=", "false", "=")
        assert "NOT EXISTS" in sql
        assert param == "is_discontinued"

    def test_text_field_not_contains(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("name", "!contains", "popcorn", "NOT_LIKE")
        assert "NOT LIKE" in sql
        assert "%popcorn%" in param

    def test_text_field_not_contains_escapes_percent(self):
        from services.product_service import _condition_to_sql

        sql, param = _condition_to_sql("name", "!contains", "100%corn", "NOT_LIKE")
        assert "NOT LIKE" in sql
        assert "\\%" in param

    def test_numeric_contains_raises(self):
        from services.product_service import _condition_to_sql

        with pytest.raises(ValueError, match="not valid for numeric"):
            _condition_to_sql("kcal", "contains", "foo", "LIKE")

    def test_numeric_not_contains_raises(self):
        from services.product_service import _condition_to_sql

        with pytest.raises(ValueError, match="not valid for numeric"):
            _condition_to_sql("kcal", "!contains", "foo", "NOT_LIKE")

    def test_non_numeric_value_raises(self):
        from services.product_service import _condition_to_sql

        with pytest.raises(ValueError, match="Invalid numeric value"):
            _condition_to_sql("kcal", ">", "not_a_number", ">")

    def test_text_invalid_operator_raises(self):
        from services.product_service import _condition_to_sql

        with pytest.raises(ValueError, match="not valid for text field"):
            _condition_to_sql("name", ">", "abc", ">")


# ---------------------------------------------------------------------------
# _convert_legacy_format
# ---------------------------------------------------------------------------


class TestConvertLegacyFormat:
    def test_new_format_passes_through(self):
        from services.product_service import _convert_legacy_format

        data = {
            "logic": "and",
            "children": [{"field": "kcal", "op": ">", "value": "100"}],
        }
        result = _convert_legacy_format(data)
        assert result is data

    def test_legacy_flat_conditions(self):
        from services.product_service import _convert_legacy_format

        cond = {"field": "kcal", "op": ">", "value": "100"}
        data = {"logic": "or", "conditions": [cond]}
        result = _convert_legacy_format(data)
        assert result["logic"] == "or"
        assert result["children"] == [cond]

    def test_old_grouped_format(self):
        from services.product_service import _convert_legacy_format

        cond = {"field": "kcal", "op": ">", "value": "100"}
        data = {
            "logic": "and",
            "groups": [
                {"logic": "or", "conditions": [cond]},
            ],
        }
        result = _convert_legacy_format(data)
        assert result["logic"] == "and"
        assert len(result["children"]) == 1
        child = result["children"][0]
        assert child["logic"] == "or"
        assert child["children"] == [cond]

    def test_old_grouped_skips_group_without_conditions(self):
        from services.product_service import _convert_legacy_format

        data = {
            "logic": "and",
            "groups": [
                {"logic": "or", "conditions": []},
                {
                    "logic": "and",
                    "conditions": [{"field": "kcal", "op": ">", "value": "10"}],
                },
            ],
        }
        result = _convert_legacy_format(data)
        # Only group with non-empty conditions should appear
        assert len(result["children"]) == 1

    def test_unrecognised_format_raises(self):
        from services.product_service import _convert_legacy_format

        with pytest.raises(ValueError, match="Unrecognised filter format"):
            _convert_legacy_format({"logic": "and"})


# ---------------------------------------------------------------------------
# _count_conditions
# ---------------------------------------------------------------------------


class TestCountConditions:
    def test_single_leaf(self):
        from services.product_service import _count_conditions

        node = {"field": "kcal", "op": ">", "value": "100"}
        assert _count_conditions(node) == 1

    def test_group_with_two_leaves(self):
        from services.product_service import _count_conditions

        node = {
            "logic": "and",
            "children": [
                {"field": "kcal", "op": ">", "value": "100"},
                {"field": "protein", "op": "<", "value": "20"},
            ],
        }
        assert _count_conditions(node) == 2

    def test_nested_groups(self):
        from services.product_service import _count_conditions

        node = {
            "logic": "and",
            "children": [
                {"field": "kcal", "op": ">", "value": "100"},
                {
                    "logic": "or",
                    "children": [
                        {"field": "protein", "op": "<", "value": "20"},
                        {"field": "fat", "op": ">=", "value": "5"},
                    ],
                },
            ],
        }
        assert _count_conditions(node) == 3

    def test_empty_children(self):
        from services.product_service import _count_conditions

        node = {"logic": "and", "children": []}
        assert _count_conditions(node) == 0

    def test_non_dict_children_ignored(self):
        from services.product_service import _count_conditions

        node = {"logic": "and", "children": ["not_a_dict", 42]}
        assert _count_conditions(node) == 0


# ---------------------------------------------------------------------------
# _parse_advanced_filters
# ---------------------------------------------------------------------------


class TestParseAdvancedFilters:
    def test_valid_json_single_condition(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "kcal", "op": ">=", "value": "200"}],
            }
        )
        sql, params, post = _parse_advanced_filters(filters)
        assert "kcal" in sql
        assert 200.0 in params
        assert post is None

    def test_invalid_json_raises(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        with pytest.raises(ValueError, match="Invalid filters JSON"):
            _parse_advanced_filters("{not valid json}")

    def test_non_object_json_raises(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        with pytest.raises(ValueError, match="Filters must be a JSON object"):
            _parse_advanced_filters("[1, 2, 3]")

    def test_too_many_conditions_raises(self, app_ctx):
        from services.product_service import _parse_advanced_filters
        from config import MAX_FILTER_CONDITIONS

        conditions = [
            {"field": "kcal", "op": ">", "value": str(i)}
            for i in range(MAX_FILTER_CONDITIONS + 1)
        ]
        filters = json.dumps({"logic": "and", "children": conditions})
        with pytest.raises(ValueError, match="Too many filter conditions"):
            _parse_advanced_filters(filters)

    def test_post_filter_for_total_score(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "total_score", "op": ">=", "value": "0.5"}],
            }
        )
        sql, params, post = _parse_advanced_filters(filters)
        assert sql == "" or sql is not None
        assert post is not None
        assert post["field"] == "total_score"

    def test_legacy_flat_format_accepted(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        filters = json.dumps(
            {
                "logic": "and",
                "conditions": [{"field": "kcal", "op": ">=", "value": "100"}],
            }
        )
        sql, params, post = _parse_advanced_filters(filters)
        assert "kcal" in sql

    def test_flag_filter_accepted(self, app_ctx):
        from services.product_service import _parse_advanced_filters

        filters = json.dumps(
            {
                "logic": "and",
                "children": [
                    {"field": "flag:is_discontinued", "op": "=", "value": "true"}
                ],
            }
        )
        sql, params, post = _parse_advanced_filters(filters)
        assert "is_discontinued" in params


# ---------------------------------------------------------------------------
# _evaluate_post_node
# ---------------------------------------------------------------------------


class TestEvaluatePostNode:
    def test_leaf_true_when_condition_met(self):
        from services.product_service import _evaluate_post_node

        node = {"field": "total_score", "op": ">=", "val": 0.5}
        product = {"total_score": 0.8}
        assert _evaluate_post_node(node, product) is True

    def test_leaf_false_when_condition_not_met(self):
        from services.product_service import _evaluate_post_node

        node = {"field": "total_score", "op": ">=", "val": 0.5}
        product = {"total_score": 0.3}
        assert _evaluate_post_node(node, product) is False

    def test_leaf_false_when_field_missing(self):
        from services.product_service import _evaluate_post_node

        node = {"field": "total_score", "op": ">=", "val": 0.5}
        product = {}
        assert _evaluate_post_node(node, product) is False

    def test_and_group_all_true(self):
        from services.product_service import _evaluate_post_node

        node = {
            "logic": "AND",
            "children": [
                {"field": "total_score", "op": ">=", "val": 0.5},
                {"field": "completeness", "op": ">", "val": 50.0},
            ],
        }
        product = {"total_score": 0.8, "completeness": 75.0}
        assert _evaluate_post_node(node, product) is True

    def test_and_group_one_false(self):
        from services.product_service import _evaluate_post_node

        node = {
            "logic": "AND",
            "children": [
                {"field": "total_score", "op": ">=", "val": 0.5},
                {"field": "completeness", "op": ">", "val": 50.0},
            ],
        }
        product = {"total_score": 0.8, "completeness": 30.0}
        assert _evaluate_post_node(node, product) is False

    def test_or_group_one_true(self):
        from services.product_service import _evaluate_post_node

        node = {
            "logic": "OR",
            "children": [
                {"field": "total_score", "op": ">=", "val": 0.9},
                {"field": "completeness", "op": ">", "val": 50.0},
            ],
        }
        product = {"total_score": 0.5, "completeness": 75.0}
        assert _evaluate_post_node(node, product) is True

    def test_or_group_all_false(self):
        from services.product_service import _evaluate_post_node

        node = {
            "logic": "OR",
            "children": [
                {"field": "total_score", "op": ">=", "val": 0.9},
                {"field": "completeness", "op": ">", "val": 90.0},
            ],
        }
        product = {"total_score": 0.5, "completeness": 30.0}
        assert _evaluate_post_node(node, product) is False

    def test_empty_children_returns_true(self):
        from services.product_service import _evaluate_post_node

        node = {"logic": "AND", "children": []}
        assert _evaluate_post_node(node, {}) is True

    def test_equals_operator(self):
        from services.product_service import _evaluate_post_node

        node = {"field": "completeness", "op": "=", "val": 100.0}
        assert _evaluate_post_node(node, {"completeness": 100}) is True
        assert _evaluate_post_node(node, {"completeness": 99}) is False

    def test_not_equals_operator(self):
        from services.product_service import _evaluate_post_node

        node = {"field": "completeness", "op": "!=", "val": 100.0}
        assert _evaluate_post_node(node, {"completeness": 50}) is True
        assert _evaluate_post_node(node, {"completeness": 100}) is False


# ---------------------------------------------------------------------------
# _apply_post_filters
# ---------------------------------------------------------------------------


class TestApplyPostFilters:
    def test_no_spec_returns_all(self):
        from services.product_service import _apply_post_filters

        products = [{"total_score": 0.1}, {"total_score": 0.9}]
        assert _apply_post_filters(products, None) == products

    def test_none_spec_returns_all(self):
        from services.product_service import _apply_post_filters

        products = [{"total_score": 0.8}]
        assert _apply_post_filters(products, None) is products

    def test_leaf_spec_filters_correctly(self):
        from services.product_service import _apply_post_filters

        products = [
            {"total_score": 0.2},
            {"total_score": 0.6},
            {"total_score": 0.9},
        ]
        spec = {"field": "total_score", "op": ">=", "val": 0.5}
        result = _apply_post_filters(products, spec)
        assert len(result) == 2
        assert all(p["total_score"] >= 0.5 for p in result)

    def test_group_spec_filters_correctly(self):
        from services.product_service import _apply_post_filters

        products = [
            {"total_score": 0.8, "completeness": 80},
            {"total_score": 0.3, "completeness": 80},
            {"total_score": 0.8, "completeness": 20},
        ]
        spec = {
            "logic": "AND",
            "children": [
                {"field": "total_score", "op": ">=", "val": 0.5},
                {"field": "completeness", "op": ">=", "val": 50},
            ],
        }
        result = _apply_post_filters(products, spec)
        assert len(result) == 1
        assert result[0]["total_score"] == 0.8
        assert result[0]["completeness"] == 80

    def test_empty_spec_dict_returns_all(self):
        from services.product_service import _apply_post_filters

        products = [{"total_score": 0.5}]
        assert _apply_post_filters(products, {}) == products


# ---------------------------------------------------------------------------
# list_products with advanced_filters
# ---------------------------------------------------------------------------


class TestListProductsAdvancedFilters:
    def test_filter_by_kcal(self, app_ctx, seed_product):
        from services.product_service import list_products

        # Seed product has kcal=450; filter for kcal >= 400
        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "kcal", "op": ">=", "value": "400"}],
            }
        )
        result = list_products(None, None, advanced_filters=filters)
        assert len(result["products"]) >= 1
        assert all(p["kcal"] >= 400 for p in result["products"])

    def test_filter_excludes_products(self, app_ctx, seed_product):
        from services.product_service import list_products

        # Seed product has kcal=450; filter for kcal < 10 should exclude it
        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "kcal", "op": "<", "value": "10"}],
            }
        )
        result = list_products(None, None, advanced_filters=filters)
        assert all(p.get("kcal", 0) < 10 for p in result["products"])

    def test_filter_by_name_contains(self, app_ctx, seed_product):
        from services.product_service import list_products

        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "name", "op": "contains", "value": "Popcorn"}],
            }
        )
        result = list_products(None, None, advanced_filters=filters)
        assert len(result["products"]) >= 1
        assert all("popcorn" in p["name"].lower() for p in result["products"])

    def test_filter_by_total_score_uses_post_filter(self, app_ctx, seed_product):
        from services.product_service import list_products

        # total_score is a post-query field; filter for score >= 0 should return all
        filters = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "total_score", "op": ">=", "value": "0"}],
            }
        )
        result_filtered = list_products(None, None, advanced_filters=filters)
        result_all = list_products(None, None)
        assert len(result_filtered["products"]) == len(result_all["products"])

    def test_invalid_filters_json_raises(self, app_ctx):
        from services.product_service import list_products

        with pytest.raises(ValueError, match="Invalid filters JSON"):
            list_products(None, None, advanced_filters="{bad json}")

    def test_filter_by_flag(self, app_ctx, seed_product, db):
        from services.product_service import list_products

        # Tag the seed product with is_discontinued
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        filters = json.dumps(
            {
                "logic": "and",
                "children": [
                    {"field": "flag:is_discontinued", "op": "=", "value": "true"}
                ],
            }
        )
        result = list_products(None, None, advanced_filters=filters)
        assert any(seed_product == p["id"] for p in result["products"])

    def test_filter_by_flag_false_excludes_flagged(self, app_ctx, seed_product, db):
        from services.product_service import list_products

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        filters = json.dumps(
            {
                "logic": "and",
                "children": [
                    {"field": "flag:is_discontinued", "op": "=", "value": "false"}
                ],
            }
        )
        result = list_products(None, None, advanced_filters=filters)
        assert all(p["id"] != seed_product for p in result["products"])


# ---------------------------------------------------------------------------
# add_product with flags
# ---------------------------------------------------------------------------


class TestAddProductWithFlags:
    def test_add_product_with_valid_user_flag(self, app_ctx, seed_category, db):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "Flagged Snack",
                "flags": ["is_discontinued"],
            }
        )
        pid = result["id"]
        assert "is_discontinued" in _get_flags_for(db, pid)

    def test_add_product_with_system_flag_ignored(self, app_ctx, seed_category, db):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "System Flag Snack",
                "flags": ["is_synced_with_off"],
            }
        )
        pid = result["id"]
        # system flag passed via "flags" key should be ignored by _set_user_flags
        assert "is_synced_with_off" not in _get_flags_for(db, pid)

    def test_add_product_with_unknown_flag_ignored(self, app_ctx, seed_category, db):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "Unknown Flag Snack",
                "flags": ["totally_made_up"],
            }
        )
        pid = result["id"]
        assert _get_flags_for(db, pid) == set()

    def test_add_product_without_flags_key(self, app_ctx, seed_category, db):
        from services.product_service import add_product

        result = add_product({"type": "Snacks", "name": "No Flag Snack"})
        assert _get_flags_for(db, result["id"]) == set()

    def test_add_product_with_from_off_sets_system_flag(
        self, app_ctx, seed_category, db
    ):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "OFF Synced Snack",
                "from_off": True,
            }
        )
        pid = result["id"]
        assert "is_synced_with_off" in _get_flags_for(db, pid)

    def test_add_product_from_off_false_no_system_flag(
        self, app_ctx, seed_category, db
    ):
        from services.product_service import add_product

        result = add_product(
            {
                "type": "Snacks",
                "name": "Not OFF Snack",
                "from_off": False,
            }
        )
        pid = result["id"]
        assert "is_synced_with_off" not in _get_flags_for(db, pid)


# ---------------------------------------------------------------------------
# update_product with flags only (no field changes)
# ---------------------------------------------------------------------------


class TestUpdateProductFlagsOnly:
    def test_update_flags_only_sets_flag(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        update_product(seed_product, {"flags": ["is_discontinued"]})
        assert "is_discontinued" in _get_flags_for(db, seed_product)

    def test_update_flags_only_clears_previous(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_discontinued"),
        )
        db.commit()

        update_product(seed_product, {"flags": []})
        assert "is_discontinued" not in _get_flags_for(db, seed_product)

    def test_update_flags_only_nonexistent_product_raises(self, app_ctx):
        from services.product_service import update_product

        with pytest.raises(LookupError, match="Product not found"):
            update_product(999999, {"flags": ["is_discontinued"]})

    def test_update_no_fields_no_flags_raises(self, app_ctx, seed_product):
        from services.product_service import update_product

        with pytest.raises(ValueError, match="Nothing to update"):
            update_product(seed_product, {})

    def test_update_system_flag_via_flags_key_ignored(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        update_product(seed_product, {"flags": ["is_synced_with_off"]})
        assert "is_synced_with_off" not in _get_flags_for(db, seed_product)


# ---------------------------------------------------------------------------
# update_product with from_off=True
# ---------------------------------------------------------------------------


class TestUpdateProductFromOff:
    def test_from_off_true_sets_system_flag(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        update_product(seed_product, {"name": "Updated Name", "from_off": True})
        assert "is_synced_with_off" in _get_flags_for(db, seed_product)

    def test_from_off_false_does_not_set_system_flag(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        update_product(seed_product, {"name": "Updated Name 2", "from_off": False})
        assert "is_synced_with_off" not in _get_flags_for(db, seed_product)

    def test_from_off_with_flags_only(self, app_ctx, seed_product, db):
        from services.product_service import update_product

        update_product(
            seed_product,
            {"flags": ["is_discontinued"], "from_off": True},
        )
        flags = _get_flags_for(db, seed_product)
        assert "is_discontinued" in flags
        assert "is_synced_with_off" in flags

    def test_from_off_does_not_clear_existing_system_flag(
        self, app_ctx, seed_product, db
    ):
        from services.product_service import update_product

        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (seed_product, "is_synced_with_off"),
        )
        db.commit()

        # Updating again with from_off=True should be idempotent
        update_product(seed_product, {"name": "Another Update", "from_off": True})
        assert "is_synced_with_off" in _get_flags_for(db, seed_product)
