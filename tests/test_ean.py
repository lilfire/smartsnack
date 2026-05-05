"""Tests for multiple EAN support — migration, service functions, and blueprint routes."""

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _add_product(client, name="TestProduct", ean="12345678", type_="Snacks"):
    """Add a product and return its id."""
    resp = client.post(
        "/api/products",
        json={"type": type_, "name": name, "ean": ean},
    )
    assert resp.status_code in (201, 200), resp.get_json()
    return resp.get_json()["id"]


def _add_product_no_ean(client, name="NoEanProduct"):
    """Add a product without an EAN and return its id."""
    resp = client.post(
        "/api/products",
        json={"type": "Snacks", "name": name},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["id"]


# ── Migration ──────────────────────────────────────────────────────────────────


class TestMigration006:
    def test_product_eans_table_created(self, db):
        tables = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "product_eans" in tables

    def test_seeded_product_with_ean_has_primary_row(self, db):
        """The demo seeded product has a non-empty EAN → one primary row."""
        row = db.execute("SELECT id, ean FROM products WHERE ean != '' LIMIT 1").fetchone()
        if row is None:
            pytest.skip("No seeded product with EAN")
        pid, ean = row["id"], row["ean"]
        ean_rows = db.execute(
            "SELECT * FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchall()
        assert len(ean_rows) == 1
        assert ean_rows[0]["ean"] == ean
        assert ean_rows[0]["is_primary"] == 1

    def test_product_with_empty_ean_has_no_ean_rows(self, db):
        """Products with ean='' must have no rows in product_eans."""
        row = db.execute("SELECT id FROM products WHERE ean = '' LIMIT 1").fetchone()
        if row is None:
            pytest.skip("No seeded product with empty EAN")
        pid = row["id"]
        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert count == 0

    def test_migration_tracked(self, db):
        applied = {
            r[0] for r in db.execute("SELECT name FROM schema_migrations").fetchall()
        }
        assert "006_product_eans_table" in applied


# ── Service: list_eans ─────────────────────────────────────────────────────────


class TestListEans:
    def test_returns_ean_objects(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "ListTest", "ean": "12345678"})["id"]
        eans = product_service.list_eans(pid)
        assert len(eans) == 1
        ean = eans[0]
        assert "id" in ean
        assert ean["ean"] == "12345678"
        assert ean["is_primary"] is True
        assert ean["synced_with_off"] is False

    def test_raises_for_unknown_product(self, app_ctx):
        from services import product_service

        with pytest.raises(LookupError):
            product_service.list_eans(99999)

    def test_empty_list_for_product_without_eans(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "NoEan"})["id"]
        eans = product_service.list_eans(pid)
        assert eans == []

    def test_synced_with_off_reflects_db_state(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "SyncedList", "ean": "12345678", "from_off": True}
        )["id"]
        product_service.add_ean(pid, "87654321")  # non-synced secondary
        eans = product_service.list_eans(pid)
        assert len(eans) == 2
        synced = next(e for e in eans if e["ean"] == "12345678")
        unsynced = next(e for e in eans if e["ean"] == "87654321")
        assert synced["synced_with_off"] is True
        assert unsynced["synced_with_off"] is False


# ── Service: add_ean ───────────────────────────────────────────────────────────


