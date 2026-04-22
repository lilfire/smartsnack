"""Create, read, update, delete, and list products."""

import re
import sqlite3

from db import get_db
from config import (
    PRODUCT_COLS_NO_IMAGE,
    INSERT_FIELDS,
    INSERT_PLACEHOLDERS,
    ALL_PRODUCT_FIELDS,
    _VALID_COLUMNS,
    _TEXT_FIELD_LIMITS,
    COMPUTED_FIELDS,
    DEFAULT_PAGE_SIZE,
)
from services import flag_service, tag_service
from helpers import _num, _safe_float
from services.product_scoring import (
    _load_weight_config,
    _compute_category_ranges,
    _score_product,
    _compute_completeness,
)
from services.product_filters import _parse_advanced_filters, _apply_post_filters
from services.product_duplicate import _find_duplicate

_TEXT_FIELD_SET = frozenset(_TEXT_FIELD_LIMITS.keys())


def _get_product_flags(cur, product_ids: list) -> dict:
    """Batch-fetch flags for a list of product IDs. Returns {pid: [flag, ...]}."""
    if not product_ids:
        return {}
    placeholders = ",".join("?" * len(product_ids))
    rows = cur.execute(
        f"SELECT product_id, flag FROM product_flags WHERE product_id IN ({placeholders})",
        product_ids,
    ).fetchall()
    result: dict[int, list[str]] = {}
    for r in rows:
        result.setdefault(r["product_id"], []).append(r["flag"])
    return result


def _set_user_flags(conn, pid: int, flags: list) -> None:
    """Replace all user flags for a product. Ignores unknown or system flags."""
    user_flags = flag_service.get_user_flag_names()
    valid_flags = [f for f in flags if f in user_flags]
    # Delete existing user flags only
    if user_flags:
        conn.execute(
            f"DELETE FROM product_flags WHERE product_id = ? AND flag IN ({','.join('?' * len(user_flags))})",
            [pid] + list(user_flags),
        )
    for flag in valid_flags:
        conn.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid, flag),
        )


def set_system_flag(pid: int, flag_name: str, value: bool) -> None:
    """Set or clear a system flag for a product. For programmatic use only."""
    if flag_name not in flag_service.get_all_flag_names():
        raise ValueError(f"Unknown flag: {flag_name!r}")
    conn = get_db()
    if value:
        conn.execute(
            "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
            (pid, flag_name),
        )
    else:
        conn.execute(
            "DELETE FROM product_flags WHERE product_id = ? AND flag = ?",
            (pid, flag_name),
        )
    conn.commit()


def mark_product_synced_with_off(pid: int, ean: str | None = None) -> None:
    """Mark an existing local product as synced with Open Food Facts."""
    set_system_flag(pid, "is_synced_with_off", True)
    if ean:
        conn = get_db()
        conn.execute(
            "UPDATE product_eans SET synced_with_off = 1 WHERE product_id = ? AND ean = ?",
            (pid, ean),
        )
        conn.commit()


def _sync_primary_ean(conn, pid: int, new_ean: str) -> None:
    """Sync product_eans primary row when products.ean changes."""
    if new_ean:
        existing_primary = conn.execute(
            "SELECT id, ean FROM product_eans WHERE product_id = ? AND is_primary = 1",
            (pid,),
        ).fetchone()
        if existing_primary:
            if existing_primary["ean"] != new_ean:
                # Check if the new ean already exists as a non-primary row
                existing_row = conn.execute(
                    "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
                    (pid, new_ean),
                ).fetchone()
                if existing_row:
                    # Demote old primary, promote the existing row
                    conn.execute(
                        "UPDATE product_eans SET is_primary = 0 WHERE id = ?",
                        (existing_primary["id"],),
                    )
                    conn.execute(
                        "UPDATE product_eans SET is_primary = 1 WHERE id = ?",
                        (existing_row["id"],),
                    )
                else:
                    # Update primary row's ean value
                    conn.execute(
                        "UPDATE product_eans SET ean = ? WHERE id = ?",
                        (new_ean, existing_primary["id"]),
                    )
        else:
            # No primary row — insert or promote existing matching row
            existing_row = conn.execute(
                "SELECT id FROM product_eans WHERE product_id = ? AND ean = ?",
                (pid, new_ean),
            ).fetchone()
            if existing_row:
                conn.execute(
                    "UPDATE product_eans SET is_primary = 1 WHERE id = ?",
                    (existing_row["id"],),
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                    (pid, new_ean),
                )
    else:
        # EAN cleared — demote primary designation
        conn.execute(
            "UPDATE product_eans SET is_primary = 0 WHERE product_id = ? AND is_primary = 1",
            (pid,),
        )


