"""Service for managing product flag definitions."""

import re
import sqlite3

from db import get_db
from exceptions import ConflictError
from translations import (
    _flag_key,
    _flag_label,
    _get_current_lang,
    _set_translation_key,
    _delete_translation_key,
)

_FLAG_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_FLAG_NAME_LEN = 100


def _validate_flag_name(name: str) -> str | None:
    """Validate a flag name. Returns error string or None."""
    if not name or len(name) > _MAX_FLAG_NAME_LEN:
        return "Invalid flag name"
    if not _FLAG_NAME_RE.match(name):
        return "Flag name must start with a letter and contain only lowercase letters, digits and underscores"
    return None


def list_flags() -> list:
    """Return all flag definitions with translated labels and product counts."""
    conn = get_db()
    rows = conn.execute(
        "SELECT fd.name, fd.type, fd.label_key, "
        "COUNT(pf.product_id) AS count "
        "FROM flag_definitions fd "
        "LEFT JOIN product_flags pf ON pf.flag = fd.name "
        "GROUP BY fd.name, fd.type, fd.label_key "
        "ORDER BY fd.type ASC, fd.name ASC"
    ).fetchall()
    return [
        {
            "name": r["name"],
            "type": r["type"],
            "label_key": r["label_key"],
            "label": _flag_label(r["name"]),
            "count": r["count"],
        }
        for r in rows
    ]


def get_all_flag_names() -> set:
    """Return all flag names from the database."""
    conn = get_db()
    rows = conn.execute("SELECT name FROM flag_definitions").fetchall()
    return {r["name"] for r in rows}


def get_user_flag_names() -> set:
    """Return user flag names from the database."""
    conn = get_db()
    rows = conn.execute(
        "SELECT name FROM flag_definitions WHERE type = 'user'"
    ).fetchall()
    return {r["name"] for r in rows}


def get_flag_config() -> dict:
    """Return flag config dict for frontend consumption."""
    conn = get_db()
    rows = conn.execute(
        "SELECT name, type, label_key FROM flag_definitions ORDER BY type, name"
    ).fetchall()
    return {
        r["name"]: {
            "type": r["type"],
            "labelKey": r["label_key"],
            "label": _flag_label(r["name"]),
        }
        for r in rows
    }


def add_flag(name: str, label: str) -> None:
    """Add a new user flag definition."""
    if not name or not label:
        raise ValueError("name and label are required")
    err = _validate_flag_name(name)
    if err:
        raise ValueError(err)
    conn = get_db()
    label_key = _flag_key(name)
    try:
        conn.execute(
            "INSERT INTO flag_definitions (name, type, label_key) VALUES (?, 'user', ?)",
            (name, label_key),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ConflictError("Flag already exists") from None
    lang = _get_current_lang()
    _set_translation_key(label_key, {lang: label})


def update_flag_label(name: str, label: str) -> None:
    """Update a user flag's translated label."""
    if not label:
        raise ValueError("label is required")
    conn = get_db()
    row = conn.execute(
        "SELECT type, label_key FROM flag_definitions WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        raise ValueError("Flag not found")
    if row["type"] != "user":
        raise ValueError("Cannot edit system flags")
    lang = _get_current_lang()
    _set_translation_key(row["label_key"], {lang: label})


def delete_flag(name: str) -> int:
    """Delete a user flag definition and remove from all products."""
    conn = get_db()
    row = conn.execute(
        "SELECT type, label_key FROM flag_definitions WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        raise ValueError("Flag not found")
    if row["type"] != "user":
        raise ValueError("Cannot delete system flags")
    count = conn.execute(
        "SELECT COUNT(*) FROM product_flags WHERE flag = ?", (name,)
    ).fetchone()[0]
    conn.execute("DELETE FROM product_flags WHERE flag = ?", (name,))
    conn.execute("DELETE FROM flag_definitions WHERE name = ?", (name,))
    conn.commit()
    _delete_translation_key(row["label_key"])
    return count
