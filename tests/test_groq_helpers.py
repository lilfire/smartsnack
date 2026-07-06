"""Unit tests for tests/e2e/groq_helpers.py — the E2E skip-on-transient-Groq helper.

Regression coverage for LSO-1802: the helper originally only recognised 429
rate-limit errors, causing 503 "over capacity" InternalServerError to hard-fail
Groq vision E2E tests. The helper must now skip on both.
"""
import httpx
import pytest


def _fake_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "https://api.groq.com/v1/x"))


class TestIsGroqRateLimit:
    """LSO-1802 §1: _is_groq_rate_limit must recognise both 429 and 503."""

    def test_rate_limit_error_429_matches(self):
        import groq
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = groq.RateLimitError(
            "rate_limit_exceeded", response=_fake_response(429), body=None
        )
        assert _is_groq_rate_limit(exc) is True

    def test_internal_server_error_503_matches(self):
        """LSO-1802: 503 InternalServerError from Groq over-capacity must skip."""
        import groq
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = groq.InternalServerError(
            "model is currently over capacity. Please try again and back off exponentially.",
            response=_fake_response(503),
            body=None,
        )
        assert _is_groq_rate_limit(exc) is True

    def test_over_capacity_message_matches_by_text(self):
        """When status isn't 503 but the message names over capacity, still skip.

        Guards against upstream reshuffling that surfaces the same class through
        a different status (e.g. wrapped as APIError with 502).
        """
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = RuntimeError("Upstream error: model is currently over capacity")
        assert _is_groq_rate_limit(exc) is True

    def test_overloaded_message_matches_by_text(self):
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = RuntimeError("Provider overloaded, try again later")
        assert _is_groq_rate_limit(exc) is True

    def test_quota_message_matches(self):
        from tests.e2e.groq_helpers import _is_groq_rate_limit
        assert _is_groq_rate_limit(RuntimeError("token quota exceeded")) is True

    def test_429_marker_in_message_matches(self):
        from tests.e2e.groq_helpers import _is_groq_rate_limit
        assert _is_groq_rate_limit(RuntimeError("HTTP 429 Too Many Requests")) is True

    def test_generic_500_does_not_match(self):
        """A non-503 InternalServerError without over-capacity wording is a
        real bug — do NOT swallow it as a skip."""
        import groq
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = groq.InternalServerError(
            "Internal error while processing prompt",
            response=_fake_response(500),
            body=None,
        )
        assert _is_groq_rate_limit(exc) is False

    def test_unrelated_error_does_not_match(self):
        from tests.e2e.groq_helpers import _is_groq_rate_limit
        assert _is_groq_rate_limit(ValueError("invalid image encoding")) is False

    def test_authentication_error_does_not_match(self):
        """Auth failures must surface, not be silently skipped."""
        import groq
        from tests.e2e.groq_helpers import _is_groq_rate_limit

        exc = groq.AuthenticationError(
            "Invalid API key", response=_fake_response(401), body=None
        )
        assert _is_groq_rate_limit(exc) is False


class TestSkipOnGroqQuota:
    """LSO-1802 §2: skip_on_groq_quota converts transient errors to pytest.skip."""

    def test_skips_on_429(self):
        import groq
        from tests.e2e.groq_helpers import skip_on_groq_quota

        with pytest.raises(pytest.skip.Exception):
            with skip_on_groq_quota():
                raise groq.RateLimitError(
                    "rate limited", response=_fake_response(429), body=None
                )

    def test_skips_on_503_over_capacity(self):
        """LSO-1802: the exact failure that caused CI red."""
        import groq
        from tests.e2e.groq_helpers import skip_on_groq_quota

        with pytest.raises(pytest.skip.Exception):
            with skip_on_groq_quota():
                raise groq.InternalServerError(
                    "model is currently over capacity",
                    response=_fake_response(503),
                    body=None,
                )

    def test_reraises_unrelated_errors(self):
        from tests.e2e.groq_helpers import skip_on_groq_quota

        with pytest.raises(ValueError, match="bad input"):
            with skip_on_groq_quota():
                raise ValueError("bad input")

    def test_reraises_non_transient_500(self):
        import groq
        from tests.e2e.groq_helpers import skip_on_groq_quota

        with pytest.raises(groq.InternalServerError):
            with skip_on_groq_quota():
                raise groq.InternalServerError(
                    "Internal error", response=_fake_response(500), body=None
                )

    def test_no_error_returns_normally(self):
        from tests.e2e.groq_helpers import skip_on_groq_quota

        with skip_on_groq_quota():
            pass  # no exception → normal completion


