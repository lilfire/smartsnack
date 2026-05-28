"""End-to-end error-path tests for ``GET /health``.

Closes the LSO-1352 Phase 2A gap for ``blueprints/core.py``: the route's
DB-failure branch was previously untested. This file exercises the
``sqlite3.OperationalError`` branch by monkeypatching the ``get_db``
reference inside the ``blueprints.core`` module so that the handler's
``try/except`` actually fires.

Conventions:
- Live Flask server fixture (`live_url`) from ``tests/e2e/conftest.py``.
- No real DB failure is induced; the symbol is swapped on the module the
  route looks up, then restored at teardown.
- Rule 18: assertions are specific to the error response shape — status
  code 500, ``{"status":"error"}`` body, and that the error was logged.
"""

import json
import logging
import sqlite3
import urllib.error
import urllib.request

import pytest


def _get(url, timeout=5):
    req = urllib.request.Request(url, headers={"X-Requested-With": "SmartSnack"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return exc.code, parsed, dict(exc.headers)


# ---------------------------------------------------------------------------
# /health happy path — keeps regression coverage on the 200 branch so the
# error-path patching doesn't accidentally hide a working-state regression.
# ---------------------------------------------------------------------------


def test_health_ok_returns_status_ok(live_url):
    """``GET /health`` returns 200 with ``status=ok`` and a numeric ``products``
    counter when the DB is reachable.

    Regression guard so the negative-path patching below cannot mask a real
    failure in the happy path.
    """
    status, body, _ = _get(f"{live_url}/health")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body.get("status") == "ok"
    assert "version" in body
    assert isinstance(body.get("products"), int)
    assert body["products"] >= 0


# ---------------------------------------------------------------------------
# /health 500 path — DB failure
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_health_db(monkeypatch):
    """Swap the ``get_db`` reference inside ``blueprints.core`` so the route's
    ``try`` block raises ``sqlite3.OperationalError`` exactly once.

    ``blueprints.core`` does ``from db import get_db`` at import time, which
    means the route handler holds its OWN reference to the function. Patching
    ``db.get_db`` is therefore not enough — we must patch the symbol on the
    blueprint module.
    """
    from blueprints import core as core_bp

    calls: list[int] = []

    def _raise_db():
        calls.append(1)
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(core_bp, "get_db", _raise_db)
    return calls


def test_health_db_failure_returns_500_error_body(live_url, patch_health_db, caplog):
    """When ``get_db()`` raises ``sqlite3.OperationalError``, the route returns
    HTTP 500 with ``{"status": "error"}`` and logs the failure.

    Rule 18: this asserts the full contract — status code, body shape, body
    content, AND that the logger fired. "Did not crash" is not enough.
    """
    with caplog.at_level(logging.ERROR, logger="blueprints.core"):
        status, body, _ = _get(f"{live_url}/health")

    assert status == 500, f"Expected 500 on DB failure, got {status}: {body}"
    assert body == {"status": "error"}, (
        f"Body must be exactly {{'status': 'error'}}, got {body!r}"
    )
    # The patched stub was actually invoked — otherwise the test would pass
    # even if the route somehow bypassed get_db().
    assert patch_health_db, (
        "patched get_db() was never called — the route did not hit the DB branch"
    )

    # The error must be logged via the module logger so operators can
    # diagnose health-check failures from log aggregation.
    # caplog captures records across the process; the live-server thread
    # shares the same logger registry.
    matching = [
        r for r in caplog.records
        if r.name == "blueprints.core" and "Health check failed" in r.getMessage()
    ]
    assert matching, (
        "Expected 'Health check failed' error log from blueprints.core; "
        f"got records: {[(r.name, r.getMessage()) for r in caplog.records]}"
    )


def test_health_os_error_also_returns_500(live_url, monkeypatch):
    """``OSError`` (raised by ``conn.execute`` for e.g. a read-only filesystem)
    is also caught and surfaced as 500 + ``{"status":"error"}``.

    Documents the union ``(sqlite3.Error, OSError)`` in the handler so a
    future refactor can't silently narrow it without breaking this test.
    """
    from blueprints import core as core_bp

    def _raise_os():
        raise OSError("disk read-only")

    monkeypatch.setattr(core_bp, "get_db", _raise_os)
    status, body, _ = _get(f"{live_url}/health")
    assert status == 500, f"Expected 500 for OSError branch, got {status}: {body}"
    assert body == {"status": "error"}
