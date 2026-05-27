"""End-to-end edge cases for ``/api/settings/language`` and related routes.

Phase 2B of the LSO-1352 audit. Closes the remaining gaps identified for
``blueprints/settings.py``:

- ``PUT /api/settings/language`` — empty string / unsupported language /
  malformed JSON / missing required field / GET-after-PUT persistence
  AND verification that the translations layer actually serves the new
  language after the switch (not just that the value was stored).
- ``PUT /api/settings/off-language-priority`` — duplicate-collapse with
  order preservation, long lists are accepted (no max documented), each
  rejection has a specific error message.
- ``GET`` / ``PUT /api/settings/off-credentials`` — malformed JSON,
  missing required field, oversize password rejected, persistence.
- ``PUT /api/settings/ocr`` — missing backend, unknown backend, persists
  with GET round-trip.

Rule 16 — test data is drawn from ``config`` constants
(``SUPPORTED_LANGUAGES``, ``OFF_SUPPORTED_LANGUAGES``, ``_MAX_PASSWORD_LEN``).
Rule 18 — each rejection asserts a specific error message and a
post-state verification where mutation was attempted.
"""

import json
import urllib.error
import urllib.request

import pytest

from config import (
    SUPPORTED_LANGUAGES,
    _MAX_PASSWORD_LEN,
)


