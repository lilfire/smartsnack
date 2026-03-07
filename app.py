from flask import Flask, request, jsonify, send_file, Response, g
import sqlite3
import os
import json
import logging
import math
import re
import urllib.request
import urllib.error
from urllib.parse import urlparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
DB_PATH = os.environ.get("DB_PATH", "/data/smartsnack.sqlite")
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
SUPPORTED_LANGUAGES = ["no", "en"]
DEFAULT_LANGUAGE = "no"
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── All product numeric fields (excluding type, name, ean, image) ─────
NUTRITION_FIELDS = [
    "kcal", "energy_kj", "carbs", "sugar",
    "fat", "saturated_fat", "protein", "fiber", "salt",
    "volume", "price", "weight", "portion"
]
ALL_PRODUCT_FIELDS = ["taste_score", "est_pdcaas", "est_diaas","type", "name", "ean", "brand", "stores", "ingredients"] + NUTRITION_FIELDS

# Whitelist of valid column names for dynamic SQL construction
_VALID_COLUMNS = frozenset(ALL_PRODUCT_FIELDS + ["id", "image"])

# Maximum lengths for text fields
_TEXT_FIELD_LIMITS = {
    "type": 100, "name": 200, "ean": 50, "brand": 200,
    "stores": 500, "ingredients": 10000,
}

# Protein quality keyword/label limits
_PQ_MAX_KEYWORDS = 50
_PQ_MAX_KEYWORD_LEN = 100
_PQ_MAX_LABEL_LEN = 200

# (name, pdcaas, diaas) — labels and keywords live in translation files
PQ_SEED = [
    ("whey",           1.00, 1.09),
    ("egg",            1.00, 1.13),
    ("milk_casein",    1.00, 1.08),
    ("chicken_turkey", 0.99, 1.08),
    ("meat",           0.99, 1.01),
    ("fish_seafood",   0.99, 1.08),
    ("soy_protein",    0.98, 0.90),
    ("soy",            0.91, 0.84),
    ("pea_protein",    0.82, 0.82),
    ("peas",           0.73, 0.75),
    ("chickpeas",      0.71, 0.83),
    ("lentils",        0.52, 0.60),
    ("beans",          0.68, 0.72),
    ("lupin",          0.85, 0.64),
    ("wheat_gluten",   0.42, 0.45),
    ("oats",           0.57, 0.53),
    ("rice",           0.59, 0.59),
    ("corn",           0.42, 0.40),
    ("barley",         0.64, 0.55),
    ("rye",            0.68, 0.58),
    ("quinoa",         0.84, 0.85),
    ("amaranth",       0.75, 0.78),
    ("peanut",         0.52, 0.45),
    ("almond",         0.33, 0.40),
    ("cashew",         0.73, 0.69),
    ("sunflower",      0.60, 0.53),
    ("pumpkin_seed",   0.60, 0.51),
    ("hemp",           0.63, 0.66),
    ("chia",           0.62, 0.54),
    ("sesame",         0.57, 0.48),
    ("potato",         0.85, 0.87),
    ("spirulina",      0.99, 0.74),
    ("tofu_tempeh",    0.91, 0.84),
]


