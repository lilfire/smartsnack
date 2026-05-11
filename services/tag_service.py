"""Tag CRUD service — Sonarr/Radarr-style shared tag entities."""

import sqlite3

from db import get_db
from config import TAG_LABEL_MAX_LEN


def _row_to_dict(row) -> dict:
    return {"id": row["id"], "label": row["label"]}


def list_tags() -> list[dict]:
    """Return all tags sorted by label (case-insensitive)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, label FROM tags ORDER BY label COLLATE NOCASE ASC"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_tag(tag_id: int) -> dict | None:
    """Return a single tag dict or None if not found."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, label FROM tags WHERE id = ?", (tag_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_tag(label: str) -> dict:
    """Create or return existing tag with the given label.

    Strips whitespace; preserves original case.
    Raises ValueError if label is empty or exceeds TAG_LABEL_MAX_LEN.
    Idempotent: returns existing tag if label already exists (case-insensitive).
    """
    label = label.strip()
    if not label:
        raise ValueError("label is required")
    if len(label) > TAG_LABEL_MAX_LEN:
        raise ValueError(f"label exceeds maximum length of {TAG_LABEL_MAX_LEN}")
    conn = get_db()
    # Check for existing tag (case-insensitive)
    existing = conn.execute(
        "SELECT id, label FROM tags WHERE label = ? COLLATE NOCASE", (label,)
    ).fetchone()
    if existing:
        return _row_to_dict(existing)
    try:
        cur = conn.execute("INSERT INTO tags (label) VALUES (?)", (label,))
        conn.commit()
        return {"id": cur.lastrowid, "label": label}
    except sqlite3.IntegrityError:
        # Race condition: another request inserted the same label
        row = conn.execute(
            "SELECT id, label FROM tags WHERE label = ? COLLATE NOCASE", (label,)
        ).fetchone()
        return _row_to_dict(row)


def update_tag(tag_id: int, label: str) -> dict | None:
    """Rename a tag. Returns updated dict or None if not found.

    Raises ValueError if label is empty, too long, or already used by another tag.
    """
    label = label.strip()
    if not label:
        raise ValueError("label is required")
    if len(label) > TAG_LABEL_MAX_LEN:
        raise ValueError(f"label exceeds maximum length of {TAG_LABEL_MAX_LEN}")
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM tags WHERE label = ? COLLATE NOCASE", (label,)
    ).fetchone()
    if existing and existing["id"] != tag_id:
        raise ValueError("label already exists")
    cur = conn.execute(
        "UPDATE tags SET label = ? WHERE id = ?", (label, tag_id)
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    return {"id": tag_id, "label": label}


def delete_tag(tag_id: int) -> bool:
    """Delete a tag and all its product associations. Returns True if deleted."""
    conn = get_db()
    cur = conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    return cur.rowcount > 0


def get_tags_for_products(product_ids: list[int]) -> dict[int, list[dict]]:
    """Batch-fetch tags for multiple product IDs.

    Returns {product_id: [{id, label}, ...]} with tags sorted by label.
    Product IDs with no tags map to [].
    """
    if not product_ids:
        return {}
    placeholders = ",".join("?" * len(product_ids))
    conn = get_db()
    rows = conn.execute(
        f"SELECT pt.product_id, t.id, t.label"
        f" FROM product_tags pt"
        f" JOIN tags t ON t.id = pt.tag_id"
        f" WHERE pt.product_id IN ({placeholders})"
        f" ORDER BY t.label COLLATE NOCASE ASC",
        product_ids,
    ).fetchall()
    result: dict[int, list[dict]] = {pid: [] for pid in product_ids}
    for row in rows:
        result[row["product_id"]].append({"id": row["id"], "label": row["label"]})
    return result


def set_tags_for_product(product_id: int, tag_ids: list[int]) -> None:
    """Replace all tag associations for a product.

    Ignores tag_ids that do not exist in the tags table.
    Uses DELETE + INSERT in a single transaction.
    """
    conn = get_db()
    conn.execute("DELETE FROM product_tags WHERE product_id = ?", (product_id,))
    if tag_ids:
        placeholders = ",".join("?" * len(tag_ids))
        valid_ids = [
            row["id"]
            for row in conn.execute(
                f"SELECT id FROM tags WHERE id IN ({placeholders})", tag_ids
            ).fetchall()
        ]
        for tid in valid_ids:
            conn.execute(
                "INSERT OR IGNORE INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                (product_id, tid),
            )
    conn.commit()


def search_tags(prefix: str, limit: int = 10) -> list[dict]:
    """Return up to `limit` tags whose label starts with `prefix` (case-insensitive).

    If prefix is empty, returns all tags up to `limit`.
    """
    conn = get_db()
    if prefix:
        rows = conn.execute(
            "SELECT id, label FROM tags"
            " WHERE label LIKE ? ESCAPE '\\'"
            " ORDER BY label COLLATE NOCASE ASC LIMIT ?",
            (prefix.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, label FROM tags ORDER BY label COLLATE NOCASE ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
