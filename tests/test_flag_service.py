"""Tests for services/flag_service.py — flag definition management."""

import pytest


class TestListFlags:
    def test_returns_list(self, app_ctx, translations_dir):
        from services.flag_service import list_flags

        flags = list_flags()
        assert isinstance(flags, list)

    def test_includes_seeded_flags(self, app_ctx, translations_dir):
        from services.flag_service import list_flags

        flags = list_flags()
        names = [f["name"] for f in flags]
        assert "is_discontinued" in names
        assert "is_synced_with_off" in names

    def test_flag_structure(self, app_ctx, translations_dir):
        from services.flag_service import list_flags

        flags = list_flags()
        assert len(flags) >= 1
        flag = flags[0]
        assert "name" in flag
        assert "type" in flag
        assert "label_key" in flag
        assert "label" in flag
        assert "count" in flag

    def test_count_is_integer(self, app_ctx, translations_dir):
        from services.flag_service import list_flags

        flags = list_flags()
        for flag in flags:
            assert isinstance(flag["count"], int)

    def test_count_reflects_product_flags(self, app_ctx, db, translations_dir):
        from services.flag_service import list_flags

        # Attach is_discontinued to the seed product
        product_id = db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (product_id, "is_discontinued"),
        )
        db.commit()

        flags = list_flags()
        disc = next(f for f in flags if f["name"] == "is_discontinued")
        assert disc["count"] >= 1


class TestGetAllFlagNames:
    def test_returns_set(self, app_ctx):
        from services.flag_service import get_all_flag_names

        result = get_all_flag_names()
        assert isinstance(result, set)

    def test_includes_both_flag_types(self, app_ctx):
        from services.flag_service import get_all_flag_names

        result = get_all_flag_names()
        assert "is_discontinued" in result
        assert "is_synced_with_off" in result

    def test_count_matches_db(self, app_ctx, db):
        from services.flag_service import get_all_flag_names

        db_count = db.execute("SELECT COUNT(*) FROM flag_definitions").fetchone()[0]
        result = get_all_flag_names()
        assert len(result) == db_count


class TestGetUserFlagNames:
    def test_returns_set(self, app_ctx):
        from services.flag_service import get_user_flag_names

        result = get_user_flag_names()
        assert isinstance(result, set)

    def test_includes_user_flags(self, app_ctx):
        from services.flag_service import get_user_flag_names

        result = get_user_flag_names()
        assert "is_discontinued" in result

    def test_excludes_system_flags(self, app_ctx):
        from services.flag_service import get_user_flag_names

        result = get_user_flag_names()
        assert "is_synced_with_off" not in result

    def test_only_user_type(self, app_ctx, db):
        from services.flag_service import get_user_flag_names

        result = get_user_flag_names()
        for name in result:
            row = db.execute(
                "SELECT type FROM flag_definitions WHERE name = ?", (name,)
            ).fetchone()
            assert row["type"] == "user"


class TestGetFlagConfig:
    def test_returns_dict(self, app_ctx, translations_dir):
        from services.flag_service import get_flag_config

        result = get_flag_config()
        assert isinstance(result, dict)

    def test_keys_are_flag_names(self, app_ctx, translations_dir):
        from services.flag_service import get_flag_config

        result = get_flag_config()
        assert "is_discontinued" in result
        assert "is_synced_with_off" in result

    def test_value_structure(self, app_ctx, translations_dir):
        from services.flag_service import get_flag_config

        result = get_flag_config()
        entry = result["is_discontinued"]
        assert "type" in entry
        assert "labelKey" in entry
        assert "label" in entry

    def test_types_are_correct(self, app_ctx, translations_dir):
        from services.flag_service import get_flag_config

        result = get_flag_config()
        assert result["is_discontinued"]["type"] == "user"
        assert result["is_synced_with_off"]["type"] == "system"


