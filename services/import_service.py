"""Service for data import (CSV/JSON) with auto-categorization."""

import sqlite3
import logging

from config import SUPPORTED_LANGUAGES, INSERT_FIELDS, _TEXT_FIELD_LIMITS
from services import flag_service
from services.backup_core import (
    _opt_float,
    _is_empty,
    _restore_product,
    _apply_pending_translations,
)

logger = logging.getLogger(__name__)

# Mapping of keywords (lowercase) to emojis for auto-categorization
_CATEGORY_EMOJI_MAP = [
    # Drinks
    (["juice", "saft", "drikke", "drink", "beverage", "smoothie"], "🧃"),
    (["coffee", "kaffe"], "☕"),
    (["tea", "te"], "🍵"),
    (["milk", "melk", "mjölk", "dairy", "meieri"], "🥛"),
    (["water", "vann", "vatten"], "💧"),
    (["soda", "brus", "cola", "energy", "energi"], "🥤"),
    (["beer", "øl", "öl", "wine", "vin", "alcohol", "alkohol"], "🍺"),
    # Sweets & snacks
    (["candy", "godteri", "godis", "sweet", "søt"], "🍬"),
    (["chocolate", "sjokolade", "choklad"], "🍫"),
    (["ice cream", "iskrem", "is", "glass", "gelato"], "🍦"),
    (["cookie", "kjeks", "kex", "biscuit"], "🍪"),
    (["cake", "kake", "tårta", "pastry", "bakst"], "🎂"),
    (["chip", "chips", "snack", "crisp"], "🍿"),
    (["nut", "nøtt", "nöt", "almond", "mandel", "peanut"], "🥜"),
    # Bread & grains
    (["bread", "brød", "bröd", "toast"], "🍞"),
    (["cereal", "frokostblanding", "müsli", "muesli", "granola", "oat", "havre"], "🥣"),
    (["pasta", "nudel", "noodle", "spaghetti"], "🍝"),
    (["rice", "ris"], "🍚"),
    (["pizza"], "🍕"),
    # Protein
    (["meat", "kjøtt", "kött", "beef", "biff", "steak"], "🥩"),
    (["chicken", "kylling", "poultry", "fjærfe"], "🍗"),
    (["fish", "fisk", "seafood", "sjømat", "salmon", "laks", "tuna", "tunfisk"], "🐟"),
    (["egg", "egg"], "🥚"),
    (["protein", "supplement", "shake"], "💪"),
    # Fruits & vegetables
    (["fruit", "frukt", "berry", "bær", "bär"], "🍎"),
    (["vegetable", "grønnsak", "grönsak", "veggie", "salad", "salat"], "🥬"),
    # Dairy & cheese
    (["cheese", "ost"], "🧀"),
    (["yoghurt", "yogurt", "yoggi"], "🥄"),
    # Spreads & sauces
    (["spread", "pålegg", "jam", "syltetøy"], "🫙"),
    (["sauce", "saus", "dressing", "ketchup", "dip"], "🫗"),
    # Meals & prepared food
    (["meal", "måltid", "dinner", "middag", "lunch", "lunsj", "ready", "ferdig"], "🍽️"),
    (["soup", "suppe"], "🍲"),
    (["sandwich", "wrap", "burrito", "taco"], "🌮"),
    (["burger", "hamburger"], "🍔"),
    # Health & supplements
    (["vitamin", "health", "helse", "supplement", "tilskudd"], "💊"),
    (["baby", "barn", "barnemat"], "🍼"),
    (["organic", "økologisk", "ekologisk", "bio"], "🌿"),
    # Other food categories
    (["frozen", "frys", "frossen"], "🧊"),
    (["spice", "krydder", "herb"], "🌶️"),
    (["oil", "olje", "butter", "smør"], "🧈"),
    (["flour", "mel", "baking", "bake"], "🧁"),
    (["canned", "hermetikk", "boks"], "🥫"),
]


def _pick_emoji_for_category(name):
    """Pick the best-matching emoji for a category name."""
    lower = name.lower()
    for keywords, emoji in _CATEGORY_EMOJI_MAP:
        for kw in keywords:
            if kw in lower:
                return emoji
    return "\U0001f4e6"  # 📦 default


