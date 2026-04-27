"""Isolated unit tests for services/tag_service.py."""

import pytest


# ── create_tag ────────────────────────────────────────────────────────────────


class TestCreateTag:
    def test_creates_tag_successfully(self, app_ctx):
        from services.tag_service import create_tag
        tag = create_tag("organic")
        assert tag["label"] == "organic"
        assert isinstance(tag["id"], int)

    def test_lowercases_label(self, app_ctx):
        from services.tag_service import create_tag
        tag = create_tag("ORGANIC")
        assert tag["label"] == "organic"

    def test_strips_whitespace(self, app_ctx):
        from services.tag_service import create_tag
        tag = create_tag("  organic  ")
        assert tag["label"] == "organic"

    def test_strips_and_lowercases_combined(self, app_ctx):
        from services.tag_service import create_tag
        tag = create_tag("  Organic  ")
        assert tag["label"] == "organic"

    def test_empty_label_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag
        with pytest.raises(ValueError, match="label is required"):
            create_tag("")

    def test_whitespace_only_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag
        with pytest.raises(ValueError, match="label is required"):
            create_tag("   ")

    def test_label_too_long_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag
        from config import TAG_LABEL_MAX_LEN
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_tag("x" * (TAG_LABEL_MAX_LEN + 1))

    def test_label_at_exact_max_length_succeeds(self, app_ctx):
        from services.tag_service import create_tag
        from config import TAG_LABEL_MAX_LEN
        tag = create_tag("a" * TAG_LABEL_MAX_LEN)
        assert len(tag["label"]) == TAG_LABEL_MAX_LEN

    def test_duplicate_label_returns_existing_tag(self, app_ctx):
        from services.tag_service import create_tag
        t1 = create_tag("salty")
        t2 = create_tag("salty")
        assert t1["id"] == t2["id"]
        assert t1["label"] == t2["label"]

    def test_case_insensitive_duplicate_returns_existing(self, app_ctx):
        from services.tag_service import create_tag
        t1 = create_tag("bio")
        t2 = create_tag("BIO")
        assert t1["id"] == t2["id"]

    def test_returns_dict_with_id_and_label(self, app_ctx):
        from services.tag_service import create_tag
        tag = create_tag("testlabel")
        assert "id" in tag
        assert "label" in tag
        assert len(tag) == 2

    def test_multiple_distinct_tags(self, app_ctx):
        from services.tag_service import create_tag
        t1 = create_tag("alpha")
        t2 = create_tag("beta")
        assert t1["id"] != t2["id"]


# ── list_tags ──────────────────────────────────────────────────────────────────


class TestListTags:
    def test_empty_db_returns_empty_list(self, app_ctx):
        from services.tag_service import list_tags
        assert list_tags() == []

    def test_returns_all_tags(self, app_ctx):
        from services.tag_service import create_tag, list_tags
        create_tag("alpha")
        create_tag("beta")
        tags = list_tags()
        labels = [t["label"] for t in tags]
        assert "alpha" in labels
        assert "beta" in labels

    def test_sorted_case_insensitive_ascending(self, app_ctx):
        from services.tag_service import create_tag, list_tags
        create_tag("zesty")
        create_tag("apple")
        create_tag("mango")
        labels = [t["label"] for t in list_tags()]
        assert labels == sorted(labels, key=str.lower)

    def test_mixed_case_ordering(self, app_ctx):
        from services.tag_service import create_tag, list_tags
        create_tag("Zucchini")
        create_tag("apple")
        create_tag("Banana")
        labels = [t["label"] for t in list_tags()]
        assert labels == sorted(labels, key=str.lower)

    def test_returns_dicts_with_id_and_label(self, app_ctx):
        from services.tag_service import create_tag, list_tags
        create_tag("testval")
        tags = list_tags()
        assert all("id" in t and "label" in t for t in tags)

    def test_list_includes_all_created_tags(self, app_ctx):
        from services.tag_service import create_tag, list_tags
        for i in range(5):
            create_tag(f"tag{i:02d}")
        tags = list_tags()
        assert len(tags) >= 5