class TestAddEan:
    def test_adds_secondary_ean(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "AddEanTest", "ean": "12345678"})["id"]
        result = product_service.add_ean(pid, "87654321")
        assert result["ean"] == "87654321"
        assert result["is_primary"] is False
        assert "id" in result

    def test_new_ean_is_not_primary(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "NewEanPrimary", "ean": "11111111"})["id"]
        result = product_service.add_ean(pid, "22222222")
        assert result["is_primary"] is False

    def test_invalid_ean_raises_value_error(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "InvalidEan", "ean": "12345678"})["id"]
        with pytest.raises(ValueError):
            product_service.add_ean(pid, "abc")

    def test_invalid_ean_too_short(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "ShortEan", "ean": "12345678"})["id"]
        with pytest.raises(ValueError):
            product_service.add_ean(pid, "1234567")  # 7 digits — too short

    def test_invalid_ean_too_long(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "LongEan", "ean": "12345678"})["id"]
        with pytest.raises(ValueError):
            product_service.add_ean(pid, "12345678901234")  # 14 digits — too long

    def test_duplicate_ean_on_same_product_raises_409(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "DupEan", "ean": "12345678"})["id"]
        with pytest.raises(ValueError, match="ean_already_exists"):
            product_service.add_ean(pid, "12345678")

    def test_raises_for_unknown_product(self, app_ctx):
        from services import product_service

        with pytest.raises(LookupError):
            product_service.add_ean(99999, "12345678")

    def test_first_ean_added_to_product_without_ean_is_primary(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "FirstEanPrimary"})["id"]
        result = product_service.add_ean(pid, "12345678")
        assert result["is_primary"] is True

    def test_valid_ean_boundaries(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "EanBounds", "ean": "12345678"})["id"]
        # 8-digit EAN (minimum)
        r8 = product_service.add_ean(pid, "87654321")
        assert r8["ean"] == "87654321"
        # 13-digit EAN (maximum)
        r13 = product_service.add_ean(pid, "1234567890123")
        assert r13["ean"] == "1234567890123"


# ── Service: delete_ean ────────────────────────────────────────────────────────


class TestDeleteEan:
    def test_deletes_non_primary_ean(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "DelNonPrimary", "ean": "12345678"})["id"]
        sec = product_service.add_ean(pid, "87654321")
        product_service.delete_ean(pid, sec["id"])
        eans = product_service.list_eans(pid)
        assert len(eans) == 1
        assert eans[0]["ean"] == "12345678"

    def test_primary_ean_unchanged_after_deleting_secondary(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "UnchangedEan", "ean": "12345678"})["id"]
        sec = product_service.add_ean(pid, "87654321")
        product_service.delete_ean(pid, sec["id"])
        row = db.execute(
            "SELECT ean FROM product_eans WHERE product_id = ? AND is_primary = 1", (pid,)
        ).fetchone()
        assert row["ean"] == "12345678"

    def test_deleting_primary_promotes_lowest_id(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "PromoteEan", "ean": "11111111"})["id"]
        sec1 = product_service.add_ean(pid, "22222222")
        sec2 = product_service.add_ean(pid, "33333333")

        primary_row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND is_primary = 1", (pid,)
        ).fetchone()
        product_service.delete_ean(pid, primary_row["id"])

        eans = product_service.list_eans(pid)
        new_primary = next(e for e in eans if e["is_primary"])
        # lowest-id remaining should be promoted
        lowest_remaining_id = min(e["id"] for e in eans)
        assert new_primary["id"] == lowest_remaining_id

    def test_deleting_primary_promotes_new_primary_in_product_eans(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "SyncEan", "ean": "11111111"})["id"]
        product_service.add_ean(pid, "22222222")

        primary_row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND is_primary = 1", (pid,)
        ).fetchone()
        product_service.delete_ean(pid, primary_row["id"])

        row = db.execute(
            "SELECT ean FROM product_eans WHERE product_id = ? AND is_primary = 1", (pid,)
        ).fetchone()
        assert row["ean"] == "22222222"

    def test_cannot_delete_only_ean(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "OnlyEan", "ean": "12345678"})["id"]
        ean_id = product_service.list_eans(pid)[0]["id"]
        with pytest.raises(ValueError, match="cannot_delete_only_ean"):
            product_service.delete_ean(pid, ean_id)

    def test_raises_404_for_unknown_ean_id(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "UnknownEanId", "ean": "12345678"})["id"]
        with pytest.raises(LookupError):
            product_service.delete_ean(pid, 99999)

    def test_cannot_delete_synced_ean(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "DelSynced", "ean": "11111111", "from_off": True}
        )["id"]
        product_service.add_ean(pid, "22222222")  # secondary so count check wouldn't also trip
        synced_row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        with pytest.raises(ValueError, match="cannot_delete_synced_ean"):
            product_service.delete_ean(pid, synced_row["id"])


# ── Service: unsync_ean ────────────────────────────────────────────────────────