class TestAddFlag:
    def test_happy_path(self, app_ctx, db, translations_dir):
        from services.flag_service import add_flag

        add_flag("is_on_sale", "On sale")
        row = db.execute(
            "SELECT type FROM flag_definitions WHERE name = ?", ("is_on_sale",)
        ).fetchone()
        assert row is not None
        assert row["type"] == "user"

    def test_added_flag_appears_in_all_names(self, app_ctx, translations_dir):
        from services.flag_service import add_flag, get_all_flag_names

        add_flag("is_organic", "Organic")
        names = get_all_flag_names()
        assert "is_organic" in names

    def test_empty_name_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag

        with pytest.raises(ValueError):
            add_flag("", "Some label")

    def test_empty_label_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag

        with pytest.raises(ValueError):
            add_flag("is_valid_name", "")

    def test_invalid_chars_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag

        with pytest.raises(ValueError):
            add_flag("Has-Hyphens", "Label")

    def test_starts_with_digit_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag

        with pytest.raises(ValueError):
            add_flag("1invalid", "Label")

    def test_uppercase_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag

        with pytest.raises(ValueError):
            add_flag("IsUpper", "Label")

    def test_duplicate_raises_conflict_error(self, app_ctx, translations_dir):
        from services.flag_service import add_flag
        from exceptions import ConflictError

        add_flag("is_new_flag", "New flag")
        with pytest.raises(ConflictError):
            add_flag("is_new_flag", "Duplicate")

    def test_existing_seeded_flag_raises_conflict(self, app_ctx, translations_dir):
        from services.flag_service import add_flag
        from exceptions import ConflictError

        with pytest.raises(ConflictError):
            add_flag("is_discontinued", "Already exists")


class TestUpdateFlagLabel:
    def test_happy_path(self, app_ctx, db, translations_dir):
        from services.flag_service import update_flag_label

        # is_discontinued is a user flag so it can be updated
        update_flag_label("is_discontinued", "Utgatt")
        # No exception means success; verify the label key persists in the DB
        row = db.execute(
            "SELECT label_key FROM flag_definitions WHERE name = 'is_discontinued'"
        ).fetchone()
        assert row is not None

    def test_system_flag_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import update_flag_label

        with pytest.raises(ValueError, match="system"):
            update_flag_label("is_synced_with_off", "New label")

    def test_not_found_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import update_flag_label

        with pytest.raises(ValueError, match="not found"):
            update_flag_label("nonexistent_flag", "Label")

    def test_empty_label_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import update_flag_label

        with pytest.raises(ValueError):
            update_flag_label("is_discontinued", "")

    def test_newly_added_flag_can_be_updated(self, app_ctx, translations_dir):
        from services.flag_service import add_flag, update_flag_label

        add_flag("is_seasonal", "Seasonal")
        # Should not raise
        update_flag_label("is_seasonal", "Sesongvare")


class TestDeleteFlag:
    def test_happy_path_returns_count(self, app_ctx, db, translations_dir):
        from services.flag_service import add_flag, delete_flag

        add_flag("is_temp_flag", "Temp")
        count = delete_flag("is_temp_flag")
        assert isinstance(count, int)
        assert count == 0

    def test_flag_removed_from_db(self, app_ctx, db, translations_dir):
        from services.flag_service import add_flag, delete_flag

        add_flag("is_removable", "Removable")
        delete_flag("is_removable")
        row = db.execute(
            "SELECT name FROM flag_definitions WHERE name = 'is_removable'"
        ).fetchone()
        assert row is None

    def test_returns_affected_product_count(self, app_ctx, db, translations_dir):
        from services.flag_service import add_flag, delete_flag

        add_flag("is_flagged_product", "Flagged")
        product_id = db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (product_id, "is_flagged_product"),
        )
        db.commit()

        count = delete_flag("is_flagged_product")
        assert count == 1

    def test_product_flags_cleaned_up(self, app_ctx, db, translations_dir):
        from services.flag_service import add_flag, delete_flag

        add_flag("is_cleanup_test", "Cleanup")
        product_id = db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (product_id, "is_cleanup_test"),
        )
        db.commit()

        delete_flag("is_cleanup_test")
        remaining = db.execute(
            "SELECT COUNT(*) FROM product_flags WHERE flag = 'is_cleanup_test'"
        ).fetchone()[0]
        assert remaining == 0

    def test_system_flag_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import delete_flag

        with pytest.raises(ValueError, match="system"):
            delete_flag("is_synced_with_off")

    def test_not_found_raises_value_error(self, app_ctx, translations_dir):
        from services.flag_service import delete_flag

        with pytest.raises(ValueError, match="not found"):
            delete_flag("no_such_flag_xyz")

    def test_deleted_flag_absent_from_all_names(self, app_ctx, translations_dir):
        from services.flag_service import add_flag, delete_flag, get_all_flag_names

        add_flag("is_transient", "Transient")
        delete_flag("is_transient")
        names = get_all_flag_names()
        assert "is_transient" not in names
