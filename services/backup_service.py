import math
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
    _category_label, _pq_label, _pq_keywords,
    _set_translation_key,
)

logger = logging.getLogger(__name__)


def _restore_product(cur, p):
    def _n(v):
        if v is None:
            return None
        result = float(v)
        if not math.isfinite(result):
            raise ValueError(f"Non-finite numeric value in product: {v}")
        return result
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = p.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(f"{tf} exceeds max length of {max_len}")
    cur.execute(
        INSERT_WITH_IMAGE_SQL,
        (p.get("type",""), p.get("name",""), p.get("ean",""),
         p.get("brand",""), p.get("stores",""), p.get("ingredients",""),
         _n(p.get("taste_score")), _n(p.get("kcal")), _n(p.get("energy_kj")),
         _n(p.get("carbs")), _n(p.get("sugar")), _n(p.get("fat")),
         _n(p.get("saturated_fat")), _n(p.get("protein")), _n(p.get("fiber")),
         _n(p.get("salt")), _n(p.get("volume")), _n(p.get("price")),
         _n(p.get("weight")), _n(p.get("portion")),
         _n(p.get("est_pdcaas")), _n(p.get("est_diaas")), p.get("image","")))


def create_backup():
    conn = get_db()
    products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()]
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


def restore_backup(data):
    if not data or "products" not in data:
        raise ValueError("Invalid backup file")
    if not isinstance(data["products"], list):
        raise ValueError("products must be an array")
    if "score_weights" in data and not isinstance(data["score_weights"], list):
        raise ValueError("score_weights must be an array")
    if "categories" in data and not isinstance(data["categories"], list):
        raise ValueError("categories must be an array")
    if "protein_quality" in data and not isinstance(data["protein_quality"], list):
        raise ValueError("protein_quality must be an array")
    conn = get_db()
    cur = conn.cursor()
    try:
        if "score_weights" in data:
            cur.execute("DELETE FROM score_weights")
            for w in data["score_weights"]:
                f = w.get("field")
                if f in SCORE_CONFIG_MAP:
                    defaults = SCORE_CONFIG_MAP[f]
                    cur.execute("INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?)",
                                (f, w.get("enabled", 0), _safe_float(w.get("weight", 0), "weight"),
                                 w.get("direction", defaults["direction"]),
                                 w.get("formula", defaults["formula"]),
                                 _safe_float(w.get("formula_min", defaults.get("formula_min", 0)), "formula_min"),
                                 _safe_float(w.get("formula_max", defaults["formula_max"]), "formula_max")))

        if "categories" in data:
            cur.execute("DELETE FROM categories")
            for c in data["categories"]:
                cur.execute("INSERT INTO categories (name, emoji) VALUES (?,?)",
                            (c["name"], c.get("emoji", "\U0001F4E6")))
                translations = c.get("translations", {})
                if not translations and c.get("label"):
                    translations = {lang: c["label"] for lang in SUPPORTED_LANGUAGES}
                if translations:
                    _set_translation_key(f"category_{c['name']}", translations)
        if "protein_quality" in data:
            cur.execute("DELETE FROM protein_quality")
            for pq in data["protein_quality"]:
                name = pq.get("name", "").strip()
                if not name:
                    name = pq.get("label", "")
                    if not name:
                        kws = pq.get("keywords", [])
                        name = kws[0] if kws else "unknown"
                    name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')
                cur.execute("INSERT OR IGNORE INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
                            (name, _safe_float(pq.get("pdcaas", 0), "pdcaas"), _safe_float(pq.get("diaas", 0), "diaas")))
                translations = pq.get("translations", {})
                if translations:
                    for lang, lang_data in translations.items():
                        if lang_data.get("label"):
                            _set_translation_key(f"pq_{name}_label", {lang: lang_data["label"]})
                        if lang_data.get("keywords"):
                            kw_str = ", ".join(lang_data["keywords"]) if isinstance(lang_data["keywords"], list) else lang_data["keywords"]
                            _set_translation_key(f"pq_{name}_keywords", {lang: kw_str})
                elif pq.get("label") or pq.get("keywords"):
                    if pq.get("label"):
                        _set_translation_key(f"pq_{name}_label", {lang: pq["label"] for lang in SUPPORTED_LANGUAGES})
                    kws = pq.get("keywords", [])
                    if isinstance(kws, str):
                        kws = [k.strip() for k in kws.split(",") if k.strip()]
                    if kws:
                        _set_translation_key(f"pq_{name}_keywords", {lang: ", ".join(kws) for lang in SUPPORTED_LANGUAGES})
        cur.execute("DELETE FROM products")
        for p in data["products"]:
            _restore_product(cur, p)
        conn.commit()
        return f"Restored {len(data['products'])} products successfully"
    except Exception as e:
        conn.rollback()
        logger.error(f"Restore failed: {e}")
        raise


def import_products(data):
    if not data or "products" not in data:
        raise ValueError("Invalid import file")
    conn = get_db()
    cur = conn.cursor()
    added = 0
    try:
        if "categories" in data:
            for c in data["categories"]:
                try:
                    cur.execute("INSERT INTO categories (name, emoji) VALUES (?,?)",
                                (c["name"], c.get("emoji", "\U0001F4E6")))
                    translations = c.get("translations", {})
                    if not translations and c.get("label"):
                        translations = {lang: c["label"] for lang in SUPPORTED_LANGUAGES}
                    if translations:
                        _set_translation_key(f"category_{c['name']}", translations)
                except sqlite3.IntegrityError:
                    pass
        for p in data["products"]:
            _restore_product(cur, p)
            added += 1
        conn.commit()
        return f"Imported {added} products"
    except Exception as e:
        conn.rollback()
        logger.error(f"Import failed: {e}")
        raise