# ── Flexible Score Configuration ─────────────────────
# Labels and descriptions use translation keys resolved at request time
SCORE_CONFIG = [
    {"field": "kcal",           "label_key": "weight_label_kcal",           "desc_key": "weight_desc_kcal",           "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "energy_kj",      "label_key": "weight_label_energy_kj",      "desc_key": "weight_desc_energy_kj",      "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "carbs",          "label_key": "weight_label_carbs",          "desc_key": "weight_desc_carbs",          "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "sugar",         "label_key": "weight_label_sugar",         "desc_key": "weight_desc_sugar",         "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "fat",           "label_key": "weight_label_fat",           "desc_key": "weight_desc_fat",           "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "saturated_fat",    "label_key": "weight_label_saturated_fat",    "desc_key": "weight_desc_saturated_fat",    "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "protein",        "label_key": "weight_label_protein",        "desc_key": "weight_desc_protein",        "direction": "higher", "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "fiber",          "label_key": "weight_label_fiber",          "desc_key": "weight_desc_fiber",          "direction": "higher", "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "salt",           "label_key": "weight_label_salt",           "desc_key": "weight_desc_salt",           "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "taste_score", "label_key": "weight_label_taste_score", "desc_key": "weight_desc_taste_score", "direction": "higher", "formula": "direct", "formula_min": 0, "formula_max": 6},
    {"field": "volume",         "label_key": "weight_label_volume",         "desc_key": "weight_desc_volume",         "direction": "higher", "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "price",           "label_key": "weight_label_price",           "desc_key": "weight_desc_price",           "direction": "lower",  "formula": "minmax", "formula_min": 0, "formula_max": 0},
    {"field": "est_pdcaas",     "label_key": "weight_label_est_pdcaas",     "desc_key": "weight_desc_est_pdcaas",     "direction": "higher", "formula": "direct", "formula_min": 0, "formula_max": 1.0},
    {"field": "est_diaas",      "label_key": "weight_label_est_diaas",      "desc_key": "weight_desc_est_diaas",      "direction": "higher", "formula": "direct", "formula_min": 0, "formula_max": 1.2},
]
SCORE_CONFIG_MAP = {c["field"]: c for c in SCORE_CONFIG}

DEFAULT_WEIGHTS = {    
    "taste_score": {"enabled": 1, "weight": 100.0},    
}


# ── Translation helpers ──────────────────────────────
_translations_cache = {}

def _load_translations(lang):
    """Load and cache a translation file. Returns dict or empty dict on error."""
    if lang in _translations_cache:
        return _translations_cache[lang]
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _translations_cache[lang] = data
        return data
    except (OSError, json.JSONDecodeError):
        return {}

def _get_current_lang():
    """Get the current language from user_settings (uses its own connection to avoid request-context issues)."""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM user_settings WHERE key='language'").fetchone()
        return row["value"] if row else DEFAULT_LANGUAGE
    except Exception:
        return DEFAULT_LANGUAGE

def _t(key, lang=None):
    """Resolve a translation key to a localized string. Falls back to key itself."""
    if lang is None:
        lang = _get_current_lang()
    tr = _load_translations(lang)
    return tr.get(key, key)


def _category_label(name, lang=None):
    """Resolve category display name from translations. Falls back to internal name."""
    label = _t(f"category_{name}", lang=lang)
    if label == f"category_{name}":
        return name
    return label


def _pq_label(name, lang=None):
    """Resolve protein quality display name from translations. Falls back to internal name."""
    label = _t(f"pq_{name}_label", lang=lang)
    if label == f"pq_{name}_label":
        return name
    return label


def _pq_keywords(name, lang=None):
    """Resolve protein quality keywords for a specific language. Returns list of strings."""
    raw = _t(f"pq_{name}_keywords", lang=lang)
    if raw == f"pq_{name}_keywords":
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _pq_all_keywords(name):
    """Merge keywords from ALL languages for matching (ingredient text can be any language)."""
    seen = set()
    result = []
    for lang in SUPPORTED_LANGUAGES:
        for kw in _pq_keywords(name, lang=lang):
            lw = kw.lower()
            if lw not in seen:
                seen.add(lw)
                result.append(kw)
    return result


def _set_translation_key(key, values_by_lang):
    """Write a translation key to one or more language JSON files.

    *values_by_lang* is a dict like {"en": "Snacks", "no": "Snacks"}.
    Languages not present in the dict are skipped.
    The in-memory cache is invalidated for affected languages.
    """
    if not re.match(r'^[a-z][a-z0-9_.]*$', key):
        raise ValueError(f"Invalid translation key format: {key}")
    for lang, value in values_by_lang.items():
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        data[key] = value
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # Invalidate cache so _t picks up new value
        _translations_cache.pop(lang, None)


def _delete_translation_key(key):
    """Remove a translation key from all language files."""
    for lang in SUPPORTED_LANGUAGES:
        filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if key in data:
            del data[key]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            _translations_cache.pop(lang, None)


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS score_weights (
            field TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            weight REAL NOT NULL DEFAULT 0,
            direction TEXT NOT NULL DEFAULT 'lower',
            formula TEXT NOT NULL DEFAULT 'minmax',
            formula_max REAL NOT NULL DEFAULT 0,
            formula_min REAL NOT NULL DEFAULT 0
        )
    """)

    cur.execute("SELECT COUNT(*) FROM score_weights")
    if cur.fetchone()[0] == 0:
        for sc in SCORE_CONFIG:
            f = sc["field"]
            d = DEFAULT_WEIGHTS.get(f, {"enabled": 0, "weight": 0})
            cur.execute("INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?)",
                        (f, d["enabled"], d["weight"], sc["direction"], sc["formula"], sc["formula_min"], sc["formula_max"]))

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            emoji TEXT NOT NULL DEFAULT '\U0001F4E6'
        )
    """)

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO categories (name, emoji) VALUES (?,?)", [
            ("Snacks", "\U0001F37F")      
        ])

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            ean TEXT NOT NULL DEFAULT '',
            brand TEXT NOT NULL DEFAULT '',
            stores TEXT NOT NULL DEFAULT '',
            ingredients TEXT NOT NULL DEFAULT '',
            taste_score REAL DEFAULT NULL,
            kcal REAL DEFAULT NULL,
            energy_kj REAL DEFAULT NULL,
            carbs REAL DEFAULT NULL,
            sugar REAL DEFAULT NULL,
            fat REAL DEFAULT NULL,
            saturated_fat REAL DEFAULT NULL,
            protein REAL DEFAULT NULL,
            fiber REAL DEFAULT NULL,
            salt REAL DEFAULT NULL,
            volume REAL DEFAULT NULL,
            price REAL DEFAULT NULL,
            weight REAL DEFAULT NULL,
            portion REAL DEFAULT NULL,
            est_pdcaas REAL DEFAULT NULL,
            est_diaas REAL DEFAULT NULL,
            image TEXT NOT NULL DEFAULT ''
        )
    """)

    # ── Protein quality lookup table ──────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS protein_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            pdcaas REAL NOT NULL,
            diaas REAL NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM protein_quality")
    if cur.fetchone()[0] == 0:
        for name, pdcaas, diaas in PQ_SEED:
            cur.execute("INSERT INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
                        (name, pdcaas, diaas))

    # ── User settings (key-value store) ──────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM user_settings WHERE key='language'")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO user_settings (key, value) VALUES ('language', ?)", (DEFAULT_LANGUAGE,))

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        seed_products(cur)

    conn.commit()
    conn.close()


def seed_products(cur):
    # Small Base64 string that serves as a grey placeholder box
    demo_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABs0lEQVR4nO2YzZGCQBSEe7Y2hM0AI8DDXsxAwjAswsAMuOxBIpAMzME9rM9CGGRWZmiq7O8mP1Pd/d4bpgSEEEIIIYQQQgjxbji2gD7nKr/2r22KJpnOVQVwrvJrtjsMrrd1mSyEjxSLvsKYeQDIdgdvZ8RgFQE8M2+kCmHxEfCZmDLfJfY4fMZaKARfpdu6XFLCgGQBdCu9KRoX0ubPSBVU9ADMeNfsuSpfnl0z7lsvxihE3QOmqtzW5WDefZW1Z3zP99+dG8Kie0CfMYNTxmMSrQNCZ9zMhVQ3dL05XUA5B4SYs5BSQwkgtL2XCGEVJ0EmswO43oghZq6GV7RE64Bsf5ps19jt3NYlsv1p1hpvPwKzP4P9lmuPWwCPG939NHerVnvcBn/iDN96l6LBt6fjnXPBvqIHAAA/zuGryu+/+21q96fOAV2DFizwZ9xYbQCGT6DdHwvBzE+9P3b/PwFQj8KXogGq4cbYrXBqqAEAw/EAgMuC/9O8/VdAAbAFsFEAbAFsFABbABsFwBbARgGwBbBRAGwBbBQAWwAbBcAWwEYBsAWwUQBsAWwUAFuAEILKLyvl1WbjKX5wAAAAAElFTkSuQmCC"

    data = [
        (
            "Snacks",            # type
            "Classic Popcorn",  # name
            "7000000000001",     # ean
            "SmartSnack",        # brand
            "All stores",        # stores
            "Corn, sunflower oil, sea salt", # ingredients
            3.0,                 # taste_score
            450.0,               # kcal
            1880.0,              # energy_kj
            55.0,                # carbs
            1.0,                 # sugar
            20.0,                # fat
            2.5,                 # saturated_fat
            9.0,                 # protein
            12.0,                # fiber
            1.5,                 # salt
            1.0,                 # volume
            25.0,                # price
            100.0,               # weight
            25.0,                # portion
            0.5,                 # est_pdcaas
            0.4,                 # est_diaas
            demo_image_base64    # image (Base64 string)
        )
    ]
    
    cur.executemany(
        """
        INSERT INTO products (
            type, name, ean, brand, stores, ingredients, taste_score, 
            kcal, energy_kj, carbs, sugar, fat, saturated_fat, protein, 
            fiber, salt, volume, price, weight, portion, est_pdcaas, est_diaas, image
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        data
    )


