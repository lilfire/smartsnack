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
def _env_setup(request, tmp_path, monkeypatch):
    """Set up environment for every test: temp DB path and secret key.

    Skipped for e2e tests, which manage their own server and database.
    """
    if "e2e" in str(request.fspath):
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


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


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


@pytest.fixture()
def translations_dir(tmp_path, monkeypatch):
    """Create a temporary translations directory with minimal files."""
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
