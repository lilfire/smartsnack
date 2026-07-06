"""Shared helpers for Groq-dependent E2E tests."""
from contextlib import contextmanager

import pytest


def _is_groq_rate_limit(exc: Exception) -> bool:
    """Return True for transient Groq failures we should skip in CI.

    Covers both:
      - 429 RateLimitError / TPD quota exhaustion
      - 503 InternalServerError with "over capacity" / "overloaded" (LSO-1802)

    Message-based fallbacks catch cases where the SDK isn't installed or
    the exception was wrapped/reraised without preserving the class.
    """
    try:
        import groq
        if isinstance(exc, groq.RateLimitError):
            return True
        if isinstance(exc, groq.InternalServerError):
            status = getattr(exc, "status_code", None)
            msg_lower = str(exc).lower()
            if status == 503:
                return True
            if "over capacity" in msg_lower or "overloaded" in msg_lower:
                return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return (
        "429" in str(exc)
        or "rate_limit" in msg
        or "quota" in msg
        or "over capacity" in msg
        or "overloaded" in msg
    )


@contextmanager
def skip_on_groq_quota():
    """Convert a transient Groq failure into pytest.skip instead of failure.

    Handles 429 rate-limit / TPD quota AND 503 over-capacity responses so
    upstream flakiness never blocks CI merges (LSO-1802).
    """
    try:
        yield
    except Exception as exc:
        if _is_groq_rate_limit(exc):
            pytest.skip(f"Groq unavailable (quota or over-capacity): {exc}")
        raise
