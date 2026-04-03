"""Service for database backup creation and restore."""

import math
import re
import sqlite3
import logging
from datetime import datetime, timezone

from config import (
    APP_VERSION,
    SUPPORTED_LANGUAGES,
    SCORE_CONFIG_MAP,
    INSERT_FIELDS,
    INSERT_WITH_IMAGE_SQL,
    _TEXT_FIELD_LIMITS,
)
from services import flag_service

logger = logging.getLogger(__name__)


def _opt_float(v):
    """Convert a value to float, returning None for None values."""
    if v is None:
        return None
    try:
        result = float(v)
    except (ValueError, TypeError) as e:
        raise ValueError("Invalid numeric value for product field") from e
    if not math.isfinite(result):
        raise ValueError("Non-finite numeric value for product field")
    return result


def _is_empty(val):
    """Return True if a value is considered empty (None or empty string)."""
    return val is None or val == ""


def _restore_product(cur, p, valid_flags=None):
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = p.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    cur.execute(
        INSERT_WITH_IMAGE_SQL,
        (
            p.get("type", ""),
            p.get("name", ""),
            p.get("ean", ""),
            p.get("brand", ""),
            p.get("stores", ""),
            p.get("ingredients", ""),
            p.get("taste_note", ""),
            _opt_float(p.get("taste_score")),
            _opt_float(p.get("kcal")),
            _opt_float(p.get("energy_kj")),
            _opt_float(p.get("carbs")),
            _opt_float(p.get("sugar")),
            _opt_float(p.get("fat")),
            _opt_float(p.get("saturated_fat")),
            _opt_float(p.get("protein")),
            _opt_float(p.get("fiber")),
            _opt_float(p.get("salt")),
            _opt_float(p.get("volume")),
            _opt_float(p.get("price")),
            _opt_float(p.get("weight")),
            _opt_float(p.get("portion")),
            _opt_float(p.get("est_pdcaas")),
            _opt_float(p.get("est_diaas")),
            p.get("image", ""),
        ),
    )
    new_id = cur.lastrowid
    if valid_flags is None:
        valid_flags = flag_service.get_all_flag_names()
    for flag in p.get("flags", []):
        if flag in valid_flags:
            cur.execute(
                "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
                (new_id, flag),
            )


def create_backup(include_images: bool = True):
    from db import get_db
    from translations import _category_label, _flag_label, _pq_label, _pq_keywords

    conn = get_db()
    if include_images:
        products = [
            dict(r)
            for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        ]
    else:
        products = [
            dict(r)
            for r in conn.execute(
                "SELECT id, type, name, ean, brand, stores, ingredients, taste_note, "
                "taste_score, kcal, energy_kj, carbs, sugar, fat, saturated_fat, "
                "protein, fiber, salt, volume, price, weight, portion, "
                "est_pdcaas, est_diaas "
                "FROM products ORDER BY id"
            ).fetchall()
        ]
    # Attach flags to products
    flag_rows = conn.execute(
        "SELECT product_id, flag FROM product_flags ORDER BY product_id, flag"
    ).fetchall()
    flags_map: dict[int, list[str]] = {}
    for r in flag_rows:
        flags_map.setdefault(r["product_id"], []).append(r["flag"])
    for p in products:
        p["flags"] = flags_map.get(p["id"], [])

    cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    categories = []
    for c in cat_rows:
        cat_data = {"name": c["name"], "emoji": c["emoji"]}
        translations = {}
        for lang in SUPPORTED_LANGUAGES:
            label = _category_label(c["name"], lang=lang)
            if label != c["name"]:
                translations[lang] = label
        if translations:
            cat_data["translations"] = translations
        categories.append(cat_data)
    weights = [
        dict(r)
        for r in conn.execute(
            "SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights"
        ).fetchall()
    ]
    pq_rows = conn.execute(
        "SELECT id, name, pdcaas, diaas FROM protein_quality ORDER BY id"
    ).fetchall()
    protein_quality = []
    for r in pq_rows:
        pq_entry: dict[str, object] = {
            "name": r["name"],
            "pdcaas": r["pdcaas"],
            "diaas": r["diaas"],
        }
        pq_translations: dict[str, dict[str, str | list]] = {}
        for lang in SUPPORTED_LANGUAGES:
            lang_data: dict[str, str | list] = {}
            label = _pq_label(r["name"], lang=lang)
            if label != r["name"]:
                lang_data["label"] = label
            keywords = _pq_keywords(r["name"], lang=lang)
            if keywords:
                lang_data["keywords"] = keywords
            if lang_data:
                pq_translations[lang] = lang_data
        if pq_translations:
            pq_entry["translations"] = pq_translations
        protein_quality.append(pq_entry)
    # Export flag definitions with translations
    flag_rows = conn.execute(
        "SELECT name, type, label_key FROM flag_definitions ORDER BY type, name"
    ).fetchall()
    flag_definitions = []
    for fd in flag_rows:
        fd_data = {"name": fd["name"], "type": fd["type"]}
        translations = {}
        for lang in SUPPORTED_LANGUAGES:
            label = _flag_label(fd["name"], lang=lang)
            if label != fd["name"]:
                translations[lang] = label
        if translations:
            fd_data["translations"] = translations
        flag_definitions.append(fd_data)
    return {
        "version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "score_weights": weights,
        "categories": categories,
        "protein_quality": protein_quality,
        "flag_definitions": flag_definitions,
        "products": products,
    }


