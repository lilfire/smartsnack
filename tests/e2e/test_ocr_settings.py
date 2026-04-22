"""End-to-end tests for OCR settings feature.

Tests the full request lifecycle through the live Flask server:
GET/PUT /api/settings/ocr, backend availability, dispatch, fallback, and i18n.
"""

import json
import os
import urllib.request
import urllib.error

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url, timeout=5):
    """GET request returning (status, parsed_json)."""
    req = urllib.request.Request(
        url,
        headers={"X-Requested-With": "SmartSnack"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _put(url, payload, timeout=5):
    """PUT request returning (status, parsed_json)."""
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
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, payload, timeout=5):
    """POST request returning (status, parsed_json)."""
    data = json.dumps(payload).encode()
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
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture(autouse=True)
def _clean_ocr_env(app_server):
    """Ensure OCR-related env vars are cleared before each test.

    Saves and restores any pre-existing values so tests don't leak state.
    """
    keys = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]
    saved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ===========================================================================
# Scenario 1: GET /api/settings/ocr returns OCR section
# ===========================================================================


class TestGetOcrSettings:
    """Scenario 1: GET /api/settings/ocr returns expected structure."""

    def test_returns_current_backend_and_available_backends(self, live_url):
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        assert "current_backend" in data
        assert "available_backends" in data
        assert isinstance(data["available_backends"], list)

    def test_default_backend_is_tesseract(self, live_url):
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        assert data["current_backend"] == "tesseract"

    def test_tesseract_always_available(self, live_url):
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        backends = {b["id"]: b for b in data["available_backends"]}
        assert "tesseract" in backends
        assert backends["tesseract"]["available"] is True

    def test_backends_without_keys_show_unavailable(self, live_url):
        """Without any API keys set, non-tesseract backends are unavailable."""
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        backends = {b["id"]: b for b in data["available_backends"]}
        for bid in ("claude_vision", "gemini", "openai"):
            assert backends[bid]["available"] is False


# ===========================================================================
# Scenario 2: Available backends reflect env vars
# ===========================================================================


class TestBackendAvailability:
    """Scenario 2: Setting API key env vars makes backends available."""

    def test_anthropic_key_enables_claude_vision(self, live_url):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        backends = {b["id"]: b for b in data["available_backends"]}
        assert backends["claude_vision"]["available"] is True

    def test_gemini_key_enables_gemini(self, live_url):
        os.environ["GEMINI_API_KEY"] = "test-key-gemini"
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        backends = {b["id"]: b for b in data["available_backends"]}
        assert backends["gemini"]["available"] is True

    def test_openai_key_enables_openai(self, live_url):
        os.environ["OPENAI_API_KEY"] = "test-key-openai"
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        backends = {b["id"]: b for b in data["available_backends"]}
        assert backends["openai"]["available"] is True

    def test_no_keys_only_tesseract_available(self, live_url):
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        available = [b["id"] for b in data["available_backends"] if b["available"]]
        assert available == ["tesseract"]


# ===========================================================================
# Scenario 3: Select and save backend
# ===========================================================================