# ── Helpers ───────────────────────────────────────────

def _require_json():
    """Return parsed JSON body or abort with 400."""
    data = request.get_json(silent=True)
    if data is None:
        return None
    return data


# ── Routes ────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Unhandled error: {e}", exc_info=True)
    return jsonify({"error": "An internal error occurred"}), 500


@app.route("/health")
def health():
    try:
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        return jsonify({"status": "ok", "version": APP_VERSION, "products": count})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error"}), 500


@app.route("/")
def index():
    return send_file(os.path.join(app.root_path, "templates", "index.html"))


# ── Products ──────────────────────────────────────────

PRODUCT_COLS_NO_IMAGE = (
    "id, type, name, ean, brand, stores, ingredients, taste_score, kcal, energy_kj, carbs, sugar, "
    "fat, saturated_fat, protein, fiber, salt, volume, price, weight, portion, est_pdcaas, est_diaas, "
    "CASE WHEN image != '' THEN 1 ELSE 0 END AS has_image"
)


@app.route("/api/products")
def get_products():
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "").strip()

    conn = get_db()
    cur = conn.cursor()

    # Load enabled weights with config
    weight_rows = cur.execute("SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights").fetchall()
    enabled_weights = {}
    weight_config = {}
    for r in weight_rows:
        if r["enabled"]:
            enabled_weights[r["field"]] = r["weight"]
            weight_config[r["field"]] = {"direction": r["direction"], "formula": r["formula"], "formula_min": r["formula_min"], "formula_max": r["formula_max"]}
    enabled_fields = [f for f in enabled_weights if f in SCORE_CONFIG_MAP]

    # Compute min/max per category for all enabled fields
    cat_ranges = {}  # {category: {field: (min, max)}}
    if enabled_fields:
        # Validate field names against whitelist before using in SQL
        for f in enabled_fields:
            if f not in _VALID_COLUMNS:
                return jsonify({"error": "Invalid field"}), 400
        agg = ", ".join(f"MIN({f}) as min_{f}, MAX({f}) as max_{f}" for f in enabled_fields)
        type_rows = cur.execute(f"SELECT type, {agg} FROM products GROUP BY type").fetchall()
        for tr in type_rows:
            cat_ranges[tr["type"]] = {
                f: (tr[f"min_{f}"] or 0, tr[f"max_{f}"] or 0) for f in enabled_fields
            }

    conditions, params = [], []
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("(name LIKE ? ESCAPE '\\' OR ean LIKE ? ESCAPE '\\')")
        params.extend([f"%{escaped}%", f"%{escaped}%"])
    if type_filter:
        types = [t.strip() for t in type_filter.split(",") if t.strip()]
        if len(types) == 1:
            conditions.append("type = ?")
            params.append(types[0])
        elif types:
            placeholders = ",".join("?" * len(types))
            conditions.append(f"type IN ({placeholders})")
            params.extend(types)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = cur.execute(f"SELECT {PRODUCT_COLS_NO_IMAGE} FROM products {where} ORDER BY name", params).fetchall()

    results = []
    for r in rows:
        p = dict(r)
        scores = {}
        weighted_score_sum = 0.0
        num_scored_fields = 0
        missing_fields = []
        ranges = cat_ranges.get(p["type"], {})
        for field in enabled_fields:
            cfg = weight_config[field]
            weight = enabled_weights[field]
            val = p.get(field)
            if val is None:
                missing_fields.append(field)
                continue

            formula = cfg["formula"]
            direction = cfg["direction"]

            if formula == "direct":
                fmin = cfg.get("formula_min", 0)
                fmax = cfg["formula_max"]
                if fmax <= fmin:
                    continue
                if direction == "lower":
                    raw = (fmax - val) / (fmax - fmin)
                else:
                    raw = (val - fmin) / (fmax - fmin)
                raw = max(0.0, min(1.0, raw))
                s = raw * 100
            else:
                # minmax
                mn, mx = ranges.get(field, (0, 0))
                if mx - mn <= 0:
                    continue
                if direction == "lower":
                    raw = (mx - val) / (mx - mn)
                else:
                    raw = (val - mn) / (mx - mn)
                raw = max(0.0, min(1.0, raw))
                s = raw * 100

            scores[field] = round(s * weight / 100, 1)
            weighted_score_sum += s * weight
            num_scored_fields += 1

        p["scores"] = scores
        p["total_score"] = round(weighted_score_sum / (num_scored_fields * 100), 1) if num_scored_fields > 0 else 0
        p["has_missing_scores"] = len(missing_fields) > 0
        p["missing_fields"] = missing_fields
        results.append(p)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return jsonify(results)