class TestUnsyncEanService:
    def test_unsync_clears_synced_with_off_on_row(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "UnsyncRow", "ean": "11111111", "from_off": True}
        )["id"]
        row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        product_service.unsync_ean(pid, row["id"])
        after = db.execute(
            "SELECT synced_with_off FROM product_eans WHERE id = ?", (row["id"],)
        ).fetchone()
        assert after["synced_with_off"] == 0

    def test_unsync_last_synced_ean_clears_product_flag(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "UnsyncLast", "ean": "11111111", "from_off": True}
        )["id"]
        row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        product_service.unsync_ean(pid, row["id"])
        flag = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag is None

    def test_unsync_preserves_flag_when_other_synced_ean_remains(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "UnsyncKeep", "ean": "11111111", "from_off": True}
        )["id"]
        ean_b = product_service.add_ean(pid, "22222222")
        # Mark the secondary EAN as also synced with OFF
        db.execute(
            "UPDATE product_eans SET synced_with_off = 1 WHERE id = ?", (ean_b["id"],)
        )
        db.commit()
        row_a = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        product_service.unsync_ean(pid, row_a["id"])
        flag = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag is not None

    def test_unsync_raises_for_unknown_ean(self, app_ctx):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "UnsyncUnknown", "ean": "11111111"}
        )["id"]
        with pytest.raises(LookupError):
            product_service.unsync_ean(pid, 99999)


# ── Service: set_primary_ean ───────────────────────────────────────────────────


class TestSetPrimaryEan:
    def test_sets_target_as_primary(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "SetPrimary", "ean": "11111111"})["id"]
        sec = product_service.add_ean(pid, "22222222")
        product_service.set_primary_ean(pid, sec["id"])

        eans = product_service.list_eans(pid)
        primary = next(e for e in eans if e["is_primary"])
        assert primary["id"] == sec["id"]
        assert primary["ean"] == "22222222"

    def test_clears_previous_primary(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "ClearPrimary", "ean": "11111111"})["id"]
        old_primary_id = product_service.list_eans(pid)[0]["id"]
        sec = product_service.add_ean(pid, "22222222")
        product_service.set_primary_ean(pid, sec["id"])

        eans = product_service.list_eans(pid)
        old = next(e for e in eans if e["id"] == old_primary_id)
        assert old["is_primary"] is False

    def test_set_primary_updates_product_eans(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "SyncPrimary", "ean": "11111111"})["id"]
        sec = product_service.add_ean(pid, "22222222")
        product_service.set_primary_ean(pid, sec["id"])

        row = db.execute(
            "SELECT ean FROM product_eans WHERE product_id = ? AND is_primary = 1", (pid,)
        ).fetchone()
        assert row["ean"] == "22222222"

    def test_raises_for_unknown_ean_id(self, app_ctx):
        from services import product_service

        pid = product_service.add_product({"type": "Snacks", "name": "UnknownSetPrimary", "ean": "11111111"})["id"]
        with pytest.raises(LookupError):
            product_service.set_primary_ean(pid, 99999)


# ── Duplicate detection ────────────────────────────────────────────────────────


class TestDuplicateDetection:
    def test_primary_ean_triggers_duplicate(self, client):
        """Existing primary EAN match still triggers duplicate detection."""
        pid = _add_product(client, name="PrimaryDup", ean="11111111")
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "AnotherPrimary", "ean": "11111111"},
        )
        assert resp.status_code == 409
        assert "duplicate" in resp.get_json()

    def test_secondary_ean_triggers_duplicate(self, client):
        """EAN that matches a secondary EAN on another product triggers duplicate detection."""
        pid = _add_product(client, name="SecDupBase", ean="11111111")
        # Add a secondary EAN to that product
        client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})

        # Now try to create a new product with the secondary EAN
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "SecDupNew", "ean": "22222222"},
        )
        assert resp.status_code == 409
        assert "duplicate" in resp.get_json()


# ── Search ─────────────────────────────────────────────────────────────────────


