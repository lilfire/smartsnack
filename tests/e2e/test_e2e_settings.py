"""End-to-end tests for OFF language settings endpoints.

Covers:
- GET  /api/settings/off-languages
- GET  /api/settings/off-language-priority
- PUT  /api/settings/off-language-priority
"""

import json
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


# ===========================================================================
# GET /api/settings/off-languages
# ===========================================================================


class TestGetOffLanguages:
    """GET /api/settings/off-languages returns the available OFF language list."""

    def test_returns_200_with_languages_list(self, live_url):
        status, data = _get(f"{live_url}/api/settings/off-languages")
        assert status == 200
        assert "languages" in data
        assert isinstance(data["languages"], list)

    def test_languages_list_is_nonempty(self, live_url):
        status, data = _get(f"{live_url}/api/settings/off-languages")
        assert status == 200
        assert len(data["languages"]) > 0

    def test_languages_contains_common_codes(self, live_url):
        """Should include well-known ISO 639-1 codes."""
        status, data = _get(f"{live_url}/api/settings/off-languages")
        assert status == 200
        langs = data["languages"]
        for code in ("en", "no", "de", "fr", "es"):
            assert code in langs, f"Expected '{code}' in OFF languages"

    def test_languages_are_all_strings(self, live_url):
        status, data = _get(f"{live_url}/api/settings/off-languages")
        assert status == 200
        assert all(isinstance(lang, str) for lang in data["languages"])


# ===========================================================================
# GET /api/settings/off-language-priority
# ===========================================================================


class TestGetOffLanguagePriority:
    """GET /api/settings/off-language-priority returns the priority list."""

    def test_returns_200_with_priority_key(self, live_url):
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert "priority" in data

    def test_default_priority_is_list(self, live_url):
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert isinstance(data["priority"], list)

    def test_default_priority_is_nonempty(self, live_url):
        """Default state should return at least one language (the app language)."""
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert len(data["priority"]) >= 1


# ===========================================================================
# PUT /api/settings/off-language-priority
# ===========================================================================


class TestSetOffLanguagePriority:
    """PUT /api/settings/off-language-priority sets and persists language order."""

    def test_set_priority_happy_path(self, live_url):
        new_priority = ["en", "no", "de"]
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": new_priority},
        )
        assert status == 200
        assert data["priority"] == new_priority

    def test_set_priority_persists_on_get(self, live_url):
        new_priority = ["fr", "es"]
        _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": new_priority},
        )
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert data["priority"] == new_priority

    def test_set_single_language(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["sv"]},
        )
        assert status == 200
        assert data["priority"] == ["sv"]

    def test_deduplicates_preserving_order(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["en", "no", "en", "de", "no"]},
        )
        assert status == 200
        assert data["priority"] == ["en", "no", "de"]

    # --- Validation errors ---

    def test_rejects_missing_priority_key(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority", {}
        )
        assert status == 400
        assert "error" in data

    def test_rejects_non_list_priority(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": "en"},
        )
        assert status == 400
        assert "error" in data

    def test_rejects_empty_list(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": []},
        )
        assert status == 400
        assert "error" in data

    def test_rejects_list_with_empty_strings(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["en", ""]},
        )
        assert status == 400
        assert "error" in data

    def test_rejects_non_string_items(self, live_url):
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": ["en", 123]},
        )
        assert status == 400
        assert "error" in data


# ===========================================================================
# Flow: set priority then verify it persists across reads
# ===========================================================================


class TestOffLanguagePriorityFlow:
    """Integration flow: set -> get -> set -> get round-trip."""

    def test_round_trip(self, live_url):
        # Step 1: Set initial priority
        first = ["da", "sv", "no"]
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": first},
        )
        assert status == 200
        assert data["priority"] == first

        # Step 2: Read back
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert data["priority"] == first

        # Step 3: Update to new priority
        second = ["fi", "en"]
        status, data = _put(
            f"{live_url}/api/settings/off-language-priority",
            {"priority": second},
        )
        assert status == 200
        assert data["priority"] == second

        # Step 4: Read back again
        status, data = _get(f"{live_url}/api/settings/off-language-priority")
        assert status == 200
        assert data["priority"] == second
