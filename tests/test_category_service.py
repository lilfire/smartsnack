"""Tests for services/category_service.py — category management."""

import pytest
from exceptions import ConflictError


class TestListCategories:
    def test_returns_categories(self, app_ctx, translations_dir):
        from services.category_service import list_categories

        cats = list_categories()
        assert len(cats) >= 1
        assert cats[0]["name"] == "Snacks"
        assert "label" in cats[0]
        assert "emoji" in cats[0]
        assert "count" in cats[0]

    def test_product_count(self, app_ctx, seed_product, translations_dir):
        from services.category_service import list_categories

        cats = list_categories()
        snacks = next(c for c in cats if c["name"] == "Snacks")
        assert snacks["count"] >= 1


class TestAddCategory:
    def test_valid_add(self, app_ctx, translations_dir):
        from services.category_service import add_category

        add_category("Drinks", "Drikker", "🧃")
        from db import get_db

        row = (
            get_db()
            .execute("SELECT emoji FROM categories WHERE name='Drinks'")
            .fetchone()
        )
        assert row["emoji"] == "🧃"

    def test_duplicate_raises_conflict(self, app_ctx, translations_dir):
        from services.category_service import add_category

        with pytest.raises(ConflictError, match="already exists"):
            add_category("Snacks", "Snacks", "🍿")

    def test_empty_name_raises(self, app_ctx, translations_dir):
        from services.category_service import add_category

        with pytest.raises(ValueError):
            add_category("", "Label", "🍿")

    def test_empty_label_raises(self, app_ctx, translations_dir):
        from services.category_service import add_category

        with pytest.raises(ValueError, match="name and label"):
            add_category("Test", "", "🍿")


class TestUpdateCategory:
    def test_update_emoji(self, app_ctx, translations_dir):
        from services.category_service import update_category

        update_category("Snacks", "", "🍕")
        from db import get_db

        row = (
            get_db()
            .execute("SELECT emoji FROM categories WHERE name='Snacks'")
            .fetchone()
        )
        assert row["emoji"] == "🍕"

    def test_update_label(self, app_ctx, translations_dir):
        from services.category_service import update_category

        update_category("Snacks", "Snackser", "")

    def test_nothing_to_update(self, app_ctx, translations_dir):
        from services.category_service import update_category

        with pytest.raises(ValueError, match="Nothing to update"):
            update_category("Snacks", "", "")


class TestDeleteCategory:
    def test_delete_empty_category(self, app_ctx, translations_dir):
        from services.category_service import add_category, delete_category

        add_category("ToDelete", "Slett meg", "🗑️")
        count = delete_category("ToDelete")
        assert count == 0

    def test_delete_with_products_no_move_to(
        self, app_ctx, seed_product, translations_dir
    ):
        from services.category_service import delete_category

        with pytest.raises(ValueError, match="Cannot delete"):
            delete_category("Snacks")

    def test_delete_with_move_to(self, app_ctx, seed_product, translations_dir):
        from services.category_service import add_category, delete_category

        add_category("NewCat", "Ny kategori", "📦")
        count = delete_category("Snacks", move_to="NewCat")
        assert count >= 1
        from db import get_db

        row = (
            get_db()
            .execute("SELECT type FROM products WHERE id=?", (seed_product,))
            .fetchone()
        )
        assert row["type"] == "NewCat"

    def test_move_to_same_category(self, app_ctx, seed_product, translations_dir):
        from services.category_service import delete_category

        with pytest.raises(ValueError, match="same category"):
            delete_category("Snacks", move_to="Snacks")

    def test_move_to_nonexistent(self, app_ctx, seed_product, translations_dir):
        from services.category_service import delete_category

        with pytest.raises(ValueError, match="Target category does not exist"):
            delete_category("Snacks", move_to="NoSuchCat")