def _overwrite_product(cur, existing_id, p, valid_flags=None):
    """Overwrite an existing product with all values from import data ``p``.

    Unlike merge, this replaces every field unconditionally — even if the
    imported value is blank/zero and the existing product has data.
    """
    fields = [f.strip() for f in INSERT_FIELDS.split(",")]
    text_fields = set(_TEXT_FIELD_LIMITS.keys())
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = p.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    updates, vals = [], []
    for f in fields:
        val = p.get(f)
        if f in text_fields:
            updates.append(f"{f} = ?")
            vals.append(val if val is not None else "")
        else:
            fval = _opt_float(val) if val is not None and val != "" else None
            updates.append(f"{f} = ?")
            vals.append(fval)
    # Image: always overwrite (may clear it)
    updates.append("image = ?")
    vals.append(p.get("image") or "")
    if updates:
        vals.append(existing_id)
        cur.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals
        )
    # Sync EAN to product_eans table
    ean = (p.get("ean") or "").strip()
    if ean:
        primary_row = cur.execute(
            "SELECT id FROM product_eans WHERE product_id = ? AND is_primary = 1",
            (existing_id,),
        ).fetchone()
        if primary_row:
            cur.execute(
                "UPDATE product_eans SET ean = ? WHERE id = ?",
                (ean, primary_row["id"]),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                (existing_id, ean),
            )
    # Replace flags: remove existing, then insert imported
    cur.execute(
        "DELETE FROM product_flags WHERE product_id = ?", (existing_id,)
    )
    if valid_flags is None:
        valid_flags = flag_service.get_all_flag_names()
    for flag in p.get("flags", []):
        if flag in valid_flags:
            cur.execute(
                "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
                (existing_id, flag),
            )


def _merge_product(cur, existing_id, p, merge_priority, valid_flags=None):
    """Merge import data into an existing product using sync-aware rules.

    Rules:
    - Existing synced, imported not → existing wins (only fill empty fields)
    - Imported synced, existing not → imported wins
    - Both synced → imported wins
    - Neither synced → ``merge_priority`` decides: "keep_existing" or "use_imported"
    """
    fields = [f.strip() for f in INSERT_FIELDS.split(",")]
    text_fields = set(_TEXT_FIELD_LIMITS.keys())
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = p.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")

    # Determine sync status
    existing_synced = bool(
        cur.execute(
            "SELECT 1 FROM product_flags WHERE product_id = ? AND flag = 'is_synced_with_off'",
            (existing_id,),
        ).fetchone()
    )
    imported_synced = "is_synced_with_off" in (p.get("flags") or [])

    # Determine winner: who takes priority when both have a value
    if existing_synced and not imported_synced:
        imported_wins = False
    elif imported_synced and not existing_synced:
        imported_wins = True
    elif existing_synced and imported_synced:
        imported_wins = True
    else:
        # Neither synced — user-chosen fallback
        imported_wins = merge_priority == "use_imported"

    # Fetch existing product row for comparison
    existing = cur.execute(
        "SELECT * FROM products WHERE id = ?", (existing_id,)
    ).fetchone()

    updates, vals = [], []
    for f in fields:
        new_val = p.get(f)
        if new_val is None or new_val == "":
            continue
        if f not in text_fields:
            new_val = _opt_float(new_val)
            if new_val is None or new_val == 0:
                continue
        existing_val = existing[f] if existing else None
        if _is_empty(existing_val):
            # Existing is empty → always fill
            updates.append(f"{f} = ?")
            vals.append(new_val)
        elif imported_wins:
            # Both have values, imported wins
            updates.append(f"{f} = ?")
            vals.append(new_val)
        # else: existing wins, keep existing value

    # Image: fill if empty, or replace if imported wins
    img = p.get("image", "")
    if img:
        existing_img = existing["image"] if existing else ""
        if _is_empty(existing_img) or imported_wins:
            updates.append("image = ?")
            vals.append(img)

    if updates:
        vals.append(existing_id)
        cur.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals
        )

    # Merge flags (additive)
    if valid_flags is None:
        valid_flags = flag_service.get_all_flag_names()
    for flag in p.get("flags", []):
        if flag in valid_flags:
            cur.execute(
                "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
                (existing_id, flag),
            )


