"""End-to-end edge cases for the translations blueprint.

Phase 2B of the LSO-1352 audit. Covers ``blueprints/translations.py``,
which exposes two GET endpoints:

- ``GET /api/languages`` — returns the list of available languages
  with code / label / flag.
- ``GET /api/translations/<lang>`` — returns translations for the
  given language, or 404.

There is no PUT/POST/DELETE on this blueprint — translation writes are
performed indirectly by category / flag / protein-quality services via
``translations._set_translation_key``. The audit asked for "404 on
non-existent language code" and "lookup non-existent translation key";
the second case is exercised through the category-rename path which
writes a key, GETs the translations, and asserts the key is present.

Rule 16 — fixtures derived from ``config.SUPPORTED_LANGUAGES``.
Rule 18 — every test makes a specific assertion about response shape,
status code, or persisted state.
"""

import json
import urllib.error
import urllib.request

import pytest

from config import SUPPORTED_LANGUAGES


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
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


def _post(url, payload):
    return _request("POST", url, payload=payload)


def _put(url, payload):
    return _request("PUT", url, payload=payload)


# ===========================================================================
# GET /api/languages — shape & content
# ===========================================================================


class TestGetLanguages:
    """``GET /api/languages`` returns one entry per supported language."""

    def test_returns_list_of_dicts(self, live_url):
        status, body = _get(f"{live_url}/api/languages")
        assert status == 200
        assert isinstance(body, list), f"Expected list, got {type(body)}: {body}"
        assert all(isinstance(item, dict) for item in body)

    def test_each_entry_has_required_keys(self, live_url):
        status, body = _get(f"{live_url}/api/languages")
        assert status == 200
        for entry in body:
            assert "code" in entry, f"Missing 'code' in entry: {entry}"
            assert "label" in entry, f"Missing 'label' in entry: {entry}"
            assert "flag" in entry, f"Missing 'flag' in entry: {entry}"

    def test_codes_match_supported_languages(self, live_url):
        """The returned codes are exactly ``SUPPORTED_LANGUAGES``."""
        status, body = _get(f"{live_url}/api/languages")
        assert status == 200
        codes = sorted(entry["code"] for entry in body)
        assert codes == sorted(SUPPORTED_LANGUAGES), (
            f"GET /api/languages codes {codes!r} should equal "
            f"SUPPORTED_LANGUAGES {sorted(SUPPORTED_LANGUAGES)!r}"
        )

    def test_label_is_translated_not_code(self, live_url):
        """``label`` is the translated language name, not just the code."""
        status, body = _get(f"{live_url}/api/languages")
        assert status == 200
        # At least one entry should have a label different from its code.
        differing = [e for e in body if e["label"] != e["code"]]
        assert differing, (
            f"At least one language entry should have a translated label "
            f"different from its code; got: {body}"
        )


# ===========================================================================
# GET /api/translations/<lang> — 404 and 200 paths
# ===========================================================================


class TestGetTranslationsLanguageLookup:
    """``GET /api/translations/<lang>`` returns 200 for known langs, 404 else."""

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_each_supported_lang_returns_200(self, live_url, lang):
        status, body = _get(f"{live_url}/api/translations/{lang}")
        assert status == 200, f"Expected 200 for {lang}: {body}"
        assert isinstance(body, dict), f"Expected dict body: {body}"
        assert body, f"Translations dict for {lang} must be non-empty"

    def test_unknown_language_returns_404(self, live_url):
        """An unknown 2-letter code returns 404 with explanatory error."""
        status, body = _get(f"{live_url}/api/translations/xx")
        assert status == 404, f"Expected 404 for 'xx': {body}"
        assert "error" in body
        assert "unsupported" in body["error"].lower() or (
            "not found" in body["error"].lower()
        )

    def test_unknown_long_string_returns_404(self, live_url):
        """A long bogus code is rejected (regression guard against any silent
        passthrough behaviour for unusual paths)."""
        status, body = _get(
            f"{live_url}/api/translations/definitely_not_a_real_language_code"
        )
        assert status == 404, f"Expected 404: {body}"
        assert "error" in body

    def test_uppercase_supported_language_returns_404(self, live_url):
        """Lookups are case-sensitive — uppercase ``"EN"`` returns 404
        (codes are stored lowercase in ``SUPPORTED_LANGUAGES``)."""
        status, body = _get(f"{live_url}/api/translations/EN")
        assert status == 404, f"Expected 404 for uppercase: {body}"
        assert "error" in body

    def test_returns_well_known_keys(self, live_url):
        """English translations contain ``nav_search`` (UI-critical key)."""
        status, body = _get(f"{live_url}/api/translations/en")
        assert status == 200
        assert "nav_search" in body, (
            f"Expected 'nav_search' in English translations; "
            f"got keys: {list(body.keys())[:20]}..."
        )


# ===========================================================================
# Translation file round-trip via category rename
# ===========================================================================
#
# The blueprint exposes only GETs, but a category POST writes a translation
# key for that category's label. We exercise the full round-trip here:
# POST category → GET translations → key is present → re-GET shows
# the new value (cache-invalidation regression guard).


class TestTranslationFileRoundTrip:
    """Verify writes flow from the category endpoint through to GET."""

    def test_category_label_written_to_translation_file(
        self, live_url, unique_name
    ):
        """Creating a category writes ``category_<slug>`` to every language's
        translation JSON, and the new key is observable via GET."""
        # Use only ASCII letters so the slug equals the category name.
        suffix = unique_name("").replace("-", "").lower()[:8]
        cat_name = f"cat{suffix}"
        new_label = f"E2E Label {suffix}"

        status, _ = _post(
            f"{live_url}/api/categories",
            {"name": cat_name, "label": new_label, "emoji": "\U0001f4e6"},
        )
        assert status == 201, f"Category create failed: {status}"

        # Fetch translations for the default language and assert the key/value
        # round-tripped through the translation JSON file (not just the DB).
        status, trans = _get(f"{live_url}/api/translations/no")
        assert status == 200
        key = f"category_{cat_name}"
        assert key in trans, (
            f"Expected new translation key {key!r} after category create; "
            f"got keys with 'category_' prefix: "
            f"{[k for k in trans if k.startswith('category_')][:10]}..."
        )
        assert trans[key] == new_label, (
            f"Translation value mismatch: expected {new_label!r}, "
            f"got {trans[key]!r}"
        )

    def test_category_label_update_propagates_to_translations(
        self, live_url, unique_name
    ):
        """A PUT to ``/api/categories/<name>`` updates the translation
        immediately; the cache is invalidated so the next GET reflects the
        new value (mtime-based cache regression guard)."""
        suffix = unique_name("").replace("-", "").lower()[:8]
        cat_name = f"cat{suffix}"
        original_label = f"Original {suffix}"
        new_label = f"Updated {suffix}"

        _post(
            f"{live_url}/api/categories",
            {"name": cat_name, "label": original_label, "emoji": "\U0001f4e6"},
        )
        status, trans = _get(f"{live_url}/api/translations/no")
        assert trans[f"category_{cat_name}"] == original_label

        # Update the label
        status, _ = _put(
            f"{live_url}/api/categories/{cat_name}",
            {"label": new_label, "emoji": "\U0001f4e6"},
        )
        assert status == 200, f"Category PUT must succeed: {status}"

        # GET again — must reflect the updated label (cache invalidation).
        status, trans = _get(f"{live_url}/api/translations/no")
        assert status == 200
        assert trans[f"category_{cat_name}"] == new_label, (
            f"Updated label not propagated to GET response; "
            f"got {trans[f'category_{cat_name}']!r}, expected {new_label!r}"
        )
