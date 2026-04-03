"""Database migrations tracked in the schema_migrations table.

Each migration is a (name, sql_list) tuple. Add new migrations at the end.
"""

MIGRATIONS = [
    (
        "001_volume_direct_formula",
        [
            "UPDATE score_weights SET formula='direct', formula_min=1, formula_max=3 "
            "WHERE field='volume' AND formula='minmax'",
        ],
    ),
    (
        "002_product_flags_table",
        [
            """CREATE TABLE IF NOT EXISTS product_flags (
                product_id INTEGER NOT NULL,
                flag TEXT NOT NULL,
                PRIMARY KEY (product_id, flag),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )""",
        ],
    ),
    (
        "003_flag_definitions_table",
        [
            """CREATE TABLE IF NOT EXISTS flag_definitions (
                name TEXT PRIMARY KEY,
                type TEXT NOT NULL CHECK(type IN ('user', 'system')),
                label_key TEXT NOT NULL
            )""",
            "INSERT OR IGNORE INTO flag_definitions (name, type, label_key) "
            "VALUES ('is_discontinued', 'user', 'flag_is_discontinued')",
            "INSERT OR IGNORE INTO flag_definitions (name, type, label_key) "
            "VALUES ('is_synced_with_off', 'system', 'flag_is_synced_with_off')",
        ],
    ),
    (
        "004_add_taste_note",
        [
            "ALTER TABLE products ADD COLUMN taste_note TEXT NOT NULL DEFAULT ''",
        ],
    ),
    (
        "005_fix_direct_formula_ranges",
        [
            "UPDATE score_weights SET formula_max = 6.0 WHERE field = 'taste_score' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_max = 1.0 WHERE field = 'est_pdcaas' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_max = 1.2 WHERE field = 'est_diaas' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_max = 100.0 WHERE field = 'pct_protein_cal' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_max = 100.0 WHERE field = 'pct_fat_cal' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_max = 100.0 WHERE field = 'pct_carb_cal' AND formula = 'direct' AND formula_max = 0",
            "UPDATE score_weights SET formula_min = 1.0, formula_max = 3.0 WHERE field = 'volume' AND formula = 'direct' AND formula_max = 0",
        ],
    ),
    (
        "006_product_eans_table",
        [
            """CREATE TABLE IF NOT EXISTS product_eans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                ean TEXT NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                UNIQUE(product_id, ean)
            )""",
            """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1 FROM products WHERE ean != ''""",
        ],
    ),
    (
        "007_add_fk_indexes",
        [
            "CREATE INDEX IF NOT EXISTS idx_product_flags_product_id ON product_flags(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_product_eans_product_id ON product_eans(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_product_tags_product_id ON product_tags(product_id)",
        ],
    ),
]


def run_migrations(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    applied = {
        r[0] for r in cur.execute("SELECT name FROM schema_migrations").fetchall()
    }
    for name, statements in MIGRATIONS:
        if name in applied:
            continue
        for sql in statements:
            cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (name) VALUES (?)", (name,))
