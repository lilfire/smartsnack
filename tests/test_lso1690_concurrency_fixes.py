"""Tests for LSO-1690: multi-process/SQLite concurrency fixes.

Covers:
  H4  — bulk-refresh job state is DB-backed (bulk_refresh_jobs table),
        visible across connections, with an atomic already-running guard
  M4  — language priority is read in Flask context and passed into
        _run_refresh; the thread never calls get_off_language_priority()
  M5  — per-product except blocks roll back partial writes
  M12 — init_db() holds an exclusive cross-process file lock
  M13 — PRAGMA foreign_keys = ON on all direct sqlite3.connect() calls
"""

import os
import sqlite3
import subprocess
import sys
import threading
from unittest.mock import patch

import config
from services import bulk_refresh_state

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────────────────────
# H4 — DB-backed job state
# ─────────────────────────────────────────────────────────────────────────────


class TestDbBackedJobState:
    def test_state_visible_across_connections(self, app_ctx):
        """Every read/write opens a fresh connection, so an update made by
        one 'worker' is visible to a status poll on another."""
        bulk_refresh_state.update_job(
            running=True, current=5, total=10, name="X", ean="123", status="fetching"
        )
        try:
            job = bulk_refresh_state.read_job()
            assert job["running"] is True
            assert job["current"] == 5
            assert job["total"] == 10
            assert job["name"] == "X"
            assert job["ean"] == "123"
            assert job["status"] == "fetching"
        finally:
            bulk_refresh_state.update_job(
                running=False, current=0, total=0, name="", ean="", status=""
            )

    def test_get_refresh_status_reads_db_state(self, app_ctx):
        from services.bulk_service import get_refresh_status

        bulk_refresh_state.update_job(running=True, current=3, total=7)
        try:
            status = get_refresh_status()
            assert status["running"] is True
            assert status["current"] == 3
            assert status["total"] == 7
        finally:
            bulk_refresh_state.update_job(running=False, current=0, total=0)

    def test_try_acquire_sets_running(self, app_ctx):
        assert bulk_refresh_state.try_acquire() is True
        try:
            assert bulk_refresh_state.read_job()["running"] is True
        finally:
            bulk_refresh_state.update_job(running=False)

    def test_second_acquire_rejected(self, app_ctx):
        assert bulk_refresh_state.try_acquire() is True
        try:
            assert bulk_refresh_state.try_acquire() is False
        finally:
            bulk_refresh_state.update_job(running=False)

    def test_acquire_resets_counters_and_report(self, app_ctx):
        bulk_refresh_state.update_job(
            updated=9, skipped=8, errors=7, done=True, report=[{"x": 1}]
        )
        assert bulk_refresh_state.try_acquire() is True
        try:
            job = bulk_refresh_state.read_job()
            assert job["updated"] == 0
            assert job["skipped"] == 0
            assert job["errors"] == 0
            assert job["done"] is False
            assert "report" not in job
        finally:
            bulk_refresh_state.update_job(running=False)

    def test_report_returned_only_when_done(self, app_ctx):
        from services.bulk_service import get_refresh_status

        bulk_refresh_state.update_job(done=False, report=[{"name": "a"}])
        try:
            assert "report" not in get_refresh_status()
            bulk_refresh_state.update_job(done=True)
            assert get_refresh_status()["report"] == [{"name": "a"}]
        finally:
            bulk_refresh_state.update_job(done=False, running=False, report=[])

    def test_concurrent_acquire_only_one_wins(self, app_ctx):
        """Simultaneous try_acquire() calls: exactly one caller may win."""
        n = 4
        results = []
        barrier = threading.Barrier(n)

        def worker():
            barrier.wait()
            results.append(bulk_refresh_state.try_acquire())

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        try:
            assert results.count(True) == 1
            assert results.count(False) == n - 1
        finally:
            bulk_refresh_state.update_job(running=False)

    def test_stale_running_flag_cleared_on_startup(self, app_ctx):
        """A crash mid-refresh must not leave the guard stuck: init_db()
        clears the persisted running flag (no refresh survives a restart)."""
        import db as db_mod

        bulk_refresh_state.update_job(running=True)
        db_mod.init_db()
        assert bulk_refresh_state.read_job()["running"] is False

    def test_acquire_rejected_from_another_process(self, app_ctx):
        """A second gunicorn worker (separate process) must see running=1."""
        assert bulk_refresh_state.try_acquire() is True
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from services import bulk_refresh_state; "
                    "print(bulk_refresh_state.try_acquire())",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
                env={**os.environ, "DB_PATH": config.DB_PATH},
            )
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == "False"
        finally:
            bulk_refresh_state.update_job(running=False)


