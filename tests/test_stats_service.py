"""Tests for services/stats_service.py — product statistics."""


class TestGetStats:
    def test_returns_stats(self, app_ctx, seed_product):
        from services.stats_service import get_stats

        stats = get_stats()
        assert stats["total"] >= 1
        assert stats["types"] >= 1
        assert "type_counts" in stats
        assert "categories" in stats

    def test_category_info(self, app_ctx, seed_product):
        from services.stats_service import get_stats

        stats = get_stats()
        cats = stats["categories"]
        assert len(cats) >= 1
        assert "name" in cats[0]
        assert "emoji" in cats[0]
        assert "label" in cats[0]

    def test_type_counts(self, app_ctx, seed_product):
        from services.stats_service import get_stats

        stats = get_stats()
        assert "Snacks" in stats["type_counts"]
        assert stats["type_counts"]["Snacks"] >= 1

    def test_type_counts_sum_equals_total(self, app_ctx, seed_product):
        """Sum of all type counts should equal total product count."""
        from services.stats_service import get_stats

        stats = get_stats()
        assert sum(stats["type_counts"].values()) == stats["total"]

    def test_categories_have_required_fields(self, app_ctx, seed_product):
        """Each category entry must have name, emoji, and label fields."""
        from services.stats_service import get_stats

        stats = get_stats()
        for cat in stats["categories"]:
            assert "name" in cat
            assert "emoji" in cat
            assert "label" in cat
            assert isinstance(cat["name"], str)
            assert isinstance(cat["label"], str)

    def test_stats_total_is_nonnegative(self, app_ctx, seed_product):
        """Total count should never be negative."""
        from services.stats_service import get_stats

        stats = get_stats()
        assert stats["total"] >= 0
        assert stats["types"] >= 0