class TestSearchByEan:
    def test_search_by_primary_ean_returns_product(self, client):
        _add_product(client, name="PrimarySearch", ean="55555555")
        resp = client.get("/api/products?search=55555555")
        assert resp.status_code == 200
        results = resp.get_json()["products"]
        names = [p["name"] for p in results]
        assert "PrimarySearch" in names

    def test_search_by_secondary_ean_returns_product(self, client):
        pid = _add_product(client, name="SecondarySearch", ean="66666666")
        client.post(f"/api/products/{pid}/eans", json={"ean": "77777777"})

        resp = client.get("/api/products?search=77777777")
        assert resp.status_code == 200
        results = resp.get_json()["products"]
        names = [p["name"] for p in results]
        assert "SecondarySearch" in names

    def test_search_by_primary_ean_with_multiple_secondaries(self, client):
        """Primary EAN is still findable when product has many secondary EANs."""
        pid = _add_product(client, name="ManyEans", ean="88880001")
        for ean in ["88880002", "88880003", "88880004", "88880005"]:
            client.post(f"/api/products/{pid}/eans", json={"ean": ean})
        resp = client.get("/api/products?search=88880001")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.get_json()["products"]]
        assert "ManyEans" in names

    def test_search_returns_product_for_any_secondary_ean(self, client):
        """Product is found when searching by any of its secondary EANs."""
        pid = _add_product(client, name="AnySecondary", ean="99990001")
        for ean in ["99990002", "99990003"]:
            client.post(f"/api/products/{pid}/eans", json={"ean": ean})
        for ean in ["99990002", "99990003"]:
            resp = client.get(f"/api/products?search={ean}")
            assert resp.status_code == 200
            names = [p["name"] for p in resp.get_json()["products"]]
            assert "AnySecondary" in names, f"Not found via secondary EAN {ean}"

    def test_search_no_match_returns_empty_list(self, client):
        """Search for non-existent EAN returns empty product list, not an error."""
        resp = client.get("/api/products?search=zzzNoMatchAtAll999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["products"] == []
        assert data["total"] == 0

    def test_search_by_brand_returns_product(self, client):
        """Search matches product brand name, not just EAN or product name."""
        client.post("/api/products", json={
            "type": "Snacks", "name": "BrandTest", "brand": "SuperBrand",
        })
        resp = client.get("/api/products?search=SuperBrand")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.get_json()["products"]]
        assert "BrandTest" in names


# ── Product create ─────────────────────────────────────────────────────────────


class TestProductCreateEanSync:
    def test_create_with_ean_inserts_primary_ean_row(self, client, db):
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "CreateWithEan", "ean": "12345678"},
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]

        rows = db.execute(
            "SELECT * FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["ean"] == "12345678"
        assert rows[0]["is_primary"] == 1

    def test_create_without_ean_no_ean_row(self, client, db):
        resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "CreateNoEan"},
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]

        count = db.execute(
            "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert count == 0


# ── Product update ─────────────────────────────────────────────────────────────


class TestProductUpdateEanSync:
    def test_update_ean_updates_primary_ean_row(self, client, db):
        pid = _add_product(client, name="UpdateEan", ean="11111111")
        resp = client.put(f"/api/products/{pid}", json={"ean": "99999999"})
        assert resp.status_code == 200

        rows = db.execute(
            "SELECT ean, is_primary FROM product_eans WHERE product_id = ? AND is_primary = 1",
            (pid,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["ean"] == "99999999"

    def test_clear_ean_removes_primary_designation(self, client, db):
        pid = _add_product(client, name="ClearEan", ean="11111111")
        resp = client.put(f"/api/products/{pid}", json={"ean": ""})
        assert resp.status_code == 200

        # Primary should be cleared
        primary_row = db.execute(
            "SELECT * FROM product_eans WHERE product_id = ? AND is_primary = 1",
            (pid,),
        ).fetchone()
        assert primary_row is None


# ── Blueprint: GET /api/products/<pid>/eans ────────────────────────────────────


class TestListEansBlueprint:
    def test_returns_200_with_ean_list(self, client):
        pid = _add_product(client, name="BPListEan", ean="12345678")
        resp = client.get(f"/api/products/{pid}/eans")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["ean"] == "12345678"
        assert data[0]["is_primary"] is True
        assert "id" in data[0]

    def test_returns_404_for_unknown_product(self, client):
        resp = client.get("/api/products/99999/eans")
        assert resp.status_code == 404

    def test_returns_all_eans_ordered_primary_first(self, client):
        pid = _add_product(client, name="MultiEan", ean="11111111")
        client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        client.post(f"/api/products/{pid}/eans", json={"ean": "33333333"})

        resp = client.get(f"/api/products/{pid}/eans")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        assert data[0]["is_primary"] is True  # primary first


# ── Blueprint: POST /api/products/<pid>/eans ──────────────────────────────────


class TestAddEanBlueprint:
    def test_adds_secondary_ean_returns_201(self, client):
        pid = _add_product(client, name="BPAddEan", ean="12345678")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "87654321"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ean"] == "87654321"
        assert data["is_primary"] is False

    def test_invalid_ean_format_returns_400(self, client):
        pid = _add_product(client, name="BPInvalidEan", ean="12345678")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "abc"})
        assert resp.status_code == 400

    def test_duplicate_ean_on_same_product_returns_409(self, client):
        pid = _add_product(client, name="BPDupEan", ean="12345678")
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "12345678"})
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "ean_already_exists"

    def test_unknown_product_returns_404(self, client):
        resp = client.post("/api/products/99999/eans", json={"ean": "12345678"})
        assert resp.status_code == 404

    def test_adds_ean_returns_201_when_product_has_is_synced_with_off(self, client, db):
        """POST /api/products/<pid>/eans returns 201 even when the product is synced with OFF."""
        pid = _add_product(client, name="SyncedProduct", ean="11111111")
        # Set is_synced_with_off system flag on the product
        db.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, 'is_synced_with_off')",
            (pid,),
        )
        db.commit()
        # Verify the flag is set
        row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert row is not None, "is_synced_with_off flag should be set"
        # Adding a secondary EAN should still succeed with 201
        resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ean"] == "22222222"
        assert data["is_primary"] is False


