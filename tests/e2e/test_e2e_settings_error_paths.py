"""Direct-API error-path tests for ``blueprints/settings.py``.

LSO-1352 Phase 2D-1 audit gaps:

- **#5** — ``PUT /api/settings/off-credentials`` 500 path. The route catches
  ``RuntimeError`` raised by ``settings_service._resolve_secret_key`` and
  surfaces ``{"error": "encryption_not_configured"}`` with status 500. See
  ``blueprints/settings.py:60-63``.
- **#6** — ``PUT /api/settings/ocr`` 400 for an unavailable backend. The
  route guards against selecting a backend whose ``available`` flag is
  ``False`` (missing API key) and returns 400 with a message naming the
  backend. See ``blueprints/settings.py:122-125``.

Conventions (Rules 8, 16, 17, 18):
- Live Flask server via ``live_url``; no browser.
- Boundary mocks against ``services.settings_service`` and
  ``services.ocr_service`` via ``create_autospec`` so the mock shape stays
  pinned to the real signature.
- Every assertion is specific about status and message text.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import create_autospec, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _put(url, payload, timeout=5):
    """PUT JSON to ``url`` and return ``(status, parsed_body)``."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ===========================================================================
# Audit item #5 — PUT /api/settings/off-credentials  → 500
# ===========================================================================


class TestSetOffCredentialsEncryptionMissing:
    """``PUT /api/settings/off-credentials`` returns 500 when encryption is
    not configured.

    Trigger: monkeypatch ``settings_service.set_off_credentials`` to raise a
    ``RuntimeError`` (the real code does this from ``_resolve_secret_key``
    when ``SMARTSNACK_SECRET_KEY`` is unset *and* the data dir is
    unwriteable). The route at ``blueprints/settings.py:60-63`` MUST catch
    that ``RuntimeError`` and return 500 + the *specific* token
    ``encryption_not_configured`` — a generic "internal error" body is a
    Rule 18 violation because the frontend keys behaviour off the token.
    """

    def test_runtime_error_returns_500_with_specific_token(self, live_url):
        """The ``RuntimeError`` arm must produce the documented 500 body."""
        from services import settings_service

        spec = create_autospec(settings_service.set_off_credentials, spec_set=True)
        # Match the real exception emitted by ``_resolve_secret_key``.
        spec.side_effect = RuntimeError(
            "SMARTSNACK_SECRET_KEY environment variable is required"
        )
        with patch("services.settings_service.set_off_credentials", spec):
            status, body = _put(
                f"{live_url}/api/settings/off-credentials",
                {"off_user_id": "off-user", "off_password": "pw"},
            )

        assert status == 500, (
            f"Expected 500 on RuntimeError, got {status}: {body}"
        )
        assert body == {"error": "encryption_not_configured"}, (
            f"Route must return the documented token verbatim; got {body!r}"
        )
        # Service must have been called with both stripped values.
        assert spec.call_count == 1, "Service must be invoked exactly once"
        args, _kwargs = spec.call_args
        assert args == ("off-user", "pw"), (
            f"set_off_credentials must receive (user_id, password) positional "
            f"args; got args={args!r}"
        )

    def test_runtime_error_does_not_leak_original_message(self, live_url):
        """The 500 body must NOT contain the raw exception text — clients
        rely on the stable ``encryption_not_configured`` token, and leaking
        infra details into error bodies is a security smell."""
        from services import settings_service

        spec = create_autospec(settings_service.set_off_credentials, spec_set=True)
        spec.side_effect = RuntimeError(
            "/data/.smartsnack_secret_key: Permission denied"
        )
        with patch("services.settings_service.set_off_credentials", spec):
            status, body = _put(
                f"{live_url}/api/settings/off-credentials",
                {"off_user_id": "x", "off_password": "y"},
            )

        assert status == 500
        assert body == {"error": "encryption_not_configured"}, (
            "Original RuntimeError message must not leak into the response"
        )
        # Defence in depth: explicitly assert the leak-prone substrings are gone.
        raw = json.dumps(body)
        assert "Permission denied" not in raw
        assert "smartsnack_secret_key" not in raw.lower()

    def test_long_password_short_circuits_before_service(self, live_url):
        """The ``_MAX_PASSWORD_LEN`` guard must fire BEFORE the service is
        called — otherwise an oversized password would still trip encryption
        in the service layer. Asserting call_count==0 pins this contract."""
        from config import _MAX_PASSWORD_LEN
        from services import settings_service

        oversized = "a" * (_MAX_PASSWORD_LEN + 1)
        spec = create_autospec(settings_service.set_off_credentials, spec_set=True)
        with patch("services.settings_service.set_off_credentials", spec):
            status, body = _put(
                f"{live_url}/api/settings/off-credentials",
                {"off_user_id": "x", "off_password": oversized},
            )

        assert status == 400, f"Expected 400 for oversized password, got {status}: {body}"
        assert body == {"error": "Password too long"}, (
            f"Expected exact 'Password too long' message, got {body!r}"
        )
        assert spec.call_count == 0, (
            "Service must not be called when password exceeds max length"
        )


