"""End-to-end tests for the OCR settings/provider routes.

Direct API tests against the live Flask server for:
  - GET  /api/ocr/providers
  - GET  /api/ocr/settings
  - POST /api/ocr/settings

These routes were previously only covered by Playwright route mocks that
replaced the response payload, so the real handler logic was never exercised
end-to-end (gap report on LSO-1282).

LSO-1288 / LSO-1285. Tests are direct urllib calls against the live Flask
test server; they exercise the real DB persistence path through
``services.ocr_settings_service``.
"""

import json
import os
import urllib.error
import urllib.request

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


def _get_raw(url, timeout=5):
    """GET request returning (status, raw body string)."""
    req = urllib.request.Request(
        url,
        headers={"X-Requested-With": "SmartSnack"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(url, payload, timeout=5, content_type="application/json"):
    """POST request returning (status, parsed_json).

    ``payload`` may be a dict (will be JSON-encoded), a bytes body, or
    None (no body). Pass ``content_type=None`` to omit the header
    altogether.
    """
    if payload is None:
        data = b""
    elif isinstance(payload, (bytes, bytearray)):
        data = bytes(payload)
    else:
        data = json.dumps(payload).encode()
    headers = {"X-Requested-With": "SmartSnack"}
    if content_type is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


_ALL_LLM_KEYS = (
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "LLM_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_ocr_env(app_server):
    """Clear OCR API key env vars before each test; restore after.

    Each test starts with no provider keys so the providers list begins
    at the deterministic baseline (tesseract only).
    """
    saved = {k: os.environ.pop(k, None) for k in _ALL_LLM_KEYS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ===========================================================================
# GET /api/ocr/providers
# ===========================================================================


class TestGetProviders:
    """GET /api/ocr/providers returns availability-filtered provider list."""

    def test_returns_tesseract_only_when_no_keys_set(self, live_url):
        status, data = _get(f"{live_url}/api/ocr/providers")
        assert status == 200
        assert "providers" in data
        assert isinstance(data["providers"], list)
        keys = [p["key"] for p in data["providers"]]
        assert keys == ["tesseract"]

    def test_returns_multiple_providers_when_keys_set(self, live_url):
        os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-test"
        os.environ["GEMINI_API_KEY"] = "sk-gemini-test"
        os.environ["OPENAI_API_KEY"] = "sk-openai-test"

        status, data = _get(f"{live_url}/api/ocr/providers")
        assert status == 200
        keys = [p["key"] for p in data["providers"]]
        # tesseract is always first; the other three are present when keyed.
        assert keys[0] == "tesseract"
        assert set(keys) == {"tesseract", "claude_vision", "gemini", "openai"}

    def test_each_provider_entry_has_required_fields(self, live_url):
        os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-test"
        status, data = _get(f"{live_url}/api/ocr/providers")
        assert status == 200
        for entry in data["providers"]:
            assert set(entry.keys()) >= {"key", "label", "models"}
            assert isinstance(entry["key"], str) and entry["key"]
            assert isinstance(entry["label"], str) and entry["label"]
            assert isinstance(entry["models"], list)

    def test_provider_models_list_matches_config(self, live_url):
        """Each provider's ``models`` list must match the OCR_BACKENDS config."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-anthropic-test"
        os.environ["GEMINI_API_KEY"] = "sk-gemini-test"
        from config import OCR_BACKENDS

        status, data = _get(f"{live_url}/api/ocr/providers")
        assert status == 200
        for entry in data["providers"]:
            expected_models = OCR_BACKENDS[entry["key"]].get("models", [])
            assert entry["models"] == expected_models

    def test_no_api_key_values_leak_in_response(self, live_url):
        """The provider endpoint must never echo back the actual API keys."""
        secret = "sk-secret-do-not-leak-1234567890"
        os.environ["ANTHROPIC_API_KEY"] = secret
        status, body = _get_raw(f"{live_url}/api/ocr/providers")
        assert status == 200
        assert secret not in body

    def test_unkeyed_provider_excluded(self, live_url):
        """Providers without a configured env key must not appear."""
        # ANTHROPIC_API_KEY is intentionally not set.
        status, data = _get(f"{live_url}/api/ocr/providers")
        assert status == 200
        keys = [p["key"] for p in data["providers"]]
        assert "claude_vision" not in keys
        assert "gemini" not in keys
        assert "openai" not in keys


# ===========================================================================
# GET /api/ocr/settings — default shape and post-save round-trip
# ===========================================================================


class TestGetSettings:
    """GET /api/ocr/settings returns persisted OCR settings."""

    def test_default_response_shape(self, live_url):
        """With no saved settings the endpoint returns documented defaults."""
        status, data = _get(f"{live_url}/api/ocr/settings")
        assert status == 200
        assert data["provider"] == "tesseract"
        assert data["fallback_to_tesseract"] is False
        assert "models" in data
        assert isinstance(data["models"], dict)

    def test_models_dict_has_entry_per_fixed_list_provider(self, live_url):
        """The default ``models`` dict pre-populates the first model for each
        provider with a fixed model list (and ``openrouter`` is special)."""
        from config import OCR_BACKENDS

        status, data = _get(f"{live_url}/api/ocr/settings")
        assert status == 200
        for provider_key, info in OCR_BACKENDS.items():
            provider_models = info.get("models", [])
            if provider_models:
                # Default selection is the first model in the configured list.
                assert data["models"].get(provider_key) == provider_models[0]

    def test_get_reflects_persisted_post(self, live_url):
        """POST then GET round-trip — persisted provider + flag come back."""
        post_status, _ = _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "claude_vision", "fallback_to_tesseract": True},
        )
        assert post_status == 200

        get_status, data = _get(f"{live_url}/api/ocr/settings")
        assert get_status == 200
        assert data["provider"] == "claude_vision"
        assert data["fallback_to_tesseract"] is True

    def test_get_reflects_persisted_model_selection(self, live_url):
        """POSTed model selection comes back via GET."""
        _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "openai",
                "fallback_to_tesseract": False,
                "models": {"openai": "gpt-4o-mini"},
            },
        )
        get_status, data = _get(f"{live_url}/api/ocr/settings")
        assert get_status == 200
        assert data["models"].get("openai") == "gpt-4o-mini"


# ===========================================================================
# POST /api/ocr/settings — happy paths
# ===========================================================================


class TestPostSettingsHappyPath:
    """POST /api/ocr/settings success cases."""

    def test_save_valid_provider_returns_ok(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "gemini", "fallback_to_tesseract": True},
        )
        assert status == 200
        assert data == {"ok": True}

    def test_persistence_round_trip(self, live_url):
        """After POSTing settings, GET must return the saved values."""
        _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "openai", "fallback_to_tesseract": False},
        )
        _, data = _get(f"{live_url}/api/ocr/settings")
        assert data["provider"] == "openai"
        assert data["fallback_to_tesseract"] is False

    def test_save_with_valid_model_for_fixed_list_provider(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "claude_vision",
                "fallback_to_tesseract": False,
                "models": {"claude_vision": "claude-haiku-4-5-20251001"},
            },
        )
        assert status == 200
        assert data == {"ok": True}
        # And the model is persisted
        _, get_data = _get(f"{live_url}/api/ocr/settings")
        assert get_data["models"].get("claude_vision") == "claude-haiku-4-5-20251001"

    def test_openrouter_free_text_model_accepted(self, live_url):
        """OpenRouter uses free-text model names — any non-empty string is ok."""
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": "anthropic/claude-3.5-sonnet"},
            },
        )
        assert status == 200
        assert data == {"ok": True}
        _, get_data = _get(f"{live_url}/api/ocr/settings")
        assert get_data["models"].get("openrouter") == "anthropic/claude-3.5-sonnet"

    def test_models_omitted_preserves_existing_selection(self, live_url):
        """When ``models`` is omitted, existing per-provider model selections
        must be preserved (not reset to default)."""
        _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "openai",
                "fallback_to_tesseract": False,
                "models": {"openai": "gpt-4o-mini"},
            },
        )
        _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "openai", "fallback_to_tesseract": False},
        )
        _, data = _get(f"{live_url}/api/ocr/settings")
        assert data["models"].get("openai") == "gpt-4o-mini"


# ===========================================================================
# POST /api/ocr/settings — validation failures
# ===========================================================================


class TestPostSettingsValidation:
    """POST /api/ocr/settings rejects malformed payloads with 400."""

    def test_missing_provider_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {"fallback_to_tesseract": True},
        )
        assert status == 400
        assert "error" in data
        assert "provider" in data["error"].lower()

    def test_unknown_provider_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "bogus_provider", "fallback_to_tesseract": False},
        )
        assert status == 400
        assert "error" in data

    def test_models_not_an_object_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "tesseract",
                "fallback_to_tesseract": False,
                "models": ["gpt-4o-mini"],
            },
        )
        assert status == 400
        assert "models" in data["error"].lower()

    def test_models_with_unknown_provider_key_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "tesseract",
                "fallback_to_tesseract": False,
                "models": {"definitely_not_a_provider": "some-model"},
            },
        )
        assert status == 400
        assert "definitely_not_a_provider" in data["error"]

    def test_invalid_model_for_fixed_list_provider_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "gemini",
                "fallback_to_tesseract": False,
                "models": {"gemini": "gemini-nonexistent-model"},
            },
        )
        assert status == 400
        assert "gemini-nonexistent-model" in data["error"]

    def test_openrouter_empty_string_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": ""},
            },
        )
        assert status == 400
        assert "OpenRouter" in data["error"]

    def test_openrouter_non_string_returns_400(self, live_url):
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            {
                "provider": "openrouter",
                "fallback_to_tesseract": False,
                "models": {"openrouter": 12345},
            },
        )
        assert status == 400
        assert "OpenRouter" in data["error"]

    def test_missing_body_returns_400(self, live_url):
        """No body at all must be rejected as a 400 before any persistence."""
        status, data = _post(
            f"{live_url}/api/ocr/settings",
            None,
        )
        assert status == 400
        assert "error" in data

    def test_failed_validation_does_not_persist(self, live_url):
        """A 400 response from POST must NOT mutate the saved settings."""
        # Establish a known baseline first.
        _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "tesseract", "fallback_to_tesseract": False},
        )
        # Now send a bad payload.
        status, _ = _post(
            f"{live_url}/api/ocr/settings",
            {"provider": "bogus_provider"},
        )
        assert status == 400
        # Confirm the baseline survived.
        _, data = _get(f"{live_url}/api/ocr/settings")
        assert data["provider"] == "tesseract"
        assert data["fallback_to_tesseract"] is False