# ── Blueprint: DELETE /api/products/<pid>/eans/<ean_id> ───────────────────────


class TestDeleteEanBlueprint:
    def test_deletes_non_primary_ean_returns_200(self, client):
        pid = _add_product(client, name="BPDelEan", ean="11111111")
        add_resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        ean_id = add_resp.get_json()["id"]
        resp = client.delete(f"/api/products/{pid}/eans/{ean_id}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_primary_ean_unchanged_after_deleting_secondary(self, client):
        pid = _add_product(client, name="BPUnchanged", ean="11111111")
        add_resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        ean_id = add_resp.get_json()["id"]
        client.delete(f"/api/products/{pid}/eans/{ean_id}")

        eans = client.get(f"/api/products/{pid}/eans").get_json()
        assert eans[0]["ean"] == "11111111"

    def test_last_ean_cannot_be_deleted(self, client):
        pid = _add_product(client, name="BPLastEan", ean="11111111")
        ean_id = client.get(f"/api/products/{pid}/eans").get_json()[0]["id"]
        resp = client.delete(f"/api/products/{pid}/eans/{ean_id}")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "cannot_delete_only_ean"
        eans_after = client.get(f"/api/products/{pid}/eans").get_json()
        assert len(eans_after) == 1
        assert eans_after[0]["id"] == ean_id
        assert eans_after[0]["ean"] == "11111111"

    def test_unknown_ean_id_returns_404(self, client):
        pid = _add_product(client, name="BPUnknownEan", ean="11111111")
        resp = client.delete(f"/api/products/{pid}/eans/99999")
        assert resp.status_code == 404

    def test_synced_ean_returns_400_cannot_delete_synced_ean(self, client, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "BPDelSynced", "ean": "11111111", "from_off": True}
        )["id"]
        client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        synced_row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        resp = client.delete(f"/api/products/{pid}/eans/{synced_row['id']}")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "cannot_delete_synced_ean"

    def test_deleting_primary_promotes_next_and_syncs_products_ean(self, client):
        pid = _add_product(client, name="BPPromotion", ean="11111111")
        client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})

        eans = client.get(f"/api/products/{pid}/eans").get_json()
        primary_id = next(e["id"] for e in eans if e["is_primary"])

        resp = client.delete(f"/api/products/{pid}/eans/{primary_id}")
        assert resp.status_code == 200

        updated_eans = client.get(f"/api/products/{pid}/eans").get_json()
        assert len(updated_eans) == 1
        assert updated_eans[0]["is_primary"] is True
        assert updated_eans[0]["ean"] == "22222222"


