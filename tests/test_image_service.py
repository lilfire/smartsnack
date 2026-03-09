"""Tests for services/image_service.py — product image management."""

import pytest


class TestGetImage:
    def test_existing_image(self, app_ctx, seed_product):
        from services.image_service import get_image
        result = get_image(seed_product)
        assert result is not None
        assert result.startswith("data:image/")

    def test_no_image(self, app_ctx, db, seed_category):
        from services.image_service import get_image
        db.execute(
            "INSERT INTO products (type, name) VALUES (?, ?)",
            ("Snacks", "NoImage"),
        )
        db.commit()
        pid = db.execute("SELECT id FROM products WHERE name='NoImage'").fetchone()["id"]
        assert get_image(pid) is None

    def test_nonexistent_product(self, app_ctx):
        from services.image_service import get_image
        assert get_image(99999) is None


class TestSetImage:
    def test_valid_image(self, app_ctx, seed_product):
        from services.image_service import set_image
        img = "data:image/png;base64,iVBORw0KGgo="
        assert set_image(seed_product, img) is True

    def test_invalid_prefix(self, app_ctx, seed_product):
        from services.image_service import set_image
        with pytest.raises(ValueError, match="Invalid image format"):
            set_image(seed_product, "data:text/plain;base64,abc")

    def test_empty_image(self, app_ctx, seed_product):
        from services.image_service import set_image
        with pytest.raises(ValueError, match="Invalid image format"):
            set_image(seed_product, "")

    def test_too_large(self, app_ctx, seed_product):
        from services.image_service import set_image
        img = "data:image/png;base64," + "A" * (2 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="too large"):
            set_image(seed_product, img)

    def test_product_not_found(self, app_ctx):
        from services.image_service import set_image
        img = "data:image/jpeg;base64,abc"
        assert set_image(99999, img) is False

    def test_webp_format(self, app_ctx, seed_product):
        from services.image_service import set_image
        img = "data:image/webp;base64,abc"
        assert set_image(seed_product, img) is True

    def test_gif_format(self, app_ctx, seed_product):
        from services.image_service import set_image
        img = "data:image/gif;base64,abc"
        assert set_image(seed_product, img) is True


class TestDeleteImage:
    def test_delete_existing(self, app_ctx, seed_product):
        from services.image_service import delete_image
        assert delete_image(seed_product) is True
        from services.image_service import get_image
        assert get_image(seed_product) is None

    def test_delete_nonexistent(self, app_ctx):
        from services.image_service import delete_image
        assert delete_image(99999) is False
