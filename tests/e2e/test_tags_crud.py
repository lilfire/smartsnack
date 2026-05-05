"""E2E tests for Tags CRUD endpoints and tag lifecycle flow.

Covers:
- GET /api/tags (list all + search with ?q=)
- POST /api/tags (create)
- GET /api/tags/<id> (get single)
- PUT /api/tags/<id> (update)
- DELETE /api/tags/<id> (delete)
- Tag management lifecycle with product associations
"""

import json
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_raw(live_url, path, *, method="GET", body=None):
    """Make a JSON API request, returning (status_code, parsed_body)."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _api(live_url, path, *, method="GET", body=None):
    """Make a JSON API request, returning parsed body only."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _cleanup_tag(live_url, tag_id):
    """Best-effort delete a tag by ID."""
    _api_raw(live_url, f"/api/tags/{tag_id}", method="DELETE")


def _get_product_by_id(live_url, product_id):
    """Fetch a single product by searching the product list.

    There is no GET /api/products/<id> endpoint; use the list endpoint
    and filter client-side.
    """
    _, data = _api_raw(live_url, f"/api/products?limit=1000")
    for p in data.get("products", []):
        if p["id"] == product_id:
            return p
    return {}


# ---------------------------------------------------------------------------
# POST /api/tags — Create
# ---------------------------------------------------------------------------


def test_create_tag_happy_path(live_url, unique_name):
    """POST /api/tags with valid label creates a tag and returns 201."""
    label = unique_name("e2e-create-test").lower()
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert "id" in body
    assert body["label"] == label
    _cleanup_tag(live_url, body["id"])


def test_create_tag_strips_whitespace_and_preserves_case(live_url, unique_name):
    """POST /api/tags strips whitespace but preserves the original case (LSO-1035)."""
    base = unique_name("E2E-Case-Test")
    raw = f"  {base}  "
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": raw})
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert body["label"] == base
    _cleanup_tag(live_url, body["id"])


def test_create_tag_idempotent(live_url, unique_name):
    """POST /api/tags with an existing label returns the existing tag."""
    label = unique_name("e2e-idempotent").lower()
    status1, tag1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    assert status1 == 201
    status2, tag2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    assert status2 == 201
    assert tag1["id"] == tag2["id"]
    assert tag1["label"] == tag2["label"]
    _cleanup_tag(live_url, tag1["id"])


def test_create_tag_empty_label(live_url):
    """POST /api/tags with empty label returns 400."""
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": ""})
    assert status == 400
    assert "error" in body
    assert "label is required" in body["error"]


def test_create_tag_whitespace_only_label(live_url):
    """POST /api/tags with whitespace-only label returns 400."""
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": "   "})
    assert status == 400
    assert "label is required" in body["error"]


def test_create_tag_exceeds_max_length(live_url):
    """POST /api/tags with label > 50 chars returns 400."""
    long_label = "x" * 51
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": long_label})
    assert status == 400
    assert "maximum length" in body["error"]


def test_create_tag_exactly_max_length(live_url):
    """POST /api/tags with label of exactly 50 chars succeeds."""
    label = "a" * 50
    status, body = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    assert status == 201
    assert body["label"] == label
    _cleanup_tag(live_url, body["id"])


# ---------------------------------------------------------------------------
# GET /api/tags — List all
# ---------------------------------------------------------------------------


def test_list_tags_returns_list(live_url, unique_name):
    """GET /api/tags returns a list."""
    label = unique_name("e2e-list-check").lower()
    _, tag = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tags = _api(live_url, "/api/tags")
    assert isinstance(tags, list)
    labels = [t["label"] for t in tags]
    assert label in labels
    _cleanup_tag(live_url, tag["id"])


