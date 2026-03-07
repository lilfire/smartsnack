import os
import sqlite3
import logging

from flask import g

from config import DB_PATH, SCORE_CONFIG, DEFAULT_WEIGHTS, PQ_SEED, DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


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
    demo_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABs0lEQVR4nO2YzZGCQBSEe7Y2hM0AI8DDXsxAwjAswsAMuOxBIpAMzME9rM9CGGRWZmiq7O8mP1Pd/d4bpgSEEEIIIYQQQgjxbji2gD7nKr/2r22KJpnOVQVwrvJrtjsMrrd1mSyEjxSLvsKYeQDIdgdvZ8RgFQE8M2+kCmHxEfCZmDLfJfY4fMZaKARfpdu6XFLCgGQBdCu9KRoX0ubPSBVU9ADMeNfsuSpfnl0z7lsvxihE3QOmqtzW5WDefZW1Z3zP99+dG8Kie0CfMYNTxmMSrQNCZ9zMhVQ3dL05XUA5B4SYs5BSQwkgtL2XCGEVJ0EmswO43oghZq6GV7RE64Bsf5ps19jt3NYlsv1p1hpvPwKzP4P9lmuPWwCPG939NHerVnvcBn/iDN96l6LBt6fjnXPBvqIHAAA/zuGryu+/+21q96fOAV2DFizwZ9xYbQCGT6DdHwvBzE+9P3b/PwFQj8KXogGq4cbYrXBqqAEAw/EAgMuC/9O8/VdAAbAFsFABbABsFwBbARgGwBbBRAGwBbBQAWwAbBcAWwEYBsAWwUQBsAWwUAFuAEILKLyvl1WbjKX5wAAAAAElFTkSuQmCC"

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
