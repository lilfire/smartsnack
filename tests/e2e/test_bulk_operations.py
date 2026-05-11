"""E2E tests for bulk operations: refresh from OFF, estimate PQ."""

import json
import urllib.error
import urllib.request
from unittest.mock import patch


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _post(url, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_refresh_off_sync(live_url):
    """POST /api/bulk/refresh-off runs synchronous refresh with mock."""
    with patch("services.bulk_service.refresh_from_off") as mock_refresh:
        mock_refresh.return_value = {
            "total": 0, "updated": 0, "skipped": 0,
            "errors": 0, "error_details": [],
        }
        status, body = _post(f"{live_url}/api/bulk/refresh-off")

    assert status == 200
    assert "total" in body
    assert "updated" in body
    assert "skipped" in body


def test_refresh_off_start(live_url):
    """POST /api/bulk/refresh-off/start begins async refresh."""
    with patch("services.bulk_service.start_refresh_from_off") as mock_start:
        mock_start.return_value = True
        status, body = _post(f"{live_url}/api/bulk/refresh-off/start", {
            "search_missing": False,
            "min_certainty": 50,
            "min_completeness": 50,
        })

    assert status == 200
    assert body.get("ok") is True


def test_refresh_off_start_already_running(live_url):
    """POST /api/bulk/refresh-off/start returns 409 if already running."""
    with patch("services.bulk_service.start_refresh_from_off") as mock_start:
        mock_start.return_value = False
        status, body = _post(f"{live_url}/api/bulk/refresh-off/start")

    assert status == 409
    assert body.get("error") == "already_running"


def test_refresh_off_status(live_url):
    """GET /api/bulk/refresh-off/status returns job state."""
    with patch("services.bulk_service.get_refresh_status") as mock_status:
        mock_status.return_value = {
            "running": False, "current": 0, "total": 0,
            "done": False, "updated": 0, "skipped": 0, "errors": 0,
        }
        status, body = _get(f"{live_url}/api/bulk/refresh-off/status")

    assert status == 200
    assert "running" in body
    assert "current" in body
    assert "total" in body


def test_refresh_off_stream(live_url):
    """GET /api/bulk/refresh-off/stream returns SSE stream."""
    with patch("services.bulk_service.get_refresh_status") as mock_status:
        mock_status.return_value = {
            "running": False, "current": 0, "total": 0,
            "done": True, "updated": 0, "skipped": 0, "errors": 0,
        }
        req = urllib.request.Request(f"{live_url}/api/bulk/refresh-off/stream")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ct = resp.headers.get("Content-Type", "")
            data = resp.read().decode()

    assert "text/event-stream" in ct
    assert "data:" in data


def test_estimate_pq_bulk(live_url):
    """POST /api/bulk/estimate-pq estimates PQ for all products."""
    with patch("services.bulk_service.estimate_all_pq") as mock_est:
        mock_est.return_value = {"total": 5, "updated": 3, "skipped": 2}
        status, body = _post(f"{live_url}/api/bulk/estimate-pq")

    assert status == 200
    assert body["total"] == 5
    assert body["updated"] == 3
    assert body["skipped"] == 2