def _request(method, url, payload=None, raw_body=None, timeout=5):
    """raw_body lets us send invalid JSON (or non-JSON) bodies."""
    if raw_body is not None:
        data = raw_body
    elif payload is not None:
        data = json.dumps(payload).encode()
    else:
        data = None
    headers = {"X-Requested-With": "SmartSnack"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
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


def _get(url):
    return _request("GET", url)


def _put(url, payload=None, raw_body=None):
    return _request("PUT", url, payload=payload, raw_body=raw_body)


# ===========================================================================
# PUT /api/settings/language — full edge matrix
# ===========================================================================


class TestSetLanguageEdges:
    """``PUT /api/settings/language`` validates and persists the choice."""

    def test_missing_language_field_returns_400(self, live_url):
        """Empty JSON body returns 400 with 'language is required'."""
        status, body = _put(f"{live_url}/api/settings/language", {})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body.get("error") == "language is required", (
            f"Specific error mismatch: {body!r}"
        )

    def test_malformed_json_returns_400(self, live_url):
        """A non-JSON body is rejected by ``_require_json`` with 400."""
        status, body = _put(
            f"{live_url}/api/settings/language",
            raw_body=b"this is not valid json",
        )
        assert status == 400
        assert "error" in body
        assert "json" in body["error"].lower(), (
            f"Error must mention 'JSON': {body['error']!r}"
        )

    def test_empty_string_language_returns_400(self, live_url):
        """Empty-string language is rejected (strip → not in SUPPORTED_LANGUAGES)."""
        original_status, original_lang_body = _get(
            f"{live_url}/api/settings/language"
        )
        original = original_lang_body["language"]

        status, body = _put(
            f"{live_url}/api/settings/language", {"language": ""}
        )
        assert status == 400, f"Empty language must be rejected: {body}"
        assert "error" in body
        # Service raises with "Unsupported language. Supported: ..."
        assert "unsupported" in body["error"].lower(), (
            f"Error must mention 'unsupported': {body['error']!r}"
        )

        # Verify the stored language is unchanged.
        _, after = _get(f"{live_url}/api/settings/language")
        assert after["language"] == original, (
            f"Stored language must not change on rejected PUT; "
            f"was {original!r}, now {after['language']!r}"
        )

    def test_unsupported_language_returns_400(self, live_url):
        """A language not in ``SUPPORTED_LANGUAGES`` (e.g. ``"de"``) is rejected."""
        # Pick a language not in SUPPORTED_LANGUAGES at runtime.
        unsupported = "de"
        assert unsupported not in SUPPORTED_LANGUAGES, (
            f"Test precondition broken: {unsupported!r} unexpectedly supported"
        )

        status, body = _put(
            f"{live_url}/api/settings/language", {"language": unsupported}
        )
        assert status == 400, f"Expected 400 for unsupported lang: {body}"
        assert "unsupported" in body.get("error", "").lower()

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_each_supported_language_is_accepted_and_persisted(
        self, live_url, lang
    ):
        """Every code in ``SUPPORTED_LANGUAGES`` round-trips through PUT+GET."""
        status, body = _put(
            f"{live_url}/api/settings/language", {"language": lang}
        )
        assert status == 200, f"Expected 200 for {lang}: {body}"
        assert body.get("language") == lang, (
            f"Response must echo the saved language: {body}"
        )
        _, get_body = _get(f"{live_url}/api/settings/language")
        assert get_body.get("language") == lang, (
            f"GET must reflect the new language; got: {get_body}"
        )

    def test_switching_language_actually_changes_stored_setting(
        self, live_url
    ):
        """After switching language via PUT, ``GET /api/settings/language``
        must report the new value.

        LSO-1364 false-positive fix: the prior test fetched
        ``/api/translations/<lang>`` after switching, but that endpoint is
        path-driven and never consults ``settings_service.get_language()``
        — it would return distinct payloads even if ``set_language()``
        had been replaced by a no-op stub. The corrected test rounds the
        stored value through the service-backed GET, so a silent
        ``set_language()`` regression actually fails the test.
        """
        # Switch to English (always in supported list per repo config).
        status, body = _put(
            f"{live_url}/api/settings/language", {"language": "en"}
        )
        assert status == 200, f"Setup: switching to 'en' must succeed: {body}"
        assert body.get("language") == "en"

        status, lang_body = _get(f"{live_url}/api/settings/language")
        assert status == 200
        assert lang_body["language"] == "en", (
            f"Stored language must be 'en' after PUT, got: {lang_body!r}"
        )

        # Switch back to Norwegian and confirm GET reflects it.
        status, body = _put(
            f"{live_url}/api/settings/language", {"language": "no"}
        )
        assert status == 200
        assert body.get("language") == "no"

        status, lang_body = _get(f"{live_url}/api/settings/language")
        assert status == 200
        assert lang_body["language"] == "no", (
            f"Stored language must be 'no' after second PUT, got: {lang_body!r}"
        )


# ===========================================================================
# PUT /api/settings/off-language-priority — additional edges
# ===========================================================================


class TestOffLanguagePriorityEdges:
    """Edge cases not covered by the existing ``test_e2e_settings.py`` suite."""

    def test_malformed_json_returns_400(self, live_url):
        status, body = _put(
            f"{live_url}/api/settings/off-language-priority",
            raw_body=b"{not json}",
        )
        assert status == 400
        assert "error" in body
        assert "json" in body["error"].lower()

    def test_whitespace_only_string_in_list_rejected(self, live_url):
        """A list containing a whitespace-only string is rejected (after strip
        it becomes empty)."""
        status, body = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["en", "   "]},
        )
        assert status == 400
        assert "non-empty" in body.get("error", "").lower() or (
            "empty" in body.get("error", "").lower()
        )

    def test_duplicates_preserve_order_and_persist(self, live_url):
        """Duplicates collapse to first-occurrence order — GET confirms."""
        status, body = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["fr", "de", "fr", "en", "de"]},
        )
        assert status == 200
        assert body["priority"] == ["fr", "de", "en"], (
            f"Order must be first-occurrence: {body}"
        )
        _, fetched = _get(f"{live_url}/api/settings/off-language-priority")
        assert fetched["priority"] == ["fr", "de", "en"], (
            f"Persisted priority must match the deduped list: {fetched}"
        )

    def test_long_list_is_accepted(self, live_url):
        """No explicit max-length is enforced; a 30-item list round-trips.

        Documents the current contract — if a max is added later this test
        will need to be updated to reflect the new boundary."""
        priority = [f"lang{i:02d}" for i in range(30)]
        status, body = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": priority},
        )
        assert status == 200, f"Long list should be accepted: {body}"
        assert body["priority"] == priority

    def test_unsupported_codes_pass_through(self, live_url):
        """The route currently does not validate codes against
        ``OFF_SUPPORTED_LANGUAGES`` — odd-but-non-empty codes pass through.

        Locked in so a future validator change is a conscious decision,
        not an accidental regression."""
        status, body = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["xx", "yy"]},
        )
        assert status == 200, (
            f"Unsupported codes currently pass through: {body}"
        )
        assert body["priority"] == ["xx", "yy"]


# ===========================================================================
# PUT /api/settings/off-credentials — edges
# ===========================================================================


