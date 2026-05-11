"""Direct unit tests for services/product_filters.py."""
import json
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────


def _parse(filters_dict, app_ctx=None):
    """Shorthand: parse a filter dict and return (sql, params, post)."""
    from services.product_filters import _parse_advanced_filters
    return _parse_advanced_filters(json.dumps(filters_dict))


def _add_product(db, name, **kwargs):
    from services.product_crud import add_product
    data = {"name": name, "type": "", "ean": "", "on_duplicate": "allow_duplicate"}
    data.update(kwargs)
    return add_product(data)["id"]


# ── _parse_advanced_filters format support ────────────────────────────────────


class TestParseAdvancedFilters:
    def test_legacy_flat_format(self, db):
        sql, params, post = _parse(
            {"logic": "and", "conditions": [{"field": "protein", "op": ">=", "value": "10"}]}
        )
        assert "protein" in sql
        assert params == [10.0]
        assert post is None

    def test_old_grouped_format(self, db):
        sql, params, post = _parse({
            "logic": "and",
            "groups": [{"logic": "and", "conditions": [{"field": "kcal", "op": "<", "value": "200"}]}],
        })
        assert "kcal" in sql

    def test_new_recursive_format(self, db):
        sql, params, post = _parse(
            {"logic": "and", "children": [{"field": "fat", "op": "<=", "value": "5"}]}
        )
        assert "fat" in sql
        assert params == [5.0]

    def test_returns_tuple_of_three(self, db):
        result = _parse({"logic": "and", "children": [{"field": "protein", "op": ">=", "value": "10"}]})
        assert len(result) == 3

    def test_exceeds_max_conditions_raises(self, db):
        from config import MAX_FILTER_CONDITIONS
        from services.product_filters import _parse_advanced_filters
        conditions = [{"field": "protein", "op": ">=", "value": "1"}] * (MAX_FILTER_CONDITIONS + 1)
        with pytest.raises(ValueError, match="Too many"):
            _parse_advanced_filters(json.dumps({"logic": "and", "children": conditions}))

    def test_invalid_json_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError, match="Invalid"):
            _parse_advanced_filters("not-json")


# ── Operator coverage for text fields ────────────────────────────────────────


class TestTextFieldOperators:
    def _filter(self, field, op, value, db):
        sql, params, _ = _parse({"logic": "and", "children": [{"field": field, "op": op, "value": value}]})
        return sql, params

    def test_eq_text(self, db):
        sql, params = self._filter("name", "=", "Test", db)
        assert "=" in sql
        assert params == ["Test"]

    def test_neq_text(self, db):
        sql, params = self._filter("brand", "!=", "Acme", db)
        assert "!=" in sql

    def test_contains(self, db):
        sql, params = self._filter("name", "contains", "foo", db)
        assert "LIKE" in sql

    def test_not_contains(self, db):
        sql, params = self._filter("name", "!contains", "bar", db)
        assert "NOT LIKE" in sql

    def test_is_set(self, db):
        sql, params = self._filter("ingredients", "is_set", "", db)
        assert "IS NOT NULL" in sql

    def test_is_not_set(self, db):
        sql, params = self._filter("ingredients", "is_not_set", "", db)
        assert "IS NULL" in sql or "= ''" in sql


# ── Operator coverage for numeric fields ─────────────────────────────────────


class TestNumericFieldOperators:
    def _filter(self, op, value, db):
        sql, params, _ = _parse({"logic": "and", "children": [{"field": "kcal", "op": op, "value": str(value)}]})
        return sql, params

    def test_eq_numeric(self, db):
        sql, params = self._filter("=", 100, db)
        assert params == [100.0]

    def test_neq_numeric(self, db):
        sql, params = self._filter("!=", 200, db)
        assert params == [200.0]

    def test_lt(self, db):
        sql, params = self._filter("<", 50, db)
        assert "<" in sql and params == [50.0]

    def test_gt(self, db):
        sql, params = self._filter(">", 300, db)
        assert ">" in sql

    def test_lte(self, db):
        sql, params = self._filter("<=", 400, db)
        assert "<=" in sql

    def test_gte(self, db):
        sql, params = self._filter(">=", 150, db)
        assert ">=" in sql

    def test_numeric_is_set(self, db):
        sql, params = self._filter("is_set", "", db)
        assert "IS NOT NULL" in sql

    def test_numeric_is_not_set(self, db):
        sql, params = self._filter("is_not_set", "", db)
        assert "IS NULL" in sql

    def test_invalid_op_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "kcal", "op": "invalid_op", "value": "5"}]}
            ))

    def test_contains_on_numeric_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "kcal", "op": "contains", "value": "5"}]}
            ))


