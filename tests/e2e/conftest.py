"""Shared fixtures for SmartSnack Playwright e2e tests.

Starts a live Flask server on a temporary SQLite database so that
Playwright can drive a real browser against it.
"""

import os
import shutil
import sys
import threading
import time

import subprocess
import urllib.request

import pytest

# Ensure project root is importable
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


@pytest.fixture(scope="session", autouse=True)
def _inject_csrf_header():
    """Auto-inject X-Requested-With header into all urllib requests for CSRF."""
    _orig_init = urllib.request.Request.__init__

    def _patched_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        if not self.has_header("X-requested-with"):
            self.add_header("X-Requested-With", "SmartSnack")

    urllib.request.Request.__init__ = _patched_init
    yield
    urllib.request.Request.__init__ = _orig_init


_BROWSERS_PATH = "/tmp/ms-playwright"

# Set PLAYWRIGHT_BROWSERS_PATH early so that both the install subprocess
# and the Playwright library resolve the browser from a writable location
# rather than /root/.cache which may be inaccessible in agent containers.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _BROWSERS_PATH)


@pytest.fixture(scope="session", autouse=True)
def _ensure_browsers():
    """Install Playwright Chromium if not already present."""
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": _BROWSERS_PATH}
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        env=env,
    )


@pytest.fixture(scope="session")
def browser(launch_browser):
    """Launch browser, skipping all browser-based tests if unavailable."""
    try:
        b = launch_browser()
    except Exception as exc:
        pytest.skip(f"Browser unavailable in this environment: {exc}")
    yield b
    b.close()


@pytest.fixture(scope="session")
def app_server(tmp_path_factory):
    """Start a live Flask dev server in a background thread.

    Yields the base URL (e.g. ``http://127.0.0.1:<port>``).
    The server is stopped when the session ends.
    """
    db_file = str(tmp_path_factory.mktemp("data") / "e2e.sqlite")

    # Patch DB_PATH BEFORE any app imports so that init_db creates tables
    # in the right file.
    os.environ["DB_PATH"] = db_file
    os.environ["SMARTSNACK_SECRET_KEY"] = "e2e-testing-secret"

    import config

    config.DB_PATH = db_file

    # Redirect translations to a temp directory so e2e tests don't
    # pollute the real translation files.
    trans_dir = str(tmp_path_factory.mktemp("translations"))
    real_dir = config.TRANSLATIONS_DIR
    if os.path.isdir(real_dir):
        for f in os.listdir(real_dir):
            if f.endswith(".json"):
                shutil.copy(os.path.join(real_dir, f), trans_dir)
    config.TRANSLATIONS_DIR = trans_dir

    # Now import db module — it does `from config import DB_PATH` at
    # module level, but since config is already imported and patched,
    # Python's import will re-read the patched value.  However, the
    # `from … import` copies by value, so we also patch the module attr.
    import db as db_mod

    db_mod.DB_PATH = db_file

    # Also patch translations module if already imported
    if "translations" in sys.modules:
        sys.modules["translations"].TRANSLATIONS_DIR = trans_dir

    # Now import the app.  `create_app()` calls `init_db()` which reads
    # db.DB_PATH (a module global).  Since we patched it above, the DB
    # will be created at the temp path.
    from app import create_app

    # create_app was already called at import time (module‑level
    # ``app = create_app()``), but init_db uses the patched path, so
    # tables should exist.  Create a *fresh* application instance for
    # the test server anyway.
    application = create_app()
    application.config["TESTING"] = True
    application.config["RATELIMIT_ENABLED"] = False

    # Disable rate limiting for e2e tests (limiter is already init'd)
    from extensions import limiter as _limiter
    _limiter.enabled = False

    # Ensure the translations module uses the temp directory
    import translations as trans_mod

    trans_mod.TRANSLATIONS_DIR = trans_dir

    import socket

    host = "127.0.0.1"
    # Pick a free port to avoid conflicts with concurrent test runs
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_thread = threading.Thread(
        target=lambda: application.run(host=host, port=port, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to be ready
    import urllib.request

    base_url = f"http://{host}:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("Flask server did not start in time")

    yield base_url


@pytest.fixture()
def live_url(app_server):
    """Convenience alias for the live server base URL."""
    return app_server


@pytest.fixture()
def page(browser, live_url):
    """Create a Playwright page that navigates to the app.

    External CDN requests (Google Fonts, cdnjs, etc.) are blocked so that
    the page doesn't hang waiting for unreachable hosts.
    """
    _page = browser.new_page()
    # Block external resources that can hang in sandboxed environments
    _page.route(
        "**/*",
        lambda route: (
            route.abort()
            if not route.request.url.startswith(live_url)
            else route.continue_()
        ),
    )
    _page.goto(live_url, wait_until="domcontentloaded")
    # Wait for the app to finish initial load (products list populated)
    _page.wait_for_selector("#results-container", state="attached", timeout=10000)
    # Wait for loading spinners to disappear
    _page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )
    yield _page
    _page.close()


# ---------------------------------------------------------------------------
# Helper to register a product via the API (faster than UI for setup)
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_create_product(live_url):
    """Return a callable that creates a product via the REST API."""
    import urllib.request
    import json

    def _create(name="Test Product", category="Snacks", **overrides):
        payload = {
            "name": name,
            "type": category,
            "kcal": 200,
            "fat": 10,
            "saturated_fat": 3,
            "carbs": 25,
            "sugar": 5,
            "protein": 8,
            "fiber": 3,
            "salt": 0.5,
            "smak": 4,
            **overrides,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{live_url}/api/products",
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    return _create
