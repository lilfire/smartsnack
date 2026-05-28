"""E2E validation tests for ``POST/PUT /api/flags``.

Phase 2D-2 of LSO-1352 (audit items 26–27). Pins the validator + service
contract:

- Item 26 — ``POST /api/flags`` 400 paths:
  * names not matching ``^[a-z][a-z0-9_]*$`` (uppercase first char, leading
    digit, dash) -> ``Flag name must start with a letter ...``
  * empty ``name`` or empty ``label`` -> ``name and label are required``
  * ``name`` longer than ``_MAX_FLAG_NAME_LEN`` -> ``Invalid flag name``
- Item 27 — ``PUT /api/flags/<name>``:
  * empty ``label`` -> 400 ``label is required``
  * PUT to non-existent flag -> the service raises ``LookupError("Flag not
    found")`` so the route surfaces ``404`` — *not* a silent no-op. This pins
    the corrected contract identified by the audit (item 27 asks the team to
    "decide based on the service code"; the current code path returns 404, so
    that is the locked behaviour).

Constants are read from ``services.flag_service`` so a future
``_MAX_FLAG_NAME_LEN`` bump re-applies the boundary automatically.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

from services.flag_service import _MAX_FLAG_NAME_LEN


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


# ===========================================================================
# Item 26 — POST /api/flags name + label validation
# ===========================================================================


class TestPostFlagValidation:
    """``POST /api/flags`` rejects malformed names and required-field gaps."""

    @pytest.mark.parametrize(
        "bad_name",
        ["Foo", "1bad", "a-b", "a b", "_leading_underscore", "BAD"],
    )
    def test_bad_name_format_returns_400(self, live_url, bad_name):
        """Each rejected pattern triggers ``_validate_flag_name`` -> 400 with
        the regex-explanation message."""
        status, body = _request(
            "POST",
            f"{live_url}/api/flags",
            payload={"name": bad_name, "label": "Some Label"},
        )
        assert status == 400, f"Expected 400 for {bad_name!r}, got {status}: {body}"
        assert body == {
            "error": (
                "Flag name must start with a letter and contain only lowercase "
                "letters, digits and underscores"
            )
        }

    def test_empty_name_returns_400(self, live_url):
        """Empty name short-circuits with ``name and label are required``
        before regex validation."""
        status, body = _request(
            "POST",
            f"{live_url}/api/flags",
            payload={"name": "", "label": "OK"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "name and label are required"}

    def test_whitespace_only_name_returns_400(self, live_url):
        """Blueprint strips whitespace, so an all-whitespace name becomes
        empty -> same 400."""
        status, body = _request(
            "POST",
            f"{live_url}/api/flags",
            payload={"name": "   ", "label": "OK"},
        )
        assert status == 400
        assert body == {"error": "name and label are required"}

    def test_empty_label_returns_400(self, live_url):
        """Same handling for an empty ``label``."""
        status, body = _request(
            "POST",
            f"{live_url}/api/flags",
            payload={"name": "valid_flag_name", "label": ""},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "name and label are required"}

    def test_name_over_max_length_returns_400(self, live_url):
        """Name longer than ``_MAX_FLAG_NAME_LEN`` -> ``Invalid flag name``.
        The length check runs *before* the regex check in
        ``_validate_flag_name``."""
        long_name = "a" + "b" * _MAX_FLAG_NAME_LEN  # _MAX + 1 chars, valid regex
        status, body = _request(
            "POST",
            f"{live_url}/api/flags",
            payload={"name": long_name, "label": "OK"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid flag name"}


# ===========================================================================
# Item 27 — PUT /api/flags/<name> contract
# ===========================================================================


@pytest.fixture()
def existing_user_flag(live_url, unique_name):
    """Create a user flag and return its name."""
    raw = unique_name("putflag").replace("-", "_").lower()
    status, body = _request(
        "POST",
        f"{live_url}/api/flags",
        payload={"name": raw, "label": "Original"},
    )
    assert status == 201, f"Fixture setup failed: {status} {body}"
    return raw


class TestPutFlagContract:
    """``PUT /api/flags/<name>`` error contract per audit item 27."""

    def test_empty_label_returns_400(self, live_url, existing_user_flag):
        """``flag_service.update_flag_label`` raises ``ValueError("label is
        required")`` for empty ``label`` -> 400."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/flags/{existing_user_flag}",
            payload={"label": ""},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "label is required"}

    def test_whitespace_only_label_returns_400(self, live_url, existing_user_flag):
        """Whitespace-only ``label`` is stripped to empty by the blueprint ->
        same 400."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/flags/{existing_user_flag}",
            payload={"label": "   \t  "},
        )
        assert status == 400
        assert body == {"error": "label is required"}

    def test_put_unknown_flag_returns_404(self, live_url):
        """Audit item 27 — pin the contract: PUT to an unknown flag must 404
        (the service raises ``LookupError("Flag not found")``, surfaced as
        404 by the blueprint). This is *not* a silent no-op."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/flags/__never_existed_flag__",
            payload={"label": "Anything"},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Flag not found"}

    def test_put_system_flag_label_returns_400(self, live_url):
        """System flags (e.g. ``is_synced_with_off``) cannot be edited. The
        service raises ``ValueError("Cannot edit system flags")`` -> 400."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/flags/is_synced_with_off",
            payload={"label": "Renamed"},
        )
        assert status == 400, f"Expected 400 for system-flag edit, got {status}: {body}"
        assert body == {"error": "Cannot edit system flags"}

    def test_put_updates_label_when_valid(self, live_url, existing_user_flag):
        """Sanity: a valid PUT actually changes the stored label — confirms the
        404/400 paths above are not over-restrictive."""
        status, _ = _request(
            "PUT",
            f"{live_url}/api/flags/{existing_user_flag}",
            payload={"label": "Renamed"},
        )
        assert status == 200
        # Verify via GET /api/flags
        s, flags = _request("GET", f"{live_url}/api/flags")
        assert s == 200
        match = next((f for f in flags if f["name"] == existing_user_flag), None)
        assert match is not None
        assert match["label"] == "Renamed"
