"""Tests for product tags feature (LSO-93)."""

import json
import pytest


@pytest.fixture()
def product_id(client):
    """Create a product and return its id."""
    resp = client.post(
        "/api/products",
        data=json.dumps({"name": "Test Popcorn", "type": "Snacks", "ean": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_save_and_get_tags(client, product_id):
    """Save tags via PUT, GET returns them."""
    pid = product_id
    put_resp = client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn", "salty"]}),
        content_type="application/json",
    )
    assert put_resp.status_code == 200

    get_resp = client.get("/api/products")
    products = get_resp.get_json()["products"]
    product = next((p for p in products if p["id"] == pid), None)
    assert product is not None
    assert sorted(product["tags"]) == ["popcorn", "salty"]


def test_autocomplete_returns_match(client, product_id):
    """?q=pop returns [\"popcorn\"]."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn"]}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions?q=pop")
    assert resp.status_code == 200
    assert resp.get_json() == ["popcorn"]


def test_autocomplete_case_insensitive(client, product_id):
    """?q=POP also returns [\"popcorn\"]."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn"]}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions?q=POP")
    assert resp.status_code == 200
    assert resp.get_json() == ["popcorn"]


def test_deduplication(client, product_id):
    """Saving [\"popcorn\", \"Popcorn\"] stores only one entry."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn", "Popcorn"]}),
        content_type="application/json",
    )
    get_resp = client.get("/api/products")
    products = get_resp.get_json()["products"]
    product = next((p for p in products if p["id"] == pid), None)
    assert product is not None
    assert product["tags"] == ["popcorn"]


def test_clear_tags(client, product_id):
    """PUT with tags: [] clears all tags."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn", "salty"]}),
        content_type="application/json",
    )
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": []}),
        content_type="application/json",
    )
    get_resp = client.get("/api/products")
    products = get_resp.get_json()["products"]
    product = next((p for p in products if p["id"] == pid), None)
    assert product is not None
    assert product["tags"] == []


def test_autocomplete_empty_query(client, product_id):
    """?q= (empty) returns []."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn"]}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions?q=")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_autocomplete_no_q_param(client, product_id):
    """Missing q param returns []."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn"]}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_autocomplete_max_10_results(client, product_id):
    """Suggestions are capped at 10."""
    pid = product_id
    tags = [f"tag{i:02d}" for i in range(15)]
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": tags}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions?q=tag")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 10


def test_autocomplete_no_match(client, product_id):
    """No matching prefix returns []."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["popcorn"]}),
        content_type="application/json",
    )
    resp = client.get("/api/products/tags/suggestions?q=xyz")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_tags_on_create_then_update(client):
    """Tags are stored when updating a newly created product via PUT."""
    resp = client.post(
        "/api/products",
        data=json.dumps({"name": "Tag Create Test", "type": "Snacks", "ean": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    pid = resp.get_json()["id"]

    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Tag Create Test", "tags": ["fresh", "organic"]}),
        content_type="application/json",
    )

    get_resp = client.get("/api/products")
    product = next((p for p in get_resp.get_json()["products"] if p["id"] == pid), None)
    assert product is not None
    assert sorted(product["tags"]) == ["fresh", "organic"]


def test_tags_update_replaces(client, product_id):
    """PUT with new tags replaces old tags entirely."""
    pid = product_id
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["old1", "old2"]}),
        content_type="application/json",
    )
    client.put(
        f"/api/products/{pid}",
        data=json.dumps({"name": "Test Popcorn", "tags": ["new1"]}),
        content_type="application/json",
    )
    get_resp = client.get("/api/products")
    product = next((p for p in get_resp.get_json()["products"] if p["id"] == pid), None)
    assert product is not None
    assert product["tags"] == ["new1"]
