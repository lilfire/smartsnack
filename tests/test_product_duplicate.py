"""Tests for services/product_duplicate.py."""
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _insert_product(db, name, ean="", synced=False):
    """Insert a product directly and return its id."""
    cur = db.execute(
        "INSERT INTO products (type, name, ean, brand, stores, ingredients, taste_note)"
        " VALUES ('', ?, ?, '', '', '', '')",
        (name, ean),
    )
    pid = cur.lastrowid
    if ean:
        db.execute(
            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
            (pid, ean),
        )
    if synced:
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag)"
            " VALUES (?, 'is_synced_with_off')",
            (pid,),
        )
    db.commit()
    return pid


# ── _find_duplicate ───────────────────────────────────────────────────────────


class TestFindDuplicate:
    def test_returns_none_when_no_products(self, db):
        from services.product_duplicate import _find_duplicate
        assert _find_duplicate("1234567890", "Test") is None

    def test_returns_none_on_miss(self, db):
        from services.product_duplicate import _find_duplicate
        _insert_product(db, "Other", "9999999999")
        assert _find_duplicate("1234567890", "Test") is None

    def test_ean_match(self, db):
        from services.product_duplicate import _find_duplicate
        pid = _insert_product(db, "Product A", "1234567890")
        result = _find_duplicate("1234567890", "Different Name")
        assert result is not None
        assert result["id"] == pid
        assert result["match_type"] == "ean"

    def test_name_match_when_no_ean(self, db):
        from services.product_duplicate import _find_duplicate
        pid = _insert_product(db, "Product A", "")
        result = _find_duplicate("", "product a")  # case-insensitive
        assert result is not None
        assert result["id"] == pid
        assert result["match_type"] == "name"

    def test_ean_takes_priority_over_name(self, db):
        from services.product_duplicate import _find_duplicate
        ean_pid = _insert_product(db, "EAN Product", "1234567890")
        _insert_product(db, "Name Match", "")
        result = _find_duplicate("1234567890", "Name Match")
        assert result is not None
        assert result["match_type"] == "ean"
        assert result["id"] == ean_pid

    def test_exclude_id_prevents_match(self, db):
        from services.product_duplicate import _find_duplicate
        pid = _insert_product(db, "Product A", "1234567890")
        assert _find_duplicate("1234567890", "Product A", exclude_id=pid) is None

    def test_returned_dict_has_all_product_fields(self, db):
        from services.product_duplicate import _find_duplicate
        from config import ALL_PRODUCT_FIELDS
        _insert_product(db, "Product A", "1234567890")
        result = _find_duplicate("1234567890", "")
        assert result is not None
        assert "id" in result
        assert "match_type" in result
        assert "is_synced_with_off" in result
        for f in ALL_PRODUCT_FIELDS:
            assert f in result

    def test_is_synced_with_off_true(self, db):
        from services.product_duplicate import _find_duplicate
        _insert_product(db, "Product A", "1234567890", synced=True)
        result = _find_duplicate("1234567890", "")
        assert result["is_synced_with_off"] is True

    def test_is_synced_with_off_false(self, db):
        from services.product_duplicate import _find_duplicate
        _insert_product(db, "Product A", "1234567890", synced=False)
        result = _find_duplicate("1234567890", "")
        assert result["is_synced_with_off"] is False


# ── check_duplicate_for_edit ──────────────────────────────────────────────────


class TestCheckDuplicateForEdit:
    def test_no_duplicate_returns_none_false(self, db):
        from services.product_duplicate import check_duplicate_for_edit
        pid = _insert_product(db, "Product A", "1234567890")
        dup, synced = check_duplicate_for_edit(pid, "9999999999", "Other")
        assert dup is None
        assert synced is False

    def test_duplicate_found_returns_dict(self, db):
        from services.product_duplicate import check_duplicate_for_edit
        pid1 = _insert_product(db, "Product A", "1234567890")
        pid2 = _insert_product(db, "Product B", "9999999999")
        dup, synced = check_duplicate_for_edit(pid2, "1234567890", "Product A")
        assert dup is not None
        assert isinstance(dup, dict)
        assert dup["id"] == pid1

    def test_excludes_self_from_duplicate_search(self, db):
        from services.product_duplicate import check_duplicate_for_edit
        pid = _insert_product(db, "Product A", "1234567890")
        dup, _ = check_duplicate_for_edit(pid, "1234567890", "Product A")
        assert dup is None

    def test_is_synced_reflects_editing_product(self, db):
        from services.product_duplicate import check_duplicate_for_edit
        pid1 = _insert_product(db, "Product A", "1234567890", synced=True)
        pid2 = _insert_product(db, "Product B", "9999999999", synced=False)
        _, synced_true = check_duplicate_for_edit(pid1, "9999999999", "Other")
        assert synced_true is True
        _, synced_false = check_duplicate_for_edit(pid2, "1111111111", "Other")
        assert synced_false is False