# ── Flag field operator ───────────────────────────────────────────────────────


class TestFlagFieldOperator:
    def test_flag_eq_true(self, db):
        sql, params, post = _parse(
            {"logic": "and", "children": [{"field": "flag:is_synced_with_off", "op": "=", "value": "true"}]}
        )
        assert "EXISTS" in sql

    def test_flag_eq_false(self, db):
        sql, params, post = _parse(
            {"logic": "and", "children": [{"field": "flag:is_synced_with_off", "op": "=", "value": "false"}]}
        )
        assert "NOT EXISTS" in sql

    def test_flag_invalid_op_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "flag:is_synced_with_off", "op": "!=", "value": "true"}]}
            ))


# ── _evaluate_post_node ───────────────────────────────────────────────────────


class TestEvaluatePostNode:
    def _eval(self, node, product):
        from services.product_filters import _evaluate_post_node
        return _evaluate_post_node(node, product)

    def test_lt_true(self):
        assert self._eval({"field": "total_score", "op": "<", "val": 0.9}, {"total_score": 0.5}) is True

    def test_lt_false(self):
        assert self._eval({"field": "total_score", "op": "<", "val": 0.3}, {"total_score": 0.8}) is False

    def test_gt_true(self):
        assert self._eval({"field": "completeness", "op": ">", "val": 0.4}, {"completeness": 0.7}) is True

    def test_lte_at_boundary(self):
        assert self._eval({"field": "total_score", "op": "<=", "val": 0.5}, {"total_score": 0.5}) is True

    def test_gte_at_boundary(self):
        assert self._eval({"field": "total_score", "op": ">=", "val": 0.5}, {"total_score": 0.5}) is True

    def test_is_not_set(self):
        assert self._eval({"field": "total_score", "op": "is_not_set", "val": None}, {"total_score": None}) is True

    def test_is_set(self):
        assert self._eval({"field": "total_score", "op": "is_set", "val": None}, {"total_score": 0.5}) is True

    def test_null_value_returns_false(self):
        assert self._eval({"field": "total_score", "op": ">=", "val": 0.5}, {"total_score": None}) is False

    def test_and_logic_all_true(self):
        node = {"logic": "AND", "children": [
            {"field": "total_score", "op": ">=", "val": 0.3},
            {"field": "total_score", "op": "<=", "val": 0.9},
        ]}
        assert self._eval(node, {"total_score": 0.6}) is True

    def test_or_logic_one_true(self):
        node = {"logic": "OR", "children": [
            {"field": "total_score", "op": ">=", "val": 0.9},
            {"field": "total_score", "op": "<=", "val": 0.2},
        ]}
        assert self._eval(node, {"total_score": 0.95}) is True

    def test_or_logic_all_false(self):
        node = {"logic": "OR", "children": [
            {"field": "total_score", "op": ">=", "val": 0.9},
            {"field": "total_score", "op": "<=", "val": 0.2},
        ]}
        assert self._eval(node, {"total_score": 0.5}) is False


# ── _apply_post_filters ───────────────────────────────────────────────────────


class TestApplyPostFilters:
    def test_filters_matching_products(self):
        from services.product_filters import _apply_post_filters
        products = [
            {"total_score": 0.8},
            {"total_score": 0.3},
            {"total_score": 0.9},
        ]
        spec = {"field": "total_score", "op": ">=", "val": 0.7}
        result = _apply_post_filters(products, spec)
        assert len(result) == 2
        assert all(p["total_score"] >= 0.7 for p in result)

    def test_none_spec_returns_all(self):
        from services.product_filters import _apply_post_filters
        products = [{"total_score": 0.5}, {"total_score": 0.1}]
        assert _apply_post_filters(products, None) == products


# ── Range filter integration via client ──────────────────────────────────────


