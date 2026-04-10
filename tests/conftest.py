"""Shared fixtures for SmartSnack unit tests."""

import os
import sys
import shutil

import pytest

# Ensure the project root is on sys.path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _patch_db_path(monkeypatch, db_file):
    """Patch DB_PATH in all modules that import it by value."""
    import config

    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setattr(config, "DB_PATH", db_file)
    try:
        import db as db_mod

        monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _reset_scoring_caches():
    """Reset module-level scoring caches between tests to prevent cross-test pollution."""
    import services.product_scoring as ps
    ps.invalidate_scoring_cache()
    yield
    ps.invalidate_scoring_cache()


@pytest.fixture(autouse=True)
def _env_setup(request, tmp_path, monkeypatch):
    """Set up environment for every test: temp DB path and secret key.

    Skipped for e2e tests, which manage their own server and database.
    """
    import pathlib
    if "e2e" in pathlib.Path(str(request.fspath)).parts:
        return
    db_file = str(tmp_path / "test.sqlite")
    monkeypatch.setenv("SMARTSNACK_SECRET_KEY", "test-secret-key-for-unit-tests")
    _patch_db_path(monkeypatch, db_file)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Create a Flask app with a fresh database."""
    db_file = str(tmp_path / "app_test.sqlite")
    _patch_db_path(monkeypatch, db_file)

    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application


class _CsrfTestClient:
    """Wraps Flask test client to automatically include CSRF header."""

    def __init__(self, inner):
        self._inner = inner

    def _inject(self, kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("X-Requested-With", "SmartSnack")
        kwargs["headers"] = headers
        return kwargs

    def get(self, *a, **kw):
        return self._inner.get(*a, **kw)

    def head(self, *a, **kw):
        return self._inner.head(*a, **kw)

    def options(self, *a, **kw):
        return self._inner.options(*a, **kw)

    def post(self, *a, **kw):
        return self._inner.post(*a, **self._inject(kw))

    def put(self, *a, **kw):
        return self._inner.put(*a, **self._inject(kw))

    def patch(self, *a, **kw):
        return self._inner.patch(*a, **self._inject(kw))

    def delete(self, *a, **kw):
        return self._inner.delete(*a, **self._inject(kw))

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.fixture()
def client(app):
    """Flask test client with automatic CSRF header."""
    return _CsrfTestClient(app.test_client())


@pytest.fixture()
def app_ctx(app):
    """Push an application context for tests that need it."""
    with app.app_context():
        yield app


@pytest.fixture()
def db(app_ctx):
    """Get a database connection within the app context."""
    from db import get_db

    return get_db()


@pytest.fixture()
def seed_category(db):
    """Ensure the default 'Snacks' category exists and return its name."""
    row = db.execute("SELECT name FROM categories WHERE name='Snacks'").fetchone()
    assert row is not None
    return "Snacks"


@pytest.fixture()
def seed_product(db, seed_category):
    """Ensure the demo product exists and return its id."""
    row = db.execute("SELECT id FROM products LIMIT 1").fetchone()
    assert row is not None
    return row["id"]


@pytest.fixture(autouse=True)
def translations_dir(request, tmp_path, monkeypatch):
    """Redirect translations to a temp directory so tests don't pollute real files.

    Skipped for e2e tests, which manage their own setup.
    """
    import pathlib
    if "e2e" in pathlib.Path(str(request.fspath)).parts:
        return None
    import config

    trans_dir = str(tmp_path / "translations")
    os.makedirs(trans_dir, exist_ok=True)
    real_dir = config.TRANSLATIONS_DIR
    if os.path.isdir(real_dir):
        for f in os.listdir(real_dir):
            if f.endswith(".json"):
                shutil.copy(os.path.join(real_dir, f), trans_dir)
    monkeypatch.setattr(config, "TRANSLATIONS_DIR", trans_dir)
    import translations

    monkeypatch.setattr(translations, "TRANSLATIONS_DIR", trans_dir)
    return trans_dir
