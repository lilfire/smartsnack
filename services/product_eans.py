"""EAN CRUD operations for products."""

import re
import sqlite3

from db import get_db
from services.product_crud import set_system_flag


def list_eans(pid: int) -> list:
    """List all EANs for a product."""
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    rows = conn.execute(
        "SELECT id, ean, is_primary, synced_with_off FROM product_eans "
        "WHERE product_id = ? ORDER BY is_primary DESC, id ASC",
        (pid,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "ean": r["ean"],
            "is_primary": bool(r["is_primary"]),
            "synced_with_off": bool(r["synced_with_off"]),
        }
        for r in rows
    ]


def add_ean(pid: int, ean: str) -> dict:
    """Add a new EAN to a product. Idempotent: returns existing record if EAN already on this product."""
    ean = ean.strip()
    if not re.fullmatch(r"\d{8,13}", ean):
        raise ValueError("EAN must be 8-13 digits")
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    # Check if EAN already belongs to this product
    existing = conn.execute(
        "SELECT id, ean, is_primary FROM product_eans WHERE product_id = ? AND ean = ?",
        (pid, ean),
    ).fetchone()
    if existing:
        raise ValueError("ean_already_exists")
    count = conn.execute(
        "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
    ).fetchone()[0]
    is_primary = 1 if count == 0 else 0
    try:
        cur = conn.execute(
            "INSERT INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, ?)",
            (pid, ean, is_primary),
        )
    except sqlite3.IntegrityError:
        raise ValueError("ean_already_exists")
    new_id = cur.lastrowid
    if is_primary:
        conn.execute("UPDATE products SET ean = ? WHERE id = ?", (ean, pid))
    conn.commit()
    return {"id": new_id, "ean": ean, "is_primary": bool(is_primary)}


def delete_ean(pid: int, ean_id: int) -> None:
    """Delete an EAN from a product."""
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    row = conn.execute(
        "SELECT id, ean, is_primary, synced_with_off FROM product_eans WHERE id = ? AND product_id = ?",
        (ean_id, pid),
    ).fetchone()
    if not row:
        raise LookupError("EAN not found")
    if row["synced_with_off"]:
        raise ValueError("cannot_delete_synced_ean")
    conn.execute("DELETE FROM product_eans WHERE id = ?", (ean_id,))
    if row["is_primary"]:
        next_row = conn.execute(
            "SELECT id, ean FROM product_eans WHERE product_id = ? ORDER BY id ASC LIMIT 1",
            (pid,),
        ).fetchone()
        if next_row:
            conn.execute(
                "UPDATE product_eans SET is_primary = 1 WHERE id = ?", (next_row["id"],)
            )
            conn.execute(
                "UPDATE products SET ean = ? WHERE id = ?", (next_row["ean"], pid)
            )
    # Check if any remaining EANs are still synced with OFF
    synced_count = conn.execute(
        "SELECT COUNT(*) FROM product_eans WHERE product_id = ? AND synced_with_off = 1",
        (pid,),
    ).fetchone()[0]
    if synced_count == 0:
        set_system_flag(pid, "is_synced_with_off", False)
    conn.commit()


def unsync_ean(pid: int, ean_id: int) -> None:
    """Clear the synced_with_off flag for a single EAN.

    If no synced EANs remain on the product after this, also clears the
    product-level is_synced_with_off system flag.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM product_eans WHERE id = ? AND product_id = ?",
        (ean_id, pid),
    ).fetchone()
    if not row:
        raise LookupError("EAN not found")
    conn.execute(
        "UPDATE product_eans SET synced_with_off = 0 WHERE id = ?", (ean_id,)
    )
    synced_count = conn.execute(
        "SELECT COUNT(*) FROM product_eans "
        "WHERE product_id = ? AND synced_with_off = 1",
        (pid,),
    ).fetchone()[0]
    if synced_count == 0:
        set_system_flag(pid, "is_synced_with_off", False)
    conn.commit()


def set_primary_ean(pid: int, ean_id: int) -> None:
    """Set an EAN as primary for a product."""
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    row = conn.execute(
        "SELECT id, ean FROM product_eans WHERE id = ? AND product_id = ?",
        (ean_id, pid),
    ).fetchone()
    if not row:
        raise LookupError("EAN not found")
    conn.execute(
        "UPDATE product_eans SET is_primary = 0 WHERE product_id = ?", (pid,)
    )
    conn.execute(
        "UPDATE product_eans SET is_primary = 1 WHERE id = ?", (ean_id,)
    )
    conn.execute("UPDATE products SET ean = ? WHERE id = ?", (row["ean"], pid))
    conn.commit()