class TestJobStateEdgeCases:
    def test_read_job_returns_idle_default_without_table(self, tmp_path, monkeypatch):
        """Before migrations have run, read_job() must not crash."""
        empty_db = str(tmp_path / "empty.sqlite")
        sqlite3.connect(empty_db).close()
        monkeypatch.setattr(config, "DB_PATH", empty_db)

        job = bulk_refresh_state.read_job()
        assert job["running"] is False
        assert job["done"] is False
        assert job["current"] == 0

    def test_try_acquire_inserts_row_when_missing(self, app_ctx):
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("DELETE FROM bulk_refresh_jobs")
        conn.commit()
        conn.close()
        try:
            assert bulk_refresh_state.try_acquire() is True
            assert bulk_refresh_state.read_job()["running"] is True
        finally:
            bulk_refresh_state.update_job(running=False)

    def test_try_acquire_returns_false_when_db_write_locked(
        self, app_ctx, monkeypatch
    ):
        """If another worker holds the write lock through the busy timeout,
        try_acquire must report busy instead of raising."""

        def fast_connect():
            conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 100")
            return conn

        monkeypatch.setattr(bulk_refresh_state, "_connect", fast_connect)
        blocker = sqlite3.connect(config.DB_PATH, isolation_level=None)
        try:
            blocker.execute("BEGIN EXCLUSIVE")
            assert bulk_refresh_state.try_acquire() is False
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()

    def test_update_job_rejects_unknown_field(self, app_ctx):
        import pytest

        with pytest.raises(ValueError):
            bulk_refresh_state.update_job(nonsense_field=1)

    def test_update_job_no_fields_is_noop(self, app_ctx):
        before = bulk_refresh_state.read_job()
        bulk_refresh_state.update_job()
        assert bulk_refresh_state.read_job() == before

    def test_read_job_tolerates_malformed_report(self, app_ctx):
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute(
            "UPDATE bulk_refresh_jobs SET done = 1, report = 'not-json{' WHERE id = 1"
        )
        conn.commit()
        conn.close()
        try:
            job = bulk_refresh_state.read_job()
            assert job["done"] is True
            assert "report" not in job
        finally:
            bulk_refresh_state.update_job(done=False, running=False, report=[])


# ─────────────────────────────────────────────────────────────────────────────
# M4 — language priority passed into the worker thread
# ─────────────────────────────────────────────────────────────────────────────


class TestLanguagePriorityM4:
    def test_run_refresh_never_reads_language_priority(self, app_ctx, db, monkeypatch):
        """_run_refresh must use the priority it was handed and never call
        get_off_language_priority() (which needs Flask app context)."""
        import services.bulk_service as svc

        db.execute("DELETE FROM product_eans")
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", config.DB_PATH)

        with patch(
            "services.bulk_service.get_off_language_priority", autospec=True
        ) as prio_mock, patch("services.bulk_service.time.sleep", autospec=True):
            svc._run_refresh(["se", "en"], {})

        prio_mock.assert_not_called()
        job = bulk_refresh_state.read_job()
        assert job["done"] is True
        bulk_refresh_state.update_job(done=False, running=False)

    def test_run_refresh_uses_passed_priority_for_mapping(
        self, app_ctx, db, monkeypatch
    ):
        """The passed priority decides which OFF language fields are used."""
        import services.bulk_service as svc

        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
            ("Snacks", "", "2222222222222", ""),
        )
        pid = db.execute(
            "SELECT id FROM products WHERE ean = '2222222222222'"
        ).fetchone()[0]
        db.execute(
            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
            (pid, "2222222222222"),
        )
        db.commit()
        monkeypatch.setattr(svc, "DB_PATH", config.DB_PATH)

        off_data = {
            "product": {
                "product_name_se": "Svenskt Namn",
                "product_name_no": "Norsk Navn",
                "nutriments": {},
            },
            "status": 1,
        }
        with patch(
            "services.bulk_service.proxy_service.off_product",
            return_value=off_data,
            autospec=True,
        ), patch(
            "services.bulk_service._fetch_off_image", return_value=None, autospec=True
        ), patch("services.bulk_service.time.sleep", autospec=True):
            svc._run_refresh(["se", "no"], {})

        name = db.execute("SELECT name FROM products WHERE id = ?", (pid,)).fetchone()[0]
        assert name == "Svenskt Namn"
        bulk_refresh_state.update_job(done=False, running=False, updated=0)