INSERT_FIELDS = "type, name, ean, brand, stores, ingredients, taste_score, kcal, energy_kj, carbs, sugar, fat, saturated_fat, protein, fiber, salt, volume, price, weight, portion, est_pdcaas, est_diaas"
INSERT_PLACEHOLDERS = ",".join(["?"] * 22)
INSERT_WITH_IMAGE_SQL = f"INSERT INTO products ({INSERT_FIELDS}, image) VALUES ({INSERT_PLACEHOLDERS}, ?)"


def _num(data, field):
    """Return None if value is None/null/empty string, otherwise float."""
    v = data.get(field)
    if v is None or v == "":
        return None
    try:
        result = float(v)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {field}")
    if not math.isfinite(result):
        raise ValueError(f"Invalid numeric value for {field}")
    return result


def _safe_float(v, label="value"):
    """Convert to float, rejecting inf/nan."""
    result = float(v)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric value for {label}")
    return result


def _validate_keywords(keywords):
    """Normalise and validate a keywords value (list or comma-separated string).

    Returns (cleaned_list, error_string). error_string is None on success.
    """
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if not isinstance(keywords, list):
        return None, "keywords must be a list or comma-separated string"
    if len(keywords) > _PQ_MAX_KEYWORDS:
        return None, f"Too many keywords (max {_PQ_MAX_KEYWORDS})"
    for kw in keywords:
        if not isinstance(kw, str) or len(kw) > _PQ_MAX_KEYWORD_LEN:
            return None, f"Each keyword must be a string of max {_PQ_MAX_KEYWORD_LEN} chars"
    return keywords, None