def test_list_tags_response_shape(live_url, unique_name):
    """GET /api/tags items have id and label keys."""
    label = unique_name("e2e-shape-check").lower()
    _, tag = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tags = _api(live_url, "/api/tags")
    for t in tags:
        assert "id" in t, "Each tag should have 'id'"
        assert "label" in t, "Each tag should have 'label'"
        assert isinstance(t["id"], int)
        assert isinstance(t["label"], str)
    _cleanup_tag(live_url, tag["id"])


def test_list_tags_sorted_case_insensitive(live_url, unique_name):
    """GET /api/tags returns tags sorted by label case-insensitively."""
    suffix = unique_name("").lower()
    zebra = f"e2e-zebra-sort-{suffix}"
    alpha = f"e2e-alpha-sort-{suffix}"
    _, t1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": zebra})
    _, t2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": alpha})
    tags = _api(live_url, "/api/tags")
    labels = [t["label"] for t in tags]
    idx_alpha = labels.index(alpha)
    idx_zebra = labels.index(zebra)
    assert idx_alpha < idx_zebra, "Tags should be sorted alphabetically"
    _cleanup_tag(live_url, t1["id"])
    _cleanup_tag(live_url, t2["id"])


# ---------------------------------------------------------------------------
# GET /api/tags?q=<query> — Search
# ---------------------------------------------------------------------------


def test_search_tags_matching(live_url, unique_name):
    """GET /api/tags?q=prefix returns matching tags."""
    suffix = unique_name("").lower()
    label = f"e2e-searchmatch-{suffix}"
    _, tag = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    status, results = _api_raw(live_url, f"/api/tags?q=e2e-searchmatch-{suffix}")
    assert status == 200
    assert isinstance(results, list)
    labels = [t["label"] for t in results]
    assert label in labels
    _cleanup_tag(live_url, tag["id"])


def test_search_tags_no_results(live_url):
    """GET /api/tags?q=nonexistent returns empty list."""
    status, results = _api_raw(live_url, "/api/tags?q=zzz-no-such-tag-exists-xyz")
    assert status == 200
    assert results == []


def test_search_tags_partial_match(live_url, unique_name):
    """GET /api/tags?q= with partial prefix returns matches."""
    suffix = unique_name("").lower()
    aaa = f"e2e-partial-{suffix}-aaa"
    bbb = f"e2e-partial-{suffix}-bbb"
    _, t1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": aaa})
    _, t2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": bbb})
    results = _api(live_url, f"/api/tags?q=e2e-partial-{suffix}")
    labels = [t["label"] for t in results]
    assert aaa in labels
    assert bbb in labels
    _cleanup_tag(live_url, t1["id"])
    _cleanup_tag(live_url, t2["id"])


# ---------------------------------------------------------------------------
# GET /api/tags/<id> — Get single
# ---------------------------------------------------------------------------


def test_get_tag_happy_path(live_url, unique_name):
    """GET /api/tags/<id> returns the tag."""
    label = unique_name("e2e-get-single").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}")
    assert status == 200
    assert body["id"] == tag_id
    assert body["label"] == label
    _cleanup_tag(live_url, tag_id)


def test_get_tag_not_found(live_url):
    """GET /api/tags/<id> with invalid id returns 404."""
    status, body = _api_raw(live_url, "/api/tags/999999")
    assert status == 404
    assert "error" in body
    assert "not found" in body["error"].lower()


# ---------------------------------------------------------------------------
# PUT /api/tags/<id> — Update
# ---------------------------------------------------------------------------


def test_update_tag_happy_path(live_url, unique_name):
    """PUT /api/tags/<id> renames the tag."""
    old_label = unique_name("e2e-update-old").lower()
    new_label = unique_name("e2e-update-new").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": old_label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}", method="PUT", body={"label": new_label})
    assert status == 200
    assert body["id"] == tag_id
    assert body["label"] == new_label
    # Verify via GET
    _, fetched = _api_raw(live_url, f"/api/tags/{tag_id}")
    assert fetched["label"] == new_label
    _cleanup_tag(live_url, tag_id)