# ─────────────────────────────────────────────────────────────────────────────
# M5 — rollback of partial writes in the per-product except blocks
# ─────────────────────────────────────────────────────────────────────────────


class _SpyConn:
    """Wraps a real connection; fails on a chosen SQL prefix and counts
    commits/rollbacks."""

    def __init__(self, real, fail_on_prefix=None):
        self._real = real
        self._fail_on_prefix = fail_on_prefix
        self.rollbacks = 0
        self.commits = 0

    def execute(self, sql, *args):
        if self._fail_on_prefix and sql.strip().startswith(self._fail_on_prefix):
            raise sqlite3.OperationalError("simulated failure")
        return self._real.execute(sql, *args)

    def commit(self):
        self.commits += 1
        self._real.commit()

    def rollback(self):
        self.rollbacks += 1
        self._real.rollback()

    def close(self):
        self._real.close()


class TestRollbackOnErrorM5:
    def _make_products(self, db, eans):
        db.execute("DELETE FROM product_eans")
        db.execute("UPDATE products SET ean = ''")
        pids = []
        for ean in eans:
            db.execute(
                "INSERT INTO products (type, name, ean, image) VALUES (?, ?, ?, ?)",
                ("Snacks", "Original", ean, ""),
            )
            pid = db.execute(
                "SELECT id FROM products WHERE ean = ?", (ean,)
            ).fetchone()[0]
            db.execute(
                "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                (pid, ean),
            )
            pids.append(pid)
        db.commit()
        return pids

    def test_phase1_partial_write_rolled_back(self, app_ctx, db, monkeypatch):
        """A failure between the field UPDATE and commit must roll back the
        pending write so the next product's commit cannot flush it."""
        import services.bulk_service as svc

        pids = self._make_products(db, ["3333333333333", "4444444444444"])

        real = sqlite3.connect(config.DB_PATH)
        real.row_factory = sqlite3.Row
        real.execute("PRAGMA foreign_keys = ON")
        real.execute("PRAGMA busy_timeout = 5000")
        # Fail on the image UPDATE: by then the field UPDATE for the same
        # product has already been executed but not committed.
        spy = _SpyConn(real, fail_on_prefix="UPDATE products SET image")

        off_data = {
            "product": {"product_name_no": "Endret Navn", "nutriments": {}},
            "status": 1,
        }
        with patch(
            "services.bulk_service._open_worker_connection",
            return_value=spy,
            autospec=True,
        ), patch(
            "services.bulk_service.proxy_service.off_product",
            return_value=off_data,
            autospec=True,
        ), patch(
            "services.bulk_service._fetch_off_image",
            side_effect=["data:image/png;base64,xx", None],
            autospec=True,
        ), patch("services.bulk_service.time.sleep", autospec=True):
            svc._run_refresh(["no", "en"], {})

        assert spy.rollbacks >= 1
        # First product hit the simulated failure: its pending name update
        # must NOT have been committed by the second product's commit.
        name1 = db.execute(
            "SELECT name FROM products WHERE id = ?", (pids[0],)
        ).fetchone()[0]
        name2 = db.execute(
            "SELECT name FROM products WHERE id = ?", (pids[1],)
        ).fetchone()[0]
        assert name1 == "Original"
        assert name2 == "Endret Navn"

        job = bulk_refresh_state.read_job()
        assert job["errors"] == 1
        assert job["updated"] == 1
        bulk_refresh_state.update_job(
            done=False, running=False, updated=0, errors=0, skipped=0
        )

    def test_phase2_error_calls_rollback(self, app_ctx, db, monkeypatch):
        """The phase-2 (search-by-name) except block must also roll back."""
        import services.bulk_service as svc

        db.execute("DELETE FROM product_eans")
        db.execute("UPDATE products SET ean = ''")
        db.execute(
            "INSERT INTO products (type, name) VALUES (?, ?)",
            ("Snacks", "No EAN Product"),
        )
        db.commit()

        real = sqlite3.connect(config.DB_PATH)
        real.row_factory = sqlite3.Row
        real.execute("PRAGMA foreign_keys = ON")
        real.execute("PRAGMA busy_timeout = 5000")
        spy = _SpyConn(real)

        with patch(
            "services.bulk_service._open_worker_connection",
            return_value=spy,
            autospec=True,
        ), patch(
            "services.bulk_service.proxy_service.off_search",
            side_effect=RuntimeError("search exploded"),
            autospec=True,
        ), patch("services.bulk_service.time.sleep", autospec=True):
            svc._run_refresh(
                ["no", "en"],
                {"search_missing": True, "min_certainty": 50, "min_completeness": 50},
            )

        assert spy.rollbacks >= 1
        job = bulk_refresh_state.read_job()
        assert job["errors"] >= 1
        bulk_refresh_state.update_job(
            done=False, running=False, updated=0, errors=0, skipped=0
        )


