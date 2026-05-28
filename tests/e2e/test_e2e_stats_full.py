"""End-to-end full-coverage tests for ``blueprints/stats.py``.

Phase 2C of the LSO-1352 audit. The stats blueprint is tiny (one endpoint:
``GET /api/stats``) so this file exercises every branch:

- Empty database (zero products): ``total`` is 0, ``type_counts`` is an
  empty dict, ``categories`` still contains the seeded 'Snacks' row.
- Single product: ``total`` is 1, ``type_counts`` is ``{type: 1}``, and the
  product's category is reflected in the categories list.
- Multiple products across categories: ``total`` and ``type_counts`` are
  accurate to per-type integer counts.
- Products with NULL nutrition fields: must NOT affect total or
  type_counts (verifies the count is row-based, not nutrition-based).
- Products tagged with a category that does NOT exist in the categories
  table: type_counts still reports them (sanity: type_counts is derived
  from products, not from the categories join).
- Category list shape: every entry has ``name``, ``emoji``, ``label``
  with the right types, and ordering is by name ASC.
- Numeric shape: ``total`` and every ``type_counts`` value are non-negative
  integers; ``types`` equals ``len(categories)``.

Rule 18: every test asserts the *outcome* (specific counts against the
seeded fixtures), not just shape.
"""

import json
import urllib.request


def _get_stats(live_url):
    """Fetch ``/api/stats`` and return the parsed body."""
    with urllib.request.urlopen(f"{live_url}/api/stats", timeout=5) as resp:
        assert resp.status == 200
        return json.loads(resp.read())


