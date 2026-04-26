"""Tests for the reimplemented tag system (Sonarr/Radarr style)."""

import json
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


@pytest.fixture()
def tag_id(client):
    """Create a tag and return its id."""
    resp = client.post(
        "/api/tags",
        data=json.dumps({"label": "organic"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


# ── Tag CRUD ──────────────────────────────────────────────────────────────────


def test_create_tag(client):
    resp = client.post(
        "/api/tags",
        data=json.dumps({"label": "organic"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["label"] == "organic"
    assert isinstance(data["id"], int)


def test_create_tag_lowercases_and_strips(client):
    resp = client.post(
        "/api/tags",
        data=json.dumps({"label": "  Organic  "}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.get_json()["label"] == "organic"


def test_create_tag_idempotent_on_duplicate(client):
    """POST with duplicate label returns existing tag (201, not error)."""
    r1 = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json")
    r2 = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.get_json()["id"] == r2.get_json()["id"]


def test_create_tag_case_insensitive_idempotent(client):
    r1 = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json")
    r2 = client.post("/api/tags", data=json.dumps({"label": "SALTY"}), content_type="application/json")
    assert r1.get_json()["id"] == r2.get_json()["id"]


def test_create_tag_empty_label_returns_400(client):
    resp = client.post("/api/tags", data=json.dumps({"label": ""}), content_type="application/json")
    assert resp.status_code == 400


def test_create_tag_too_long_returns_400(client):
    resp = client.post(
        "/api/tags",
        data=json.dumps({"label": "x" * 51}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_create_tag_exactly_50_chars(client):
    resp = client.post(
        "/api/tags",
        data=json.dumps({"label": "a" * 50}),
        content_type="application/json",
    )
    assert resp.status_code == 201


def test_get_tag(client, tag_id):
    resp = client.get(f"/api/tags/{tag_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == tag_id
    assert data["label"] == "organic"


def test_get_tag_not_found(client):
    resp = client.get("/api/tags/99999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_list_tags(client):
    client.post("/api/tags", data=json.dumps({"label": "zesty"}), content_type="application/json")
    client.post("/api/tags", data=json.dumps({"label": "apple"}), content_type="application/json")
    resp = client.get("/api/tags")
    assert resp.status_code == 200
    labels = [t["label"] for t in resp.get_json()]
    assert labels == sorted(labels)
    assert "zesty" in labels
    assert "apple" in labels


def test_list_tags_returns_all(client):
    """GET /api/tags without ?q returns all tags (no limit)."""
    for i in range(12):
        client.post("/api/tags", data=json.dumps({"label": f"tag{i:02d}"}), content_type="application/json")
    resp = client.get("/api/tags")
    assert len(resp.get_json()) >= 12


def test_update_tag(client, tag_id):
    resp = client.put(
        f"/api/tags/{tag_id}",
        data=json.dumps({"label": "bio"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == tag_id
    assert data["label"] == "bio"


def test_update_tag_not_found(client):
    resp = client.put(
        "/api/tags/99999",
        data=json.dumps({"label": "newname"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_update_tag_duplicate_label_returns_400(client):
    r1 = client.post("/api/tags", data=json.dumps({"label": "first"}), content_type="application/json")
    r2 = client.post("/api/tags", data=json.dumps({"label": "second"}), content_type="application/json")
    id2 = r2.get_json()["id"]
    resp = client.put(
        f"/api/tags/{id2}",
        data=json.dumps({"label": "first"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_update_tag_same_label_idempotent(client, tag_id):
    """Renaming to same label should succeed."""
    resp = client.put(
        f"/api/tags/{tag_id}",
        data=json.dumps({"label": "organic"}),
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_update_tag_empty_label_returns_400(client, tag_id):
    resp = client.put(
        f"/api/tags/{tag_id}",
        data=json.dumps({"label": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_delete_tag(client, tag_id):
    resp = client.delete(f"/api/tags/{tag_id}")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    # confirm gone
    assert client.get(f"/api/tags/{tag_id}").status_code == 404


def test_delete_tag_not_found(client):
    resp = client.delete("/api/tags/99999")
    assert resp.status_code == 404


# ── Autocomplete / search ─────────────────────────────────────────────────────


def test_search_tags_prefix(client):
    client.post("/api/tags", data=json.dumps({"label": "organic"}), content_type="application/json")
    client.post("/api/tags", data=json.dumps({"label": "orange"}), content_type="application/json")
    client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json")
    # "or" matches both "organic" and "orange"; "salty" should not match
    resp = client.get("/api/tags?q=or")
    assert resp.status_code == 200
    labels = [t["label"] for t in resp.get_json()]
    assert "organic" in labels
    assert "orange" in labels
    assert "salty" not in labels


def test_search_tags_case_insensitive(client):
    client.post("/api/tags", data=json.dumps({"label": "organic"}), content_type="application/json")
    resp = client.get("/api/tags?q=ORG")
    labels = [t["label"] for t in resp.get_json()]
    assert "organic" in labels


def test_search_tags_empty_q_returns_up_to_10(client):
    for i in range(12):
        client.post("/api/tags", data=json.dumps({"label": f"tag{i:02d}"}), content_type="application/json")
    resp = client.get("/api/tags?q=")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 10


def test_search_tags_no_match(client):
    client.post("/api/tags", data=json.dumps({"label": "organic"}), content_type="application/json")
    resp = client.get("/api/tags?q=xyz")
    assert resp.get_json() == []


# ── Product-tag integration ───────────────────────────────────────────────────


def test_product_update_with_tag_ids(client, product_id):
    tag_resp = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json")
    tid = tag_resp.get_json()["id"]

    put_resp = client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [tid]}),
        content_type="application/json",
    )
    assert put_resp.status_code == 200

    get_resp = client.get("/api/products")
    products = get_resp.get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    assert product["tags"] == [{"id": tid, "label": "salty"}]


def test_product_tags_returned_as_objects(client, product_id):
    """GET /api/products returns tags: [{id, label}], not strings."""
    t1 = client.post("/api/tags", data=json.dumps({"label": "bio"}), content_type="application/json").get_json()
    t2 = client.post("/api/tags", data=json.dumps({"label": "vegan"}), content_type="application/json").get_json()

    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [t1["id"], t2["id"]]}),
        content_type="application/json",
    )

    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    tag_ids = {t["id"] for t in product["tags"]}
    tag_labels = {t["label"] for t in product["tags"]}
    assert tag_ids == {t1["id"], t2["id"]}
    assert tag_labels == {"bio", "vegan"}
    # Each element must be a dict with id and label
    for t in product["tags"]:
        assert "id" in t and "label" in t


def test_product_clear_tags_with_empty_list(client, product_id):
    tid = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json").get_json()["id"]
    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [tid]}),
        content_type="application/json",
    )
    # Clear
    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": []}),
        content_type="application/json",
    )
    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    assert product["tags"] == []


def test_product_update_without_tag_ids_leaves_tags(client, product_id):
    """PUT without tagIds key does not change existing tags."""
    tid = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json").get_json()["id"]
    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [tid]}),
        content_type="application/json",
    )
    # Update without tagIds — tags should remain
    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Renamed Popcorn"}),
        content_type="application/json",
    )
    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    assert len(product["tags"]) == 1
    assert product["tags"][0]["label"] == "salty"


def test_delete_tag_removes_product_associations(client, product_id):
    tid = client.post("/api/tags", data=json.dumps({"label": "salty"}), content_type="application/json").get_json()["id"]
    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [tid]}),
        content_type="application/json",
    )
    client.delete(f"/api/tags/{tid}")
    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    assert product["tags"] == []


def test_invalid_tag_ids_silently_ignored(client, product_id):
    """tagIds with non-existent IDs are silently ignored."""
    valid_tid = client.post("/api/tags", data=json.dumps({"label": "valid"}), content_type="application/json").get_json()["id"]
    put_resp = client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [valid_tid, 99999]}),
        content_type="application/json",
    )
    assert put_resp.status_code == 200
    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    assert len(product["tags"]) == 1
    assert product["tags"][0]["label"] == "valid"


def test_tags_sorted_alphabetically(client, product_id):
    t1 = client.post("/api/tags", data=json.dumps({"label": "zesty"}), content_type="application/json").get_json()
    t2 = client.post("/api/tags", data=json.dumps({"label": "apple"}), content_type="application/json").get_json()
    t3 = client.post("/api/tags", data=json.dumps({"label": "mango"}), content_type="application/json").get_json()

    client.put(
        f"/api/products/{product_id}",
        data=json.dumps({"name": "Test Popcorn", "tagIds": [t1["id"], t2["id"], t3["id"]]}),
        content_type="application/json",
    )
    products = client.get("/api/products").get_json()["products"]
    product = next(p for p in products if p["id"] == product_id)
    labels = [t["label"] for t in product["tags"]]
    assert labels == sorted(labels)
