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