# ── get_tag ────────────────────────────────────────────────────────────────────


class TestGetTag:
    def test_returns_tag_when_found(self, app_ctx):
        from services.tag_service import create_tag, get_tag
        t = create_tag("organic")
        result = get_tag(t["id"])
        assert result == {"id": t["id"], "label": "organic"}

    def test_returns_none_when_not_found(self, app_ctx):
        from services.tag_service import get_tag
        assert get_tag(99999) is None

    def test_returns_correct_tag_when_multiple_exist(self, app_ctx):
        from services.tag_service import create_tag, get_tag
        t1 = create_tag("first")
        t2 = create_tag("second")
        assert get_tag(t1["id"])["label"] == "first"
        assert get_tag(t2["id"])["label"] == "second"


# ── update_tag ─────────────────────────────────────────────────────────────────


class TestUpdateTag:
    def test_renames_tag_successfully(self, app_ctx):
        from services.tag_service import create_tag, update_tag, get_tag
        t = create_tag("old")
        result = update_tag(t["id"], "new")
        assert result is not None
        assert result["label"] == "new"
        assert get_tag(t["id"])["label"] == "new"

    def test_returns_none_when_tag_not_found(self, app_ctx):
        from services.tag_service import update_tag
        assert update_tag(99999, "newlabel") is None

    def test_empty_label_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        t = create_tag("valid")
        with pytest.raises(ValueError, match="label is required"):
            update_tag(t["id"], "")

    def test_whitespace_only_label_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        t = create_tag("valid")
        with pytest.raises(ValueError, match="label is required"):
            update_tag(t["id"], "   ")

    def test_label_too_long_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        from config import TAG_LABEL_MAX_LEN
        t = create_tag("valid")
        with pytest.raises(ValueError, match="exceeds maximum length"):
            update_tag(t["id"], "x" * (TAG_LABEL_MAX_LEN + 1))

    def test_duplicate_label_raises_value_error(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        create_tag("first")
        t2 = create_tag("second")
        with pytest.raises(ValueError, match="already exists"):
            update_tag(t2["id"], "first")

    def test_rename_to_same_label_succeeds(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        t = create_tag("organic")
        result = update_tag(t["id"], "organic")
        assert result is not None
        assert result["label"] == "organic"

    def test_rename_lowercases_and_strips(self, app_ctx):
        from services.tag_service import create_tag, update_tag
        t = create_tag("old")
        result = update_tag(t["id"], "  NEW  ")
        assert result["label"] == "new"


# ── delete_tag ─────────────────────────────────────────────────────────────────


class TestDeleteTag:
    def test_deletes_existing_tag(self, app_ctx):
        from services.tag_service import create_tag, delete_tag, get_tag
        t = create_tag("bye")
        assert delete_tag(t["id"]) is True
        assert get_tag(t["id"]) is None

    def test_returns_false_when_not_found(self, app_ctx):
        from services.tag_service import delete_tag
        assert delete_tag(99999) is False

    def test_delete_removes_from_list(self, app_ctx):
        from services.tag_service import create_tag, delete_tag, list_tags
        t = create_tag("temporary")
        delete_tag(t["id"])
        labels = [x["label"] for x in list_tags()]
        assert "temporary" not in labels

    def test_delete_removes_product_associations(self, app_ctx, db):
        from services.tag_service import create_tag, delete_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t = create_tag("doomed")
        set_tags_for_product(prod["id"], [t["id"]])
        delete_tag(t["id"])
        result = get_tags_for_products([prod["id"]])
        assert result[prod["id"]] == []


# ── search_tags ────────────────────────────────────────────────────────────────


class TestSearchTags:
    def test_returns_matches_by_prefix(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("organic")
        create_tag("orange")
        create_tag("salty")
        results = search_tags("or")
        labels = [t["label"] for t in results]
        assert "organic" in labels
        assert "orange" in labels
        assert "salty" not in labels

    def test_case_insensitive_prefix(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("organic")
        results = search_tags("ORG")
        assert any(t["label"] == "organic" for t in results)

    def test_empty_prefix_returns_up_to_limit(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        for i in range(15):
            create_tag(f"tag{i:02d}")
        results = search_tags("", limit=10)
        assert len(results) <= 10

    def test_no_match_returns_empty_list(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("organic")
        assert search_tags("xyz") == []

    def test_percent_char_does_not_wildcard_match(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("percent")
        results = search_tags("%")
        assert all(t["label"] != "percent" for t in results)

    def test_underscore_does_not_wildcard_match(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("under_score")
        results = search_tags("_")
        assert all(t["label"] != "under_score" for t in results)

    def test_results_sorted_alphabetically(self, app_ctx):
        from services.tag_service import create_tag, search_tags
        create_tag("orzo")
        create_tag("orange")
        create_tag("organic")
        results = search_tags("or")
        labels = [t["label"] for t in results]
        assert labels == sorted(labels, key=str.lower)


# ── get_tags_for_products ──────────────────────────────────────────────────────


class TestGetTagsForProducts:
    def test_empty_list_returns_empty_dict(self, app_ctx):
        from services.tag_service import get_tags_for_products
        assert get_tags_for_products([]) == {}

    def test_product_with_no_tags_returns_empty_list(self, app_ctx, db):
        from services.tag_service import get_tags_for_products
        row = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        result = get_tags_for_products([row["id"]])
        assert result[row["id"]] == []

    def test_product_with_tags_returned(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t = create_tag("testlabel")
        set_tags_for_product(prod["id"], [t["id"]])
        result = get_tags_for_products([prod["id"]])
        assert len(result[prod["id"]]) == 1
        assert result[prod["id"]][0]["label"] == "testlabel"

    def test_nonexistent_product_id_returns_empty_list(self, app_ctx):
        from services.tag_service import get_tags_for_products
        result = get_tags_for_products([99999])
        assert result[99999] == []

    def test_tags_sorted_by_label(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t1 = create_tag("zesty")
        t2 = create_tag("apple")
        set_tags_for_product(prod["id"], [t1["id"], t2["id"]])
        result = get_tags_for_products([prod["id"]])
        labels = [x["label"] for x in result[prod["id"]]]
        assert labels == sorted(labels, key=str.lower)


# ── set_tags_for_product ───────────────────────────────────────────────────────


class TestSetTagsForProduct:
    def test_sets_tags_for_product(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t = create_tag("mytag")
        set_tags_for_product(prod["id"], [t["id"]])
        result = get_tags_for_products([prod["id"]])
        assert any(x["label"] == "mytag" for x in result[prod["id"]])

    def test_replaces_existing_tags(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t1 = create_tag("oldtag")
        t2 = create_tag("newtag")
        set_tags_for_product(prod["id"], [t1["id"]])
        set_tags_for_product(prod["id"], [t2["id"]])
        result = get_tags_for_products([prod["id"]])
        labels = [x["label"] for x in result[prod["id"]]]
        assert "oldtag" not in labels
        assert "newtag" in labels

    def test_empty_list_clears_all_tags(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t = create_tag("temporary")
        set_tags_for_product(prod["id"], [t["id"]])
        set_tags_for_product(prod["id"], [])
        result = get_tags_for_products([prod["id"]])
        assert result[prod["id"]] == []

    def test_invalid_tag_ids_are_ignored(self, app_ctx, db):
        from services.tag_service import create_tag, set_tags_for_product, get_tags_for_products
        prod = db.execute("SELECT id FROM products LIMIT 1").fetchone()
        t = create_tag("valid")
        set_tags_for_product(prod["id"], [t["id"], 99999])
        result = get_tags_for_products([prod["id"]])
        assert len(result[prod["id"]]) == 1
        assert result[prod["id"]][0]["label"] == "valid"