# ── Blueprint: PATCH /api/products/<pid>/eans/<ean_id>/set-primary ─────────────


class TestSetPrimaryEanBlueprint:
    def test_sets_primary_returns_200(self, client):
        pid = _add_product(client, name="BPSetPrimary", ean="11111111")
        add_resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        ean_id = add_resp.get_json()["id"]

        resp = client.patch(f"/api/products/{pid}/eans/{ean_id}/set-primary")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_target_becomes_primary(self, client):
        pid = _add_product(client, name="BPNewPrimary", ean="11111111")
        add_resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        ean_id = add_resp.get_json()["id"]
        client.patch(f"/api/products/{pid}/eans/{ean_id}/set-primary")

        eans = client.get(f"/api/products/{pid}/eans").get_json()
        primary = next(e for e in eans if e["is_primary"])
        assert primary["ean"] == "22222222"

    def test_old_primary_cleared(self, client):
        pid = _add_product(client, name="BPOldPrimary", ean="11111111")
        old_ean_id = client.get(f"/api/products/{pid}/eans").get_json()[0]["id"]
        add_resp = client.post(f"/api/products/{pid}/eans", json={"ean": "22222222"})
        new_ean_id = add_resp.get_json()["id"]
        client.patch(f"/api/products/{pid}/eans/{new_ean_id}/set-primary")

        eans = client.get(f"/api/products/{pid}/eans").get_json()
        old_ean = next(e for e in eans if e["id"] == old_ean_id)
        assert old_ean["is_primary"] is False

    def test_unknown_ean_id_returns_404(self, client):
        pid = _add_product(client, name="BPUnknownSetPrimary", ean="11111111")
        resp = client.patch(f"/api/products/{pid}/eans/99999/set-primary")
        assert resp.status_code == 404


# ── Blueprint: POST /api/products/<pid>/eans/<ean_id>/unsync ──────────────────


class TestUnsyncEanBlueprint:
    def test_unsync_returns_200(self, client, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "BPUnsync", "ean": "11111111", "from_off": True}
        )["id"]
        row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        resp = client.post(f"/api/products/{pid}/eans/{row['id']}/unsync")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_unsync_clears_row_flag(self, client, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "BPUnsyncRow", "ean": "11111111", "from_off": True}
        )["id"]
        row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        client.post(f"/api/products/{pid}/eans/{row['id']}/unsync")
        after = db.execute(
            "SELECT synced_with_off FROM product_eans WHERE id = ?", (row["id"],)
        ).fetchone()
        assert after["synced_with_off"] == 0

    def test_unsync_clears_product_flag_when_last(self, client, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "BPUnsyncProdFlag", "ean": "11111111", "from_off": True}
        )["id"]
        row = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        client.post(f"/api/products/{pid}/eans/{row['id']}/unsync")
        flag = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag is None

    def test_unsync_unknown_ean_returns_404(self, client):
        pid = _add_product(client, name="BPUnsyncUnknown", ean="11111111")
        resp = client.post(f"/api/products/{pid}/eans/99999/unsync")
        assert resp.status_code == 404


# ── EAN-scoped OFF sync flag ────────────────────────────────────────────────────


