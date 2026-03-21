"""Tests for the /api/stats endpoint and the stats-line UI element."""

import json
import re
import urllib.request

from playwright.sync_api import expect


def test_stats_api_returns_data(live_url, api_create_product):
    """GET /api/stats should return total, types, and categories after products exist."""
    api_create_product(name="StatsApiProduct1")
    api_create_product(name="StatsApiProduct2")

    with urllib.request.urlopen(f"{live_url}/api/stats", timeout=5) as resp:
        data = json.loads(resp.read())

    assert "total" in data, "Response missing 'total' key"
    assert "types" in data, "Response missing 'types' key"
    assert "categories" in data, "Response missing 'categories' key"
    assert data["total"] >= 2, (
        f"Expected total >= 2 after creating 2 products, got {data['total']}"
    )


def test_stats_api_counts_categories(live_url, api_create_product):
    """GET /api/stats should include well-formed category objects in the response.

    The database seeds a 'Snacks' category on first run.  Creating products
    tagged as 'Snacks' ensures at least one category is always present so the
    response shape can be validated.
    """
    api_create_product(name="StatsCatProduct1", category="Snacks")
    api_create_product(name="StatsCatProduct2", category="Snacks")

    with urllib.request.urlopen(f"{live_url}/api/stats", timeout=5) as resp:
        data = json.loads(resp.read())

    categories = data["categories"]
    assert isinstance(categories, list), "'categories' should be a list"
    assert len(categories) >= 1, "Expected at least one category in response"

    # The 'Snacks' category is always present — it is seeded in db.init_db().
    category_names = {cat["name"] for cat in categories}
    assert "Snacks" in category_names, (
        f"'Snacks' not found in categories: {category_names}"
    )

    # Every category object must carry the three required keys.
    for cat in categories:
        assert "name" in cat, f"Category entry missing 'name': {cat}"
        assert "emoji" in cat, f"Category entry missing 'emoji': {cat}"
        assert "label" in cat, f"Category entry missing 'label': {cat}"


def test_stats_line_visible(page, api_create_product):
    """#stats-line should be visible and contain product count text after load."""
    api_create_product(name="StatsLineProduct1")
    api_create_product(name="StatsLineProduct2")

    page.reload()
    page.wait_for_function(
        "() => !document.querySelector('#results-container .loading')",
        timeout=10000,
    )

    stats_line = page.locator("#stats-line")
    expect(stats_line).to_be_visible()
    # The element is populated by JS with a translation string like
    # "N produkter · M kategorier" — verify it contains a digit (the count).
    expect(stats_line).to_have_text(re.compile(r"\d+"))
