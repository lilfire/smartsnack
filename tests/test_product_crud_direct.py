"""Direct unit tests for services/product_crud.py."""
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _add(name="Test Product", ean="", on_duplicate="allow_duplicate", **kwargs):
    """Build a product data dict and call add_product with on_duplicate kwarg."""
    from services.product_crud import add_product
    data = {"name": name, "ean": ean, "type": ""}
    data.update(kwargs)
    return add_product(data, on_duplicate=on_duplicate)


# ── add_product ───────────────────────────────────────────────────────────────


class TestAddProduct:
    def test_inserts_and_returns_id(self, db):
        result = _add("My Snack")
        assert "id" in result
        row = db.execute("SELECT name FROM products WHERE id=?", (result["id"],)).fetchone()
        assert row["name"] == "My Snack"

    def test_inserts_nutrition_fields(self, db):
        result = _add("Nutrition Test", kcal=300.0, protein=25.0)
        row = db.execute("SELECT kcal, protein FROM products WHERE id=?", (result["id"],)).fetchone()
        assert row["kcal"] == 300.0
        assert row["protein"] == 25.0

    def test_ean_written_to_product_eans(self, db):
        result = _add("EAN Test", ean="12345678")
        row = db.execute(
            "SELECT ean, is_primary FROM product_eans WHERE product_id=?",
            (result["id"],),
        ).fetchone()
        assert row is not None
        assert row["ean"] == "12345678"
        assert row["is_primary"] == 1

    def test_duplicate_ean_returns_duplicate_info(self, db):
        _add("First", ean="12345678")
        result = _add("Second", ean="12345678", on_duplicate=None)
        assert "duplicate" in result
        assert isinstance(result["duplicate"], dict)

    def test_overwrite_merges_into_existing(self, db):
        from services.product_crud import add_product
        first = _add("Original", ean="12345678")
        result = add_product({"name": "Updated", "ean": "12345678", "type": "", "brand": "NewBrand"}, on_duplicate="overwrite")
        assert result.get("merged") is True
        assert result["id"] == first["id"]

    def test_missing_name_raises_value_error(self, db):
        from services.product_crud import add_product
        with pytest.raises(ValueError, match="name is required"):
            add_product({"name": "", "ean": ""})

    def test_invalid_ean_raises_value_error(self, db):
        from services.product_crud import add_product
        with pytest.raises(ValueError, match="EAN"):
            add_product({"name": "Test", "ean": "123"}, on_duplicate="allow_duplicate")  # too short

    def test_nonexistent_category_raises_value_error(self, db):
        from services.product_crud import add_product
        with pytest.raises(ValueError, match="Category"):
            add_product({"name": "Test", "ean": "", "type": "NonExistentCat"})


# ── update_product ────────────────────────────────────────────────────────────


class TestUpdateProduct:
    def test_updates_string_field(self, db):
        from services.product_crud import update_product
        pid = _add("Original")["id"]
        update_product(pid, {"name": "Updated"})
        row = db.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()
        assert row["name"] == "Updated"

    def test_updates_numeric_field(self, db):
        from services.product_crud import update_product
        pid = _add("Product")["id"]
        update_product(pid, {"protein": 30.5})
        row = db.execute("SELECT protein FROM products WHERE id=?", (pid,)).fetchone()
        assert row["protein"] == 30.5

    def test_changing_ean_syncs_product_eans(self, db):
        from services.product_crud import update_product
        pid = _add("P", ean="11111111")["id"]
        update_product(pid, {"ean": "22222222"})
        row = db.execute(
            "SELECT ean FROM product_eans WHERE product_id=? AND is_primary=1", (pid,)
        ).fetchone()
        assert row["ean"] == "22222222"

    def test_unknown_field_raises_value_error(self, db):
        from services.product_crud import update_product
        pid = _add("P")["id"]
        with pytest.raises(ValueError):
            update_product(pid, {"nonexistent_field": "value"})

    def test_name_exceeding_limit_raises_value_error(self, db):
        from services.product_crud import update_product
        pid = _add("P")["id"]
        with pytest.raises(ValueError):
            update_product(pid, {"name": "x" * 201})

    def test_nonexistent_product_raises_lookup_error(self, db):
        from services.product_crud import update_product
        with pytest.raises(LookupError):
            update_product(99999, {"name": "New Name"})

    def test_nothing_to_update_raises_value_error(self, db):
        from services.product_crud import update_product
        pid = _add("P")["id"]
        with pytest.raises(ValueError, match="Nothing to update"):
            update_product(pid, {})


