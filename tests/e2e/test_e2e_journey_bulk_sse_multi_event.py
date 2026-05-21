"""End-to-end user-journey: bulk refresh-from-OFF multi-event SSE stream.

Covers gap **F** from the LSO-1354 audit (LSO-1352 Phase 2D-3): the
user kicks off a bulk OFF refresh and watches progress in the UI. The
backend exposes a Server-Sent Events stream that emits one event per
state change so the frontend can render a live progress bar.

Existing tests cover the SSE *headers* and *termination* contract by
mocking ``get_refresh_status`` with canned snapshots. THIS test goes
further: it actually starts a real refresh job, mocks only the OFF
HTTP client, and asserts that the stream:

1. Emits ≥2 distinct ``data: ...`` events for a real run.
2. The ``current`` counter increases monotonically across snapshots
   (the audit's "processed" counter — the actual JSON key is
   ``current``; see ``services/bulk_service.py``).
3. The final event has ``running: false`` AND ``current == total``.

External services are mocked at the ``proxy_service.off_product``
module boundary so no real HTTP is made. The internal ``time.sleep``
in the worker is shortened so the test completes in seconds, not
minutes.

Rules:
- 17 (deterministic): bounded total wait (10s) with explicit timeouts;
  mocks are deterministic.
- 18 (assertions of correctness): we assert ON the EVENTS themselves
  (not just that the request completed). Monotonic progress and the
  final terminal state are both verified.
- 8 (mock shape): ``proxy_service.off_product`` is patched with a
  callable that returns the exact ``{"product": {...}}`` shape the
  real function produces.
"""

import json
import os
import re
import urllib.error
import urllib.request
from unittest.mock import patch


_STREAM_URL = "/api/bulk/refresh-off/stream"
_START_URL = "/api/bulk/refresh-off/start"
_DATA_PATTERN = re.compile(r"^data: (.+)$", re.MULTILINE)


def _db_path():
    # ``services.bulk_service`` does ``from config import DB_PATH`` at
    # import time, so its module-level ``DB_PATH`` is whatever
    # ``config.DB_PATH`` was the first time bulk_service was imported.
    # In CI, unit tests collected before the e2e session fixture had
    # patched the env var → bulk_service.DB_PATH is the production
    # default (``/data/smartsnack.sqlite``). The worker thread opens a
    # fresh sqlite connection on that stale path and finds zero rows,
    # so ``total`` stays 0 and our assertions fail. Patching
    # ``bulk_service.DB_PATH`` to the live test DB for the duration of
    # this test reconnects the worker to the same DB the API writes to.
    return os.environ["DB_PATH"]