def import_products(
    data: dict,
    match_criteria: str = "both",
    on_duplicate: str = "skip",
    merge_priority: str = "keep_existing",
) -> str:
    """Import products (and optionally categories) without deleting existing data."""
    from db import get_db
    from translations import _category_key, _flag_key

    if not data or "products" not in data:
        raise ValueError("Invalid import file")
    if match_criteria not in ("ean", "name", "both"):
        match_criteria = "both"
    if on_duplicate not in ("skip", "overwrite", "allow_duplicate", "merge"):
        on_duplicate = "skip"
    if merge_priority not in ("keep_existing", "use_imported"):
        merge_priority = "keep_existing"
    conn = get_db()
    cur = conn.cursor()
    added = 0
    skipped = 0
    overwritten = 0
    merged = 0
    pending_translations = []
    try:
        if "categories" in data:
            for c in data["categories"]:
                try:
                    cur.execute(
                        "INSERT INTO categories (name, emoji) VALUES (?,?)",
                        (c["name"], c.get("emoji", "\U0001f4e6")),
                    )
                    translations = c.get("translations", {})
                    if not translations and c.get("label"):
                        translations = {
                            lang: c["label"] for lang in SUPPORTED_LANGUAGES
                        }
                    if translations:
                        pending_translations.append(
                            (_category_key(c["name"]), translations)
                        )
                except sqlite3.IntegrityError:
                    pass
        if "flag_definitions" in data:
            for fd in data["flag_definitions"]:
                name = fd.get("name", "").strip()
                fd_type = fd.get("type", "user")
                if not name or fd_type not in ("user", "system"):
                    continue
                label_key = _flag_key(name)
                try:
                    cur.execute(
                        "INSERT INTO flag_definitions (name, type, label_key) VALUES (?,?,?)",
                        (name, fd_type, label_key),
                    )
                    translations = fd.get("translations", {})
                    if translations:
                        pending_translations.append((label_key, translations))
                except sqlite3.IntegrityError:
                    pass
        existing_cats = {
            r["name"] for r in cur.execute("SELECT name FROM categories").fetchall()
        }
        valid_flags = {
            r[0] for r in cur.execute("SELECT name FROM flag_definitions").fetchall()
        }
        for p in data["products"]:
            cat = p.get("type", "").strip()
            if cat and cat not in existing_cats:
                emoji = _pick_emoji_for_category(cat)
                try:
                    cur.execute(
                        "INSERT INTO categories (name, emoji) VALUES (?,?)",
                        (cat, emoji),
                    )
                    pending_translations.append(
                        (
                            _category_key(cat),
                            {lang: cat for lang in SUPPORTED_LANGUAGES},
                        )
                    )
                    existing_cats.add(cat)
                except sqlite3.IntegrityError:
                    existing_cats.add(cat)
            ean = p.get("ean", "").strip()
            name = p.get("name", "").strip()
            existing_id = None
            if match_criteria in ("ean", "both") and ean:
                row = cur.execute(
                    "SELECT product_id as id FROM product_eans WHERE ean = ? LIMIT 1", (ean,)
                ).fetchone()
                if row:
                    existing_id = row["id"]
            if existing_id is None and match_criteria in ("name", "both") and name:
                row = cur.execute(
                    "SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (name,)
                ).fetchone()
                if row:
                    existing_id = row["id"]
            if existing_id is not None:
                if on_duplicate == "skip":
                    skipped += 1
                    continue
                elif on_duplicate == "overwrite":
                    _overwrite_product(cur, existing_id, p, valid_flags)
                    overwritten += 1
                    continue
                elif on_duplicate == "merge":
                    _merge_product(cur, existing_id, p, merge_priority, valid_flags)
                    merged += 1
                    continue
                # "allow_duplicate" — fall through to insert
            _restore_product(cur, p, valid_flags=valid_flags)
            added += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Import failed: %s", e)
        raise
    # Apply translation file writes only after DB commit succeeds
    _apply_pending_translations(pending_translations)
    msg = f"Imported {added} products"
    if merged:
        msg += f", {merged} merged"
    if overwritten:
        msg += f", {overwritten} overwritten"
    if skipped:
        msg += f", {skipped} skipped as duplicates"
    return msg