def test_update_tag_not_found(live_url):
    """PUT /api/tags/<id> with invalid id returns 404."""
    status, body = _api_raw(live_url, f"/api/tags/999999", method="PUT", body={"label": "anything"})
    assert status == 404
    assert "not found" in body["error"].lower()


def test_update_tag_empty_label(live_url, unique_name):
    """PUT /api/tags/<id> with empty label returns 400."""
    label = unique_name("e2e-update-empty").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}", method="PUT", body={"label": ""})
    assert status == 400
    assert "label is required" in body["error"]
    _cleanup_tag(live_url, tag_id)


def test_update_tag_exceeds_max_length(live_url, unique_name):
    """PUT /api/tags/<id> with label > 50 chars returns 400."""
    label = unique_name("e2e-update-long").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}", method="PUT", body={"label": "x" * 51})
    assert status == 400
    assert "maximum length" in body["error"]
    _cleanup_tag(live_url, tag_id)


def test_update_tag_duplicate_label(live_url, unique_name):
    """PUT /api/tags/<id> with label used by another tag returns 400."""
    existing = unique_name("e2e-dup-existing").lower()
    rename = unique_name("e2e-dup-rename").lower()
    _, tag1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": existing})
    _, tag2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": rename})
    status, body = _api_raw(live_url, f"/api/tags/{tag2['id']}", method="PUT", body={"label": existing})
    assert status == 400
    assert "already exists" in body["error"]
    _cleanup_tag(live_url, tag1["id"])
    _cleanup_tag(live_url, tag2["id"])


def test_update_tag_same_label_succeeds(live_url, unique_name):
    """PUT /api/tags/<id> with its own current label succeeds (no-op rename)."""
    label = unique_name("e2e-same-label").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}", method="PUT", body={"label": label})
    assert status == 200
    assert body["label"] == label
    _cleanup_tag(live_url, tag_id)


# ---------------------------------------------------------------------------
# DELETE /api/tags/<id>
# ---------------------------------------------------------------------------


def test_delete_tag_happy_path(live_url, unique_name):
    """DELETE /api/tags/<id> deletes the tag and returns ok."""
    label = unique_name("e2e-delete-me").lower()
    _, created = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})
    tag_id = created["id"]
    status, body = _api_raw(live_url, f"/api/tags/{tag_id}", method="DELETE")
    assert status == 200
    assert body["ok"] is True
    # Verify it's gone
    status2, _ = _api_raw(live_url, f"/api/tags/{tag_id}")
    assert status2 == 404


def test_delete_tag_not_found(live_url):
    """DELETE /api/tags/<id> with invalid id returns 404."""
    status, body = _api_raw(live_url, "/api/tags/999999", method="DELETE")
    assert status == 404
    assert "not found" in body["error"].lower()


# ---------------------------------------------------------------------------
# Tag management lifecycle with product associations
# ---------------------------------------------------------------------------


