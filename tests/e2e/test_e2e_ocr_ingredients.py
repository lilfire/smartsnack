"""End-to-end tests for POST /api/ocr/ingredients.

Tests the full request lifecycle through the live Flask server with mocked
OCR providers. Covers happy path, error responses, edge cases, and both
JSON (base64) and multipart upload paths.
"""

import base64
import io
import json
import os
import urllib.request
import urllib.error

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid 1x1 PNG image
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
    b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
_MINIMAL_PNG_B64 = base64.b64encode(_MINIMAL_PNG).decode()


def _post_json(url, payload, timeout=5):
    """POST JSON request returning (status, parsed_json)."""
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


def _post_multipart(url, image_bytes, filename="test.png", timeout=5):
    """POST multipart/form-data with an image file field."""
    boundary = "----WebKitFormBoundaryE2ETest"
    body = (
        f"------WebKitFormBoundaryE2ETest\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + image_bytes + b"\r\n------WebKitFormBoundaryE2ETest--\r\n"

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary=----WebKitFormBoundaryE2ETest",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _put_json(url, payload, timeout=5):
    """PUT JSON request returning (status, parsed_json)."""
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


@pytest.fixture(autouse=True)
def _clean_ocr_env(app_server):
    """Clear OCR API key env vars before each test."""
    keys = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]
    saved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ===========================================================================
# Happy path: JSON body with base64 image
# ===========================================================================


class TestOcrIngredientsHappyPath:
    """POST /api/ocr/ingredients with a valid image returns extracted text."""

    def test_json_body_returns_text(self, live_url):
        """Valid base64 image via JSON body should return 200 with text."""
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(return_value="sugar, flour, water")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            # Ensure tesseract is selected
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})

            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 200
            assert "text" in data
            assert data["text"] == "sugar, flour, water"
            assert "tesseract" in data["provider"].lower()
            assert data["fallback"] is False
        finally:
            ocr_service._PROVIDERS["tesseract"] = original

    def test_response_shape(self, live_url):
        """Response must include text, provider, and fallback keys."""
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(return_value="ingredients here")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})

            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 200
            assert "text" in data
            assert "provider" in data
            assert "fallback" in data
        finally:
            ocr_service._PROVIDERS["tesseract"] = original


# ===========================================================================
# Edge case: empty OCR result
# ===========================================================================


class TestOcrIngredientsEmptyResult:
    """When the OCR provider returns empty text, endpoint should handle it."""

    def test_empty_text_returns_no_text_error(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(return_value="")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})

            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 200
            assert data["text"] == ""
            assert data["error_type"] == "no_text"
        finally:
            ocr_service._PROVIDERS["tesseract"] = original


# ===========================================================================
# Error cases: no image / missing body
# ===========================================================================