def _validate_backup(data: dict) -> None:
    """Validate the structure of a backup payload."""
    if not data or "products" not in data:
        raise ValueError("Invalid backup file")
    if not isinstance(data["products"], list):
        raise ValueError("products must be an array")
    for key in ("score_weights", "categories", "protein_quality"):
        if key in data and not isinstance(data[key], list):
            raise ValueError(f"{key} must be an array")


def _restore_score_weights(cur: sqlite3.Cursor, weights: list) -> None:
    """Restore score weights from backup data."""
    from helpers import _safe_float

    cur.execute("DELETE FROM score_weights")
    for w in weights:
        field = w.get("field")
        if field not in SCORE_CONFIG_MAP:
            continue
        defaults = SCORE_CONFIG_MAP[field]
        cur.execute(
            "INSERT INTO score_weights "
            "(field, enabled, weight, direction, formula, "
            "formula_min, formula_max) VALUES (?,?,?,?,?,?,?)",
            (
                field,
                w.get("enabled", 0),
                _safe_float(w.get("weight", 0), "weight"),
                w.get("direction", defaults["direction"]),
                w.get("formula", defaults["formula"]),
                _safe_float(
                    w.get("formula_min", defaults.get("formula_min", 0)),
                    "formula_min",
                ),
                _safe_float(
                    w.get("formula_max", defaults["formula_max"]),
                    "formula_max",
                ),
            ),
        )


def _restore_categories(cur: sqlite3.Cursor, categories: list) -> list:
    """Restore categories from backup data. Returns pending translation ops."""
    from translations import _category_key

    pending_translations = []
    cur.execute("DELETE FROM categories")
    for c in categories:
        cur.execute(
            "INSERT INTO categories (name, emoji) VALUES (?,?)",
            (c["name"], c.get("emoji", "\U0001f4e6")),
        )
        translations = c.get("translations", {})
        if not translations and c.get("label"):
            translations = {lang: c["label"] for lang in SUPPORTED_LANGUAGES}
        if translations:
            pending_translations.append((_category_key(c["name"]), translations))
    return pending_translations