class TestRangeFilterIntegration:
    def test_range_filter_returns_matching_products(self, client, db):
        from services.product_crud import add_product
        add_product({"name": "HighProtein", "type": "", "ean": "", "protein": 30.0, "on_duplicate": "allow_duplicate"})
        add_product({"name": "LowProtein", "type": "", "ean": "", "protein": 2.0, "on_duplicate": "allow_duplicate"})
        filters = json.dumps(
            {"logic": "and", "children": [{"field": "protein", "op": ">=", "value": "20"}]}
        )
        resp = client.get(f"/api/products?filters={filters}")
        assert resp.status_code == 200
        data = resp.get_json()["products"]
        names = [p["name"] for p in data]
        assert "HighProtein" in names
        assert "LowProtein" not in names

    def test_and_logic_filters_correctly(self, client, db):
        from services.product_crud import add_product
        add_product({"name": "Both", "type": "", "ean": "", "protein": 25.0, "kcal": 150.0, "on_duplicate": "allow_duplicate"})
        add_product({"name": "HighKcal", "type": "", "ean": "", "protein": 25.0, "kcal": 500.0, "on_duplicate": "allow_duplicate"})
        filters = json.dumps({"logic": "and", "children": [
            {"field": "protein", "op": ">=", "value": "20"},
            {"field": "kcal", "op": "<=", "value": "200"},
        ]})
        resp = client.get(f"/api/products?filters={filters}")
        assert resp.status_code == 200
        data = resp.get_json()["products"]
        names = [p["name"] for p in data]
        assert "Both" in names
        assert "HighKcal" not in names

    def test_or_logic_filters_correctly(self, client, db):
        from services.product_crud import add_product
        add_product({"name": "LowFat", "type": "", "ean": "", "fat": 1.0, "kcal": 300.0, "on_duplicate": "allow_duplicate"})
        add_product({"name": "LowKcal", "type": "", "ean": "", "fat": 15.0, "kcal": 80.0, "on_duplicate": "allow_duplicate"})
        add_product({"name": "Neither", "type": "", "ean": "", "fat": 20.0, "kcal": 500.0, "on_duplicate": "allow_duplicate"})
        filters = json.dumps({"logic": "or", "children": [
            {"field": "fat", "op": "<=", "value": "5"},
            {"field": "kcal", "op": "<=", "value": "100"},
        ]})
        resp = client.get(f"/api/products?filters={filters}")
        assert resp.status_code == 200
        data = resp.get_json()["products"]
        names = [p["name"] for p in data]
        assert "LowFat" in names
        assert "LowKcal" in names
        assert "Neither" not in names


# ── _parse_condition edge cases ───────────────────────────────────────────────


class TestParseConditionEdgeCases:
    def test_nonexistent_flag_field_raises_invalid_field(self, db):
        from services.product_filters import _parse_advanced_filters
        # A flag field not in the DB is rejected as "Invalid filter field"
        # (it never enters flag_fields, so the "Unknown flag" branch is unreachable)
        with pytest.raises(ValueError, match="Invalid filter field"):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "flag:nonexistent_flag_xyz", "op": "=", "value": "true"}]}
            ))

    def test_type_field_empty_value_with_eq_op_allowed(self, db):
        from services.product_filters import _parse_advanced_filters
        # Empty value for type field with = op is a special case (uncategorized products)
        sql, params, post = _parse_advanced_filters(json.dumps(
            {"logic": "and", "children": [{"field": "type", "op": "=", "value": ""}]}
        ))
        assert "type" in sql

    def test_type_field_none_value_with_neq_op_allowed(self, db):
        from services.product_filters import _parse_advanced_filters
        sql, params, post = _parse_advanced_filters(json.dumps(
            {"logic": "and", "children": [{"field": "type", "op": "!=", "value": ""}]}
        ))
        assert "type" in sql


# ── _condition_to_sql edge cases ──────────────────────────────────────────────


class TestConditionToSqlEdgeCases:
    def test_non_finite_value_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        # infinity is non-finite: should raise ValueError
        with pytest.raises(ValueError):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "kcal", "op": ">=", "value": "inf"}]}
            ))

    def test_nan_value_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": [{"field": "kcal", "op": ">=", "value": "nan"}]}
            ))


# ── _process_node edge cases ──────────────────────────────────────────────────


