"""E2E tests for product merge, unsync, and check-duplicate endpoints."""

import json
import urllib.error
import urllib.request


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def test_unsync_product(live_url, api_create_product):
    """POST /api/products/<id>/unsync removes the synced flag."""
    product = api_create_product(name="UnsyncProduct")
    pid = product["id"]

    status, body = _post(f"{live_url}/api/products/{pid}/unsync", {})
    assert status == 200
    assert body.get("ok") is True


def test_unsync_nonexistent(live_url):
    """POST /api/products/999999/unsync returns 400."""
    status, body = _post(f"{live_url}/api/products/999999/unsync", {})
    assert status == 400


def test_check_duplicate(live_url, api_create_product):
    """POST /api/products/<id>/check-duplicate returns duplicate info."""
    product = api_create_product(name="DupCheckProduct", ean="1111111111111")
    pid = product["id"]

    status, body = _post(
        f"{live_url}/api/products/{pid}/check-duplicate",
        {"ean": "1111111111111", "name": "DupCheckProduct"},
    )
    assert status == 200
    assert "duplicate" in body
    assert "a_is_synced_with_off" in body


def test_merge_products(live_url, api_create_product):
    """POST /api/products/<id>/merge merges source into target."""
    target = api_create_product(name="MergeTarget")
    source = api_create_product(name="MergeSource")
    target_id = target["id"]
    source_id = source["id"]

    status, body = _post(
        f"{live_url}/api/products/{target_id}/merge",
        {"source_id": source_id, "choices": {}},
    )
    assert status == 200
    assert body.get("ok") is True

    # Source product should be deleted after merge
    result = _get(f"{live_url}/api/products")
    ids = [p["id"] for p in result["products"]]
    assert target_id in ids, "Target should still exist after merge"
    assert source_id not in ids, "Source should be deleted after merge"


def test_merge_invalid_source(live_url, api_create_product):
    """POST /api/products/<id>/merge with invalid source_id returns 400."""
    product = api_create_product(name="MergeInvalid")
    pid = product["id"]

    status, body = _post(
        f"{live_url}/api/products/{pid}/merge",
        {"source_id": "not_an_int"},
    )
    assert status == 400


def test_merge_nonexistent_target(live_url):
    """POST /api/products/999999/merge returns 404."""
    status, body = _post(
        f"{live_url}/api/products/999999/merge",
        {"source_id": 1},
    )
    assert status in (400, 404)