@app.route("/api/products", methods=["POST"])
def add_product():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    if not data.get("type", "").strip() or not data.get("name", "").strip():
        return jsonify({"error": "type and name are required"}), 400
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        val = data.get(tf, "")
        if isinstance(val, str) and len(val) > max_len:
            return jsonify({"error": f"{tf} exceeds max length of {max_len}"}), 400
    conn = get_db()
    cur = conn.cursor()
    cat_exists = cur.execute("SELECT 1 FROM categories WHERE name = ?", (data["type"].strip(),)).fetchone()
    if not cat_exists:
        return jsonify({"error": "Category does not exist"}), 400
    try:
        cur.execute(
            f"INSERT INTO products ({INSERT_FIELDS}) VALUES ({INSERT_PLACEHOLDERS})",
            (data["type"], data["name"].strip(), data.get("ean", "").strip(),
             data.get("brand", "").strip(), data.get("stores", "").strip(), data.get("ingredients", "").strip(),
             _num(data, "taste_score"), _num(data, "kcal"),
             _num(data, "energy_kj"), _num(data, "carbs"),
             _num(data, "sugar"), _num(data, "fat"),
             _num(data, "saturated_fat"), _num(data, "protein"),
             _num(data, "fiber"), _num(data, "salt"),
             _num(data, "volume"), _num(data, "price"),
             _num(data, "weight"), _num(data, "portion"),
             _num(data, "est_pdcaas"), _num(data, "est_diaas")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    conn.commit()
    pid = cur.lastrowid
    return jsonify({"id": pid, "message": "Product added"}), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    updates, vals = [], []
    TEXT_FIELDS = {"type", "name", "ean", "brand", "stores", "ingredients"}
    for f in data:
        if f in ("id", "image"):
            continue
        if f not in _VALID_COLUMNS:
            return jsonify({"error": "Invalid field"}), 400
    for tf, max_len in _TEXT_FIELD_LIMITS.items():
        if tf in data and isinstance(data[tf], str) and len(data[tf]) > max_len:
            return jsonify({"error": f"{tf} exceeds max length of {max_len}"}), 400
    for f in ALL_PRODUCT_FIELDS:
        if f in data:
            v = data[f]
            if f not in TEXT_FIELDS:
                if v is None or v == "":
                    v = None
                else:
                    try:
                        v = _safe_float(v, f)
                    except (ValueError, TypeError):
                        return jsonify({"error": f"Invalid numeric value for {f}"}), 400
            updates.append(f"{f} = ?")
            vals.append(v)
    if not updates:
        return jsonify({"error": "Nothing to update"}), 400
    if "type" in data:
        conn = get_db()
        cat_exists = conn.execute("SELECT 1 FROM categories WHERE name = ?", (data["type"],)).fetchone()
        if not cat_exists:
            return jsonify({"error": "Category does not exist"}), 400
    else:
        conn = get_db()
    vals.append(pid)
    conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", vals)
    conn.commit()
    return jsonify({"message": "Product updated"})


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": "Deleted"})


# ── Product Images ────────────────────────────────────

@app.route("/api/products/<int:pid>/image")
def get_product_image(pid):
    conn = get_db()
    row = conn.execute("SELECT image FROM products WHERE id = ?", (pid,)).fetchone()
    if not row or not row["image"]:
        return jsonify({"error": "No image"}), 404
    return jsonify({"image": row["image"]})


@app.route("/api/products/<int:pid>/image", methods=["PUT"])
def set_product_image(pid):
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    image = data.get("image", "")
    if not image or not image.startswith("data:image/"):
        return jsonify({"error": "Invalid image format"}), 400
    max_image_bytes = 2 * 1024 * 1024  # 2 MB base64 string limit
    if len(image) > max_image_bytes:
        return jsonify({"error": "Image too large (max 2 MB)"}), 413
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET image = ? WHERE id = ?", (image, pid))
    if cur.rowcount == 0:
        return jsonify({"error": "Product not found"}), 404
    conn.commit()
    return jsonify({"message": "Image saved"})


@app.route("/api/products/<int:pid>/image", methods=["DELETE"])
def delete_product_image(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET image = '' WHERE id = ?", (pid,))
    if cur.rowcount == 0:
        return jsonify({"error": "Product not found"}), 404
    conn.commit()
    return jsonify({"message": "Image removed"})



# ── Protein Quality Estimation ────────────────────────
# PDCAAS capped at 1.0, DIAAS uncapped (whey can reach ~1.09)
# Sources: FAO 2013 DIAAS report, Marinangeli & House 2017, van Vliet 2015
def _load_protein_quality_table():
    """Load protein quality lookup from DB + translation keywords (all languages)."""
    conn = get_db()
    rows = conn.execute("SELECT name, pdcaas, diaas FROM protein_quality ORDER BY id").fetchall()
    table = []
    for r in rows:
        keywords = _pq_all_keywords(r["name"])
        table.append((r["name"], keywords, r["pdcaas"], r["diaas"]))
    return table


def estimate_protein_quality(ingredients: str) -> dict:
    """
    Estimate PDCAAS and DIAAS from an ingredient list string.

    Method:
    - Split ingredients into tokens, scan against lookup table
    - Weight each match by 1/(position+1) since ingredients are
      listed in descending order by mass
    - Weighted average of matched scores
    - If no protein sources found, return None
    """
    if not ingredients:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}

    text = ingredients.lower()
    # Split on common delimiters
    tokens_raw = re.split(r"[,;()\[\]\/\\|•\n]+", text)
    tokens = [t.strip() for t in tokens_raw if t.strip()]

    pq_table = _load_protein_quality_table()
    matched = []  # (position, pdcaas, diaas, pq_name)
    for pos, token in enumerate(tokens):
        for pq_name, keywords, pdcaas, diaas in pq_table:
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', token):
                    matched.append((pos, pdcaas, diaas, pq_name))
                    break  # one match per token per row

    if not matched:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}

    # Deduplicate: keep first occurrence per (pdcaas, diaas) pair
    seen = set()
    deduped = []
    for pos, pdcaas, diaas, pq_name in matched:
        key = (round(pdcaas, 2), round(diaas, 2))
        if key not in seen:
            seen.add(key)
            deduped.append((pos, pdcaas, diaas, pq_name))

    # Position weight: w = 1 / (pos + 1)
    total_w = sum(1.0 / (pos + 1) for pos, *_ in deduped)
    if total_w == 0:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}
    w_pdcaas = sum((1.0 / (pos + 1)) * pdcaas for pos, pdcaas, diaas, _ in deduped) / total_w
    w_diaas  = sum((1.0 / (pos + 1)) * diaas  for pos, pdcaas, diaas, _ in deduped) / total_w

    return {
        "est_pdcaas": round(min(w_pdcaas, 1.0), 3),
        "est_diaas":  round(min(w_diaas, 1.2), 3),
        "sources": [_pq_label(pq_name) for _, _, _, pq_name in deduped],
    }


@app.route("/api/estimate-protein-quality", methods=["POST"])
def api_estimate_protein_quality():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    ingredients = (data.get("ingredients") or "").strip()
    if not ingredients:
        return jsonify({"error": "ingredients required"}), 400
    result = estimate_protein_quality(ingredients)
    return jsonify(result)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from following redirects to block SSRF via open redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirects not allowed", headers, fp)


_no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler)


