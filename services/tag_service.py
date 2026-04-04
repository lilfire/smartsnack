"""Tag management service."""
import sqlite3

from db import get_db


def list_tags() -> list:
    conn = get_db()
    rows = conn.execute("SELECT id, label FROM tags ORDER BY label COLLATE NOCASE").fetchall()
    return [{"id": r["id"], "label": r["label"]} for r in rows]


def create_tag(label: str) -> dict:
    label = label.strip().lower()
    if not label:
        raise ValueError("label is required")
    if len(label) > 50:
        raise ValueError("label exceeds max length of 50")
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO tags (label) VALUES (?)", (label,))
        conn.commit()
        return {"id": cur.lastrowid, "label": label}
    except sqlite3.IntegrityError:
        raise ValueError("tag_already_exists")


def delete_tag(tag_id: int) -> bool:
    conn = get_db()
    row = conn.execute("SELECT label FROM tags WHERE id = ?", (tag_id,)).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM product_tags WHERE tag = ?", (row["label"],))
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    return True