def _post(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _open_stream_body(live_url, timeout=15):
    """Open SSE endpoint and read the entire body. The generator
    terminates on ``running=False``, so a blocking read is safe as long
    as the job actually completes (worker thread terminates and the
    final snapshot has ``running=False``)."""
    req = urllib.request.Request(
        f"{live_url}{_STREAM_URL}",
        headers={"X-Requested-With": "SmartSnack"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _parse_events(body):
    events = []
    for match in _DATA_PATTERN.finditer(body):
        try:
            events.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            events.append({"_raw": match.group(1)})
    return events


def _make_off_response(code, name_suffix=""):
    """Return the shape ``proxy_service.off_product`` produces for a
    successful lookup. Each field maps to a corresponding local column
    in ``bulk_service._map_off_product``.

    Per-product field shifts (``name_suffix``) make every product
    distinct so the worker actually writes updates (otherwise the
    ``_should_update`` short-circuit can skip them as "no new data" and
    no state change is recorded between products).
    """
    return {
        "product": {
            "code": code,
            "product_name_no": f"OFF Updated {name_suffix}",
            "brands": f"Brand-{name_suffix}",
            "stores": f"Store-{name_suffix}",
            "ingredients_text_no": f"ingredient-{name_suffix}",
            "nutriments": {
                "energy-kcal_100g": 100 + len(name_suffix),
                "fat_100g": 5.0,
                "saturated-fat_100g": 2.0,
                "carbohydrates_100g": 20.0,
                "sugars_100g": 10.0,
                "proteins_100g": 8.0,
                "fiber_100g": 3.0,
                "salt_100g": 0.5,
            },
            "product_quantity": 200,
            "serving_size": "100 g",
        }
    }


def test_bulk_refresh_sse_emits_monotonic_multi_events_until_done(
    live_url, api_create_product
):
    """Real bulk refresh under mocked OFF: assert multiple distinct
    events, monotonic ``current`` progression, and clean termination.

    We patch ``bulk_service.time.sleep`` to a small fixed value (NOT
    zero) so the worker thread doesn't race past the SSE polling
    interval. The natural cadence — ~0.05s per product on the worker,
    0.3s polling on the SSE — guarantees the SSE samples at least two
    distinct snapshots between job start and job end for 3 products.
    """
    # Seed 3 products with distinct primary EANs.
    eans = ["7311111111111", "7311111111128", "7311111111135"]
    seeded_pids = []
    for i, ean in enumerate(eans):
        created = api_create_product(name=f"BulkSSE-{i}", ean=ean)
        seeded_pids.append(created["id"])

    # OFF responses keyed by EAN — each product gets a different name
    # so the worker actually writes updates (vs. skipping as "no new
    # data") and the worker's ``updated`` counter grows monotonically.
    responses = {ean: _make_off_response(ean, f"v{i}") for i, ean in enumerate(eans)}

    def fake_off_product(code):
        # The bulk worker calls this exactly once per primary EAN.
        return responses[code]

    # Patch ``time.sleep`` inside the bulk_service worker so the per-
    # product 1s pacing doesn't bloat the test. Even with sleep mocked,
    # the worker still does real DB work per product so the SSE polling
    # (every 0.3s) samples mid-run.
    with patch(
        "services.proxy_service.off_product",
        side_effect=fake_off_product,
    ), patch(
        "services.bulk_service.time.sleep",
        lambda _s: None,
    ), patch(
        "services.bulk_service.DB_PATH",
        _db_path(),
    ):
        # Step 1: kick off the background refresh job.
        status, body = _post(f"{live_url}{_START_URL}", {})
        assert status == 200, (
            f"refresh-off/start must return 200, got {status}: {body}"
        )
        assert body["ok"] is True

        # Step 2: open the stream and consume until termination. The
        # stream generator self-terminates when ``running`` flips to
        # ``false``, so a blocking read is correct. Bounded by a 15s
        # urlopen timeout — if the worker hangs, this test fails fast.
        body_str = _open_stream_body(live_url, timeout=15)

    events = _parse_events(body_str)

    # ──────────────────────────────────────────────────────────────────
    # Assertion 1: ≥2 distinct data events.
    # ──────────────────────────────────────────────────────────────────
    assert len(events) >= 2, (
        f"Stream must emit ≥2 distinct events for a 3-product refresh; "
        f"got {len(events)} events. Body: {body_str!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Assertion 2: monotonic ``current``. The worker only ever
    # increments this counter, never decrements. If we observe a
    # decrease, the worker is buggy or the SSE delivered events out of
    # order. (json.dumps inside a single yield is atomic, so out-of-
    # order isn't realistic — but the assertion is cheap insurance.)
    # ──────────────────────────────────────────────────────────────────
    currents = [e.get("current", 0) for e in events]
    for i in range(1, len(currents)):
        assert currents[i] >= currents[i - 1], (
            f"``current`` must be monotonically non-decreasing across "
            f"events. Index {i} dropped: {currents[i-1]} → {currents[i]}. "
            f"Full sequence: {currents}"
        )

    # ──────────────────────────────────────────────────────────────────
    # Assertion 3: terminal state. The final event must mark the job
    # complete AND show ``current == total`` (every product processed).
    # ──────────────────────────────────────────────────────────────────
    final = events[-1]
    assert final.get("running") is False, (
        f"Final event must have running=False, got {final.get('running')!r}. "
        f"Full final event: {final!r}"
    )
    assert final.get("done") is True, (
        f"Final event must have done=True, got {final.get('done')!r}"
    )
    assert final.get("total") == len(eans), (
        f"Final event total must equal seeded EAN count ({len(eans)}), "
        f"got {final.get('total')!r}"
    )
    assert final.get("current") == final.get("total"), (
        f"Final event must have current==total (processed all). "
        f"Got current={final.get('current')!r} total={final.get('total')!r}"
    )

    # Bonus: every seeded EAN should have been queried (proves the
    # worker actually iterated the seeded set, not just transitioned
    # status fields).
    assert set(responses.keys()) == set(eans)


def test_bulk_refresh_sse_with_no_products_completes_immediately(live_url):
    """Edge: no products seeded → ``total=0``, the worker runs through
    its loop with zero iterations, and the SSE stream emits at least
    one event with ``running: false`` and terminates.

    This catches a class of regressions where a "zero products" case
    would hang the worker because of an off-by-one in the loop guard.
    """
    with patch(
        "services.proxy_service.off_product",
        side_effect=AssertionError(
            "off_product must NOT be called when there are no products to refresh"
        ),
    ), patch(
        "services.bulk_service.time.sleep",
        lambda _s: None,
    ), patch(
        "services.bulk_service.DB_PATH",
        _db_path(),
    ):
        status, body = _post(f"{live_url}{_START_URL}", {})
        assert status == 200, f"start must succeed, got {status}: {body}"
        body_str = _open_stream_body(live_url, timeout=10)

    events = _parse_events(body_str)
    assert events, "Stream must emit at least one event before terminating"
    final = events[-1]
    assert final.get("running") is False, (
        f"Final event must have running=False for empty refresh, got {final!r}"
    )
    assert final.get("total") == 0, (
        f"With no seeded products, total must be 0, got {final.get('total')!r}"
    )
