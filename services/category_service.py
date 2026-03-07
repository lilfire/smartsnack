import sqlite3

from db import get_db
from helpers import _validate_category_name
from translations import _category_label, _get_current_lang, _set_translation_key, _delete_translation_key


def list_categories():
    conn = get_db()
    cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    counts = {}
    for r in conn.execute("SELECT type, COUNT(*) as count FROM products GROUP BY type").fetchall():
        counts[r["type"]] = r["count"]
    return [{"name": c["name"], "emoji": c["emoji"], "label": _category_label(c["name"]), "count": counts.get(c["name"], 0)} for c in cats]


def add_category(name, label, emoji):
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
        raise ValueError("Category already exists")
    lang = _get_current_lang()
    _set_translation_key(f"category_{name}", {lang: label})


def update_category(name, label, emoji):
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
        _set_translation_key(f"category_{name}", {lang: label})


def delete_category(name):
    err = _validate_category_name(name)
    if err:
        raise ValueError(err)
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM products WHERE type = ?", (name,)).fetchone()[0]
    if count > 0:
        raise ValueError(f"Cannot delete: {count} products still use this category")
    conn.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()
    _delete_translation_key(f"category_{name}")
