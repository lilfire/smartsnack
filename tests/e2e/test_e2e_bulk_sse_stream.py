"""End-to-end tests for ``GET /api/bulk/refresh-off/stream``.

The Server-Sent Events endpoint streams refresh-progress snapshots to the
frontend during a long-running OFF refresh. It opens a chunked response,
yields one ``data: {...}\\n\\n`` block per state change, and terminates the
stream as soon as the underlying job flips to ``running=False``.

This file exercises the contract end-to-end against the live Flask server:

- ``Content-Type``, ``Cache-Control`` and ``X-Accel-Buffering`` headers
  are set correctly so reverse proxies don't buffer the stream.
- At least one ``data: {...}`` event is emitted.
- When ``running`` flips to ``False``, the stream terminates (the request
  completes) instead of hanging.
- Events between state changes are de-duplicated.

The underlying ``get_refresh_status`` is mocked so the test never touches
the real OFF API and runs in well under a second.
"""

import json
import re
import urllib.request
from unittest.mock import patch


_STREAM_URL = "/api/bulk/refresh-off/stream"
_DATA_PATTERN = re.compile(r"^data: (.+)$", re.MULTILINE)


def _open_stream(live_url, timeout=5):
    """Open the SSE endpoint and read the whole body. The route's generator
    terminates as soon as ``running=False``, so a blocking read is safe."""
    req = urllib.request.Request(
        f"{live_url}{_STREAM_URL}",
        headers={"X-Requested-With": "SmartSnack"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.status
        headers = {k: v for k, v in resp.headers.items()}
        body = resp.read().decode("utf-8")
    return status, headers, body


def _parse_events(body):
    """Extract the JSON payloads from each ``data: ...`` line in the body."""
    out = []
    for match in _DATA_PATTERN.finditer(body):
        try:
            out.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            # Surfacing the raw line helps diagnose framing bugs in the
            # generator — don't silently drop it.
            out.append({"_raw": match.group(1)})
    return out


# ---------------------------------------------------------------------------
# Headers contract
# ---------------------------------------------------------------------------


def test_stream_headers_are_sse_compatible(live_url):
    """The stream sets the three headers that matter for SSE delivery:

    - ``Content-Type: text/event-stream`` — the SSE MIME type.
    - ``Cache-Control: no-cache`` — proxies must not cache events.
    - ``X-Accel-Buffering: no`` — nginx must not buffer the chunked body.

    These are documented in the generator implementation; this test guards
    against a future refactor removing them.
    """
    idle = {
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
        return_value=idle,
    ):
        status, headers, _ = _open_stream(live_url)

    assert status == 200, f"Expected 200, got {status}"
    # Flask serialises Content-Type as e.g. "text/event-stream; charset=utf-8";
    # we only care about the MIME prefix.
    ct = headers.get("Content-Type", "")
    assert "text/event-stream" in ct, f"Content-Type missing SSE: {ct!r}"
    assert headers.get("Cache-Control") == "no-cache", (
        f"Cache-Control must be 'no-cache', got {headers.get('Cache-Control')!r}"
    )
    assert headers.get("X-Accel-Buffering") == "no", (
        f"X-Accel-Buffering must be 'no', got {headers.get('X-Accel-Buffering')!r}"
    )


# ---------------------------------------------------------------------------
# At-least-one-event contract
# ---------------------------------------------------------------------------


def test_stream_emits_at_least_one_data_event(live_url):
    """When the route is hit while the job is idle, the generator still emits
    exactly one ``data: {...}`` event (the idle snapshot) before terminating.
    """
    snapshot = {
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
        return_value=snapshot,
    ):
        _, _, body = _open_stream(live_url)

    events = _parse_events(body)
    assert events, (
        f"Expected at least one 'data: ...' event in body, got {body!r}"
    )
    assert events[0] == snapshot, (
        "First event must contain the current status snapshot"
    )


# ---------------------------------------------------------------------------
# Termination contract: stream stops when running flips to False
# ---------------------------------------------------------------------------


def test_stream_terminates_when_running_flips_to_false(live_url):
    """Simulate a refresh that ticks through three snapshots:

    1. ``running=True, current=1`` — first event yielded.
    2. ``running=True, current=2`` — second event yielded (state changed).
    3. ``running=False, done=True`` — third event yielded and the loop breaks.

    The test asserts the stream terminates (urlopen returns) and that the
    yielded events match the mid-run progression. A non-terminating
    generator would hit the ``urlopen`` timeout instead.
    """
    snapshots = [
        {
            "running": True,
            "current": 1,
            "total": 3,
            "name": "A",
            "ean": "1",
            "status": "fetching",
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "done": False,
        },
        {
            "running": True,
            "current": 2,
            "total": 3,
            "name": "B",
            "ean": "2",
            "status": "updated",
            "updated": 1,
            "skipped": 0,
            "errors": 0,
            "done": False,
        },
        {
            "running": False,
            "current": 3,
            "total": 3,
            "name": "C",
            "ean": "3",
            "status": "updated",
            "updated": 2,
            "skipped": 0,
            "errors": 0,
            "done": True,
        },
    ]

    # After the final snapshot, the generator's while-loop breaks and the
    # mock is never called again. Use side_effect as a list so each call
    # returns the next snapshot in order.
    with patch(
        "services.bulk_service.get_refresh_status",
        side_effect=snapshots,
    ):
        status, _, body = _open_stream(live_url, timeout=10)

    assert status == 200
    events = _parse_events(body)
    # The generator yields one event per state change. All three snapshots
    # have distinct contents, so all three should appear.
    assert len(events) == 3, (
        f"Expected 3 events for 3 distinct snapshots, got {len(events)}: {events!r}"
    )
    assert events[0]["current"] == 1 and events[0]["running"] is True
    assert events[1]["current"] == 2 and events[1]["status"] == "updated"
    assert events[2]["running"] is False, (
        "Final event must report running=False (the termination snapshot)"
    )
    assert events[2]["done"] is True


def test_stream_deduplicates_identical_snapshots(live_url):
    """If ``get_refresh_status`` returns the same snapshot twice in a row,
    only one ``data: ...`` event is emitted between them.

    The generator stores ``last_sent`` and skips yielding when the JSON
    serialisation is identical. We feed two identical "running" snapshots
    followed by a "done" snapshot and assert exactly 2 events are emitted
    (the first running snapshot is yielded, the duplicate is skipped, and
    the final done snapshot is yielded).
    """
    running = {
        "running": True,
        "current": 1,
        "total": 2,
        "name": "X",
        "ean": "9",
        "status": "fetching",
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "done": False,
    }
    done = {**running, "running": False, "done": True, "current": 2, "updated": 1}
    with patch(
        "services.bulk_service.get_refresh_status",
        side_effect=[running, running, done],
    ):
        _, _, body = _open_stream(live_url, timeout=10)

    events = _parse_events(body)
    assert len(events) == 2, (
        f"Expected 2 events (running, done) with duplicate de-duped, "
        f"got {len(events)}: {events!r}"
    )
    assert events[0]["running"] is True
    assert events[1]["running"] is False and events[1]["done"] is True