def list_products(
    search: str | None,
    type_filter: str | None,
    advanced_filters: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> dict:
    """List products with computed scores, filtered and sorted. Returns {products, total}."""
    conn = get_db()
    cur = conn.cursor()

    enabled_weights, weight_config, enabled_fields = _load_weight_config(cur)
    cat_ranges = _compute_category_ranges(cur, enabled_fields)

    conditions, params = [], []
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            "(name LIKE ? ESCAPE '\\' OR EXISTS ("
            "SELECT 1 FROM product_eans pe WHERE pe.product_id = products.id AND pe.ean LIKE ? ESCAPE '\\'"
            ") OR brand LIKE ? ESCAPE '\\')"
        )
        params.extend([f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"])
    if type_filter is not None:
        types = [t.strip() for t in type_filter.split(",")]
        # Support filtering by empty type (uncategorized products)
        has_empty = "" in types
        named = [t for t in types if t]
        parts = []
        if named:
            if len(named) == 1:
                parts.append("type = ?")
                params.append(named[0])
            else:
                placeholders = ",".join("?" * len(named))
                parts.append(f"type IN ({placeholders})")
                params.extend(named)
        if has_empty:
            parts.append("type = ''")
        if parts:
            conditions.append("(" + " OR ".join(parts) + ")")
    post_filter_spec = None
    if advanced_filters:
        af_sql, af_params, post_filter_spec = _parse_advanced_filters(advanced_filters)
        if af_sql:
            conditions.append(af_sql)
            params.extend(af_params)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total_count = cur.execute(
        f"SELECT COUNT(*) FROM products {where}", params
    ).fetchone()[0]

    rows = cur.execute(
        f"SELECT {PRODUCT_COLS_NO_IMAGE} FROM products {where} ORDER BY name LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    results = []
    for r in rows:
        p = dict(r)
        for cf, compute_fn in COMPUTED_FIELDS.items():
            p[cf] = compute_fn(p)
        _score_product(
            p,
            enabled_fields,
            enabled_weights,
            weight_config,
            cat_ranges,
        )
        p["completeness"] = _compute_completeness(p)
        results.append(p)

    # Attach flags BEFORE post-filtering — flag conditions may be evaluated
    # in post-filter when OR groups mix SQL and computed fields.
    pids = [p["id"] for p in results]
    flags_map = _get_product_flags(cur, pids)
    tags_map = tag_service.get_tags_for_products(pids)
    for p in results:
        p["flags"] = flags_map.get(p["id"], [])
        p["tags"] = tags_map.get(p["id"], [])

    results = _apply_post_filters(results, post_filter_spec)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return {"products": results, "total": total_count}


def add_product(data: dict, on_duplicate: str | None = None) -> dict:
    # from_off_ean is only meaningful on update (per-row fetch on an existing
    # product). On add there's only ever one EAN, so just drop it.
    data.pop("from_off_ean", None)
    if not data.get("name", "").strip():
        raise ValueError("name is required")
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = data.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    ean = data.get("ean", "").strip()
    if ean and not re.fullmatch(r"\d{8,13}", ean):
        raise ValueError("EAN must be 8-13 digits")
    conn = get_db()
    cur = conn.cursor()
    product_type = data.get("type", "").strip()
    if product_type:
        cat_exists = cur.execute(
            "SELECT 1 FROM categories WHERE name = ?", (product_type,)
        ).fetchone()
        if not cat_exists:
            raise ValueError("Category does not exist")
    name = data["name"].strip()

    # Duplicate detection
    if on_duplicate != "allow_duplicate":
        dup = _find_duplicate(ean, name)
        if dup:
            if dup["is_synced_with_off"]:
                if on_duplicate == "overwrite":
                    raise ValueError(
                        "Cannot overwrite a product synced with OpenFoodFacts"
                    )
                return {
                    "duplicate": {
                        "id": dup["id"],
                        "name": dup["name"],
                        "ean": dup["ean"],
                        "match_type": dup["match_type"],
                        "is_synced_with_off": True,
                    },
                    "actions": [],
                }
            # Duplicate found, not synced
            if on_duplicate == "overwrite":
                # Merge data into existing product — only non-empty fields
                merge_data = dict(data)
                merge_data.pop("on_duplicate", None)
                from_off = merge_data.pop("from_off", False)
                merge_data = {
                    k: v for k, v in merge_data.items()
                    if v is not None and v != ""
                    and (not isinstance(v, str) or v.strip() != "")
                }
                merge_data["from_off"] = from_off
                update_product(dup["id"], merge_data)
                return {"id": dup["id"], "merged": True, "message": "Product merged"}
            # No on_duplicate set — return duplicate info for frontend
            from_off = data.get("from_off", False)
            actions = ["overwrite"]
            if not from_off:
                actions.append("create_new")
            return {
                "duplicate": {
                    "id": dup["id"],
                    "name": dup["name"],
                    "ean": dup["ean"],
                    "match_type": dup["match_type"],
                    "is_synced_with_off": dup["is_synced_with_off"],
                },
                "actions": actions,
            }

    cur.execute(
        f"INSERT INTO products ({INSERT_FIELDS}) VALUES ({INSERT_PLACEHOLDERS})",
        (
            data.get("type", "").strip(),
            data["name"].strip(),
            data.get("ean", "").strip(),
            data.get("brand", "").strip(),
            data.get("stores", "").strip(),
            data.get("ingredients", "").strip(),
            data.get("taste_note", "").strip(),
            _num(data, "taste_score"),
            _num(data, "kcal"),
            _num(data, "energy_kj"),
            _num(data, "carbs"),
            _num(data, "sugar"),
            _num(data, "fat"),
            _num(data, "saturated_fat"),
            _num(data, "protein"),
            _num(data, "fiber"),
            _num(data, "salt"),
            _num(data, "volume"),
            _num(data, "price"),
            _num(data, "weight"),
            _num(data, "portion"),
            _num(data, "est_pdcaas"),
            _num(data, "est_diaas"),
        ),
    )
    new_id = cur.lastrowid
    if ean:
        conn.execute(
            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
            (new_id, ean),
        )
    if "flags" in data and isinstance(data["flags"], list):
        _set_user_flags(conn, new_id, data["flags"])
    conn.commit()
    if data.get("from_off"):
        mark_product_synced_with_off(new_id, ean)
    from services.product_scoring import invalidate_scoring_cache
    invalidate_scoring_cache()
    return {"id": new_id, "message": "Product added"}


def update_product(pid: int, data: dict) -> None:
    """Update a product's fields by ID."""
    # Extract flags, tagIds, and from_off before field validation loop
    incoming_flags = data.pop("flags", None)
    incoming_tag_ids = data.pop("tagIds", None)
    data.pop("tags", None)  # ignore legacy tags field if present
    from_off = data.pop("from_off", False)
    # from_off_ean names the specific EAN that was fetched from OFF, so the
    # caller can target a non-primary row without causing a primary swap via
    # data["ean"]. If absent, fall back to data["ean"] (the primary).
    from_off_ean = data.pop("from_off_ean", None)

    updates, vals = [], []
    for f in data:
        if f in ("id", "image"):
            continue
        if f not in _VALID_COLUMNS:
            raise ValueError("Invalid field")
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        if tf in data and isinstance(data[tf], str) and len(data[tf]) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    if "ean" in data:
        ean = (data["ean"] or "").strip()
        if ean and not re.fullmatch(r"\d{8,13}", ean):
            raise ValueError("EAN must be 8-13 digits")
    for f in ALL_PRODUCT_FIELDS:
        if f in data:
            v = data[f]
            if f not in _TEXT_FIELD_SET:
                if v is None or v == "":
                    v = None
                else:
                    v = _safe_float(v, f)
            updates.append(f"{f} = ?")
            vals.append(v)
    if not updates and incoming_flags is None and incoming_tag_ids is None:
        raise ValueError("Nothing to update")
    conn = get_db()
    if "type" in data and data["type"]:
        cat_exists = conn.execute(
            "SELECT 1 FROM categories WHERE name = ?", (data["type"],)
        ).fetchone()
        if not cat_exists:
            raise ValueError("Category does not exist")
    if updates:
        vals.append(pid)
        cur = conn.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals
        )
        if cur.rowcount == 0:
            raise LookupError("Product not found")
    else:
        # Only flags/tags are being updated — verify product exists
        exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
        if not exists:
            raise LookupError("Product not found")
    if "ean" in data:
        new_ean = (data["ean"] or "").strip()
        _sync_primary_ean(conn, pid, new_ean)
    if incoming_flags is not None and isinstance(incoming_flags, list):
        _set_user_flags(conn, pid, incoming_flags)
    if incoming_tag_ids is not None and isinstance(incoming_tag_ids, list):
        tag_service.set_tags_for_product(pid, incoming_tag_ids)
    conn.commit()
    from services.product_scoring import invalidate_scoring_cache
    invalidate_scoring_cache()
    if from_off:
        # Prefer the explicitly targeted EAN (from per-row fetch in the UI);
        # fall back to the primary EAN on the form.
        ean_val = (from_off_ean or data.get("ean") or "").strip() or None
        mark_product_synced_with_off(pid, ean_val)


def delete_product(pid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
    from services.product_scoring import invalidate_scoring_cache
    invalidate_scoring_cache()
    return cur.rowcount > 0


# ── EAN CRUD ──────────────────────────────────────────────────────────────────


def list_eans(pid: int) -> list:
    """List all EANs for a product."""
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    rows = conn.execute(
        "SELECT id, ean, is_primary FROM product_eans WHERE product_id = ? ORDER BY is_primary DESC, id ASC",
        (pid,),
    ).fetchall()
    return [{"id": r["id"], "ean": r["ean"], "is_primary": bool(r["is_primary"])} for r in rows]


def add_ean(pid: int, ean: str) -> dict:
    """Add a new EAN to a product. Idempotent: returns existing record if EAN already on this product."""
    ean = ean.strip()
    if not re.fullmatch(r"\d{8,13}", ean):
        raise ValueError("EAN must be 8-13 digits")
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone()
    if not exists:
        raise LookupError("Product not found")
    # Idempotency: if EAN already belongs to this product, return existing record
    existing = conn.execute(
        "SELECT id, ean, is_primary FROM product_eans WHERE product_id = ? AND ean = ?",
        (pid, ean),
    ).fetchone()
    if existing:
        return {"id": existing["id"], "ean": existing["ean"], "is_primary": bool(existing["is_primary"]), "already_exists": True}
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
        "SELECT id, ean, is_primary FROM product_eans WHERE id = ? AND product_id = ?",
        (ean_id, pid),
    ).fetchone()
    if not row:
        raise LookupError("EAN not found")
    count = conn.execute(
        "SELECT COUNT(*) FROM product_eans WHERE product_id = ?", (pid,)
    ).fetchone()[0]
    if count == 1:
        raise ValueError("cannot_remove_only_ean")
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
