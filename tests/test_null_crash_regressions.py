"""Null-crash regression tests for LSO-1672 H3.

JSON ``null`` on optional string fields used to crash three services with
``AttributeError: 'NoneType' object has no attribute 'strip'`` → HTTP 500:

- ``services/backup_core.py`` — ``_restore_protein_quality`` on a
  ``{"name": null}`` protein-quality entry
- ``services/import_service.py`` — ``import_products`` on ``{"name": null}``
  flag definitions and ``{"type": null}`` / ``{"name": null}`` products
- ``services/proxy_service.py`` — ``off_search`` on an OFF product whose
  language variant (e.g. ``ingredients_text_no``) is explicitly ``null``

Each test reproduces the crash with the key *present and set to null* —
absent keys hit the ``""`` default and never crashed. Blueprint handlers
only map ``ValueError``/``OSError``/``RuntimeError`` to error responses, so
any ``AttributeError`` raised here surfaced to the client as a 500.
"""

from unittest.mock import patch

import pytest


class TestRestoreProteinQualityNullName:
    """POST /api/restore with ``{"name": null}`` in protein_quality."""

    def test_restore_null_pq_name_does_not_crash(self, app_ctx, db):
        from services.backup_core import restore_backup

        msg = restore_backup(
            {
                "products": [],
                "protein_quality": [
                    {
                        "name": None,
                        "label": "Whey Isolate",
                        "pdcaas": 0.9,
                        "diaas": 1.0,
                    }
                ],
            }
        )
        assert "Restored 0 products" in msg
        row = db.execute(
            "SELECT name, pdcaas, diaas FROM protein_quality"
        ).fetchone()
        assert row is not None
        # Null name falls back to the sanitized label, exactly like an
        # absent name key does.
        assert row["name"] == "whey_isolate"
        assert row["pdcaas"] == pytest.approx(0.9)
        assert row["diaas"] == pytest.approx(1.0)

    def test_restore_null_pq_name_without_label_uses_keyword(self, app_ctx, db):
        from services.backup_core import restore_backup

        restore_backup(
            {
                "products": [],
                "protein_quality": [
                    {
                        "name": None,
                        "keywords": ["soy"],
                        "pdcaas": 0.5,
                        "diaas": 0.5,
                    }
                ],
            }
        )
        row = db.execute("SELECT name FROM protein_quality").fetchone()
        assert row is not None
        assert row["name"] == "soy"


class TestRestoreProductNullTextFields:
    """Restore must coerce null product text fields instead of 500ing.

    ``_restore_product`` inserts into NOT NULL columns; passing raw ``None``
    raised ``sqlite3.IntegrityError`` → 500 even after the ``.strip()``
    sweep, so nulls must be coerced to ``""`` before the INSERT.
    """

    @pytest.mark.parametrize("field", ["name", "type", "brand", "ingredients"])
    def test_restore_product_with_null_field(self, app_ctx, db, field):
        from services.backup_core import restore_backup

        product = {"name": "Restored", "type": "Snacks"}
        product[field] = None
        msg = restore_backup({"products": [product]})
        assert "Restored 1 products" in msg
        row = db.execute(
            f"SELECT {field} FROM products"  # noqa: S608 — field is parametrized above, not user input
        ).fetchone()
        assert row is not None
        assert row[field] == ""


class TestImportNullStringFields:
    """POST /api/import with nulls in flag_definitions and products."""

    def test_import_null_flag_definition_name_is_skipped(self, app_ctx, db):
        from services.import_service import import_products

        msg = import_products(
            {
                "products": [],
                "flag_definitions": [{"name": None, "type": "user"}],
            }
        )
        assert "Imported 0 products" in msg
        rows = db.execute(
            "SELECT name FROM flag_definitions WHERE name IS NULL OR name = ''"
        ).fetchall()
        assert rows == []

    def test_import_product_with_null_type(self, app_ctx, db):
        from services.import_service import import_products

        msg = import_products(
            {"products": [{"name": "NullType Product", "type": None}]}
        )
        assert "Imported 1 products" in msg
        row = db.execute(
            "SELECT type FROM products WHERE name = ?", ("NullType Product",)
        ).fetchone()
        assert row is not None
        assert row["type"] == ""

    def test_import_product_with_null_name(self, app_ctx, db):
        from services.import_service import import_products

        msg = import_products(
            {
                "products": [
                    {"name": None, "type": "Snacks", "ean": "7038010009999"}
                ]
            }
        )
        assert "Imported 1 products" in msg
        row = db.execute(
            "SELECT p.name FROM products p "
            "JOIN product_eans pe ON pe.product_id = p.id WHERE pe.ean = ?",
            ("7038010009999",),
        ).fetchone()
        assert row is not None
        assert row["name"] == ""


class TestProxySearchNullLanguageVariant:
    """GET /api/off/search where the OFF payload has a null language variant."""

    def test_off_search_null_ingredients_variant_does_not_crash(self):
        from services.proxy_service import off_search
        import services.llm_translate_service as translate_svc

        product = {
            "code": "1234",
            "lang": "de",
            "product_name": "Testprodukt",
            "ingredients_text": "Zucker, Wasser",
            # OFF can return an explicit null for a language variant; the
            # translation gate used to crash on ``None.strip()`` here.
            "ingredients_text_no": None,
            "nutriments": {},
            "completeness": 0.5,
        }

        with patch(
            "services.proxy_service._off_search_a_licious",
            return_value={"products": [product]},
            autospec=True,
        ), patch(
            "services.proxy_service._off_search_classic",
            return_value={"products": []},
            autospec=True,
        ), patch(
            "services.settings_service.get_off_language_priority",
            return_value=["no", "en"],
            autospec=True,
        ), patch.object(
            translate_svc, "is_available", return_value=True, autospec=True
        ), patch.object(
            translate_svc,
            "translate_ingredients",
            return_value="Sukker, vann",
            autospec=True,
        ) as mock_translate:
            result = off_search("Testprodukt")

        p = result["products"][0]
        # The null variant counts as "no native text": translation runs and
        # its result is surfaced to the client.
        assert p["ingredients_text"] == "Sukker, vann"
        assert p.get("ingredients_translated") is True
        mock_translate.assert_called_once_with("Zucker, Wasser", "no")
