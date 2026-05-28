"""Direct-API error-path tests for ``blueprints/proxy.py`` OFF routes.

LSO-1352 Phase 2D-1 audit gaps:

- **#8** — ``POST /api/off/search`` 500 path. The route catches the bare
  ``except Exception`` arm at ``blueprints/proxy.py:63-65`` and returns
  ``{"error": "Search failed"}`` with status 500. The 400 (``ValueError``)
  and 502 (``RuntimeError``) arms are covered for completeness.
- **#9** — ``GET /api/off/product/<code>`` 502 mapping. The route at
  ``blueprints/proxy.py:74-75`` catches ``RuntimeError`` and returns 502
  with the exception message in ``error``. The 400 (``ValueError``) arm
  is also pinned.

Conventions (Rules 8, 16, 17, 18):
- Live Flask server via ``live_url``; no browser.
- ``services.proxy_service`` callables are mocked at the module boundary
  with ``unittest.mock.create_autospec`` so signature drift breaks the
  test.
- Tests never reach the real OpenFoodFacts API.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import create_autospec, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_json(url, payload=None, timeout=5):
    """POST JSON to ``url``; return ``(status, parsed_body)``."""
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


def _get_json(url, timeout=5):
    """GET ``url``; return ``(status, parsed_body)``."""
    req = urllib.request.Request(url, headers={"X-Requested-With": "SmartSnack"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ===========================================================================
# Audit item #8 — POST /api/off/search  500 / 400 / 502
# ===========================================================================


class TestOffSearchErrorPaths:
    """All three error arms of ``POST /api/off/search``.

    The route layers three handlers in ``blueprints/proxy.py:56-65``:
    ``ValueError → 400``, ``RuntimeError → 502``, and a bare
    ``except Exception → 500``. The audit specifically calls out the bare
    ``Exception`` arm (audit item #8); the other two are pinned alongside
    so the catch ordering doesn't silently regress.
    """

    def test_unexpected_exception_returns_500_with_generic_body(self, live_url):
        """An arbitrary ``Exception`` from ``off_search`` must NOT leak the
        original message — the route returns the *generic* body
        ``{"error": "Search failed"}`` to avoid exposing internals."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_search, spec_set=True)
        spec.side_effect = Exception("OFF API returned malformed payload")
        with patch("services.proxy_service.off_search", spec):
            status, body = _post_json(
                f"{live_url}/api/off/search",
                {"q": "chocolate", "category": "Snacks"},
            )

        assert status == 500, (
            f"Expected 500 for bare Exception, got {status}: {body}"
        )
        assert body == {"error": "Search failed"}, (
            f"Bare-Exception arm must return generic body; got {body!r}"
        )
        # Original message must not leak into the response.
        assert "malformed" not in json.dumps(body)

    def test_value_error_returns_400_with_specific_message(self, live_url):
        """A short query trips ``ValueError("Query too short")`` in the real
        service. Driven via real input (no mock) to also pin the actual
        service contract from ``services/proxy_service.py:268-269``."""
        status, body = _post_json(
            f"{live_url}/api/off/search",
            {"q": "x"},
        )
        assert status == 400, f"Expected 400 for short query, got {status}: {body}"
        assert body == {"error": "Query too short"}, (
            f"Expected exact service error 'Query too short'; got {body!r}"
        )

    def test_runtime_error_returns_502_with_specific_message(self, live_url):
        """A ``RuntimeError`` from ``off_search`` must hit the 502 branch
        with the exception message in the body (502 = upstream/bad-gateway
        per the route mapping)."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_search, spec_set=True)
        spec.side_effect = RuntimeError("OFF API timeout after 30s")
        with patch("services.proxy_service.off_search", spec):
            status, body = _post_json(
                f"{live_url}/api/off/search",
                {"q": "chocolate"},
            )

        assert status == 502, f"Expected 502, got {status}: {body}"
        assert body == {"error": "OFF API timeout after 30s"}, (
            f"502 body must echo the RuntimeError message; got {body!r}"
        )

    def test_get_search_also_routes_500_for_bare_exception(self, live_url):
        """``GET /api/off/search?q=...`` shares the same handler. The 500
        arm must fire identically — this guards against the route
        accidentally branching its error handling between methods."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_search, spec_set=True)
        spec.side_effect = Exception("some weird crash")
        with patch("services.proxy_service.off_search", spec):
            status, body = _get_json(f"{live_url}/api/off/search?q=chocolate")

        assert status == 500
        assert body == {"error": "Search failed"}, (
            f"GET path must share the 500 contract; got {body!r}"
        )

    def test_service_invoked_once_per_request(self, live_url):
        """Sanity-check the boundary: each request invokes the service
        exactly once. Catches a regression where the route accidentally
        double-calls (e.g. after refactoring the catch block)."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_search, spec_set=True)
        spec.side_effect = Exception("boom")
        with patch("services.proxy_service.off_search", spec):
            _post_json(f"{live_url}/api/off/search", {"q": "tea"})

        assert spec.call_count == 1, (
            f"off_search must be invoked exactly once per request; "
            f"call_count={spec.call_count}"
        )


# ===========================================================================
# Audit item #9 — GET /api/off/product/<code>  502 / 400
# ===========================================================================


class TestOffProductErrorPaths:
    """``GET /api/off/product/<code>`` error mapping.

    The route at ``blueprints/proxy.py:68-76`` has two arms:
    ``ValueError → 400`` and ``RuntimeError → 502``. Note that this route
    does NOT have a bare-``Exception`` arm — uncaught exceptions surface
    as Flask 500s, which is desirable (a programming bug should not be
    silently mapped to "Bad Gateway").
    """

    def test_runtime_error_returns_502_with_message(self, live_url):
        """``RuntimeError`` from ``off_product`` maps to 502 — that's how
        the route signals an upstream OFF failure to the frontend, which
        toggles different UI affordances for 502 vs 500."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_product, spec_set=True)
        spec.side_effect = RuntimeError("OFF API error (HTTP 503)")
        with patch("services.proxy_service.off_product", spec):
            status, body = _get_json(
                f"{live_url}/api/off/product/7311041010358"
            )

        assert status == 502, (
            f"Expected 502 for RuntimeError, got {status}: {body}"
        )
        assert body == {"error": "OFF API error (HTTP 503)"}, (
            f"502 body must echo the RuntimeError message; got {body!r}"
        )
        # Code was passed through to the service as a stripped string.
        assert spec.call_count == 1
        args, _kwargs = spec.call_args
        assert args == ("7311041010358",), (
            f"off_product must receive the URL code positional; got args={args!r}"
        )

    def test_generic_upstream_runtime_error_maps_to_502(self, live_url):
        """Generic upstream failure ("Failed to fetch from OpenFoodFacts") —
        the real message produced by ``_off_get_json`` on network errors.
        Pinning this exact string guards against client-side error
        copy-deck regressions."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_product, spec_set=True)
        spec.side_effect = RuntimeError("Failed to fetch from OpenFoodFacts")
        with patch("services.proxy_service.off_product", spec):
            status, body = _get_json(f"{live_url}/api/off/product/0000000000000")

        assert status == 502
        assert body == {"error": "Failed to fetch from OpenFoodFacts"}, (
            f"Expected exact upstream-failure message; got {body!r}"
        )

    def test_value_error_returns_400(self, live_url):
        """``ValueError("Invalid product code")`` from ``off_product`` maps
        to 400 — the route's first catch arm."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_product, spec_set=True)
        spec.side_effect = ValueError("Invalid product code")
        with patch("services.proxy_service.off_product", spec):
            status, body = _get_json(f"{live_url}/api/off/product/abcd")

        assert status == 400
        assert body == {"error": "Invalid product code"}, (
            f"Expected exact 'Invalid product code'; got {body!r}"
        )

    def test_value_error_specific_message_propagates(self, live_url):
        """A different ``ValueError`` message must propagate verbatim — the
        route does not rewrite or sanitize ``ValueError`` text."""
        from services import proxy_service

        spec = create_autospec(proxy_service.off_product, spec_set=True)
        spec.side_effect = ValueError("Product code must be numeric")
        with patch("services.proxy_service.off_product", spec):
            status, body = _get_json(f"{live_url}/api/off/product/abc123")

        assert status == 400
        assert body == {"error": "Product code must be numeric"}, (
            f"Route must surface str(exc); got {body!r}"
        )

    def test_happy_path_returns_service_payload_verbatim(self, live_url):
        """Contrast case: when the service returns a dict, the route forwards
        it as JSON with status 200. Without this, the 502/400 contracts are
        ambiguous about what "no error" actually looks like."""
        from services import proxy_service

        payload = {
            "status": 1,
            "code": "7311041010358",
            "product": {"product_name": "Some Snack", "brands": "Acme"},
        }
        spec = create_autospec(proxy_service.off_product, spec_set=True)
        spec.return_value = payload
        with patch("services.proxy_service.off_product", spec):
            status, body = _get_json(
                f"{live_url}/api/off/product/7311041010358"
            )

        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body == payload, (
            f"Happy path must echo the service payload verbatim; got {body!r}"
        )
