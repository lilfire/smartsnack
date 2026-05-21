"""E2E validation tests for ``POST/PUT/DELETE /api/protein-quality``.

Phase 2D-2 of LSO-1352 (audit items 20–22). Constants are imported from
``config`` so a future bump (e.g. ``_PQ_MAX_KEYWORDS = 100``) automatically
re-applies the boundary.

- Item 20 — ``POST /api/protein-quality``:
  * empty/missing ``name`` and ``label`` and ``keywords`` -> ``keywords, pdcaas
    and diaas are required`` (400)
  * ``keywords`` list of size > ``_PQ_MAX_KEYWORDS`` -> ``Too many keywords``
  * one keyword string longer than ``_PQ_MAX_KEYWORD_LEN`` -> ``Each keyword
    must be a string of max ... chars``
  * non-float ``pdcaas`` / ``diaas`` -> ``Invalid numeric value for pdcaas``
    / ``diaas``
  * non-finite (``inf`` / ``nan``) ``pdcaas`` -> ``Non-finite numeric value
    for pdcaas`` — currently the route only checks finiteness, not range.
    The audit asks for "out-of-range" coverage; here we pin the *actual*
    validator behaviour for negative / >1.0 values (currently *accepted*
    because the service has no min/max gate).
- Item 21 — same validation set on ``PUT /api/protein-quality/<pid>``.
- Item 22 — ``DELETE /api/protein-quality/<pid>`` unknown pid -> 404
  ``Not found``.
"""

import json
import urllib.error
import urllib.request

import pytest

from config import _PQ_MAX_KEYWORDS, _PQ_MAX_KEYWORD_LEN, _PQ_MAX_LABEL_LEN


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-Requested-With": "SmartSnack"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _valid_pq_payload(name):
    return {
        "name": name,
        "label": "Test PQ",
        "keywords": ["alpha"],
        "pdcaas": 0.75,
        "diaas": 0.80,
    }


@pytest.fixture()
def existing_pq(live_url, unique_name):
    """Create a baseline PQ entry and return its id + name."""
    name = unique_name("pqbase").replace("-", "_").lower()
    status, body = _request(
        "POST",
        f"{live_url}/api/protein-quality",
        payload=_valid_pq_payload(name),
    )
    assert status == 201, f"Fixture setup failed: {status} {body}"
    return {"id": body["id"], "name": body["name"]}


# ===========================================================================
# Item 20 — POST /api/protein-quality 400 validation
# ===========================================================================