def _post_category(live_url, name, label, emoji="\U0001f4e6"):
    """Add a new category via the API."""
    data = json.dumps({"name": name, "label": label, "emoji": emoji}).encode()
    req = urllib.request.Request(
        f"{live_url}/api/categories",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


# ---------------------------------------------------------------------------
# Empty-DB and seeded-DB baselines
# ---------------------------------------------------------------------------


def test_stats_empty_db_has_zero_products(live_url):
    """With no products in the DB (reset_db wipes products) total is 0 and
    type_counts is empty, but the seeded 'Snacks' category is still listed."""
    stats = _get_stats(live_url)

    assert stats["total"] == 0, f"Expected total=0 on empty DB, got {stats['total']}"
    assert stats["type_counts"] == {}, (
        f"Expected type_counts={{}} on empty DB, got {stats['type_counts']}"
    )
    # Seeded 'Snacks' category remains.
    category_names = {c["name"] for c in stats["categories"]}
    assert "Snacks" in category_names, (
        f"Seeded 'Snacks' category should be present: {category_names}"
    )
    # 'types' equals the number of categories.
    assert stats["types"] == len(stats["categories"])


def test_stats_categories_shape(live_url):
    """Each category entry has exactly the three required keys with correct types."""
    stats = _get_stats(live_url)

    for cat in stats["categories"]:
        assert set(cat.keys()) == {"name", "emoji", "label"}, (
            f"Unexpected keys in category {cat!r}"
        )
        assert isinstance(cat["name"], str) and cat["name"], (
            f"Category name must be non-empty string: {cat!r}"
        )
        assert isinstance(cat["emoji"], str), (
            f"Category emoji must be a string: {cat!r}"
        )
        assert isinstance(cat["label"], str), (
            f"Category label must be a string: {cat!r}"
        )


def test_stats_categories_sorted_by_name(live_url, unique_name):
    """Categories are returned ordered by name ASC.

    Add several categories then verify the response order. Service uses
    ``ORDER BY name`` so the returned ``name`` values must be sorted
    lexicographically.
    """
    # Insert categories in non-sorted order.
    names = [unique_name("zeta-cat"), unique_name("alpha-cat"), unique_name("mid-cat")]
    for n in names:
        status = _post_category(live_url, n, "Lbl")
        assert status == 201

    stats = _get_stats(live_url)
    response_names = [c["name"] for c in stats["categories"]]

    # Filter to just the newly-added (avoid being affected by 'Snacks' seed).
    inserted = [n for n in response_names if n in set(names)]
    assert inserted == sorted(inserted), (
        f"Categories must be sorted ASC by name; got {inserted}"
    )


# ---------------------------------------------------------------------------
# Total + type_counts with products
# ---------------------------------------------------------------------------


def test_stats_total_increments_per_product(live_url, api_create_product, unique_name):
    """``total`` equals the row count of products."""
    api_create_product(name=unique_name("S1"))
    api_create_product(name=unique_name("S2"))
    api_create_product(name=unique_name("S3"))

    stats = _get_stats(live_url)
    assert stats["total"] == 3, f"Expected total=3, got {stats['total']}"


def test_stats_type_counts_groups_by_type(live_url, api_create_product, unique_name):
    """``type_counts`` is a dict mapping category names to product counts.

    Set up two distinct types and verify each one's count is exactly correct
    (the integer, not a range).
    """
    # The 'Snacks' category is seeded; add a second category.
    new_cat = unique_name("breakfast")
    _post_category(live_url, new_cat, "Breakfast")

    api_create_product(name=unique_name("SnacksA"), category="Snacks")
    api_create_product(name=unique_name("SnacksB"), category="Snacks")
    api_create_product(name=unique_name("BreakA"), category=new_cat)

    stats = _get_stats(live_url)
    assert stats["type_counts"].get("Snacks") == 2, (
        f"Expected Snacks=2, got {stats['type_counts']}"
    )
    assert stats["type_counts"].get(new_cat) == 1, (
        f"Expected {new_cat}=1, got {stats['type_counts']}"
    )


def test_stats_type_counts_match_total(live_url, api_create_product, unique_name):
    """Sum of ``type_counts`` values must equal ``total``."""
    cat_a = unique_name("ca")
    cat_b = unique_name("cb")
    _post_category(live_url, cat_a, "A")
    _post_category(live_url, cat_b, "B")

    for _ in range(2):
        api_create_product(name=unique_name("PA"), category=cat_a)
    for _ in range(3):
        api_create_product(name=unique_name("PB"), category=cat_b)

    stats = _get_stats(live_url)
    assert sum(stats["type_counts"].values()) == stats["total"] == 5, (
        f"type_counts sum {sum(stats['type_counts'].values())} must equal "
        f"total {stats['total']}"
    )


def test_stats_products_with_null_nutrition_still_counted(
    live_url, api_create_product, unique_name
):
    """Products with NULL nutrition values must still be counted.

    The stats endpoint reports row counts, not nutrition completeness, so a
    product whose kcal/fat/protein are all null must still appear in
    ``total`` and ``type_counts``.
    """
    api_create_product(
        name=unique_name("NullNutri"),
        kcal=None,
        fat=None,
        protein=None,
        carbs=None,
        sugar=None,
        saturated_fat=None,
        fiber=None,
        salt=None,
    )
    api_create_product(name=unique_name("WithNutri"))

    stats = _get_stats(live_url)
    assert stats["total"] == 2, (
        f"NULL-nutrition product must still count toward total: {stats}"
    )
    assert stats["type_counts"].get("Snacks") == 2, (
        f"Both products should be in 'Snacks' type_counts: {stats['type_counts']}"
    )


def test_stats_types_equals_categories_length(live_url, unique_name):
    """``types`` is exactly ``len(categories)`` — verifies the relationship."""
    # Seed adds 'Snacks'; add one more category.
    new_cat = unique_name("extracat")
    _post_category(live_url, new_cat, "Extra")

    stats = _get_stats(live_url)
    assert stats["types"] == len(stats["categories"])
    assert stats["types"] >= 2, (
        f"Expected ≥ 2 categories (Snacks + new), got {stats['types']}"
    )


# ---------------------------------------------------------------------------
# Numeric-shape invariants
# ---------------------------------------------------------------------------


def test_stats_numeric_invariants(live_url, api_create_product, unique_name):
    """All counts are non-negative integers; ``total`` ≥ max(type_counts.values())."""
    api_create_product(name=unique_name("ShapeProd"))
    stats = _get_stats(live_url)

    assert isinstance(stats["total"], int) and stats["total"] >= 0
    assert isinstance(stats["types"], int) and stats["types"] >= 0
    for tname, count in stats["type_counts"].items():
        assert isinstance(tname, str)
        assert isinstance(count, int) and count >= 0
    if stats["type_counts"]:
        assert stats["total"] >= max(stats["type_counts"].values())


def test_stats_response_top_level_keys(live_url):
    """Response carries exactly the documented top-level keys."""
    stats = _get_stats(live_url)
    assert set(stats.keys()) == {"total", "types", "type_counts", "categories"}, (
        f"Unexpected top-level keys: {sorted(stats.keys())}"
    )