# ─────────────────────────────────────────────────────────────────────────────
# M12 — cross-process file lock around init_db()
# ─────────────────────────────────────────────────────────────────────────────


class TestInitDbFileLockM12:
    def test_init_db_takes_exclusive_file_lock(self, tmp_path, monkeypatch):
        import fcntl

        import db as db_mod

        db_file = str(tmp_path / "lock_test.sqlite")
        monkeypatch.setattr(db_mod, "DB_PATH", db_file)
        monkeypatch.setattr(config, "DB_PATH", db_file)

        calls = []
        real_flock = fcntl.flock

        def spy_flock(fh, op):
            calls.append(op)
            return real_flock(fh, op)

        monkeypatch.setattr(db_mod.fcntl, "flock", spy_flock)
        db_mod.init_db()

        assert fcntl.LOCK_EX in calls
        assert fcntl.LOCK_UN in calls
        assert os.path.exists(str(tmp_path / ".db_init.lock"))

    def test_concurrent_init_db_processes_do_not_crash(self, tmp_path):
        """Simulate 4 gunicorn workers running init_db() -> migrations on the
        same fresh database simultaneously (first-deploy crash-loop, M12)."""
        db_file = str(tmp_path / "concurrent.sqlite")
        env = {**os.environ, "DB_PATH": db_file}
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", "import db; db.init_db()"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(4)
        ]
        failures = []
        for p in procs:
            _, err = p.communicate(timeout=120)
            if p.returncode != 0:
                failures.append(err.decode())
        assert not failures, f"init_db crashed in {len(failures)} workers: {failures[0]}"

        conn = sqlite3.connect(db_file)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE name = '021_bulk_refresh_jobs'"
            ).fetchone()[0]
            assert count == 1
            row = conn.execute(
                "SELECT COUNT(*) FROM bulk_refresh_jobs WHERE id = 1"
            ).fetchone()[0]
            assert row == 1
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# M13 — PRAGMA foreign_keys = ON on direct connections
# ─────────────────────────────────────────────────────────────────────────────


class TestForeignKeysPragmaM13:
    def test_worker_connection_enforces_foreign_keys(self, app_ctx, monkeypatch):
        import services.bulk_service as svc

        monkeypatch.setattr(svc, "DB_PATH", config.DB_PATH)
        conn = svc._open_worker_connection()
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_state_connection_enforces_foreign_keys(self, app_ctx):
        conn = bulk_refresh_state._connect()
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_init_db_connection_enables_foreign_keys(self, tmp_path, monkeypatch):
        import db as db_mod

        db_file = str(tmp_path / "fk_test.sqlite")
        monkeypatch.setattr(db_mod, "DB_PATH", db_file)
        monkeypatch.setattr(config, "DB_PATH", db_file)

        executed = []
        real_connect = sqlite3.connect

        class _RecordingConn:
            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def execute(self, sql, *args):
                executed.append(sql)
                return self._real.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(object.__getattribute__(self, "_real"), name)

            def __setattr__(self, name, value):
                setattr(object.__getattribute__(self, "_real"), name, value)

        def recording_connect(path, *args, **kwargs):
            return _RecordingConn(real_connect(path, *args, **kwargs))

        monkeypatch.setattr(db_mod.sqlite3, "connect", recording_connect)
        db_mod.init_db()

        assert any("foreign_keys = ON" in sql for sql in executed)