class TestOcrIngredientsValidationErrors:
    """POST /api/ocr/ingredients with invalid input returns proper errors."""

    def test_missing_image_in_json(self, live_url):
        status, data = _post_json(
            f"{live_url}/api/ocr/ingredients", {}
        )
        assert status == 400
        assert "error" in data

    def test_empty_image_string(self, live_url):
        status, data = _post_json(
            f"{live_url}/api/ocr/ingredients",
            {"image": ""},
        )
        assert status == 400
        assert "error" in data

    def test_no_json_body(self, live_url):
        """POST with no body at all should return 400."""
        req = urllib.request.Request(
            f"{live_url}/api/ocr/ingredients",
            data=b"",
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            status = e.code
            body = json.loads(e.read())
        assert status == 400
        assert "error" in body


# ===========================================================================
# Error case: provider exception handling
# ===========================================================================


class TestOcrIngredientsProviderErrors:
    """Provider exceptions should map to structured error responses."""

    def test_value_error_returns_400(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(side_effect=ValueError("Bad image data"))
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 400
            assert "error" in data
        finally:
            ocr_service._PROVIDERS["tesseract"] = original

    def test_timeout_returns_503(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(side_effect=TimeoutError("Provider timed out"))
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 503
            assert data["error_type"] == "provider_timeout"
        finally:
            ocr_service._PROVIDERS["tesseract"] = original

    def test_connection_error_returns_503(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(side_effect=ConnectionError("Connection refused"))
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 503
            assert data["error_type"] == "provider_timeout"
        finally:
            ocr_service._PROVIDERS["tesseract"] = original

    def test_generic_exception_returns_500(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(side_effect=RuntimeError("Unexpected failure"))
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64},
            )
            assert status == 500
            assert "error" in data
            assert data["error_type"] == "generic"
        finally:
            ocr_service._PROVIDERS["tesseract"] = original


# ===========================================================================
# Multipart upload path
# ===========================================================================


class TestOcrIngredientsMultipart:
    """POST /api/ocr/ingredients with multipart/form-data image upload."""

    def test_multipart_upload_returns_text(self, live_url):
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_tess = MagicMock(return_value="salt, pepper")
        original = ocr_service._PROVIDERS["tesseract"]
        ocr_service._PROVIDERS["tesseract"] = mock_tess
        try:
            _put_json(f"{live_url}/api/settings/ocr", {"backend": "tesseract"})
            status, data = _post_multipart(
                f"{live_url}/api/ocr/ingredients",
                _MINIMAL_PNG,
            )
            assert status == 200
            assert data["text"] == "salt, pepper"
            assert "tesseract" in data["provider"].lower()
        finally:
            ocr_service._PROVIDERS["tesseract"] = original


# ===========================================================================
# LSO-1222 multilingual regression — Norwegian/German/Polish biscuit label
# ===========================================================================


class TestOcrIngredientsLSO1222Multilingual:
    """End-to-end coverage for the LSO-1222 fix.

    The OCR provider is mocked to simulate the output a properly-instructed
    vision LLM produces from a Norwegian/German/Polish biscuit label — only
    the Norwegian section, allergens in ALL CAPS, E-numbers preserved, single
    comma-separated line ending in a period. The endpoint must surface that
    output unchanged (apart from the llm_cleanup pass) and never leak any
    German or Polish fragments.
    """

    _NORWEGIAN_ONLY_OUTPUT = (
        "HVETEMEL, sukker, vegetabilsk olje (palme, raps), glukose-fruktosesirup, "
        "MELKPULVER, salt, hevemiddel (E 503, E 500), emulgator (SOYALESITIN), "
        "aroma. Kan inneholde spor av EGG og NØTTER."
    )

    _FORBIDDEN_FRAGMENTS = (
        # German block fragments that the hardened prompt must isolate away
        "ZUTATEN", "ZUCKER", "WEIZENMEHL", "Weizenmehl", "pflanzliche", "Spuren",
        # Polish block fragments
        "SKLADNIKI", "Mąka", "pszenna", "śladowe",
        # Italian block fragments
        "AGENTI LEVITANTI", "INGREDIENTI", "KARBONATDI SODIO",
    )

    def _patch_providers_with_norwegian_only_output(self, monkeypatch_target):
        """Make every LLM provider return the canonical Norwegian-only output.

        Returns (originals, mock) so the caller can restore state.
        """
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_extract = MagicMock(return_value=self._NORWEGIAN_ONLY_OUTPUT)
        originals = {}
        for backend_id in ("claude_vision", "openai", "gemini", "groq", "openrouter"):
            originals[backend_id] = ocr_service._PROVIDERS[backend_id]
            ocr_service._PROVIDERS[backend_id] = mock_extract
        return originals, mock_extract

    def _restore_providers(self, originals):
        from services import ocr_service

        for backend_id, fn in originals.items():
            ocr_service._PROVIDERS[backend_id] = fn

    def test_norwegian_only_output_surfaces_unchanged(self, live_url):
        """When the LLM returns properly-isolated Norwegian text, the API
        delivers it intact (with llm_cleanup_skipped or unchanged cleanup)."""
        from unittest.mock import patch

        originals, _ = self._patch_providers_with_norwegian_only_output(self)
        try:
            # Select an LLM backend that we know is now mocked. We must
            # configure availability so dispatch picks it.
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            _put_json(
                f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
            )

            # Mock llm_cleanup to be a no-op so we observe the dispatch
            # output unchanged.
            with patch(
                "services.llm_cleanup_service.cleanup_ingredients",
                return_value={
                    "text": self._NORWEGIAN_ONLY_OUTPUT,
                    "llm_cleanup_skipped": True,
                },
            ):
                status, data = _post_json(
                    f"{live_url}/api/ocr/ingredients",
                    {"image": _MINIMAL_PNG_B64, "lang": "no"},
                )

            assert status == 200
            assert data["text"] == self._NORWEGIAN_ONLY_OUTPUT
            for forbidden in self._FORBIDDEN_FRAGMENTS:
                assert forbidden not in data["text"], (
                    f"Non-Norwegian fragment {forbidden!r} leaked into endpoint output"
                )
        finally:
            self._restore_providers(originals)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_endpoint_response_has_correct_shape(self, live_url):
        """The endpoint must return the documented {text, llm_cleanup_skipped,
        provider, fallback} shape on the multilingual happy path."""
        from unittest.mock import patch

        originals, _ = self._patch_providers_with_norwegian_only_output(self)
        try:
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            _put_json(
                f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
            )
            with patch(
                "services.llm_cleanup_service.cleanup_ingredients",
                return_value={
                    "text": self._NORWEGIAN_ONLY_OUTPUT,
                    "llm_cleanup_skipped": True,
                },
            ):
                status, data = _post_json(
                    f"{live_url}/api/ocr/ingredients",
                    {"image": _MINIMAL_PNG_B64, "lang": "no"},
                )

            assert status == 200
            assert set(data.keys()) >= {
                "text",
                "llm_cleanup_skipped",
                "provider",
                "fallback",
            }
            assert isinstance(data["llm_cleanup_skipped"], bool)
            assert data["provider"]  # non-empty provider display name
        finally:
            self._restore_providers(originals)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_norwegian_output_ends_with_period_single_line(self, live_url):
        """Phase 2 guarantees a single comma-separated line ending in a period.
        That contract must hold through the endpoint."""
        from unittest.mock import patch

        originals, _ = self._patch_providers_with_norwegian_only_output(self)
        try:
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            _put_json(
                f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
            )
            with patch(
                "services.llm_cleanup_service.cleanup_ingredients",
                return_value={
                    "text": self._NORWEGIAN_ONLY_OUTPUT,
                    "llm_cleanup_skipped": True,
                },
            ):
                status, data = _post_json(
                    f"{live_url}/api/ocr/ingredients",
                    {"image": _MINIMAL_PNG_B64, "lang": "no"},
                )
            assert status == 200
            assert "\n" not in data["text"]
            assert data["text"].rstrip().endswith(".")
        finally:
            self._restore_providers(originals)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_empty_llm_output_produces_no_text_error(self, live_url):
        """Phase 2 Rule 13 says return empty if no target-language section
        is found. The endpoint must surface that as the standard no_text
        error so the frontend can show the right toast."""
        from unittest.mock import MagicMock
        from services import ocr_service

        mock_extract = MagicMock(return_value="")
        original_claude = ocr_service._PROVIDERS["claude_vision"]
        ocr_service._PROVIDERS["claude_vision"] = mock_extract
        try:
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            _put_json(
                f"{live_url}/api/settings/ocr", {"backend": "claude_vision"}
            )
            status, data = _post_json(
                f"{live_url}/api/ocr/ingredients",
                {"image": _MINIMAL_PNG_B64, "lang": "no"},
            )
            assert status == 200
            assert data["text"] == ""
            assert data["error_type"] == "no_text"
            assert data["llm_cleanup_skipped"] is True
        finally:
            ocr_service._PROVIDERS["claude_vision"] = original_claude
            os.environ.pop("ANTHROPIC_API_KEY", None)
