from db import get_db
from translations import _category_label


def get_stats():
    conn = get_db()
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    cats = cur.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    type_counts = {}
    for r in cur.execute("SELECT type, COUNT(*) as count FROM products GROUP BY type").fetchall():
        type_counts[r["type"]] = r["count"]
    return {
        "total": total, "types": len(cats), "type_counts": type_counts,
        "categories": [{"name": c["name"], "emoji": c["emoji"], "label": _category_label(c["name"])} for c in cats],
    }