class TestEanSyncedWithOff:
    def test_add_product_from_off_marks_ean_as_synced(self, app_ctx, db):
        from services import product_service

        result = product_service.add_product(
            {"type": "Snacks", "name": "FromOffAdd", "ean": "11111111", "from_off": True}
        )
        pid = result["id"]
        row = db.execute(
            "SELECT synced_with_off FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "11111111"),
        ).fetchone()
        assert row is not None
        assert row["synced_with_off"] == 1

    def test_update_product_from_off_marks_ean_as_synced(self, app_ctx, db):
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "FromOffUpdate", "ean": "22222222"}
        )["id"]
        product_service.update_product(pid, {"ean": "22222222", "from_off": True})
        row = db.execute(
            "SELECT synced_with_off FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "22222222"),
        ).fetchone()
        assert row is not None
        assert row["synced_with_off"] == 1

    def test_from_off_ean_targets_secondary_without_swapping_primary(self, app_ctx, db):
        """Fetching OFF for a secondary EAN must mark THAT row as synced and
        leave the primary designation untouched. The UI sends the primary EAN
        in `ean` and the fetched EAN in `from_off_ean`."""
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "FromOffSecondary", "ean": "10000000"}
        )["id"]
        product_service.add_ean(pid, "20000000")

        product_service.update_product(
            pid,
            {"ean": "10000000", "from_off": True, "from_off_ean": "20000000"},
        )

        # Only the targeted (secondary) EAN is marked synced
        rows = {
            r["ean"]: (bool(r["is_primary"]), bool(r["synced_with_off"]))
            for r in db.execute(
                "SELECT ean, is_primary, synced_with_off FROM product_eans "
                "WHERE product_id = ?",
                (pid,),
            ).fetchall()
        }
        assert rows["10000000"] == (True, False), "primary must stay primary and unsynced"
        assert rows["20000000"] == (False, True), "secondary must be marked synced"

        # Product-level system flag is also set
        flag_row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag_row is not None

    def test_from_off_ean_falls_back_to_data_ean_when_absent(self, app_ctx, db):
        """When from_off_ean is not provided, from_off still marks data.ean."""
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "FromOffFallback", "ean": "30000000"}
        )["id"]
        product_service.update_product(
            pid, {"ean": "30000000", "from_off": True}
        )
        row = db.execute(
            "SELECT synced_with_off FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "30000000"),
        ).fetchone()
        assert row["synced_with_off"] == 1

    def test_delete_ean_rejects_synced_ean_and_preserves_flag(self, app_ctx, db):
        """Deleting a synced EAN is rejected; the product-level flag stays."""
        from services import product_service

        # Create product with EAN A synced from OFF, plus a non-synced EAN B
        pid = product_service.add_product(
            {"type": "Snacks", "name": "ClearFlag", "ean": "33333333", "from_off": True}
        )["id"]
        product_service.add_ean(pid, "44444444")

        ean_a = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "33333333"),
        ).fetchone()

        # Delete of synced EAN A is rejected
        with pytest.raises(ValueError, match="cannot_delete_synced_ean"):
            product_service.delete_ean(pid, ean_a["id"])

        # Product flag remains intact since nothing was deleted
        flag_row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag_row is not None

    def test_delete_ean_rejects_synced_ean_when_another_synced_ean_exists(self, app_ctx, db):
        """Rejection also applies when the product has multiple synced EANs."""
        from services import product_service

        pid = product_service.add_product(
            {"type": "Snacks", "name": "KeepFlag", "ean": "55555555", "from_off": True}
        )["id"]
        ean_b = product_service.add_ean(pid, "66666666")
        db.execute(
            "UPDATE product_eans SET synced_with_off = 1 WHERE id = ?", (ean_b["id"],)
        )
        db.commit()

        ean_a = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "55555555"),
        ).fetchone()

        with pytest.raises(ValueError, match="cannot_delete_synced_ean"):
            product_service.delete_ean(pid, ean_a["id"])

        flag_row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag_row is not None

    def test_delete_ean_does_not_clear_off_flag_when_deleted_ean_was_not_synced(self, app_ctx, db):
        from services import product_service

        # Create product with EAN A synced, EAN B not synced
        pid = product_service.add_product(
            {"type": "Snacks", "name": "DeleteNotSynced", "ean": "77777777", "from_off": True}
        )["id"]
        ean_b = product_service.add_ean(pid, "88888888")
        # EAN B is NOT synced (synced_with_off = 0 by default)

        # Delete the non-synced EAN B
        product_service.delete_ean(pid, ean_b["id"])

        # Flag should remain since EAN A is still synced
        flag_row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag_row is not None

    def test_delete_ean_no_flag_set_when_no_off_eans(self, app_ctx, db):
        from services import product_service

        # Create product with 2 EANs, neither synced
        pid = product_service.add_product(
            {"type": "Snacks", "name": "NoFlagNoSync", "ean": "12312312"}
        )["id"]
        ean_b = product_service.add_ean(pid, "32132132")

        # Delete one EAN — flag should still be absent
        ean_a = db.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
            (pid, "12312312"),
        ).fetchone()
        product_service.delete_ean(pid, ean_a["id"])

        flag_row = db.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
        assert flag_row is None
