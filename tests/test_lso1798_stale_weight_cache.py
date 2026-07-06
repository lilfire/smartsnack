"""LSO-1798: scoring cache must detect writes made by other workers.

The board reported that a custom category score weight (energydrinks) was
ignored — the product list kept showing scores computed from GLOBAL weights.
Live reproduction showed the override was persisted correctly, but the
scoring weight cache never reloaded on gunicorn workers that did not handle
the save: PRAGMA data_version is per-connection and always reports the same
baseline on a freshly opened connection, and db.get_db() opens a fresh
connection per request. These tests pin the fixed behavior: a long-lived
probe connection that observes commits from any other connection or process.
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest


def _external_write_override(db_path, category="Snacks", field="taste_score", weight=100.0):
    """Write a category override from a separate connection WITHOUT calling
    invalidate_scoring_cache() — exactly what a save handled by another
    gunicorn worker looks like to this process."""
    other = sqlite3.connect(db_path)
    try:
        other.execute(
            "INSERT INTO category_score_weights "
            "(category, field, enabled, weight, direction, formula, formula_min, formula_max) "
            "VALUES (?, ?, 1, ?, 'higher', 'direct', 0, 6) "
            "ON CONFLICT(category, field) DO UPDATE SET weight=excluded.weight",
            (category, field, weight),
        )
        other.commit()
    finally:
        other.close()


class TestFreshConnectionCacheInvalidation:
    def test_new_request_connection_sees_external_write(self, app_ctx, seed_category):
        """The production failure mode: load config on one request-scoped
        connection, close it, external write, then a NEW request-scoped
        connection (= the next HTTP request) must see the write."""
        from config import DB_PATH
        from services.product_scoring import _load_weight_config
        from db import get_db, close_db

        first = _load_weight_config(get_db().cursor())
        assert (seed_category, "taste_score") not in first[3]

        # End of "request 1": the request-scoped connection is closed.
        close_db()

        _external_write_override(DB_PATH)

        # "Request 2" opens a brand-new connection whose data_version is at
        # baseline — before the fix the cache wrongly validated against it.
        second = _load_weight_config(get_db().cursor())
        assert second is not first, (
            "weight cache served stale data to a fresh request connection"
        )
        assert (seed_category, "taste_score") in second[3]
        assert second[3][(seed_category, "taste_score")]["weight"] == 100.0

    def test_write_from_another_os_process_detected(self, app_ctx, seed_category):
        """Cross-process variant: the write comes from a real separate OS
        process, as with a second gunicorn worker."""
        from config import DB_PATH
        from services.product_scoring import _load_weight_config
        from db import get_db, close_db

        first = _load_weight_config(get_db().cursor())
        assert (seed_category, "fiber") not in first[3]
        close_db()

        code = (
            "import sqlite3,sys;"
            "c=sqlite3.connect(sys.argv[1]);"
            "c.execute(\"INSERT INTO category_score_weights "
            "(category, field, enabled, weight, direction, formula, formula_min, formula_max) "
            "VALUES (?, 'fiber', 1, 42.0, 'higher', 'minmax', 0, 0)\", (sys.argv[2],));"
            "c.commit();c.close()"
        )
        subprocess.run(
            [sys.executable, "-c", code, DB_PATH, seed_category],
            check=True,
            timeout=30,
        )

        second = _load_weight_config(get_db().cursor())
        assert (seed_category, "fiber") in second[3]
        assert second[3][(seed_category, "fiber")]["weight"] == 42.0

    def test_range_cache_also_reloads(self, app_ctx, seed_product):
        """The min/max range cache uses the same version key and must also
        pick up product writes from other connections."""
        from config import DB_PATH
        from services.product_scoring import (
            _load_weight_config,
            _compute_category_ranges,
        )
        from db import get_db, close_db

        cur = get_db().cursor()
        _, _, enabled_fields, _ = _load_weight_config(cur)
        first = _compute_category_ranges(cur, enabled_fields)
        close_db()

        other = sqlite3.connect(DB_PATH)
        try:
            other.execute(
                "INSERT INTO products (type, name, taste_score, kcal, protein) "
                "VALUES ('Snacks', 'LSO-1798 range probe', 6, 9999, 1)"
            )
            other.commit()
        finally:
            other.close()

        second = _compute_category_ranges(get_db().cursor(), enabled_fields)
        assert second is not first, (
            "range cache served stale data after an external product write"
        )


class TestVersionProbeLifecycle:
    def test_probe_reopens_when_db_path_changes(self, app_ctx, monkeypatch, tmp_path):
        """Tests patch DB_PATH per test; the probe must follow, not keep
        reporting versions for the previous file."""
        import config
        import services.product_scoring as ps

        v1 = ps._db_data_version()

        new_db = str(tmp_path / "other.sqlite")
        sqlite3.connect(new_db).close()
        monkeypatch.setattr(config, "DB_PATH", new_db)

        v2 = ps._db_data_version()
        assert v2 != v1, "version key must change when DB_PATH changes"
        assert v2[0] > v1[0], "generation must bump on probe reopen"

    def test_probe_reopens_when_file_is_replaced(self, app_ctx, tmp_path):
        """Backup restore replaces the DB file on disk (new inode). The probe
        must reopen instead of watching the deleted inode forever."""
        from config import DB_PATH
        import services.product_scoring as ps

        v1 = ps._db_data_version()

        replacement = str(tmp_path / "replacement.sqlite")
        conn = sqlite3.connect(replacement)
        conn.execute("CREATE TABLE marker (x)")
        conn.commit()
        conn.close()
        os.replace(replacement, DB_PATH)

        v2 = ps._db_data_version()
        assert v2 != v1
        assert v2[0] > v1[0], "generation must bump when the file inode changes"

    def test_close_version_probe_is_idempotent(self):
        import services.product_scoring as ps

        ps._close_version_probe()
        ps._close_version_probe()
        assert ps._probe_conn is None


class TestUserScenarioEndToEnd:
    """The exact LSO-1794 board scenario, through the real HTTP API.

    Global weights taste_score=66 / est_pdcaas=75 / pct_protein_cal=100,
    an energy drink with taste 4.5, protein 0, pdcaas missing. Global-only
    scoring yields total 24.8 (Smak 49.5); the category override
    (taste_score weight 100, exclusive) must yield total 75.0.
    """

    GLOBALS = {"taste_score": 66.0, "est_pdcaas": 75.0, "pct_protein_cal": 100.0}

    @pytest.fixture()
    def seeded(self, client):
        r = client.post(
            "/api/categories", json={"name": "energydrinks", "label": "Energy Drinks"}
        )
        assert r.status_code in (200, 201)
        weights = client.get("/api/weights").get_json()
        payload = [
            {
                "field": w["field"],
                "enabled": w["field"] in self.GLOBALS,
                "weight": self.GLOBALS.get(w["field"], 0),
                "direction": w["direction"],
                "formula": w["formula"],
                "formula_min": w["formula_min"] or 0,
                "formula_max": w["formula_max"] or 0,
            }
            for w in weights
        ]
        assert client.put("/api/weights", json=payload).status_code == 200
        r = client.post(
            "/api/products",
            json={
                "name": "Ultra fantastisk Ruby red",
                "type": "energydrinks",
                "taste_score": 4.5,
                "kcal": 10,
                "protein": 0,
                "carbs": 2,
                "sugar": 0,
                "fat": 0,
            },
        )
        assert r.status_code in (200, 201)
        return client

    def _energy_drink(self, client, adv=None):
        url = "/api/products"
        if adv:
            url += "?advanced_filters=" + adv
        data = client.get(url).get_json()
        return next(p for p in data["products"] if p["type"] == "energydrinks")

    def test_global_baseline_matches_bug_report(self, seeded):
        p = self._energy_drink(seeded)
        assert p["total_score"] == 24.8
        assert p["scores"]["taste_score"] == 49.5
        assert p["scores"]["pct_protein_cal"] == 0.0
        assert "est_pdcaas" in p["missing_fields"]

    def test_override_applied_after_save_by_another_worker(self, seeded, app):
        """Warm the cache via a real request, then write the override from a
        separate connection (= another worker handled the PUT). The very next
        request must serve override-based scores — with and without the
        advanced filter."""
        from config import DB_PATH

        baseline = self._energy_drink(seeded)
        assert baseline["total_score"] == 24.8  # cache is warm with globals

        _external_write_override(
            DB_PATH, category="energydrinks", field="taste_score", weight=100.0
        )

        plain = self._energy_drink(seeded)
        assert plain["total_score"] == 75.0, (
            "stale global weights served after another worker saved an override"
        )
        assert plain["scores"] == {"taste_score": 75.0}
        assert plain["missing_fields"] == []

        adv = json.dumps(
            {
                "logic": "or",
                "children": [
                    {"field": "type", "op": "=", "value": "energydrinks"},
                    {"field": "type", "op": "=", "value": "jerky"},
                ],
            }
        )
        filtered = self._energy_drink(seeded, adv=adv)
        assert filtered["total_score"] == 75.0
        assert filtered["scores"] == {"taste_score": 75.0}

        post_filter = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "total_score", "op": ">=", "value": "0"}],
            }
        )
        post = self._energy_drink(seeded, adv=post_filter)
        assert post["total_score"] == 75.0

    def test_advanced_filter_never_diverges_from_plain_list(self, seeded):
        """H3 pin: same DB state, plain list vs advanced filter must return
        identical per-field scores and total_score."""
        adv = json.dumps(
            {
                "logic": "and",
                "children": [{"field": "type", "op": "=", "value": "energydrinks"}],
            }
        )
        plain = self._energy_drink(seeded)
        filtered = self._energy_drink(seeded, adv=adv)
        assert plain["total_score"] == filtered["total_score"]
        assert plain["scores"] == filtered["scores"]
        assert plain["missing_fields"] == filtered["missing_fields"]
