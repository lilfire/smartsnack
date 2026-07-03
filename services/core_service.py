"""Service for core app-level operations (health check, etc.)."""

import sqlite3

from db import get_db


def get_product_count() -> int:
    """Return the total number of products in the database."""
    conn = get_db()
    return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