def _restore_protein_quality(cur: sqlite3.Cursor, pq_list: list) -> list:
    """Restore protein quality entries from backup. Returns pending translation ops."""
    from helpers import _safe_float

    pending_translations = []
    cur.execute("DELETE FROM protein_quality")
    for pq in pq_list:
        name = pq.get("name", "").strip()
        if not name:
            name = pq.get("label", "")
            if not name:
                kws = pq.get("keywords", [])
                name = kws[0] if kws else "unknown"
            name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")
        cur.execute(
            "INSERT OR IGNORE INTO protein_quality "
            "(name, pdcaas, diaas) VALUES (?,?,?)",
            (
                name,
                _safe_float(pq.get("pdcaas", 0), "pdcaas"),
                _safe_float(pq.get("diaas", 0), "diaas"),
            ),
        )
        translations = pq.get("translations", {})
        if translations:
            for lang, lang_data in translations.items():
                if lang_data.get("label"):
                    pending_translations.append(
                        (f"pq_{name}_label", {lang: lang_data["label"]})
                    )
                if lang_data.get("keywords"):
                    kw_str = (
                        ", ".join(lang_data["keywords"])
                        if isinstance(lang_data["keywords"], list)
                        else lang_data["keywords"]
                    )
                    pending_translations.append((f"pq_{name}_keywords", {lang: kw_str}))
        elif pq.get("label") or pq.get("keywords"):
            if pq.get("label"):
                pending_translations.append(
                    (
                        f"pq_{name}_label",
                        {lang: pq["label"] for lang in SUPPORTED_LANGUAGES},
                    )
                )
            kws = pq.get("keywords", [])
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",") if k.strip()]
            if kws:
                pending_translations.append(
                    (
                        f"pq_{name}_keywords",
                        {lang: ", ".join(kws) for lang in SUPPORTED_LANGUAGES},
                    )
                )
    return pending_translations


def _restore_flag_definitions(cur: sqlite3.Cursor, flag_defs: list) -> list:
    """Restore flag definitions from backup data. Returns pending translation ops."""
    from translations import _flag_key

    pending_translations = []
    cur.execute("DELETE FROM flag_definitions")
    for fd in flag_defs:
        name = fd.get("name", "").strip()
        fd_type = fd.get("type", "user")
        if not name:
            continue
        if fd_type not in ("user", "system"):
            fd_type = "user"
        label_key = _flag_key(name)
        cur.execute(
            "INSERT OR IGNORE INTO flag_definitions (name, type, label_key) VALUES (?,?,?)",
            (name, fd_type, label_key),
        )
        translations = fd.get("translations", {})
        if translations:
            pending_translations.append((label_key, translations))
    return pending_translations


def _apply_pending_translations(pending: list) -> None:
    """Apply deferred translation writes after DB commit succeeds."""
    from translations import _set_translation_key

    for key, values_by_lang in pending:
        _set_translation_key(key, values_by_lang)


def restore_backup(data: dict) -> str:
    """Restore a full backup, replacing all existing data."""
    from db import get_db

    _validate_backup(data)
    conn = get_db()
    cur = conn.cursor()
    pending_translations = []
    try:
        if "score_weights" in data:
            _restore_score_weights(cur, data["score_weights"])
        if "categories" in data:
            pending_translations.extend(_restore_categories(cur, data["categories"]))
        if "protein_quality" in data:
            pending_translations.extend(
                _restore_protein_quality(cur, data["protein_quality"])
            )
        if "flag_definitions" in data:
            pending_translations.extend(
                _restore_flag_definitions(cur, data["flag_definitions"])
            )
        # Build valid flags set after flag_definitions are restored
        valid_flags = {
            r[0] for r in cur.execute("SELECT name FROM flag_definitions").fetchall()
        }
        cur.execute("DELETE FROM products")
        for p in data["products"]:
            _restore_product(cur, p, valid_flags=valid_flags)
        conn.commit()
        from services.product_scoring import invalidate_scoring_cache
        invalidate_scoring_cache()
    except Exception as e:
        conn.rollback()
        logger.error("Restore failed: %s", e)
        raise
    # Apply translation file writes only after DB commit succeeds
    _apply_pending_translations(pending_translations)
    return f"Restored {len(data['products'])} products successfully"
