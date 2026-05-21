"""End-to-end error-path tests for ``blueprints/bulk.py``.

Closes the LSO-1352 Phase 2A gaps for the bulk blueprint:

- ``POST /api/bulk/refresh-off`` — 500 path + happy-path body assertion.
- ``POST /api/bulk/refresh-off/start`` — 400 for non-numeric input, 409
  ``already_running``, and that ``min_certainty`` / ``min_completeness``
  are clamped to ``[0, 100]`` before reaching the service.
- ``GET /api/bulk/refresh-off/status`` — JSON shape contract for both
  idle and running states.
- ``POST /api/bulk/estimate-pq`` — 500 path + happy-path body assertion.

The bulk SSE stream contract is covered in ``test_e2e_bulk_sse_stream.py``.

Conventions:
- Live Flask server fixture (``live_url``) from ``tests/e2e/conftest.py``.
- External services (proxy_service → OFF) are never touched because the
  bulk service functions are mocked at the module boundary.
- Rule 8: ``unittest.mock.create_autospec`` is used so the mock structurally
  matches the real interface; signature drift breaks the test.
- Rule 18: every error path asserts the *specific* status code + error
  body; clamp tests assert the *actual* values passed to the service.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import create_autospec, patch


def _get(url, timeout=5):
    req = urllib.request.Request(url, headers={"X-Requested-With": "SmartSnack"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(url, payload=None, timeout=5):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ===========================================================================
# POST /api/bulk/refresh-off
# ===========================================================================


class TestRefreshOffSync:
    """The synchronous refresh route returns the service result on success
    and surfaces unexpected exceptions as 500."""

    def test_happy_path_returns_service_result_body(self, live_url):
        """A successful refresh returns the service result verbatim with 200."""
        from services import bulk_service

        spec = create_autospec(bulk_service.refresh_from_off, spec_set=True)
        spec.return_value = {
            "total": 4,
            "updated": 2,
            "skipped": 1,
            "errors": 1,
            "error_details": [{"id": 7, "ean": "0001", "error": "off_err_api"}],
        }
        with patch("services.bulk_service.refresh_from_off", spec):
            status, body = _post(f"{live_url}/api/bulk/refresh-off")

        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["total"] == 4
        assert body["updated"] == 2
        assert body["skipped"] == 1
        assert body["errors"] == 1
        assert body["error_details"] == [
            {"id": 7, "ean": "0001", "error": "off_err_api"}
        ]
        # The route MUST have called the service exactly once.
        assert spec.call_count == 1

    def test_service_exception_returns_500_with_error_body(self, live_url):
        """When ``refresh_from_off`` raises, the route returns 500 with the
        exception message in ``error``."""
        with patch(
            "services.bulk_service.refresh_from_off",
            side_effect=RuntimeError("OFF upstream is on fire"),
        ):
            status, body = _post(f"{live_url}/api/bulk/refresh-off")

        assert status == 500, f"Expected 500 on service exception, got {status}: {body}"
        assert body.get("error") == "OFF upstream is on fire", (
            "Route must surface the exception's str() in the error field"
        )


# ===========================================================================
# POST /api/bulk/refresh-off/start
# ===========================================================================


class TestRefreshOffStart:
    """Validation, conflict, and clamping rules for the async-refresh starter."""

    def test_invalid_numeric_param_returns_400(self, live_url):
        """``min_certainty="not-a-number"`` raises ValueError on int() and the
        route returns 400 with ``Invalid numeric parameter``. The underlying
        service must NOT be invoked when validation fails."""
        with patch("services.bulk_service.start_refresh_from_off") as mock_start:
            status, body = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_certainty": "not-a-number"},
            )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body.get("error") == "Invalid numeric parameter"
        assert mock_start.call_count == 0, (
            "Service must not be called when validation fails"
        )

    def test_invalid_min_completeness_returns_400(self, live_url):
        """``min_completeness`` is validated by the same code path."""
        with patch("services.bulk_service.start_refresh_from_off") as mock_start:
            status, body = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_completeness": "abc"},
            )

        assert status == 400
        assert body.get("error") == "Invalid numeric parameter"
        assert mock_start.call_count == 0

    def test_already_running_returns_409(self, live_url):
        """If ``start_refresh_from_off`` returns False, the route surfaces
        409 + ``{"error": "already_running"}``."""
        with patch(
            "services.bulk_service.start_refresh_from_off",
            return_value=False,
        ) as mock_start:
            status, body = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"search_missing": False},
            )

        assert status == 409, f"Expected 409, got {status}: {body}"
        assert body == {"error": "already_running"}
        assert mock_start.call_count == 1, (
            "Service must be called once even when it returns False"
        )

    def test_min_certainty_below_zero_is_clamped_to_zero(self, live_url):
        """``min_certainty=-10`` must be clamped to 0 before reaching the
        service. Asserts the clamp by inspecting the options dict passed to
        ``start_refresh_from_off``."""
        with patch(
            "services.bulk_service.start_refresh_from_off",
            return_value=True,
        ) as mock_start:
            status, body = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_certainty": -10, "min_completeness": 50},
            )

        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body == {"ok": True}
        assert mock_start.call_count == 1
        opts = mock_start.call_args[0][0]
        assert opts["min_certainty"] == 0, (
            f"min_certainty=-10 must clamp to 0, got {opts['min_certainty']!r}"
        )
        assert opts["min_completeness"] == 50

    def test_min_certainty_above_hundred_is_clamped_to_hundred(self, live_url):
        """``min_certainty=200`` must be clamped to 100."""
        with patch(
            "services.bulk_service.start_refresh_from_off",
            return_value=True,
        ) as mock_start:
            status, body = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_certainty": 200, "min_completeness": 50},
            )

        assert status == 200
        opts = mock_start.call_args[0][0]
        assert opts["min_certainty"] == 100, (
            f"min_certainty=200 must clamp to 100, got {opts['min_certainty']!r}"
        )

    def test_min_completeness_clamps_both_directions(self, live_url):
        """Boundary clamps on ``min_completeness`` mirror ``min_certainty``."""
        with patch(
            "services.bulk_service.start_refresh_from_off",
            return_value=True,
        ) as mock_start:
            _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_completeness": -10, "min_certainty": 50},
            )
            below = mock_start.call_args[0][0]["min_completeness"]

            _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"min_completeness": 200, "min_certainty": 50},
            )
            above = mock_start.call_args[0][0]["min_completeness"]

        assert below == 0, f"-10 must clamp to 0, got {below!r}"
        assert above == 100, f"200 must clamp to 100, got {above!r}"

    def test_search_missing_is_coerced_to_bool(self, live_url):
        """``search_missing`` is passed through ``bool()`` before reaching the
        service — non-bool truthy values must become ``True``."""
        with patch(
            "services.bulk_service.start_refresh_from_off",
            return_value=True,
        ) as mock_start:
            status, _ = _post(
                f"{live_url}/api/bulk/refresh-off/start",
                {"search_missing": 1, "min_certainty": 50, "min_completeness": 50},
            )

        assert status == 200
        opts = mock_start.call_args[0][0]
        assert opts["search_missing"] is True
        assert isinstance(opts["search_missing"], bool)


# ===========================================================================
# GET /api/bulk/refresh-off/status
# ===========================================================================


class TestRefreshOffStatus:
    """JSON-shape contract for the status polling endpoint."""

    def test_idle_state_shape(self, live_url):
        """An idle job exposes the full counter set with ``running=False`` and
        no ``report`` key (the service strips ``report`` until ``done``)."""
        idle_snapshot = {
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
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=idle_snapshot,
        ):
            status, body = _get(f"{live_url}/api/bulk/refresh-off/status")

        assert status == 200
        assert body == idle_snapshot, (
            "Idle status JSON must be the service snapshot verbatim"
        )
        assert "report" not in body

    def test_running_state_exposes_progress_counters(self, live_url):
        """Mid-run, the status snapshot reports ``running=True`` with the
        current/total counters and the in-flight EAN/name."""
        running_snapshot = {
            "running": True,
            "current": 7,
            "total": 42,
            "name": "Kvarg Naturell",
            "ean": "7310865004703",
            "status": "fetching",
            "updated": 4,
            "skipped": 2,
            "errors": 1,
            "done": False,
        }
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=running_snapshot,
        ):
            status, body = _get(f"{live_url}/api/bulk/refresh-off/status")

        assert status == 200
        assert body["running"] is True
        assert body["current"] == 7
        assert body["total"] == 42
        assert body["name"] == "Kvarg Naturell"
        assert body["ean"] == "7310865004703"
        assert body["status"] == "fetching"
        assert body["updated"] == 4
        assert body["skipped"] == 2
        assert body["errors"] == 1
        assert body["done"] is False
        # All documented counter keys are present (regression guard for the
        # frontend that polls this endpoint at 500ms intervals).
        for key in (
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
        ):
            assert key in body, f"Missing key {key!r} in running snapshot"

    def test_done_state_includes_report(self, live_url):
        """When the job is ``done``, the snapshot includes a ``report`` array
        of per-product outcomes (the frontend uses this to render the summary
        modal)."""
        done_snapshot = {
            "running": False,
            "current": 3,
            "total": 3,
            "name": "Last Product",
            "ean": "0000000000003",
            "status": "updated",
            "updated": 2,
            "skipped": 1,
            "errors": 0,
            "done": True,
            "report": [
                {"name": "A", "ean": "1", "status": "updated", "fields": ["kcal"]},
                {"name": "B", "ean": "2", "status": "skipped", "reason": "no_new_data"},
                {"name": "C", "ean": "3", "status": "updated", "fields": ["protein"]},
            ],
        }
        with patch(
            "services.bulk_service.get_refresh_status",
            return_value=done_snapshot,
        ):
            status, body = _get(f"{live_url}/api/bulk/refresh-off/status")

        assert status == 200
        assert body["done"] is True
        assert body["running"] is False
        assert isinstance(body["report"], list)
        assert len(body["report"]) == 3
        assert {r["status"] for r in body["report"]} == {"updated", "skipped"}


# ===========================================================================
# POST /api/bulk/estimate-pq
# ===========================================================================


class TestEstimatePqBulk:
    """Synchronous bulk PQ estimation — success and failure contracts."""

    def test_happy_path_returns_counters(self, live_url):
        """A successful estimation returns ``total / updated / skipped``."""
        from services import bulk_service

        spec = create_autospec(bulk_service.estimate_all_pq, spec_set=True)
        spec.return_value = {"total": 11, "updated": 7, "skipped": 4}
        with patch("services.bulk_service.estimate_all_pq", spec):
            status, body = _post(f"{live_url}/api/bulk/estimate-pq")

        assert status == 200
        assert body == {"total": 11, "updated": 7, "skipped": 4}
        assert spec.call_count == 1

    def test_service_exception_returns_500(self, live_url):
        """When ``estimate_all_pq`` raises, the route returns 500 + error body."""
        with patch(
            "services.bulk_service.estimate_all_pq",
            side_effect=RuntimeError("PQ estimator crashed"),
        ):
            status, body = _post(f"{live_url}/api/bulk/estimate-pq")

        assert status == 500, f"Expected 500 on exception, got {status}: {body}"
        assert body.get("error") == "PQ estimator crashed"