class TestGroqBackendRetry:
    """LSO-1802 §3: services/ocr_backends/groq.extract retries transient 503s.

    Production code must be resilient to the same over-capacity responses that
    make E2E flaky — a single retry-loop keeps user-facing OCR working when
    Groq returns 503 for the first attempt only.
    """

    def _patch_sleep(self, monkeypatch):
        """Skip real sleep between retries to keep the test fast."""
        from services.ocr_backends import groq as backend
        monkeypatch.setattr(backend, "_sleep", lambda _s: None)

    def test_extract_retries_then_succeeds_on_503(self, monkeypatch):
        import groq as groq_sdk
        from services.ocr_backends import groq as backend
        from unittest.mock import MagicMock, patch

        self._patch_sleep(monkeypatch)

        # First call raises 503, second call succeeds.
        overload = groq_sdk.InternalServerError(
            "model is currently over capacity",
            response=_fake_response(503),
            body=None,
        )
        good = MagicMock()
        good.choices = [MagicMock()]
        good.choices[0].message.content = "sukker, mel"

        with patch("groq.Groq") as mock_cls:
            client = mock_cls.return_value
            client.chat.completions.create.side_effect = [overload, good]
            result = backend.extract("dGVzdA==", "no")

        assert result == "sukker, mel"
        assert client.chat.completions.create.call_count == 2

    def test_extract_gives_up_after_max_attempts(self, monkeypatch):
        import groq as groq_sdk
        from services.ocr_backends import groq as backend
        from unittest.mock import patch

        self._patch_sleep(monkeypatch)

        overload = groq_sdk.InternalServerError(
            "model is currently over capacity",
            response=_fake_response(503),
            body=None,
        )

        with patch("groq.Groq") as mock_cls:
            client = mock_cls.return_value
            client.chat.completions.create.side_effect = [overload] * 5

            with pytest.raises(groq_sdk.InternalServerError):
                backend.extract("dGVzdA==", "no")

            # Retries 3 times total (initial + 2 retries per LSO-1802 spec).
            assert client.chat.completions.create.call_count == backend._RETRY_ATTEMPTS

    def test_extract_does_not_retry_on_authentication_error(self, monkeypatch):
        """Auth errors must fail fast — retrying would only extend user pain."""
        import groq as groq_sdk
        from services.ocr_backends import groq as backend
        from unittest.mock import patch

        self._patch_sleep(monkeypatch)

        auth_err = groq_sdk.AuthenticationError(
            "Invalid API key", response=_fake_response(401), body=None
        )

        with patch("groq.Groq") as mock_cls:
            client = mock_cls.return_value
            client.chat.completions.create.side_effect = auth_err

            with pytest.raises(groq_sdk.AuthenticationError):
                backend.extract("dGVzdA==", "no")

            assert client.chat.completions.create.call_count == 1

    def test_extract_uses_exponential_backoff(self, monkeypatch):
        """Sleeps must grow 2s → 4s (base 2s, doubling) per Groq guidance."""
        import groq as groq_sdk
        from services.ocr_backends import groq as backend
        from unittest.mock import MagicMock, patch

        sleeps: list[float] = []
        monkeypatch.setattr(backend, "_sleep", lambda s: sleeps.append(s))

        overload = groq_sdk.InternalServerError(
            "over capacity", response=_fake_response(503), body=None
        )
        good = MagicMock()
        good.choices = [MagicMock()]
        good.choices[0].message.content = "ok"

        with patch("groq.Groq") as mock_cls:
            client = mock_cls.return_value
            # Fail twice then succeed → two backoff sleeps.
            client.chat.completions.create.side_effect = [overload, overload, good]
            backend.extract("dGVzdA==", "no")

        assert sleeps == [2, 4], f"expected exponential backoff [2, 4], got {sleeps}"


class TestIsTransientOverload:
    """LSO-1802 §4: _is_transient_overload classifies only real 503 overloads."""

    def test_503_over_capacity_is_transient(self):
        import groq
        from services.ocr_backends.groq import _is_transient_overload
        exc = groq.InternalServerError(
            "model is currently over capacity",
            response=_fake_response(503),
            body=None,
        )
        assert _is_transient_overload(exc) is True

    def test_non_503_internal_error_not_transient(self):
        import groq
        from services.ocr_backends.groq import _is_transient_overload
        exc = groq.InternalServerError(
            "Internal error", response=_fake_response(500), body=None
        )
        assert _is_transient_overload(exc) is False

    def test_rate_limit_not_treated_as_transient(self):
        """429 needs longer backoff than server-side 503 — do not conflate."""
        import groq
        from services.ocr_backends.groq import _is_transient_overload
        exc = groq.RateLimitError(
            "too many requests", response=_fake_response(429), body=None
        )
        assert _is_transient_overload(exc) is False

    def test_unrelated_error_not_transient(self):
        from services.ocr_backends.groq import _is_transient_overload
        assert _is_transient_overload(ValueError("bad")) is False