def test_tag_lifecycle_create_assign_update_delete(live_url, api_create_product, unique_name):
    """Full lifecycle: create tag -> assign to product -> update tag -> delete tag -> verify removal."""
    label_a = unique_name("e2e-lifecycle-a").lower()
    label_b = unique_name("e2e-lifecycle-b").lower()
    label_renamed = unique_name("e2e-lifecycle-renamed").lower()
    # 1. Create tags
    _, tag1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label_a})
    _, tag2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label_b})
    assert tag1["id"] != tag2["id"]

    # 2. Create a product then assign tags via PUT
    product = api_create_product(name=unique_name("LifecycleTagProd"))
    product_id = product["id"]
    _api_raw(
        live_url, f"/api/products/{product_id}",
        method="PUT", body={"tagIds": [tag1["id"], tag2["id"]]}
    )

    # 3. Verify tags are associated with the product
    prod_data = _get_product_by_id(live_url, product_id)
    prod_tag_ids = [t["id"] for t in prod_data.get("tags", [])]
    assert tag1["id"] in prod_tag_ids
    assert tag2["id"] in prod_tag_ids

    # 4. Update tag1
    status, updated = _api_raw(
        live_url, f"/api/tags/{tag1['id']}", method="PUT",
        body={"label": label_renamed}
    )
    assert status == 200
    assert updated["label"] == label_renamed

    # 5. Verify product still has the renamed tag
    prod_data2 = _get_product_by_id(live_url, product_id)
    prod_tag_labels = [t["label"] for t in prod_data2.get("tags", [])]
    assert label_renamed in prod_tag_labels

    # 6. Delete tag1 — should cascade remove from product
    status, _ = _api_raw(live_url, f"/api/tags/{tag1['id']}", method="DELETE")
    assert status == 200

    # 7. Verify product no longer has deleted tag but still has tag2
    prod_data3 = _get_product_by_id(live_url, product_id)
    remaining_ids = [t["id"] for t in prod_data3.get("tags", [])]
    assert tag1["id"] not in remaining_ids
    assert tag2["id"] in remaining_ids

    # 8. Search for the tag — should not appear
    results = _api(live_url, f"/api/tags?q={label_renamed}")
    assert all(t["id"] != tag1["id"] for t in results)

    # Cleanup
    _cleanup_tag(live_url, tag2["id"])


def test_tag_assignment_multiple_products(live_url, api_create_product, unique_name):
    """A single tag can be shared across multiple products."""
    label = unique_name("e2e-multi-prod").lower()
    _, tag = _api_raw(live_url, "/api/tags", method="POST", body={"label": label})

    prod1 = api_create_product(name=unique_name("MultiTagProd1"))
    _api_raw(live_url, f"/api/products/{prod1['id']}", method="PUT", body={"tagIds": [tag["id"]]})
    prod2 = api_create_product(name=unique_name("MultiTagProd2"))
    _api_raw(live_url, f"/api/products/{prod2['id']}", method="PUT", body={"tagIds": [tag["id"]]})

    p1 = _get_product_by_id(live_url, prod1["id"])
    p2 = _get_product_by_id(live_url, prod2["id"])

    assert tag["id"] in [t["id"] for t in p1.get("tags", [])]
    assert tag["id"] in [t["id"] for t in p2.get("tags", [])]

    # Deleting the tag removes it from both products
    _api_raw(live_url, f"/api/tags/{tag['id']}", method="DELETE")

    p1_after = _get_product_by_id(live_url, prod1["id"])
    p2_after = _get_product_by_id(live_url, prod2["id"])

    assert tag["id"] not in [t["id"] for t in p1_after.get("tags", [])]
    assert tag["id"] not in [t["id"] for t in p2_after.get("tags", [])]


def test_tag_removal_from_product_via_update(live_url, api_create_product, unique_name):
    """Updating a product's tags to exclude a tag removes the association."""
    label_a = unique_name("e2e-remove-a").lower()
    label_b = unique_name("e2e-remove-b").lower()
    _, tag1 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label_a})
    _, tag2 = _api_raw(live_url, "/api/tags", method="POST", body={"label": label_b})

    product = api_create_product(name=unique_name("TagRemoveProd"))
    product_id = product["id"]
    _api_raw(
        live_url, f"/api/products/{product_id}",
        method="PUT", body={"tagIds": [tag1["id"], tag2["id"]]}
    )

    # Update product to only have tag2
    _api_raw(
        live_url, f"/api/products/{product_id}",
        method="PUT",
        body={"tagIds": [tag2["id"]]}
    )

    updated_prod = _get_product_by_id(live_url, product_id)
    tag_ids = [t["id"] for t in updated_prod.get("tags", [])]
    assert tag1["id"] not in tag_ids
    assert tag2["id"] in tag_ids

    _cleanup_tag(live_url, tag1["id"])
    _cleanup_tag(live_url, tag2["id"])
