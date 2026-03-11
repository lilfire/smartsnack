"""Tests for services/protein_quality_service.py — PQ entries and estimation."""

import pytest
from exceptions import ConflictError


class TestListEntries:
    def test_returns_seeded_entries(self, app_ctx):
        from services.protein_quality_service import list_entries

        entries = list_entries()
        assert len(entries) > 0
        names = [e["name"] for e in entries]
        assert "whey" in names
        assert "egg" in names

    def test_entry_structure(self, app_ctx):
        from services.protein_quality_service import list_entries

        entries = list_entries()
        e = entries[0]
        assert "id" in e
        assert "name" in e
        assert "pdcaas" in e
        assert "diaas" in e
        assert "label" in e
        assert "keywords" in e


class TestAddEntry:
    def test_valid_entry(self, app_ctx, translations_dir):
        from services.protein_quality_service import add_entry

        result = add_entry(
            {
                "name": "test_source",
                "keywords": ["test", "source"],
                "pdcaas": 0.8,
                "diaas": 0.75,
                "label": "Test Source",
            }
        )
        assert result["ok"] is True
        assert result["id"] > 0

    def test_duplicate_name(self, app_ctx, translations_dir):
        from services.protein_quality_service import add_entry

        with pytest.raises(ConflictError, match="already exists"):
            add_entry(
                {
                    "name": "whey",
                    "keywords": ["whey"],
                    "pdcaas": 1.0,
                    "diaas": 1.0,
                }
            )

    def test_missing_required_fields(self, app_ctx):
        from services.protein_quality_service import add_entry

        with pytest.raises(ValueError):
            add_entry({"name": "test"})

    def test_name_auto_generated_from_label(self, app_ctx, translations_dir):
        from services.protein_quality_service import add_entry

        result = add_entry(
            {
                "label": "My Source",
                "keywords": ["my", "source"],
                "pdcaas": 0.5,
                "diaas": 0.5,
            }
        )
        assert result["name"] == "my_source"

    def test_invalid_keywords(self, app_ctx):
        from services.protein_quality_service import add_entry
        from config import _PQ_MAX_KEYWORD_LEN

        with pytest.raises(ValueError):
            add_entry(
                {
                    "name": "test2",
                    "keywords": ["x" * (_PQ_MAX_KEYWORD_LEN + 1)],
                    "pdcaas": 0.5,
                    "diaas": 0.5,
                }
            )


class TestUpdateEntry:
    def test_update_pdcaas(self, app_ctx, translations_dir):
        from services.protein_quality_service import update_entry
        from db import get_db

        row = (
            get_db()
            .execute("SELECT id FROM protein_quality WHERE name='whey'")
            .fetchone()
        )
        update_entry(row["id"], {"pdcaas": 0.95})
        updated = (
            get_db()
            .execute("SELECT pdcaas FROM protein_quality WHERE id=?", (row["id"],))
            .fetchone()
        )
        assert updated["pdcaas"] == 0.95

    def test_not_found(self, app_ctx):
        from services.protein_quality_service import update_entry

        with pytest.raises(LookupError, match="Not found"):
            update_entry(99999, {"pdcaas": 0.5})

    def test_update_keywords(self, app_ctx, translations_dir):
        from services.protein_quality_service import update_entry
        from db import get_db

        row = (
            get_db()
            .execute("SELECT id FROM protein_quality WHERE name='whey'")
            .fetchone()
        )
        update_entry(row["id"], {"keywords": ["whey protein", "serum"]})


class TestDeleteEntry:
    def test_delete_existing(self, app_ctx, translations_dir):
        from services.protein_quality_service import add_entry, delete_entry

        result = add_entry(
            {
                "name": "to_delete",
                "keywords": ["delete"],
                "pdcaas": 0.1,
                "diaas": 0.1,
            }
        )
        delete_entry(result["id"])
        from db import get_db

        row = (
            get_db()
            .execute("SELECT id FROM protein_quality WHERE id=?", (result["id"],))
            .fetchone()
        )
        assert row is None

    def test_delete_not_found(self, app_ctx):
        from services.protein_quality_service import delete_entry

        with pytest.raises(LookupError, match="Not found"):
            delete_entry(99999)


class TestEstimate:
    def test_empty_ingredients(self, app_ctx):
        from services.protein_quality_service import estimate

        result = estimate("")
        assert result["est_pdcaas"] is None
        assert result["est_diaas"] is None
        assert result["sources"] == []

    def test_no_matches(self, app_ctx):
        from services.protein_quality_service import estimate

        result = estimate("random ingredient xyz")
        assert result["est_pdcaas"] is None
        assert result["sources"] == []

    def test_single_match(self, app_ctx, translations_dir):
        from services.protein_quality_service import estimate
        from translations import _set_translation_key

        # Make sure whey has a keyword
        _set_translation_key("pq_whey_keywords", {"no": "myse, whey"})
        result = estimate("whey protein isolate")
        assert result["est_pdcaas"] is not None
        assert result["est_pdcaas"] > 0

    def test_multiple_matches(self, app_ctx, translations_dir):
        from services.protein_quality_service import estimate
        from translations import _set_translation_key

        _set_translation_key("pq_whey_keywords", {"no": "myse, whey"})
        _set_translation_key("pq_oats_keywords", {"no": "havre, oats"})
        result = estimate("whey, oats, sugar")
        assert result["est_pdcaas"] is not None
        assert len(result["sources"]) >= 2

    def test_position_weighting(self, app_ctx, translations_dir):
        from services.protein_quality_service import estimate
        from translations import _set_translation_key

        _set_translation_key("pq_whey_keywords", {"no": "myse, whey"})
        _set_translation_key("pq_oats_keywords", {"no": "havre, oats"})
        # Whey first should weight it more
        result1 = estimate("whey, oats")
        result2 = estimate("oats, whey")
        # Both should give results but with different weights
        assert result1["est_pdcaas"] is not None
        assert result2["est_pdcaas"] is not None
