"""Database migrations tracked in the schema_migrations table.

Each migration entry is (name, steps) where steps is either:
  list[str]   — SQL statements executed in order
  callable    — Python function called with (cur,) for complex migrations
Add new migrations at the end.
"""


def _migrate_008_tag_system(cur):
    """Migrate product_tags from text-based to integer FK schema.

    Detects old schema (tag TEXT column) via PRAGMA table_info.
    If old schema: renames, creates new tables, migrates data, drops old.
    If already new schema or no table: creates tags + product_tags with IF NOT EXISTS.
    Idempotent.
    """
    cols = {
        row[1]
        for row in cur.execute("PRAGMA table_info(product_tags)").fetchall()
    }
    has_old_schema = "tag" in cols

    if has_old_schema:
        cur.execute("ALTER TABLE product_tags RENAME TO product_tags_old")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT    NOT NULL UNIQUE COLLATE NOCASE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_tags (
            product_id INTEGER NOT NULL,
            tag_id     INTEGER NOT NULL,
            PRIMARY KEY (product_id, tag_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id)     REFERENCES tags(id)     ON DELETE CASCADE
        )
    """)

    if has_old_schema:
        cur.execute("""
            INSERT OR IGNORE INTO tags (label)
            SELECT DISTINCT LOWER(TRIM(tag)) FROM product_tags_old
            WHERE TRIM(tag) != ''
        """)
        cur.execute("""
            INSERT OR IGNORE INTO product_tags (product_id, tag_id)
            SELECT o.product_id, t.id
            FROM product_tags_old o
            JOIN tags t ON LOWER(TRIM(o.tag)) = t.label COLLATE NOCASE
        """)
        cur.execute("DROP TABLE product_tags_old")

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_tags_product_id ON product_tags(product_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_tags_tag_id ON product_tags(tag_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_tags_label ON tags(label COLLATE NOCASE)"
    )


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
            "CREATE INDEX IF NOT EXISTS idx_products_type ON products(type)",
        ],
    ),
    (
        "008_add_synced_with_off_to_product_eans",
        [
            "ALTER TABLE product_eans ADD COLUMN synced_with_off INTEGER NOT NULL DEFAULT 0",
        ],
    ),
    (
        "009_tag_system_reimplementation",
        _migrate_008_tag_system,
    ),
    (
        "010_backfill_product_eans_from_products_ean",
        [
            # Repair products that have a non-empty products.ean but no
            # corresponding product_eans row. This drift can occur after
            # restoring a backup created before product_eans existed in the
            # backup format: restore_backup() does DELETE FROM products which
            # cascades-deletes product_eans, then re-inserts only into
            # products. Idempotent: NOT EXISTS ensures we only touch missing
            # rows.
            """INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary)
               SELECT id, ean, 1
               FROM products p
               WHERE p.ean IS NOT NULL AND p.ean != ''
                 AND NOT EXISTS (
                   SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id
                 )""",
            # Mark backfilled rows as synced_with_off=1 if the product has the
            # is_synced_with_off flag, so they behave the same as products
            # that were freshly added via OFF.
            """UPDATE product_eans
               SET synced_with_off = 1
               WHERE is_primary = 1
                 AND synced_with_off = 0
                 AND EXISTS (
                   SELECT 1 FROM product_flags pf
                   WHERE pf.product_id = product_eans.product_id
                     AND pf.flag = 'is_synced_with_off'
                 )""",
        ],
    ),
    (
        "011_add_collagen_protein_source",
        [
            "INSERT OR IGNORE INTO protein_quality (name, pdcaas, diaas) "
            "VALUES ('collagen', 0.08, 0.09)",
        ],
    ),
    (
        "012_add_pistachio_protein_source",
        [
            "INSERT OR IGNORE INTO protein_quality (name, pdcaas, diaas) "
            "VALUES ('pistachio', 0.73, 0.65)",
        ],
    ),
    (
        "013_add_dates_protein_source",
        [
            "INSERT OR IGNORE INTO protein_quality (name, pdcaas, diaas) "
            "VALUES ('dates', 0.30, 0.25)",
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
    for name, steps in MIGRATIONS:
        if name in applied:
            continue
        if callable(steps):
            steps(cur)
        else:
            for sql in steps:
                cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (name) VALUES (?)", (name,))