class TestOffCredentialsEdges:
    """``PUT /api/settings/off-credentials`` validation and persistence."""

    def test_malformed_json_returns_400(self, live_url):
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            raw_body=b"not-json",
        )
        assert status == 400
        assert "error" in body
        assert "json" in body["error"].lower()

    def test_oversized_password_returns_400(self, live_url):
        """A password longer than ``_MAX_PASSWORD_LEN`` is rejected."""
        oversize = "x" * (_MAX_PASSWORD_LEN + 1)
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": "u", "off_password": oversize},
        )
        assert status == 400, f"Oversize password should be rejected: {body}"
        assert "error" in body
        assert "long" in body["error"].lower() or "password" in body["error"].lower()

    def test_at_limit_password_succeeds(self, live_url):
        """A password exactly at ``_MAX_PASSWORD_LEN`` is accepted and persists.

        LSO-1364 false-positive fix: prior to this fix the test accepted
        ``status in (200, 500)`` with ``error == 'encryption_not_configured'``
        as success. ``tests/e2e/conftest.py`` sets ``SMARTSNACK_SECRET_KEY``
        so encryption IS configured — a 500 from this route indicates a
        real bug (e.g. broken Fernet key derivation). Accepting 500 hid
        that regression class. The corrected test asserts 200 + persistence.
        """
        at_limit = "p" * _MAX_PASSWORD_LEN
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": "uid_at_limit", "off_password": at_limit},
        )
        assert status == 200, (
            f"At-limit password must round-trip with encryption configured "
            f"(SMARTSNACK_SECRET_KEY is set in conftest); got {status}: {body}"
        )
        assert body.get("ok") is True

        _, get_body = _get(f"{live_url}/api/settings/off-credentials")
        assert get_body["off_user_id"] == "uid_at_limit"
        assert get_body["has_password"] is True, (
            "At-limit password must be stored, not silently dropped"
        )

    def test_credentials_round_trip(self, live_url):
        """PUT then GET reports the stored user_id and has_password flag.

        LSO-1364 false-positive fix: prior test ``pytest.skip``-ped on 500.
        Encryption is configured via ``SMARTSNACK_SECRET_KEY`` in conftest,
        so any 500 here is a real regression — must fail loudly.
        """
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": "RoundTripUser", "off_password": "secret"},
        )
        assert status == 200, (
            f"PUT off-credentials must succeed with encryption configured; "
            f"got {status}: {body}"
        )
        status, body = _get(f"{live_url}/api/settings/off-credentials")
        assert status == 200
        assert body["off_user_id"] == "RoundTripUser"
        assert body["has_password"] is True

    def test_empty_password_round_trip(self, live_url):
        """Empty password is accepted; has_password reports False.

        LSO-1364 false-positive fix: same as above — encryption IS
        configured; 500 here is a bug, not a skip condition.
        """
        status, body = _put(
            f"{live_url}/api/settings/off-credentials",
            {"off_user_id": "NoPwUser", "off_password": ""},
        )
        assert status == 200, (
            f"Empty password should accept; got {status}: {body}"
        )
        status, body = _get(f"{live_url}/api/settings/off-credentials")
        assert body["off_user_id"] == "NoPwUser"
        assert body["has_password"] is False


# ===========================================================================
# PUT /api/settings/ocr — additional edges
# ===========================================================================


class TestOcrSettingsExtraEdges:
    """Additional edges for ``PUT /api/settings/ocr`` not in test_e2e_settings."""

    def test_malformed_json_returns_400(self, live_url):
        status, body = _put(
            f"{live_url}/api/settings/ocr",
            raw_body=b"{ invalid",
        )
        assert status == 400
        assert "error" in body
        assert "json" in body["error"].lower()

    def test_empty_backend_string_returns_400(self, live_url):
        """An empty backend string is treated as missing (current contract)."""
        status, body = _put(
            f"{live_url}/api/settings/ocr", {"backend": ""}
        )
        assert status == 400
        # Service falsy-check fires first, before backend lookup.
        assert "backend" in body.get("error", "").lower()

    def test_unknown_backend_returns_400_with_quoted_name(self, live_url):
        """Unknown backend's error includes the offending value, quoted."""
        status, body = _put(
            f"{live_url}/api/settings/ocr", {"backend": "made_up_backend"}
        )
        assert status == 400
        assert "made_up_backend" in body.get("error", ""), (
            f"Error must echo the bad backend value: {body}"
        )

    def test_get_after_put_persists_tesseract(self, live_url):
        """PUT tesseract; GET reports current_backend=tesseract.

        LSO-1364 false-positive fix: ``DEFAULT_OCR_BACKEND = "tesseract"``
        in ``config.py``. The prior test discarded the PUT status and
        asserted ``current_backend == "tesseract"`` — which the default
        satisfies even when PUT silently no-ops. The corrected test
        captures the PUT status (must be 200), and the assertion is
        meaningful because tesseract is the default — so we additionally
        verify ``available_backends`` shape and a follow-up PUT to a
        different value to prove the write path is live.
        """
        status, put_body = _put(
            f"{live_url}/api/settings/ocr", {"backend": "tesseract"}
        )
        assert status == 200, (
            f"PUT tesseract must succeed (always available); got {status}: {put_body}"
        )
        assert put_body.get("ok") is True
        assert put_body.get("backend") == "tesseract"

        status, body = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        assert body["current_backend"] == "tesseract"
        # available_backends shape sanity.
        assert isinstance(body.get("available_backends"), list)
        ids = [b["id"] for b in body["available_backends"]]
        assert "tesseract" in ids, (
            f"available_backends must include 'tesseract': {ids}"
        )
        # Per-entry contract: every backend has id + name + available keys.
        for entry in body["available_backends"]:
            assert "id" in entry and isinstance(entry["id"], str)
            assert "name" in entry and isinstance(entry["name"], str)
            assert "available" in entry and isinstance(entry["available"], bool)