# ── merge_products ────────────────────────────────────────────────────────────


class TestMergeProducts:
    def test_source_deleted_after_merge(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "2222222222")
        merge_products(target, source)
        assert db.execute("SELECT id FROM products WHERE id=?", (source,)).fetchone() is None

    def test_empty_target_field_filled_from_source(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "")
        source = _insert_product(db, "Source", "")
        db.execute("UPDATE products SET brand='SourceBrand' WHERE id=?", (source,))
        db.commit()
        merge_products(target, source)
        row = db.execute("SELECT brand FROM products WHERE id=?", (target,)).fetchone()
        assert row["brand"] == "SourceBrand"

    def test_existing_target_field_not_overwritten(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "")
        source = _insert_product(db, "Source", "")
        db.execute("UPDATE products SET brand='TargetBrand' WHERE id=?", (target,))
        db.execute("UPDATE products SET brand='SourceBrand' WHERE id=?", (source,))
        db.commit()
        merge_products(target, source)
        row = db.execute("SELECT brand FROM products WHERE id=?", (target,)).fetchone()
        assert row["brand"] == "TargetBrand"

    def test_flags_from_source_copied_to_target(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "")
        source = _insert_product(db, "Source", "", synced=True)
        merge_products(target, source)
        flag = db.execute(
            "SELECT flag FROM product_flags WHERE product_id=? AND flag='is_synced_with_off'",
            (target,),
        ).fetchone()
        assert flag is not None

    def test_choices_override_field_value(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "")
        source = _insert_product(db, "Source", "")
        db.execute("UPDATE products SET brand='TargetBrand' WHERE id=?", (target,))
        db.execute("UPDATE products SET brand='SourceBrand' WHERE id=?", (source,))
        db.commit()
        merge_products(target, source, choices={"brand": "SourceBrand"})
        row = db.execute("SELECT brand FROM products WHERE id=?", (target,)).fetchone()
        assert row["brand"] == "SourceBrand"

    def test_identical_fields_no_data_loss(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Same Product", "1111111111")
        source = _insert_product(db, "Same Product", "2222222222")
        merge_products(target, source)
        row = db.execute("SELECT name FROM products WHERE id=?", (target,)).fetchone()
        assert row["name"] == "Same Product"

    def test_raises_lookup_error_for_missing_target(self, db):
        from services.product_duplicate import merge_products
        source = _insert_product(db, "Source", "")
        with pytest.raises(LookupError):
            merge_products(99999, source)

    def test_raises_lookup_error_for_missing_source(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "")
        with pytest.raises(LookupError):
            merge_products(target, 99999)

    def test_source_eans_transferred_to_target(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "2222222222")
        merge_products(target, source)
        eans = {r["ean"] for r in db.execute(
            "SELECT ean FROM product_eans WHERE product_id=?", (target,)
        ).fetchall()}
        assert "2222222222" in eans

    def test_ean_transfer_no_duplicates_when_same_ean(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "1111111111")
        merge_products(target, source)
        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id=? AND ean=?",
            (target, "1111111111"),
        ).fetchone()[0]
        assert count == 1

    def test_both_eans_present_on_target_after_merge(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "2222222222")
        merge_products(target, source)
        eans = {r["ean"] for r in db.execute(
            "SELECT ean FROM product_eans WHERE product_id=?", (target,)
        ).fetchall()}
        assert "1111111111" in eans
        assert "2222222222" in eans

    def test_multiple_source_eans_all_transferred(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "2222222222")
        db.execute(
            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 0)",
            (source, "3333333333"),
        )
        db.commit()
        merge_products(target, source)
        eans = {r["ean"] for r in db.execute(
            "SELECT ean FROM product_eans WHERE product_id=?", (target,)
        ).fetchall()}
        assert "2222222222" in eans
        assert "3333333333" in eans

    def test_source_eans_not_in_product_eans_after_delete(self, db):
        from services.product_duplicate import merge_products
        target = _insert_product(db, "Target", "1111111111")
        source = _insert_product(db, "Source", "2222222222")
        merge_products(target, source)
        rows = db.execute(
            "SELECT ean FROM product_eans WHERE product_id=?", (source,)
        ).fetchall()
        assert rows == []