# ── delete_product ────────────────────────────────────────────────────────────


class TestDeleteProduct:
    def test_product_removed_returns_true(self, db):
        from services.product_crud import delete_product
        pid = _add("ToDelete")["id"]
        assert delete_product(pid) is True
        assert db.execute("SELECT id FROM products WHERE id=?", (pid,)).fetchone() is None

    def test_related_eans_cascade_deleted(self, db):
        from services.product_crud import delete_product
        pid = _add("P", ean="12345678")["id"]
        delete_product(pid)
        assert db.execute("SELECT id FROM product_eans WHERE product_id=?", (pid,)).fetchone() is None

    def test_related_tags_cascade_deleted(self, db):
        from services.product_crud import update_product, delete_product
        from services import tag_service
        pid = _add("P")["id"]
        tag = tag_service.create_tag("healthy")
        update_product(pid, {"tagIds": [tag["id"]]})
        delete_product(pid)
        assert db.execute("SELECT product_id FROM product_tags WHERE product_id=?", (pid,)).fetchone() is None

    def test_related_flags_cascade_deleted(self, db):
        from services.product_crud import set_system_flag, delete_product
        pid = _add("P")["id"]
        set_system_flag(pid, "is_synced_with_off", True)
        delete_product(pid)
        assert db.execute("SELECT product_id FROM product_flags WHERE product_id=?", (pid,)).fetchone() is None

    def test_nonexistent_product_returns_false(self, db):
        from services.product_crud import delete_product
        assert delete_product(99999) is False


# ── EAN functions ─────────────────────────────────────────────────────────────


class TestEanFunctions:
    def _create_product(self, db):
        return _add("EAN Test")["id"]

    def test_add_ean_rejects_too_short(self, db):
        from services.product_crud import add_ean
        pid = self._create_product(db)
        with pytest.raises(ValueError, match="EAN"):
            add_ean(pid, "1234567")  # 7 digits

    def test_add_ean_rejects_too_long(self, db):
        from services.product_crud import add_ean
        pid = self._create_product(db)
        with pytest.raises(ValueError, match="EAN"):
            add_ean(pid, "12345678901234")  # 14 digits

    def test_add_first_ean_is_primary(self, db):
        from services.product_crud import add_ean
        pid = self._create_product(db)
        result = add_ean(pid, "12345678")
        assert result["is_primary"] is True

    def test_add_second_ean_not_primary(self, db):
        from services.product_crud import add_ean
        pid = self._create_product(db)
        add_ean(pid, "12345678")
        result = add_ean(pid, "87654321")
        assert result["is_primary"] is False

    def test_delete_ean_raises_when_only_ean(self, db):
        from services.product_crud import add_ean, delete_ean
        pid = self._create_product(db)
        ean = add_ean(pid, "12345678")
        with pytest.raises(ValueError, match="only"):
            delete_ean(pid, ean["id"])

    def test_delete_primary_ean_promotes_next(self, db):
        from services.product_crud import add_ean, delete_ean, list_eans
        pid = self._create_product(db)
        primary = add_ean(pid, "12345678")
        add_ean(pid, "87654321")
        delete_ean(pid, primary["id"])
        eans = list_eans(pid)
        assert len(eans) == 1
        assert eans[0]["is_primary"] is True

    def test_set_primary_ean_demotes_old_primary(self, db):
        from services.product_crud import add_ean, set_primary_ean, list_eans
        pid = self._create_product(db)
        add_ean(pid, "12345678")
        second = add_ean(pid, "87654321")
        set_primary_ean(pid, second["id"])
        eans = list_eans(pid)
        primaries = [e for e in eans if e["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["ean"] == "87654321"

    def test_list_eans_primary_first(self, db):
        from services.product_crud import add_ean, set_primary_ean, list_eans
        pid = self._create_product(db)
        add_ean(pid, "12345678")
        second = add_ean(pid, "87654321")
        set_primary_ean(pid, second["id"])
        eans = list_eans(pid)
        assert eans[0]["is_primary"] is True
        assert eans[0]["ean"] == "87654321"