@app.route("/api/proxy-image")
def proxy_image():
    url = request.args.get("url", "")
    if not url or not url.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid URL"}), 400
    parsed = urlparse(url)
    allowed_domains = (".openfoodfacts.org", ".openfoodfacts.net")
    if not parsed.hostname or not any(parsed.hostname == d.lstrip(".") or parsed.hostname.endswith(d) for d in allowed_domains):
        return jsonify({"error": "Domain not allowed"}), 403
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSnack/1.0"})
        with _no_redirect_opener.open(req, timeout=10) as resp:
            ct = resp.headers.get("Content-Type", "image/jpeg")
            if not ct.startswith("image/") or "svg" in ct.lower():
                return jsonify({"error": "Response is not an allowed image type"}), 400
            max_size = 5 * 1024 * 1024  # 5 MB
            data = resp.read(max_size + 1)
            if len(data) > max_size:
                return jsonify({"error": "Image too large"}), 413
            return Response(data, mimetype=ct, headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.error(f"Image proxy error: {e}")
        return jsonify({"error": "Failed to fetch image"}), 502


# ── Stats / Weights / Categories ──────────────────────

@app.route("/api/stats")
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    cats = cur.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    type_counts = {}
    for r in cur.execute("SELECT type, COUNT(*) as count FROM products GROUP BY type").fetchall():
        type_counts[r["type"]] = r["count"]
    return jsonify({
        "total": total, "types": len(cats), "type_counts": type_counts,
        "categories": [{"name": c["name"], "emoji": c["emoji"], "label": _category_label(c["name"])} for c in cats],
    })



@app.route("/api/weights")
def get_weights():
    conn = get_db()
    rows = conn.execute("SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights ORDER BY field").fetchall()
    db_map = {r["field"]: {"enabled": bool(r["enabled"]), "weight": r["weight"], "direction": r["direction"], "formula": r["formula"], "formula_min": r["formula_min"], "formula_max": r["formula_max"]} for r in rows}
    lang = _get_current_lang()
    result = []
    for sc in SCORE_CONFIG:
        f = sc["field"]
        w = db_map.get(f, {"enabled": False, "weight": 0, "direction": sc["direction"], "formula": sc["formula"], "formula_min": sc["formula_min"], "formula_max": sc["formula_max"]})
        result.append({
            "field": f,
            "label": _t(sc["label_key"], lang),
            "desc": _t(sc["desc_key"], lang),
            "enabled": w["enabled"],
            "weight": w["weight"],
            "direction": w["direction"],
            "formula": w["formula"],
            "formula_min": w["formula_min"],
            "formula_max": w["formula_max"],
        })
    return jsonify(result)


@app.route("/api/weights", methods=["PUT"])
def update_weights():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    if not isinstance(data, list):
        return jsonify({"error": "Expected array of weights"}), 400
    conn = get_db()
    _VALID_DIRECTIONS = {"lower", "higher"}
    _VALID_FORMULAS = {"minmax", "direct"}
    for item in data:
        f = item.get("field", "")
        if f not in SCORE_CONFIG_MAP:
            continue
        direction = item.get("direction", SCORE_CONFIG_MAP[f]["direction"])
        if direction not in _VALID_DIRECTIONS:
            return jsonify({"error": f"Invalid direction: {direction}"}), 400
        formula = item.get("formula", SCORE_CONFIG_MAP[f]["formula"])
        if formula not in _VALID_FORMULAS:
            return jsonify({"error": f"Invalid formula: {formula}"}), 400
        try:
            formula_min = _safe_float(item.get("formula_min", 0), "formula_min")
            formula_max = _safe_float(item.get("formula_max", 0), "formula_max")
            weight = _safe_float(item.get("weight", 0), "weight")
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid numeric value in weights"}), 400
        if not (0 <= weight <= 1000):
            return jsonify({"error": f"Weight must be between 0 and 1000"}), 400
        enabled = 1 if item.get("enabled") else 0
        conn.execute(
            "INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(field) DO UPDATE SET enabled=excluded.enabled, weight=excluded.weight, direction=excluded.direction, formula=excluded.formula, formula_min=excluded.formula_min, formula_max=excluded.formula_max",
            (f, enabled, weight, direction, formula, formula_min, formula_max)
        )
    conn.commit()
    return jsonify({"message": "Weights updated"})


@app.route("/api/categories")
def get_categories():
    conn = get_db()
    cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    counts = {}
    for r in conn.execute("SELECT type, COUNT(*) as count FROM products GROUP BY type").fetchall():
        counts[r["type"]] = r["count"]
    return jsonify([{"name": c["name"], "emoji": c["emoji"], "label": _category_label(c["name"]), "count": counts.get(c["name"], 0)} for c in cats])


_MAX_CATEGORY_NAME_LEN = 100
_CATEGORY_NAME_RE = re.compile(r"^[\w\s\-]+$", re.UNICODE)


def _validate_category_name(n):
    """Return error string if invalid, None if ok."""
    if not n or len(n) > _MAX_CATEGORY_NAME_LEN:
        return "Invalid category name"
    if not _CATEGORY_NAME_RE.match(n):
        return "Invalid category name"
    return None


@app.route("/api/categories", methods=["POST"])
def add_category():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    name = data.get("name", "").strip()
    label = data.get("label", "").strip()
    emoji = data.get("emoji", "\U0001F4E6").strip()
    if not name or not label:
        return jsonify({"error": "name and label are required"}), 400
    err = _validate_category_name(name)
    if err:
        return jsonify({"error": err}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO categories (name, emoji) VALUES (?,?)", (name, emoji))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists"}), 409
    # Write display name to the currently active language's translation file
    lang = _get_current_lang()
    _set_translation_key(f"category_{name}", {lang: label})
    return jsonify({"message": "Category added"}), 201