# ===========================================================================
# Audit item #6 — PUT /api/settings/ocr → 400 unavailable backend
# ===========================================================================


class TestSetOcrSettingsUnavailableBackend:
    """``PUT /api/settings/ocr`` returns 400 for backends whose ``available``
    flag is ``False`` (missing API key).

    The route at ``blueprints/settings.py:122-125`` builds a dict of
    available backends and checks ``backends[backend_id]["available"]``.
    If false, it returns ``{"error": "Backend '<id>' is not available
    (missing API key)"}`` with status 400 *without* persisting the choice.
    """

    def _make_backends(self, target_id: str, available: bool):
        """Build a fake ``get_available_backends`` payload that flips the
        chosen backend's availability while keeping the rest realistic.

        Args:
            target_id: Backend ID to flip.
            available: New availability flag for ``target_id``.

        Returns:
            List of backend dicts in the same shape as the real service.
        """
        from config import OCR_BACKENDS

        return [
            {
                "id": bid,
                "name": info["name"],
                "available": True if bid == "tesseract" else (
                    available if bid == target_id else False
                ),
            }
            for bid, info in OCR_BACKENDS.items()
        ]

    def test_unavailable_backend_returns_400(self, live_url):
        """Selecting a backend that the OCR service reports as unavailable
        must return 400 with the documented message — *and* the choice must
        NOT have been persisted. The post-state assertion guards against a
        regression where the route returns 400 after writing anyway."""
        from services import ocr_service, settings_service

        backends = self._make_backends("claude_vision", available=False)
        spec = create_autospec(ocr_service.get_available_backends, spec_set=True)
        spec.return_value = backends

        # We do NOT patch set_ocr_backend; the route MUST not reach it.
        real_set = settings_service.set_ocr_backend
        set_calls = []

        def _spy(backend_id):
            set_calls.append(backend_id)
            return real_set(backend_id)

        with patch("services.ocr_service.get_available_backends", spec), \
             patch("services.settings_service.set_ocr_backend", side_effect=_spy):
            status, body = _put(
                f"{live_url}/api/settings/ocr",
                {"backend": "claude_vision"},
            )

        assert status == 400, (
            f"Expected 400 for unavailable backend, got {status}: {body}"
        )
        assert body == {
            "error": "Backend 'claude_vision' is not available (missing API key)"
        }, f"Expected exact route message naming the backend; got {body!r}"
        assert set_calls == [], (
            f"set_ocr_backend must NOT be called when backend is unavailable; "
            f"calls: {set_calls}"
        )

    def test_unavailable_openai_backend_returns_400(self, live_url):
        """Same contract for ``openai``, picked so the message-template
        assertion catches any backend-name interpolation regression."""
        from services import ocr_service

        backends = self._make_backends("openai", available=False)
        spec = create_autospec(ocr_service.get_available_backends, spec_set=True)
        spec.return_value = backends

        with patch("services.ocr_service.get_available_backends", spec):
            status, body = _put(
                f"{live_url}/api/settings/ocr",
                {"backend": "openai"},
            )

        assert status == 400
        assert body == {
            "error": "Backend 'openai' is not available (missing API key)"
        }, f"Expected message naming 'openai'; got {body!r}"

    def test_tesseract_always_available_round_trip(self, live_url):
        """Negative-of-negative: when the chosen backend IS available, the
        route returns 200 and the choice persists. This is the contrast
        case that proves the availability gate is the actual cause of the
        400, not some unrelated guard."""
        from services import ocr_service

        backends = self._make_backends("tesseract", available=True)
        spec = create_autospec(ocr_service.get_available_backends, spec_set=True)
        spec.return_value = backends

        with patch("services.ocr_service.get_available_backends", spec):
            status, body = _put(
                f"{live_url}/api/settings/ocr",
                {"backend": "tesseract"},
            )

        assert status == 200, f"Expected 200 for available backend, got {status}: {body}"
        assert body == {"ok": True, "backend": "tesseract"}, (
            f"Expected echo of selected backend; got {body!r}"
        )

    def test_flipping_availability_changes_outcome(self, live_url):
        """End-to-end proof that the 400/200 difference is *caused* by the
        availability flag — same request payload, two responses, only the
        backend dict differs."""
        from services import ocr_service

        spec = create_autospec(ocr_service.get_available_backends, spec_set=True)

        # First: gemini unavailable → 400.
        spec.return_value = self._make_backends("gemini", available=False)
        with patch("services.ocr_service.get_available_backends", spec):
            denied_status, denied_body = _put(
                f"{live_url}/api/settings/ocr", {"backend": "gemini"}
            )
        assert denied_status == 400
        assert "gemini" in denied_body["error"]

        # Second: gemini available → 200 with the same request payload.
        spec.return_value = self._make_backends("gemini", available=True)
        with patch("services.ocr_service.get_available_backends", spec):
            allowed_status, allowed_body = _put(
                f"{live_url}/api/settings/ocr", {"backend": "gemini"}
            )
        assert allowed_status == 200
        assert allowed_body == {"ok": True, "backend": "gemini"}, (
            f"Availability flag flip must change the outcome; got {allowed_body!r}"
        )
