"""Duplicate detection and product merging."""

from db import get_db
from config import ALL_PRODUCT_FIELDS


def _find_duplicate(ean, name, exclude_id=None):
    """Find an existing product matching by EAN or name.

    Returns dict with id, name, ean, match_type, is_synced_with_off,
    and all product field values — or None if no duplicate found.
    """
    conn = get_db()
    cur = conn.cursor()

    fields_sql = ", ".join(f"p.{f}" for f in ALL_PRODUCT_FIELDS)
    ean_subquery = "(SELECT pe2.ean FROM product_eans pe2 WHERE pe2.product_id = p.id AND pe2.is_primary = 1) AS ean"

    # Check EAN match first (if ean is provided and non-empty)
    if ean and ean.strip():
        exclude_clause = "AND p.id != ?" if exclude_id else ""
        params = [ean.strip()]
        if exclude_id:
            params.append(exclude_id)
        row = cur.execute(
            f"""SELECT p.id, {fields_sql}, {ean_subquery},
                   EXISTS(SELECT 1 FROM product_flags pf
                          WHERE pf.product_id = p.id AND pf.flag = 'is_synced_with_off')
                   AS is_synced_with_off
            FROM products p
            WHERE EXISTS (SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id AND pe.ean = ?) {exclude_clause}
            LIMIT 1""",
            params,
        ).fetchone()
        if row:
            result = {f: row[f] for f in ALL_PRODUCT_FIELDS}
            result["id"] = row["id"]
            result["ean"] = row["ean"]
            result["match_type"] = "ean"
            result["is_synced_with_off"] = bool(row["is_synced_with_off"])
            return result

    # Then check name match (case-insensitive) for products without a primary EAN
    if name and name.strip():
        exclude_clause = "AND p.id != ?" if exclude_id else ""
        params = [name.strip()]
        if exclude_id:
            params.append(exclude_id)
        row = cur.execute(
            f"""SELECT p.id, {fields_sql}, {ean_subquery},
                   EXISTS(SELECT 1 FROM product_flags pf
                          WHERE pf.product_id = p.id AND pf.flag = 'is_synced_with_off')
                   AS is_synced_with_off
            FROM products p
            WHERE LOWER(p.name) = LOWER(?) {exclude_clause}
            LIMIT 1""",
            params,
        ).fetchone()
        if row:
            result = {f: row[f] for f in ALL_PRODUCT_FIELDS}
            result["id"] = row["id"]
            result["ean"] = row["ean"]
            result["match_type"] = "name"
            result["is_synced_with_off"] = bool(row["is_synced_with_off"])
            return result

    return None


def check_duplicate_for_edit(pid: int, ean: str, name: str):
    """Check if OFF data for an edited product matches a different existing product.

    Returns (duplicate_dict_or_None, a_is_synced_with_off).
    """
    dup = _find_duplicate(ean, name, exclude_id=pid)
    conn = get_db()
    a_synced = bool(
        conn.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (pid,),
        ).fetchone()
    )
    return dup, a_synced


def merge_products(target_id: int, source_id: int, choices: dict | None = None) -> None:
    """Merge source product into target, filling empty target fields, then delete source.

    ``choices`` is an optional dict of {field: value} for fields where both
    products had values and the user picked which to keep.
    """
    conn = get_db()
    cur = conn.cursor()
    target = cur.execute(
        "SELECT * FROM products WHERE id = ?", (target_id,)
    ).fetchone()
    if not target:
        raise LookupError("Target product not found")
    source = cur.execute(
        "SELECT * FROM products WHERE id = ?", (source_id,)
    ).fetchone()
    if not source:
        raise LookupError("Source product not found")

    choices = choices or {}
    merge_fields = [f for f in ALL_PRODUCT_FIELDS if f not in ("type",)]
    updates, vals = [], []
    for f in merge_fields:
        if f in choices:
            # User explicitly chose a value for this conflicting field
            updates.append(f"{f} = ?")
            vals.append(choices[f])
        else:
            target_val = target[f]
            source_val = source[f]
            if (target_val is None or target_val == "") and source_val not in (None, ""):
                updates.append(f"{f} = ?")
                vals.append(source_val)
    if target["image"] in (None, "") and source["image"] not in (None, ""):
        updates.append("image = ?")
        vals.append(source["image"])

    if updates:
        vals.append(target_id)
        cur.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals
        )

    # Copy flags from source to target
    source_flags = cur.execute(
        "SELECT flag FROM product_flags WHERE product_id = ?", (source_id,)
    ).fetchall()
    for row in source_flags:
        cur.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (target_id, row["flag"]),
        )

    # Transfer EANs from source to target
    source_eans = cur.execute(
        "SELECT ean FROM product_eans WHERE product_id = ?", (source_id,)
    ).fetchall()
    for row in source_eans:
        cur.execute(
            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 0)",
            (target_id, row["ean"]),
        )

    cur.execute("DELETE FROM products WHERE id = ?", (source_id,))
    conn.commit()