@app.route("/api/categories/<n>", methods=["PUT"])
def update_category(n):
    err = _validate_category_name(n)
    if err:
        return jsonify({"error": err}), 400
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    label = data.get("label", "").strip()
    emoji = data.get("emoji", "").strip()
    if not label and not emoji:
        return jsonify({"error": "Nothing to update"}), 400
    conn = get_db()
    if emoji:
        conn.execute("UPDATE categories SET emoji = ? WHERE name = ?", (emoji, n))
        conn.commit()
    if label:
        # Update display name in the currently active language's translation file
        lang = _get_current_lang()
        _set_translation_key(f"category_{n}", {lang: label})
    return jsonify({"message": "Category updated"})


@app.route("/api/categories/<n>", methods=["DELETE"])
def delete_category(n):
    err = _validate_category_name(n)
    if err:
        return jsonify({"error": err}), 400
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM products WHERE type = ?", (n,)).fetchone()[0]
    if count > 0:
        return jsonify({"error": f"Cannot delete: {count} products still use this category"}), 400
    conn.execute("DELETE FROM categories WHERE name = ?", (n,))
    conn.commit()
    _delete_translation_key(f"category_{n}")
    return jsonify({"message": "Category deleted"})


# ── Protein Quality CRUD ──────────────────────────────

@app.route("/api/protein-quality")
def list_protein_quality():
    conn = get_db()
    rows = conn.execute("SELECT id, name, pdcaas, diaas FROM protein_quality ORDER BY id").fetchall()
    result = []
    for r in rows:
        keywords = _pq_keywords(r["name"])
        result.append({
            "id": r["id"],
            "name": r["name"],
            "keywords": keywords,
            "pdcaas": r["pdcaas"],
            "diaas": r["diaas"],
            "label": _pq_label(r["name"]),
        })
    return jsonify(result)


@app.route("/api/protein-quality", methods=["POST"])
def add_protein_quality():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    name = data.get("name", "").strip()
    keywords = data.get("keywords", [])
    pdcaas = data.get("pdcaas")
    diaas = data.get("diaas")
    label = data.get("label", "").strip()
    if not name:
        # Auto-generate internal name from label or first keyword
        name = label or (keywords[0] if keywords else "")
    if not name or not keywords or pdcaas is None or diaas is None:
        return jsonify({"error": "keywords, pdcaas and diaas are required"}), 400
    # Sanitize name to be a valid internal key
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')
    if not name:
        return jsonify({"error": "Invalid name"}), 400
    keywords, kw_err = _validate_keywords(keywords)
    if kw_err:
        return jsonify({"error": kw_err}), 400
    if isinstance(label, str) and len(label) > _PQ_MAX_LABEL_LEN:
        return jsonify({"error": f"label exceeds max length of {_PQ_MAX_LABEL_LEN}"}), 400
    try:
        pdcaas_f = _safe_float(pdcaas, "pdcaas")
        diaas_f = _safe_float(diaas, "diaas")
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numeric value for pdcaas/diaas"}), 400
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
                    (name, pdcaas_f, diaas_f))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Protein quality entry with this name already exists"}), 409
    new_id = cur.lastrowid
    # Write label and keywords to the active language's translation file
    lang = _get_current_lang()
    if label:
        _set_translation_key(f"pq_{name}_label", {lang: label})
    kw_str = ", ".join(keywords)
    _set_translation_key(f"pq_{name}_keywords", {lang: kw_str})
    return jsonify({"ok": True, "id": new_id, "name": name})


@app.route("/api/protein-quality/<int:pid>", methods=["PUT"])
def update_protein_quality(pid):
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    conn = get_db()
    existing = conn.execute("SELECT id, name FROM protein_quality WHERE id=?", (pid,)).fetchone()
    if not existing:
        return jsonify({"error": "Not found"}), 404
    pq_name = existing["name"]
    lang = _get_current_lang()
    # Update DB fields (pdcaas, diaas)
    updates = []
    params = []
    for field in ("pdcaas", "diaas"):
        if field in data:
            try:
                updates.append(f"{field}=?")
                params.append(_safe_float(data[field], field))
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid numeric value for {field}"}), 400
    if updates:
        params.append(pid)
        conn.execute(f"UPDATE protein_quality SET {','.join(updates)} WHERE id=?", params)
        conn.commit()
    # Update translation fields (keywords, label) in active language
    if "keywords" in data:
        kws, kw_err = _validate_keywords(data["keywords"])
        if kw_err:
            return jsonify({"error": kw_err}), 400
        _set_translation_key(f"pq_{pq_name}_keywords", {lang: ", ".join(kws)})
    if "label" in data:
        label = data["label"].strip()
        if len(label) > _PQ_MAX_LABEL_LEN:
            return jsonify({"error": f"label exceeds max length of {_PQ_MAX_LABEL_LEN}"}), 400
        _set_translation_key(f"pq_{pq_name}_label", {lang: label})
    return jsonify({"ok": True})


@app.route("/api/protein-quality/<int:pid>", methods=["DELETE"])
def delete_protein_quality(pid):
    conn = get_db()
    existing = conn.execute("SELECT name FROM protein_quality WHERE id=?", (pid,)).fetchone()
    if not existing:
        return jsonify({"error": "Not found"}), 404
    pq_name = existing["name"]
    conn.execute("DELETE FROM protein_quality WHERE id=?", (pid,))
    conn.commit()
    _delete_translation_key(f"pq_{pq_name}_label")
    _delete_translation_key(f"pq_{pq_name}_keywords")
    return jsonify({"ok": True})


