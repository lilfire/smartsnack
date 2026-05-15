"""Shared helpers for Groq-dependent E2E tests."""
from contextlib import contextmanager

import pytest


def _is_groq_rate_limit(exc: Exception) -> bool:
    try:
        import groq
        if isinstance(exc, groq.RateLimitError):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return "429" in str(exc) or "rate_limit" in msg or "quota" in msg


@contextmanager
def skip_on_groq_quota():
    """Convert a Groq 429 / TPD quota error into pytest.skip instead of failure."""
    try:
        yield
    except Exception as exc:
        if _is_groq_rate_limit(exc):
            pytest.skip(f"Groq TPD quota exhausted: {exc}")
        raise