class TestProcessNodeEdgeCases:
    def test_depth_limit_exceeded_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        from config import MAX_FILTER_DEPTH
        # Build nesting deeper than MAX_FILTER_DEPTH
        node = {"field": "protein", "op": ">=", "value": "10"}
        for _ in range(MAX_FILTER_DEPTH + 2):
            node = {"logic": "and", "children": [node]}
        with pytest.raises(ValueError, match="too deep"):
            _parse_advanced_filters(json.dumps(node))

    def test_invalid_logic_value_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError, match="logic must be"):
            _parse_advanced_filters(json.dumps(
                {"logic": "xor", "children": [{"field": "protein", "op": ">=", "value": "10"}]}
            ))

    def test_empty_children_returns_no_sql(self, db):
        from services.product_filters import _parse_advanced_filters
        # Empty children list should produce empty SQL
        sql, params, post = _parse_advanced_filters(json.dumps(
            {"logic": "and", "children": []}
        ))
        assert sql == "" or sql is None or sql == ""
        assert params == []

    def test_non_dict_child_raises(self, db):
        from services.product_filters import _parse_advanced_filters
        with pytest.raises(ValueError, match="JSON object"):
            _parse_advanced_filters(json.dumps(
                {"logic": "and", "children": ["not_a_dict"]}
            ))

    def test_or_mixing_sql_and_post_query_fields_goes_to_post(self, db):
        from services.product_filters import _parse_advanced_filters
        # OR logic with one SQL field (protein) and one post-query field (total_score)
        # forces everything to the post-filter
        sql, params, post = _parse_advanced_filters(json.dumps(
            {
                "logic": "or",
                "children": [
                    {"field": "protein", "op": ">=", "value": "10"},
                    {"field": "total_score", "op": ">=", "value": "0.5"},
                ],
            }
        ))
        # Since OR mixes SQL and post-query, everything moves to post-filter
        assert sql == "" or sql is None or sql == ""
        assert post is not None
        assert post.get("logic") == "OR"


# ── _node_to_post function ────────────────────────────────────────────────────


class TestNodeToPost:
    def test_leaf_node_to_post(self, db):
        from services.product_filters import _node_to_post
        node = {"field": "total_score", "op": ">=", "value": "0.5"}
        result = _node_to_post(node)
        assert result["field"] == "total_score"
        assert result["op"] == ">="
        assert result["val"] == pytest.approx(0.5)

    def test_group_node_to_post(self, db):
        from services.product_filters import _node_to_post
        node = {
            "logic": "and",
            "children": [
                {"field": "total_score", "op": ">=", "value": "0.3"},
                {"field": "completeness", "op": "<=", "value": "100"},
            ],
        }
        result = _node_to_post(node)
        assert result["logic"] == "AND"
        assert len(result["children"]) == 2


# ── flag field in _evaluate_post_node ────────────────────────────────────────


class TestEvaluatePostNodeFlagField:
    def test_flag_true_product_has_flag(self):
        from services.product_filters import _evaluate_post_node
        node = {"field": "flag:is_synced_with_off", "op": "=", "val": "true"}
        product = {"flags": ["is_synced_with_off"]}
        assert _evaluate_post_node(node, product) is True

    def test_flag_true_product_missing_flag(self):
        from services.product_filters import _evaluate_post_node
        node = {"field": "flag:is_synced_with_off", "op": "=", "val": "true"}
        product = {"flags": []}
        assert _evaluate_post_node(node, product) is False

    def test_flag_false_product_has_flag(self):
        from services.product_filters import _evaluate_post_node
        node = {"field": "flag:is_synced_with_off", "op": "=", "val": "false"}
        product = {"flags": ["is_synced_with_off"]}
        assert _evaluate_post_node(node, product) is False

    def test_flag_false_product_missing_flag(self):
        from services.product_filters import _evaluate_post_node
        node = {"field": "flag:is_synced_with_off", "op": "=", "val": "false"}
        product = {"flags": []}
        assert _evaluate_post_node(node, product) is True

    def test_flag_no_flags_key_in_product(self):
        from services.product_filters import _evaluate_post_node
        node = {"field": "flag:is_synced_with_off", "op": "=", "val": "true"}
        product = {}  # no "flags" key
        assert _evaluate_post_node(node, product) is False

    def test_empty_children_post_node_returns_true(self):
        from services.product_filters import _evaluate_post_node
        node = {"logic": "AND", "children": []}
        assert _evaluate_post_node(node, {"total_score": 0.5}) is True