# ── Backup / Restore ─────────────────────────────────

@app.route("/api/backup")
def backup_db():
    conn = get_db()
    products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()]
    cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    categories = []
    for c in cat_rows:
        cat_data = {"name": c["name"], "emoji": c["emoji"]}
        # Include per-language labels from translation files for portability
        translations = {}
        for lang in SUPPORTED_LANGUAGES:
            label = _category_label(c["name"], lang=lang)
            if label != c["name"]:  # Only include if a real translation exists
                translations[lang] = label
        if translations:
            cat_data["translations"] = translations
        categories.append(cat_data)
    weights = [dict(r) for r in conn.execute("SELECT field, enabled, weight, direction, formula, formula_min, formula_max FROM score_weights").fetchall()]
    pq_rows = conn.execute("SELECT id, name, pdcaas, diaas FROM protein_quality ORDER BY id").fetchall()
    protein_quality = []
    for r in pq_rows:
        pq_entry = {"name": r["name"], "pdcaas": r["pdcaas"], "diaas": r["diaas"]}
        # Include per-language labels and keywords
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
    payload = {
        "version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "score_weights": weights,
        "categories": categories,
        "protein_quality": protein_quality,
        "products": products,
    }
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        json_str, mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=smartsnack_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"},
    )


def _restore_product(cur, p):
    def _n(v):
        """Preserve None/null, convert others to float, reject inf/nan."""
        if v is None:
            return None
        result = float(v)
        if not math.isfinite(result):
            raise ValueError(f"Non-finite numeric value in product: {v}")
        return result
    # Validate text field lengths
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


@app.route("/api/restore", methods=["POST"])
def restore_db():
    data = _require_json()
    if not data or "products" not in data:
        return jsonify({"error": "Invalid backup file"}), 400
    if not isinstance(data["products"], list):
        return jsonify({"error": "products must be an array"}), 400
    if "score_weights" in data and not isinstance(data["score_weights"], list):
        return jsonify({"error": "score_weights must be an array"}), 400
    if "categories" in data and not isinstance(data["categories"], list):
        return jsonify({"error": "categories must be an array"}), 400
    if "protein_quality" in data and not isinstance(data["protein_quality"], list):
        return jsonify({"error": "protein_quality must be an array"}), 400
    conn = get_db()
    cur = conn.cursor()
    try:
        # Restore score weights
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
                # Restore translations: prefer "translations" dict, fall back to legacy "label" field
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
                    # Legacy format: generate name from label or first keyword
                    name = pq.get("label", "")
                    if not name:
                        kws = pq.get("keywords", [])
                        name = kws[0] if kws else "unknown"
                    name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')
                cur.execute("INSERT OR IGNORE INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
                            (name, _safe_float(pq.get("pdcaas", 0), "pdcaas"), _safe_float(pq.get("diaas", 0), "diaas")))
                # Restore translations
                translations = pq.get("translations", {})
                if translations:
                    for lang, lang_data in translations.items():
                        if lang_data.get("label"):
                            _set_translation_key(f"pq_{name}_label", {lang: lang_data["label"]})
                        if lang_data.get("keywords"):
                            kw_str = ", ".join(lang_data["keywords"]) if isinstance(lang_data["keywords"], list) else lang_data["keywords"]
                            _set_translation_key(f"pq_{name}_keywords", {lang: kw_str})
                elif pq.get("label") or pq.get("keywords"):
                    # Legacy format: write to all languages
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
        return jsonify({"message": f"Restored {len(data['products'])} products successfully"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Restore failed: {e}")
        return jsonify({"error": "Restore failed"}), 500


@app.route("/api/import", methods=["POST"])
def import_products():
    data = _require_json()
    if not data or "products" not in data:
        return jsonify({"error": "Invalid import file"}), 400
    conn = get_db()
    cur = conn.cursor()
    added = 0
    try:
        if "categories" in data:
            for c in data["categories"]:
                try:
                    cur.execute("INSERT INTO categories (name, emoji) VALUES (?,?)",
                                (c["name"], c.get("emoji", "\U0001F4E6")))
                    # Write translations for new categories
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
        return jsonify({"message": f"Imported {added} products"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Import failed: {e}")
        return jsonify({"error": "Import failed"}), 500


# ── Language & Translations ───────────────────────────

@app.route("/api/settings/language")
def get_language():
    conn = get_db()
    row = conn.execute("SELECT value FROM user_settings WHERE key='language'").fetchone()
    lang = row["value"] if row else DEFAULT_LANGUAGE
    return jsonify({"language": lang})


@app.route("/api/settings/language", methods=["PUT"])
def set_language():
    data = _require_json()
    if not data or "language" not in data:
        return jsonify({"error": "language is required"}), 400
    lang = data["language"].strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language. Supported: {', '.join(SUPPORTED_LANGUAGES)}"}), 400
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('language', ?)", (lang,))
    conn.commit()
    return jsonify({"ok": True, "language": lang})


@app.route("/api/translations/<lang>")
def get_translations(lang):
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": "Unsupported language"}), 404
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(filepath):
        return jsonify({"error": "Translation file not found"}), 404
    with open(filepath, "r", encoding="utf-8") as f:
        translations = json.load(f)
    return jsonify(translations)


try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