class TestSelectAndSaveBackend:
    """Scenario 3: PUT /api/settings/ocr saves and persists the backend."""

    def test_save_tesseract_returns_ok(self, live_url):
        status, data = _put(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
        assert status == 200
        assert data["ok"] is True

    def test_saved_backend_persists_on_get(self, live_url):
        _put(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        assert data["current_backend"] == "tesseract"

    def test_save_claude_vision_with_key(self, live_url):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        status, data = _put(
            f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
        )
        assert status == 200
        assert data["ok"] is True
        assert data["backend"] == "claude_vision"
        # Verify persistence
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert data["current_backend"] == "claude_vision"


# ===========================================================================
# Scenario 4: Reject unavailable backend
# ===========================================================================


class TestRejectUnavailableBackend:
    """Scenario 4: PUT /api/settings/ocr rejects invalid/unavailable backends."""

    def test_reject_unavailable_claude_vision(self, live_url):
        """claude_vision without ANTHROPIC_API_KEY should be rejected."""
        status, data = _put(
            f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
        )
        assert status == 400
        assert "error" in data

    def test_reject_nonexistent_backend(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/ocr", {"backend": "nonexistent"}
        )
        assert status == 400
        assert "error" in data

    def test_reject_empty_payload(self, live_url):
        status, data = _put(f"{live_url}/api/settings/ocr", {})
        assert status == 400
        assert "error" in data


# ===========================================================================
# Scenario 5: Fallback behavior
# ===========================================================================


class TestFallbackBehavior:
    """Scenario 5: Stored backend survives key removal; dispatch falls back."""

    def test_get_shows_stored_backend_even_if_unavailable(self, live_url):
        """If we save claude_vision then remove the key, GET still returns it."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        # Remove the key
        del os.environ["ANTHROPIC_API_KEY"]
        status, data = _get(f"{live_url}/api/settings/ocr")
        assert status == 200
        assert data["current_backend"] == "claude_vision"

    def test_dispatch_falls_back_to_tesseract(self, live_url):
        """dispatch_ocr should fall back to tesseract when stored backend is unavailable."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        # Enable fallback so dispatch_ocr will fall back when the key is removed
        _post(f"{live_url}/api/ocr/settings", {"provider": "claude_vision", "fallback_to_tesseract": True})
        del os.environ["ANTHROPIC_API_KEY"]

        import base64
        from unittest.mock import MagicMock
        from services import ocr_service

        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
            b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        image_b64 = base64.b64encode(png_bytes).decode()

        # Patch the _PROVIDERS dict entry directly (dispatch_ocr looks up by key)
        mock_tess = MagicMock(return_value="fallback text")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert data["text"] == "fallback text"
            mock_tess.assert_called_once()
        finally:
            ocr_service._PROVIDERS["tesseract"] = original


# ===========================================================================
# Scenario 6: OCR dispatch uses selected backend
# ===========================================================================


class TestOcrDispatchUsesSelectedBackend:
    """Scenario 6: dispatch_ocr routes to the correct provider."""

    @staticmethod
    def _make_image_b64():
        """Return a minimal valid base64-encoded PNG."""
        import base64

        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
            b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        return base64.b64encode(png_bytes).decode()

    def test_dispatch_uses_tesseract(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        _put(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
        image_b64 = self._make_image_b64()

        mock_tess = MagicMock(return_value="tesseract result")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert data["text"] == "tesseract result"
            mock_tess.assert_called_once()
        finally:
            ocr_service._PROVIDERS["tesseract"] = original

    def test_dispatch_uses_claude_vision(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        _put(f"{live_url}/api/settings/ocr", {"backend": "claude_vision"})
        image_b64 = self._make_image_b64()

        mock_cv = MagicMock(return_value="claude result")
        original = ocr_service._PROVIDERS["claude_vision"]
        ocr_service._PROVIDERS["claude_vision"] = mock_cv
        try:
            status, data = _post(
                f"{live_url}/api/ocr/ingredients", {"image": image_b64}
            )
            assert status == 200
            assert data["text"] == "claude result"
            mock_cv.assert_called_once()
        finally:
            ocr_service._PROVIDERS["claude_vision"] = original


# ===========================================================================
# Scenario 7: i18n keys present
# ===========================================================================


class TestI18nKeysPresent:
    """Scenario 7: All required translation keys exist in all languages."""

    REQUIRED_KEYS = [
        "settings_ocr_title",
        "settings_ocr_subtitle",
        "settings_ocr_saved",
        "settings_ocr_error",
        "settings_ocr_unavailable",
    ]

    @pytest.mark.parametrize("lang", ["en", "no", "se"])
    def test_translation_keys_exist(self, lang):
        translations_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "translations",
        )
        with open(os.path.join(translations_dir, f"{lang}.json"), encoding="utf-8") as f:
            data = json.load(f)
        for key in self.REQUIRED_KEYS:
            assert key in data, f"Missing i18n key '{key}' in {lang}.json"
            assert data[key].strip(), f"Empty i18n key '{key}' in {lang}.json"