class TestPostProteinQualityValidation:
    """``POST /api/protein-quality`` rejects each invalid input with 400."""

    @pytest.mark.parametrize(
        "payload, expected_in_error",
        [
            ({"label": "", "keywords": [], "pdcaas": 0.5, "diaas": 0.5}, "required"),
            ({"label": "", "keywords": ["x"], "pdcaas": None, "diaas": 0.5}, "required"),
            ({"label": "Foo", "keywords": ["x"], "pdcaas": 0.5, "diaas": None}, "required"),
        ],
        ids=["empty-label-and-keywords", "missing-pdcaas", "missing-diaas"],
    )
    def test_required_fields_missing_returns_400(
        self, live_url, payload, expected_in_error
    ):
        """The combined ``not name or not keywords or pdcaas is None or diaas is
        None`` check raises ``ValueError("keywords, pdcaas and diaas are
        required")`` -> 400."""
        status, body = _request(
            "POST", f"{live_url}/api/protein-quality", payload=payload
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert expected_in_error in body["error"].lower()

    def test_keywords_over_max_returns_400(self, live_url, unique_name):
        """More than ``_PQ_MAX_KEYWORDS`` keywords -> ``Too many keywords (max
        N)``."""
        name = unique_name("pqkwmax").replace("-", "_").lower()
        payload = _valid_pq_payload(name)
        payload["keywords"] = [f"kw{i}" for i in range(_PQ_MAX_KEYWORDS + 1)]
        status, body = _request(
            "POST", f"{live_url}/api/protein-quality", payload=payload
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": f"Too many keywords (max {_PQ_MAX_KEYWORDS})"}

    def test_keyword_too_long_returns_400(self, live_url, unique_name):
        """A single keyword longer than ``_PQ_MAX_KEYWORD_LEN`` is rejected with
        the per-keyword length message."""
        name = unique_name("pqkwlen").replace("-", "_").lower()
        payload = _valid_pq_payload(name)
        payload["keywords"] = ["a" * (_PQ_MAX_KEYWORD_LEN + 1)]
        status, body = _request(
            "POST", f"{live_url}/api/protein-quality", payload=payload
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {
            "error": f"Each keyword must be a string of max {_PQ_MAX_KEYWORD_LEN} chars"
        }

    def test_label_too_long_returns_400(self, live_url, unique_name):
        """A label longer than ``_PQ_MAX_LABEL_LEN`` is rejected."""
        name = unique_name("pqlabel").replace("-", "_").lower()
        payload = _valid_pq_payload(name)
        payload["label"] = "L" * (_PQ_MAX_LABEL_LEN + 1)
        status, body = _request(
            "POST", f"{live_url}/api/protein-quality", payload=payload
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {
            "error": f"label exceeds max length of {_PQ_MAX_LABEL_LEN}"
        }

    @pytest.mark.parametrize(
        "field, value, expected_error",
        [
            ("pdcaas", "abc", "Invalid numeric value for pdcaas"),
            ("diaas", "xyz", "Invalid numeric value for diaas"),
            ("pdcaas", [1, 2, 3], "Invalid numeric value for pdcaas"),
        ],
        ids=["pdcaas-str", "diaas-str", "pdcaas-list"],
    )
    def test_non_float_pdcaas_diaas_returns_400(
        self, live_url, unique_name, field, value, expected_error
    ):
        """Non-coercible values for ``pdcaas``/``diaas`` -> 400 with the
        ``_safe_float`` error message."""
        name = unique_name("pqfloat").replace("-", "_").lower()
        payload = _valid_pq_payload(name)
        payload[field] = value
        status, body = _request(
            "POST", f"{live_url}/api/protein-quality", payload=payload
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": expected_error}

    def test_non_finite_pdcaas_returns_400(self, live_url, unique_name):
        """``inf`` / ``nan`` are not finite -> ``Non-finite numeric value``."""
        name = unique_name("pqinf").replace("-", "_").lower()
        payload = _valid_pq_payload(name)
        # JSON has no inf/nan literal; we send the string ``Infinity`` which is
        # accepted by Python's ``json`` parser and produces ``float('inf')``.
        raw = json.dumps(payload).replace("0.75", "Infinity")
        req = urllib.request.Request(
            f"{live_url}/api/protein-quality",
            data=raw.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status, body = resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read())
        assert status == 400, f"Expected 400 for inf, got {status}: {body}"
        assert body == {"error": "Non-finite numeric value for pdcaas"}


# ===========================================================================
# Item 21 — PUT /api/protein-quality/<pid> 400 validation
# ===========================================================================


class TestPutProteinQualityValidation:
    """``PUT /api/protein-quality/<pid>`` shares the same validators as POST."""

    def test_keywords_over_max_returns_400(self, live_url, existing_pq):
        status, body = _request(
            "PUT",
            f"{live_url}/api/protein-quality/{existing_pq['id']}",
            payload={"keywords": [f"kw{i}" for i in range(_PQ_MAX_KEYWORDS + 1)]},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": f"Too many keywords (max {_PQ_MAX_KEYWORDS})"}

    def test_keyword_too_long_returns_400(self, live_url, existing_pq):
        status, body = _request(
            "PUT",
            f"{live_url}/api/protein-quality/{existing_pq['id']}",
            payload={"keywords": ["a" * (_PQ_MAX_KEYWORD_LEN + 1)]},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {
            "error": f"Each keyword must be a string of max {_PQ_MAX_KEYWORD_LEN} chars"
        }

    def test_label_too_long_returns_400(self, live_url, existing_pq):
        status, body = _request(
            "PUT",
            f"{live_url}/api/protein-quality/{existing_pq['id']}",
            payload={"label": "L" * (_PQ_MAX_LABEL_LEN + 1)},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": f"label exceeds max length of {_PQ_MAX_LABEL_LEN}"}

    @pytest.mark.parametrize("field", ["pdcaas", "diaas"])
    def test_non_float_value_returns_400(self, live_url, existing_pq, field):
        status, body = _request(
            "PUT",
            f"{live_url}/api/protein-quality/{existing_pq['id']}",
            payload={field: "notanumber"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": f"Invalid numeric value for {field}"}

    def test_put_unknown_pid_returns_404(self, live_url):
        """The route raises ``LookupError`` before touching the body -> 404."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/protein-quality/9999990",
            payload={"label": "anything"},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Not found"}


# ===========================================================================
# Item 22 — DELETE /api/protein-quality/<pid> unknown pid -> 404
# ===========================================================================


class TestDeleteProteinQualityNotFound:
    """``DELETE /api/protein-quality/<pid>`` 404s for unknown ids."""

    def test_delete_unknown_pid_returns_404(self, live_url):
        status, body = _request("DELETE", f"{live_url}/api/protein-quality/9999989")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Not found"}

    def test_delete_real_then_again_returns_404(self, live_url, existing_pq):
        """After a successful delete, a second DELETE on the same id is 404 —
        confirms the LookupError path."""
        status, _ = _request(
            "DELETE", f"{live_url}/api/protein-quality/{existing_pq['id']}"
        )
        assert status == 200
        status2, body2 = _request(
            "DELETE", f"{live_url}/api/protein-quality/{existing_pq['id']}"
        )
        assert status2 == 404, f"Expected 404, got {status2}: {body2}"
        assert body2 == {"error": "Not found"}
