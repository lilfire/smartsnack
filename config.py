import os

APP_VERSION = "0.1"

DB_PATH = os.environ.get("DB_PATH", "/data/smartsnack.sqlite")
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
DEFAULT_LANGUAGE = "no"
SUPPORTED_LANGUAGES = sorted(
    [f[:-5] for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".json")],
    key=lambda x: (x != DEFAULT_LANGUAGE, x),  # default language first
)

# ── All product numeric fields (excluding type, name, ean, image) ─────
NUTRITION_FIELDS = [
    "kcal", "energy_kj", "carbs", "sugar",
    "fat", "saturated_fat", "protein", "fiber", "salt",
    "volume", "price", "weight", "portion"
]
ALL_PRODUCT_FIELDS = ["taste_score", "est_pdcaas", "est_diaas", "type", "name", "ean", "brand", "stores", "ingredients"] + NUTRITION_FIELDS

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

# ── SQL helpers ───────────────────────────────────────
PRODUCT_COLS_NO_IMAGE = (
    "id, type, name, ean, brand, stores, ingredients, taste_score, kcal, energy_kj, carbs, sugar, "
    "fat, saturated_fat, protein, fiber, salt, volume, price, weight, portion, est_pdcaas, est_diaas, "
    "CASE WHEN image != '' THEN 1 ELSE 0 END AS has_image"
)

INSERT_FIELDS = "type, name, ean, brand, stores, ingredients, taste_score, kcal, energy_kj, carbs, sugar, fat, saturated_fat, protein, fiber, salt, volume, price, weight, portion, est_pdcaas, est_diaas"
INSERT_PLACEHOLDERS = ",".join(["?"] * 22)
INSERT_WITH_IMAGE_SQL = f"INSERT INTO products ({INSERT_FIELDS}, image) VALUES ({INSERT_PLACEHOLDERS}, ?)"
