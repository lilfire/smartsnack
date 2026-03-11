"""Shared fixtures for SmartSnack Playwright e2e tests.

Starts a live Flask server on a temporary SQLite database so that
Playwright can drive a real browser against it.
"""

import os
import sys
import threading
import time

import subprocess

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture(scope="session", autouse=True)
def _ensure_browsers():
    """Install Playwright Chromium if not already present."""
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


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

    # Now import db module — it does `from config import DB_PATH` at
    # module level, but since config is already imported and patched,
    # Python's import will re-read the patched value.  However, the
    # `from … import` copies by value, so we also patch the module attr.
    import db as db_mod
    db_mod.DB_PATH = db_file

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

    host, port = "127.0.0.1", 5199

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
def page(page, live_url):
    """Override the default Playwright page fixture to navigate to the app.

    External CDN requests (Google Fonts, cdnjs, etc.) are blocked so that
    the page doesn't hang waiting for unreachable hosts.
    """
    # Block external resources that can hang in sandboxed environments
    page.route("**/*", lambda route: (
        route.abort() if not route.request.url.startswith(live_url) else route.continue_()
    ))
    page.goto(live_url, wait_until="domcontentloaded")
    # Wait for the app to finish initial load (products list populated)
    page.wait_for_selector("#results-container", state="attached", timeout=10000)
    # Wait for loading spinners to disappear
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )
    return page


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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    return _create
