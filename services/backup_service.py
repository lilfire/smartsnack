"""Service for backup, restore, and import of the full database."""

import re
import sqlite3
import logging
from datetime import datetime, timezone

from db import get_db
from config import (
    APP_VERSION, SUPPORTED_LANGUAGES, SCORE_CONFIG_MAP,
    INSERT_WITH_IMAGE_SQL, _TEXT_FIELD_LIMITS,
)
from helpers import _safe_float
from translations import (
    _category_label, _category_key, _pq_label, _pq_keywords,
    _set_translation_key,
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
    return "\U0001F4E6"  # 📦 default


def _opt_float(v):
    """Convert a value to float, returning None for None values."""
    if v is None:
        return None
    return _safe_float(v, "product field")


def _restore_product(cur, p):
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = p.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    cur.execute(
        INSERT_WITH_IMAGE_SQL,
        (p.get("type",""), p.get("name",""), p.get("ean",""),
         p.get("brand",""), p.get("stores",""), p.get("ingredients",""),
         _opt_float(p.get("taste_score")), _opt_float(p.get("kcal")), _opt_float(p.get("energy_kj")),
         _opt_float(p.get("carbs")), _opt_float(p.get("sugar")), _opt_float(p.get("fat")),
         _opt_float(p.get("saturated_fat")), _opt_float(p.get("protein")), _opt_float(p.get("fiber")),
         _opt_float(p.get("salt")), _opt_float(p.get("volume")), _opt_float(p.get("price")),
         _opt_float(p.get("weight")), _opt_float(p.get("portion")),
         _opt_float(p.get("est_pdcaas")), _opt_float(p.get("est_diaas")), p.get("image","")))


def create_backup(include_images: bool = True):
    conn = get_db()
    if include_images:
        products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()]
    else:
        products = [dict(r) for r in conn.execute(
            "SELECT id, type, name, ean, brand, stores, ingredients, taste_score, "
            "kcal, energy_kj, carbs, sugar, fat, saturated_fat, protein, fiber, "
            "salt, volume, price, weight, portion, est_pdcaas, est_diaas "
            "FROM products ORDER BY id"
        ).fetchall()]
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
    weights = [dict(r) for r in conn.execute("SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights").fetchall()]
    pq_rows = conn.execute("SELECT id, name, pdcaas, diaas FROM protein_quality ORDER BY id").fetchall()
    protein_quality = []
    for r in pq_rows:
        pq_entry = {"name": r["name"], "pdcaas": r["pdcaas"], "diaas": r["diaas"]}
        translations = {}
        for lang in SUPPORTED_LANGUAGES:
            lang_data = {}
            label = _pq_label(r["name"], lang=lang)
            if label != r["name"]:
                lang_data["label"] = label
            keywords = _pq_keywords(r["name"], lang=lang)
            if keywords:
                lang_data["keywords"] = keywords
            if lang_data:
                translations[lang] = lang_data
        if translations:
            pq_entry["translations"] = translations
        protein_quality.append(pq_entry)
    return {
        "version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "score_weights": weights,
        "categories": categories,
        "protein_quality": protein_quality,
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


def _restore_score_weights(cur: object, weights: list) -> None:
    """Restore score weights from backup data."""
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


def _restore_categories(cur: object, categories: list) -> list:
    """Restore categories from backup data. Returns pending translation ops."""
    pending_translations = []
    cur.execute("DELETE FROM categories")
    for c in categories:
        cur.execute(
            "INSERT INTO categories (name, emoji) VALUES (?,?)",
            (c["name"], c.get("emoji", "\U0001F4E6")),
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
    return pending_translations


def _restore_protein_quality(cur: object, pq_list: list) -> list:
    """Restore protein quality entries from backup. Returns pending translation ops."""
    pending_translations = []
    cur.execute("DELETE FROM protein_quality")
    for pq in pq_list:
        name = pq.get("name", "").strip()
        if not name:
            name = pq.get("label", "")
            if not name:
                kws = pq.get("keywords", [])
                name = kws[0] if kws else "unknown"
            name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')
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
                    pending_translations.append(
                        (f"pq_{name}_keywords", {lang: kw_str})
                    )
        elif pq.get("label") or pq.get("keywords"):
            if pq.get("label"):
                pending_translations.append((
                    f"pq_{name}_label",
                    {lang: pq["label"] for lang in SUPPORTED_LANGUAGES},
                ))
            kws = pq.get("keywords", [])
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",") if k.strip()]
            if kws:
                pending_translations.append((
                    f"pq_{name}_keywords",
                    {lang: ", ".join(kws) for lang in SUPPORTED_LANGUAGES},
                ))
    return pending_translations


def _apply_pending_translations(pending: list) -> None:
    """Apply deferred translation writes after DB commit succeeds."""
    for key, values_by_lang in pending:
        _set_translation_key(key, values_by_lang)


def restore_backup(data: dict) -> str:
    """Restore a full backup, replacing all existing data."""
    _validate_backup(data)
    conn = get_db()
    cur = conn.cursor()
    pending_translations = []
    try:
        if "score_weights" in data:
            _restore_score_weights(cur, data["score_weights"])
        if "categories" in data:
            pending_translations.extend(
                _restore_categories(cur, data["categories"])
            )
        if "protein_quality" in data:
            pending_translations.extend(
                _restore_protein_quality(cur, data["protein_quality"])
            )
        cur.execute("DELETE FROM products")
        for p in data["products"]:
            _restore_product(cur, p)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Restore failed: %s", e)
        raise
    # Apply translation file writes only after DB commit succeeds
    _apply_pending_translations(pending_translations)
    return f"Restored {len(data['products'])} products successfully"


def import_products(data: dict) -> str:
    """Import products (and optionally categories) without deleting existing data."""
    if not data or "products" not in data:
        raise ValueError("Invalid import file")
    conn = get_db()
    cur = conn.cursor()
    added = 0
    pending_translations = []
    try:
        if "categories" in data:
            for c in data["categories"]:
                try:
                    cur.execute(
                        "INSERT INTO categories (name, emoji) VALUES (?,?)",
                        (c["name"], c.get("emoji", "\U0001F4E6")),
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
        existing_cats = {
            r["name"]
            for r in cur.execute("SELECT name FROM categories").fetchall()
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
                    pending_translations.append((
                        _category_key(cat),
                        {lang: cat for lang in SUPPORTED_LANGUAGES},
                    ))
                    existing_cats.add(cat)
                except sqlite3.IntegrityError:
                    existing_cats.add(cat)
            _restore_product(cur, p)
            added += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Import failed: %s", e)
        raise
    # Apply translation file writes only after DB commit succeeds
    _apply_pending_translations(pending_translations)
    return f"Imported {added} products"
