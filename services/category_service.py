"""Service for managing product categories."""

import sqlite3

from db import get_db
from exceptions import ConflictError
from helpers import _validate_category_name
from translations import (
    _category_label,
    _category_key,
    _get_current_lang,
    _set_translation_key,
    _delete_translation_key,
)


def list_categories() -> list:
    """Return all categories with labels and product counts."""
    conn = get_db()
    cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    counts = {}
    for r in conn.execute(
        "SELECT type, COUNT(*) as count FROM products GROUP BY type"
    ).fetchall():
        counts[r["type"]] = r["count"]
    return [
        {
            "name": c["name"],
            "emoji": c["emoji"],
            "label": _category_label(c["name"]),
            "count": counts.get(c["name"], 0),
        }
        for c in cats
    ]


def add_category(name: str, label: str, emoji: str) -> None:
    """Add a new category with a label and emoji."""
    if not name or not label:
        raise ValueError("name and label are required")
    err = _validate_category_name(name)
    if err:
        raise ValueError(err)
    conn = get_db()
    try:
        conn.execute("INSERT INTO categories (name, emoji) VALUES (?,?)", (name, emoji))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ConflictError("Category already exists") from None
    lang = _get_current_lang()
    _set_translation_key(_category_key(name), {lang: label})


def update_category(name: str, label: str, emoji: str) -> None:
    err = _validate_category_name(name)
    if err:
        raise ValueError(err)
    if not label and not emoji:
        raise ValueError("Nothing to update")
    conn = get_db()
    if emoji:
        conn.execute("UPDATE categories SET emoji = ? WHERE name = ?", (emoji, name))
        conn.commit()
    if label:
        lang = _get_current_lang()
        _set_translation_key(_category_key(name), {lang: label})


def delete_category(name: str, move_to: str | None = None) -> int:
    """Delete a category, optionally moving its products to another."""
    err = _validate_category_name(name)
    if err:
        raise ValueError(err)
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM products WHERE type = ?", (name,)
    ).fetchone()[0]
    if count > 0:
        if not move_to:
            raise ValueError(f"Cannot delete: {count} products still use this category")
        if move_to == name:
            raise ValueError("Cannot move products to the same category")
        err = _validate_category_name(move_to)
        if err:
            raise ValueError(err)
        target = conn.execute(
            "SELECT name FROM categories WHERE name = ?", (move_to,)
        ).fetchone()
        if not target:
            raise ValueError("Target category does not exist")
        conn.execute("UPDATE products SET type = ? WHERE type = ?", (move_to, name))
    conn.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()
    # Translation cleanup is best-effort (file-based, not transactional)
    _delete_translation_key(_category_key(name))
    return count
