"""E2E request-validation tests for ``GET /api/products`` query parameters.

Phase 2D-2 of LSO-1352 (audit items 10–11). Covers:

- Item 10 — ``limit`` / ``offset`` query params: non-int values and negative
  values must be rejected with ``400 {"error": "limit and offset must be integers"}``
  (negative ints currently pass through to SQL; the audit lists this gap and the
  tests here pin the *actual* behaviour while documenting which values trip
  the validator). See ``blueprints/products.py:30``.
- Item 11 — ``filters`` query param: malformed JSON must surface ``400`` with a
  message that mentions ``Invalid filters JSON`` (the ``ValueError`` raised by
  ``services.product_filters._parse_advanced_filters``). See
  ``blueprints/products.py:33``.

The live Flask server is started by ``conftest.py``; rate limiting is disabled
there so these tests can hammer ``/api/products`` without throttling.
"""

import json
import urllib.error
import urllib.parse
import urllib.request


def _get(url, timeout=5):
    req = urllib.request.Request(
        url,
        headers={"X-Requested-With": "SmartSnack"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _q(live_url, **params):
    """Build a ``/api/products?...`` URL with the given query params."""
    return f"{live_url}/api/products?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# Item 10: limit / offset query-parameter validation
# ---------------------------------------------------------------------------


class TestProductsListPaginationValidation:
    """``GET /api/products`` rejects non-integer ``limit`` and ``offset``."""

    def test_non_integer_limit_returns_400(self, live_url):
        """``limit=abc`` triggers ``int("abc") -> ValueError`` -> 400."""
        status, body = _get(_q(live_url, limit="abc"))
        assert status == 400, f"Expected 400 for non-int limit, got {status}: {body}"
        assert body == {"error": "limit and offset must be integers"}

    def test_non_integer_offset_returns_400(self, live_url):
        """``offset=xyz`` triggers ``int("xyz") -> ValueError`` -> 400."""
        status, body = _get(_q(live_url, offset="xyz"))
        assert status == 400, f"Expected 400 for non-int offset, got {status}: {body}"
        assert body == {"error": "limit and offset must be integers"}

    def test_float_limit_returns_400(self, live_url):
        """A float-looking value like ``limit=5.5`` is not an int and must 400."""
        status, body = _get(_q(live_url, limit="5.5"))
        assert status == 400, f"Expected 400 for float limit, got {status}: {body}"
        assert body["error"] == "limit and offset must be integers"

    def test_empty_string_limit_returns_400(self, live_url):
        """Explicit empty-string ``limit`` is parsed by ``int("")`` -> 400."""
        status, body = _get(_q(live_url, limit=""))
        assert status == 400
        assert body["error"] == "limit and offset must be integers"

    def test_negative_limit_passes_validation(self, live_url):
        """The current route accepts negative ints — ``int("-5")`` succeeds and
        SQLite ``LIMIT -5`` returns no rows. This test pins the *actual* contract
        so a future tightening (rejecting negatives at the route layer) is a
        deliberate breaking change rather than a silent regression."""
        status, body = _get(_q(live_url, limit="-5"))
        assert status == 200, (
            f"Negative limit currently passes validation; if this changes update "
            f"the audit. Got {status}: {body}"
        )
        assert body == {"products": [], "total": 0}

    def test_negative_offset_passes_validation(self, live_url):
        """Same as above for ``offset=-1``."""
        status, body = _get(_q(live_url, offset="-1"))
        assert status == 200, (
            f"Negative offset currently passes validation; if this changes "
            f"update the audit. Got {status}: {body}"
        )
        assert "products" in body and "total" in body

    def test_valid_integer_limit_and_offset_succeed(self, live_url):
        """Sanity check: integer values for both params return 200."""
        status, body = _get(_q(live_url, limit="10", offset="0"))
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert "products" in body
        assert "total" in body


# ---------------------------------------------------------------------------
# Item 11: advanced filters JSON-parse validation
# ---------------------------------------------------------------------------


class TestProductsListFiltersValidation:
    """``GET /api/products?filters=...`` rejects malformed JSON with 400."""

    def test_unparseable_filters_returns_400(self, live_url):
        """A literal string that isn't valid JSON triggers
        ``json.loads -> JSONDecodeError`` which the service re-raises as
        ``ValueError("Invalid filters JSON")``."""
        status, body = _get(_q(live_url, filters="not-valid-json"))
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid filters JSON"}

    def test_unterminated_braces_returns_400(self, live_url):
        """``{`` alone is not parseable JSON -> 400 with the same message."""
        status, body = _get(_q(live_url, filters="{"))
        assert status == 400
        assert body == {"error": "Invalid filters JSON"}

    def test_filters_must_be_object_returns_400(self, live_url):
        """Valid JSON array (rather than an object) is rejected by the parser
        with a distinct message — pin the contract so a refactor doesn't
        collapse the two errors into one generic 400."""
        status, body = _get(_q(live_url, filters=json.dumps([1, 2, 3])))
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "json object" in body["error"].lower()

    def test_invalid_filter_field_returns_400(self, live_url):
        """A syntactically valid filter referencing an unknown field is rejected
        by ``_parse_condition`` with ``Invalid filter field: ...``."""
        payload = json.dumps(
            {"conditions": [{"field": "totally_made_up", "op": "=", "value": "x"}]}
        )
        status, body = _get(_q(live_url, filters=payload))
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "invalid filter field" in body["error"].lower()
        assert "totally_made_up" in body["error"]

    def test_valid_filters_succeeds(self, live_url):
        """A well-formed filter spec is *not* rejected by the validator —
        sanity check the negative-path assertions above aren't over-broad."""
        payload = json.dumps({"logic": "and", "conditions": []})
        status, body = _get(_q(live_url, filters=payload))
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert "products" in body and "total" in body
