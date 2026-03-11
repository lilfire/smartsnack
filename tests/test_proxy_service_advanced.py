"""Additional tests for proxy_service — certainty scoring, text normalization."""


class TestNormalizeText:
    def test_curly_quotes(self):
        from services.proxy_service import _normalize_text

        assert _normalize_text("Dave\u2019s") == "dave's"
        assert _normalize_text("\u201cTest\u201d") == '"test"'

    def test_dashes(self):
        from services.proxy_service import _normalize_text

        assert _normalize_text("a\u2013b\u2014c") == "a-b-c"

    def test_strips_and_lowercases(self):
        from services.proxy_service import _normalize_text

        assert _normalize_text("  Hello World  ") == "hello world"


class TestCleanSearchQuery:
    def test_removes_special_chars(self):
        from services.proxy_service import _clean_search_query

        assert _clean_search_query("test+query#1!") == "test query 1"

    def test_collapses_whitespace(self):
        from services.proxy_service import _clean_search_query

        assert _clean_search_query("  a   b   c  ") == "a b c"


class TestNutritionFieldSimilarity:
    def test_equal_values(self):
        from services.proxy_service import _nutrition_field_similarity

        assert _nutrition_field_similarity(10.0, 10.0) == 1.0

    def test_both_zero(self):
        from services.proxy_service import _nutrition_field_similarity

        assert _nutrition_field_similarity(0.0, 0.0) == 1.0

    def test_large_difference(self):
        from services.proxy_service import _nutrition_field_similarity

        assert _nutrition_field_similarity(10.0, 100.0) == 0.0

    def test_small_difference(self):
        from services.proxy_service import _nutrition_field_similarity

        result = _nutrition_field_similarity(10.0, 11.0)
        assert 0.5 < result < 1.0


class TestComputeNutritionSimilarity:
    def test_no_nutriments(self):
        from services.proxy_service import _compute_nutrition_similarity

        result = _compute_nutrition_similarity({"kcal": 100}, {"nutriments": {}})
        assert result == 0

    def test_empty_nutrition(self):
        from services.proxy_service import _compute_nutrition_similarity

        result = _compute_nutrition_similarity(
            {}, {"nutriments": {"energy-kcal_100g": 100}}
        )
        assert result == 0

    def test_matching_nutrition(self):
        from services.proxy_service import _compute_nutrition_similarity

        nutrition = {"kcal": 100, "protein": 20}
        product = {
            "nutriments": {
                "energy-kcal_100g": 100,
                "proteins_100g": 20,
            }
        }
        result = _compute_nutrition_similarity(nutrition, product)
        assert result > 0

    def test_mismatching_nutrition(self):
        from services.proxy_service import _compute_nutrition_similarity

        nutrition = {"kcal": 100}
        product = {
            "nutriments": {
                "energy-kcal_100g": 500,
            }
        }
        result = _compute_nutrition_similarity(nutrition, product)
        assert result < 0


class TestComputeCertainty:
    def test_exact_match(self):
        from services.proxy_service import _compute_certainty

        product = {"product_name": "Classic Popcorn", "brands": ""}
        score = _compute_certainty("Classic Popcorn", product)
        assert score > 50

    def test_no_match(self):
        from services.proxy_service import _compute_certainty

        product = {"product_name": "Milk Chocolate", "brands": ""}
        score = _compute_certainty("zzz nonexistent xyz", product)
        assert score == 0

    def test_empty_query(self):
        from services.proxy_service import _compute_certainty

        product = {"product_name": "Test", "brands": ""}
        score = _compute_certainty("", product)
        assert score == 0

    def test_brand_matching(self):
        from services.proxy_service import _compute_certainty

        product = {"product_name": "Milk", "brands": "Tine"}
        with_brand = _compute_certainty("Tine Milk", product)
        without_brand = _compute_certainty("Milk", product)
        assert with_brand >= without_brand

    def test_nutrition_affects_scoring(self):
        from services.proxy_service import _compute_certainty

        product = {
            "product_name": "Protein Bar",
            "brands": "",
            "nutriments": {"proteins_100g": 20, "energy-kcal_100g": 200},
        }
        with_nutrition = _compute_certainty(
            "Protein Bar", product, nutrition={"protein": 20, "kcal": 200}
        )
        without_nutrition = _compute_certainty("Protein Bar", product)
        # With matching nutrition should score at least as well
        assert with_nutrition >= without_nutrition


class TestSortByCompleteness:
    def test_sorts_descending(self):
        from services.proxy_service import _sort_by_completeness

        data = {
            "products": [
                {"name": "low", "completeness": 0.3},
                {"name": "high", "completeness": 0.9},
                {"name": "mid", "completeness": 0.6},
            ]
        }
        result = _sort_by_completeness(data)
        names = [p["name"] for p in result["products"]]
        assert names == ["high", "mid", "low"]

    def test_no_products_key(self):
        from services.proxy_service import _sort_by_completeness

        data = {"count": 0}
        result = _sort_by_completeness(data)
        assert "products" not in result
