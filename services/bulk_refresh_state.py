"""DB-backed bulk-refresh job state, shared across worker processes.

The bulk refresh runs in a background thread inside one gunicorn worker,
but status polls and duplicate-start guards can land on any worker. All
job state therefore lives in the single-row ``bulk_refresh_jobs`` table
(id=1) instead of a per-process dict. Cross-process atomicity for the
already-running guard comes from a SQLite ``BEGIN IMMEDIATE`` transaction.
"""

import json
import sqlite3

import config

# Columns of the bulk_refresh_jobs row, excluding id and report.
JOB_FIELDS = (
    "running",
    "current",
    "total",
    "name",
    "ean",
    "status",
    "updated",
    "skipped",
    "errors",
    "done",
)

_IDLE_JOB = {
    "running": False,
    "current": 0,
    "total": 0,
    "name": "",
    "ean": "",
    "status": "",
    "updated": 0,
    "skipped": 0,
    "errors": 0,
    "done": False,
}


def _connect():
    """Open a short-lived autocommit connection to the app database.

    ``config.DB_PATH`` is read at call time (not import time) so tests that
    patch it get the right database.
    """
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def read_job():
    """Return the current job state as a plain dict.

    Includes a parsed ``report`` list only when the job is done and a
    report was stored. Returns an idle default if the row is missing
    (e.g. before migrations have run).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM bulk_refresh_jobs WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        conn.close()
    if row is None:
        return dict(_IDLE_JOB)
    job = {k: row[k] for k in JOB_FIELDS}
    job["running"] = bool(job["running"])
    job["done"] = bool(job["done"])
    if job["done"] and row["report"]:
        try:
            job["report"] = json.loads(row["report"])
        except (ValueError, TypeError):
            pass
    return job


def try_acquire():
    """Atomically test-and-set the running flag. Returns True if acquired.

    Uses BEGIN IMMEDIATE so two workers cannot both observe running=0 and
    start duplicate refresh jobs. On acquisition all counters are reset.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT running FROM bulk_refresh_jobs WHERE id = 1"
        ).fetchone()
        if row is None:
            conn.execute("INSERT INTO bulk_refresh_jobs (id) VALUES (1)")
        elif row["running"]:
            conn.execute("ROLLBACK")
            return False
        conn.execute(
            "UPDATE bulk_refresh_jobs SET running=1, current=0, total=0, "
            "name='', ean='', status='', updated=0, skipped=0, errors=0, "
            "done=0, report='' WHERE id = 1"
        )
        conn.execute("COMMIT")
        return True
    except sqlite3.OperationalError:
        # Write lock held by another worker mid test-and-set: treat as busy.
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        return False
    finally:
        conn.close()


def update_job(**fields):
    """Persist the given job fields. ``report`` values are JSON-encoded."""
    assignments = []
    values = []
    for key, value in fields.items():
        if key == "report":
            value = json.dumps(value)
        elif key not in JOB_FIELDS:
            raise ValueError(f"Unknown job field: {key!r}")
        elif key in ("running", "done"):
            value = 1 if value else 0
        assignments.append(f"{key} = ?")
        values.append(value)
    if not assignments:
        return
    conn = _connect()
    try:
        conn.execute(
            f"UPDATE bulk_refresh_jobs SET {', '.join(assignments)} WHERE id = 1",
            values,
        )
    finally:
        conn.close()
