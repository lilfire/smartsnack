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
]


def run_migrations(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    applied = {r[0] for r in cur.execute("SELECT name FROM schema_migrations").fetchall()}
    for name, statements in MIGRATIONS:
        if name in applied:
            continue
        for sql in statements:
            cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (name) VALUES (?)", (name,))
