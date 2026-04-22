"""Regression tests for EAN dual-storage (products.ean + product_eans table).

Scenario A: A product with EAN only in products.ean (no product_eans row)
            must be findable via the search API after migration backfill.
Scenario B: Adding a duplicate EAN to the same product returns success
            (idempotent), not 409.

Scenario B is already covered in test_ean.py (TestAddEan and TestAddEanBlueprint).
This file adds explicit regression coverage for Scenario A.
"""

import pytest


def _add_product(client, name="TestProduct", ean="12345678"):
    resp = client.post(
        "/api/products",
        json={"type": "Snacks", "name": name, "ean": ean},
    )
    assert resp.status_code in (201, 200), resp.get_json()
    return resp.get_json()["id"]


class TestLegacyEanOnlyInProductsTable:
    """Scenario A: product with EAN only in products.ean (no product_eans row)."""

    def test_search_finds_product_after_backfill(self, client, db):
        """Simulate a legacy product missing its product_eans row, run the
        backfill migration SQL, and verify search finds it by EAN."""
        # Create a product normally (creates both products.ean and product_eans)
        pid = _add_product(client, name="LegacyEanProduct", ean="99887766")

        # Remove the product_eans row to simulate pre-migration state
        db.execute("DELETE FROM product_eans WHERE product_id = ?", (pid,))
        db.commit()

        # Verify the product_eans row is gone
        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert count == 0

        # Search should NOT find it (product_eans row is missing)
        resp = client.get("/api/products?search=99887766")
        assert resp.status_code == 200
        names_before = [p["name"] for p in resp.get_json()["products"]]
        assert "LegacyEanProduct" not in names_before

        # Run the backfill migration SQL (same as migration 010)
        db.execute(
            """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1
               FROM products p
               WHERE p.ean IS NOT NULL AND p.ean != ''
                 AND NOT EXISTS (
                   SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id
                 )"""
        )
        db.commit()

        # Now search should find it
        resp = client.get("/api/products?search=99887766")
        assert resp.status_code == 200
        names_after = [p["name"] for p in resp.get_json()["products"]]
        assert "LegacyEanProduct" in names_after

    def test_backfill_sets_primary_flag(self, client, db):
        """Backfilled product_eans row must have is_primary=1."""
        pid = _add_product(client, name="BackfillPrimary", ean="11223344")

        # Remove the product_eans row
        db.execute("DELETE FROM product_eans WHERE product_id = ?", (pid,))
        db.commit()

        # Backfill
        db.execute(
            """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1
               FROM products p
               WHERE p.ean IS NOT NULL AND p.ean != ''
                 AND NOT EXISTS (
                   SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id
                 )"""
        )
        db.commit()

        row = db.execute(
            "SELECT ean, is_primary FROM product_eans WHERE product_id = ?",
            (pid,),
        ).fetchone()
        assert row is not None
        assert row["ean"] == "11223344"
        assert row["is_primary"] == 1

    def test_backfill_skips_empty_ean(self, client, db):
        """Products with empty EAN should not get a product_eans row."""
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "NoEanBackfill"},
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]

        # Backfill should not insert for empty EAN
        db.execute(
            """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1
               FROM products p
               WHERE p.ean IS NOT NULL AND p.ean != ''
                 AND NOT EXISTS (
                   SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id
                 )"""
        )
        db.commit()

        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert count == 0

    def test_backfill_is_idempotent(self, client, db):
        """Running the backfill twice should not create duplicate rows."""
        pid = _add_product(client, name="IdempotentBackfill", ean="55667788")

        # Remove and backfill
        db.execute("DELETE FROM product_eans WHERE product_id = ?", (pid,))
        db.commit()

        backfill_sql = """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1
               FROM products p
               WHERE p.ean IS NOT NULL AND p.ean != ''
                 AND NOT EXISTS (
                   SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id
                 )"""

        db.execute(backfill_sql)
        db.commit()
        db.execute(backfill_sql)
        db.commit()

        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert count == 1


class TestDuplicateEanIdempotent:
    """Scenario B: verify duplicate EAN on same product is idempotent (not 409).

    These tests complement the existing coverage in test_ean.py by testing
    the full API roundtrip explicitly as a regression guard.
    """

    def test_add_same_ean_via_api_returns_200_not_409(self, client):
        """POST /api/products/<pid>/eans with the product's own EAN returns 200."""
        pid = _add_product(client, name="DupApiCheck", ean="44556677")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "44556677"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ean"] == "44556677"
        assert data.get("already_exists") is True

    def test_add_same_secondary_ean_twice_is_idempotent(self, client):
        """Adding the same secondary EAN twice returns 200 on the second call."""
        pid = _add_product(client, name="DupSecondary", ean="11112222")
        resp1 = client.post(f"/api/products/{pid}/eans", json={"ean": "33334444"})
        assert resp1.status_code == 201

        resp2 = client.post(f"/api/products/{pid}/eans", json={"ean": "33334444"})
        assert resp2.status_code == 200
        assert resp2.get_json().get("already_exists") is True
