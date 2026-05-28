"""E2E test for the Flask-Limiter rate limiter.

``conftest.py`` (lines around 147-151) disables the rate limiter globally
for every other e2e test — that's the only practical way to keep the
suite from tripping its own limits while exercising endpoints back-to-back.
The downside is that the rate-limiter wiring has zero e2e coverage and a
regression that silently dropped the ``@limiter.limit("…")`` decorators
would not be caught.

This module re-enables the limiter for the duration of its own class via a
class-scoped fixture, exercises a representative low-budget endpoint
(``/api/backup``, 5 per minute), and asserts a 429 is returned after the
threshold. The fixture is strictly scoped: it flips ``limiter.enabled``
back to ``False`` on teardown and resets the in-memory counters both
before and after the class, so the global "limiter disabled" invariant is
restored for the rest of the suite.

The seed ``api_create_product`` and ``unique_name`` fixtures are not used
here — ``/api/backup`` operates on whatever DB state exists, including the
empty post-snapshot state.
"""

import json
import urllib.error
import urllib.request

import pytest


class TestBackupRateLimit:
    """Rate-limit guard for POST/GET ``/api/backup`` (5 per minute)."""

    @pytest.fixture(autouse=True, scope="class")
    def _enable_limiter(self):
        """Re-enable the global Flask-Limiter for this class only.

        ``conftest.app_server`` sets ``limiter.enabled = False`` at session
        scope; this fixture flips it back to ``True`` and clears the
        in-memory counter store so this class starts from zero and does
        not pollute later tests. On teardown the global state is restored
        so the rest of the e2e suite continues to bypass rate limiting.
        """
        from extensions import limiter

        limiter.enabled = True
        # The MemoryStorage backend supports reset(); calling it via the
        # public `limiter.reset()` is safe without an active Flask app
        # context because it simply delegates to `self.storage.reset()`.
        limiter.reset()
        try:
            yield
        finally:
            limiter.reset()
            limiter.enabled = False

    @pytest.fixture(autouse=True)
    def _reset_limiter_between_tests(self):
        """Clear counters before every test in the class so each test starts fresh."""
        from extensions import limiter

        limiter.reset()
        yield

    def test_rate_limit_returns_429_after_threshold(self, live_url):
        """``GET /api/backup`` returns 429 once the 5-per-minute cap is exceeded.

        The five permitted calls must all succeed (HTTP 200), and the sixth
        must surface as a 429 Too Many Requests. Flask-Limiter uses the
        client IP as the bucket key, so all six requests share the same
        local 127.0.0.1 bucket and the rate-limit decision is deterministic.
        """
        threshold = 5
        statuses = []

        def _hit_backup() -> int:
            req = urllib.request.Request(
                f"{live_url}/api/backup", method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    # Drain so the connection is closed even if Flask
                    # streams the response.
                    resp.read()
                    return resp.status
            except urllib.error.HTTPError as exc:
                # Drain the error body too — without this, the next request
                # may reuse the socket and behave unpredictably.
                exc.read()
                return exc.code

        # The first ``threshold`` requests must all be accepted.
        for i in range(threshold):
            status = _hit_backup()
            statuses.append(status)
            assert status == 200, (
                f"Request #{i + 1} was rejected with status {status}. "
                f"All status codes so far: {statuses}. "
                f"The limiter should accept the first {threshold} requests."
            )

        # The next one must trip the limit.
        over_status = _hit_backup()
        statuses.append(over_status)
        assert over_status == 429, (
            f"Expected HTTP 429 on request #{threshold + 1}, got {over_status}. "
            f"All status codes: {statuses}. "
            f"Either the @limiter.limit('5 per minute') decorator on /api/backup "
            f"is missing, or the limiter is not enabled in this run."
        )
