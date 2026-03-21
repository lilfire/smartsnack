"""SQLite database connection management, schema init, and seed data."""

import os
import sqlite3

from flask import g

from config import DB_PATH, SCORE_CONFIG, DEFAULT_WEIGHTS, PQ_SEED, DEFAULT_LANGUAGE
from migrations import run_migrations


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 5000")
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
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    try:
        _init_schema(cur, conn)
    finally:
        conn.close()


def _init_schema(cur, conn):
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
            cur.execute(
                "INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?)",
                (
                    f,
                    d["enabled"],
                    d["weight"],
                    sc["direction"],
                    sc["formula"],
                    sc["formula_min"],
                    sc["formula_max"],
                ),
            )
    else:
        # Seed any SCORE_CONFIG fields missing from existing databases
        existing = {
            r[0]
            for r in cur.execute("SELECT field FROM score_weights").fetchall()
        }
        for sc in SCORE_CONFIG:
            f = sc["field"]
            if f not in existing:
                d = DEFAULT_WEIGHTS.get(f, {"enabled": 0, "weight": 0})
                cur.execute(
                    "INSERT INTO score_weights (field, enabled, weight, direction, formula, formula_min, formula_max) VALUES (?,?,?,?,?,?,?)",
                    (
                        f,
                        d["enabled"],
                        d["weight"],
                        sc["direction"],
                        sc["formula"],
                        sc["formula_min"],
                        sc["formula_max"],
                    ),
                )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            emoji TEXT NOT NULL DEFAULT '\U0001f4e6'
        )
    """)

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO categories (name, emoji) VALUES (?,?)",
            [("Snacks", "\U0001f37f")],
        )

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
            cur.execute(
                "INSERT INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
                (name, pdcaas, diaas),
            )

    # ── User settings (key-value store) ──────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM user_settings WHERE key='language'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO user_settings (key, value) VALUES ('language', ?)",
            (DEFAULT_LANGUAGE,),
        )

    run_migrations(cur)

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        seed_products(cur)

    conn.commit()


def seed_products(cur):
    # 64x64 popcorn icon as Base64 PNG
    demo_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAACE0lEQVR42u2aQW7CMBBFx6gn6M4s0kU2SIgDtBKqsinX4CaoN+EadIOqSu0BEBISYlEWya5XoJsmSsPYmMRj3PL/0gnB/3k84wkQQRAEXbHUpb44X88PzbH+cKr+PYDSuB5Mjq4Vm0VwECoG45cEoUKEdL6eH1yMcyDqz5DYMje+zOs0Y8d9TDJfzw86GYk8X0mZr1Zxt6Q2q1+PAs58dX2/6hQJPUnzREQ6zao97ds8EZFORuz2EAfgYr4LBBfzPiD06MoFAACAXkC2CphKIZcUuXtcEmGXUhj8HFAa5z5T7JZHIKI+BzQnzpqvlcBisyCdZmQCVl77dX8yomK/MpqP4iis04yFUDdamm9zbjBBsMEJCsAU0s3oqEL8xJZprrJORs6HoosBOKcPMEVDsVuyRksIUZbB/nCquPC3NUF6MDleaYN5W6h3TYBi5wCXDrAOwWbe534XA2CKAtHt5WH1W+WA19s7tuvajmdEb+Sc6bua345nxrk8fn0qMQA2lRBCmI+2F/A5uRDP70lN8tQLkHop1Gl2MsH5XnnxbtAGgTsH2CBImRc/CJlygn38Oei2OruMmDJvTDqnCrSuo/n9EwtCv/90cg+ToONERP2PFxVNDvgrAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXtXkFLam28+n2P0HDbwNXAyAGELFFIgRB0J/SN+/1PYzfKqMwAAAAAElFTkSuQmCC"

    data = [
        (
            "Snacks",  # type
            "Classic Popcorn",  # name
            "7000000000001",  # ean
            "SmartSnack",  # brand
            "All stores",  # stores
            "Corn, sunflower oil, sea salt",  # ingredients
            3.0,  # taste_score
            450.0,  # kcal
            1880.0,  # energy_kj
            55.0,  # carbs
            1.0,  # sugar
            20.0,  # fat
            2.5,  # saturated_fat
            9.0,  # protein
            12.0,  # fiber
            1.5,  # salt
            1.0,  # volume
            25.0,  # price
            100.0,  # weight
            25.0,  # portion
            0.5,  # est_pdcaas
            0.4,  # est_diaas
            demo_image_base64,  # image (Base64 string)
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
        data,
    )
