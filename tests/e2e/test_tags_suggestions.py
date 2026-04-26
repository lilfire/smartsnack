"""E2E tests for tag suggestions endpoint."""

import json
import urllib.request


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _put(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def test_tag_suggestions_empty_query(live_url):
    """GET /api/products/tags/suggestions without q returns empty list."""
    data = _get(f"{live_url}/api/products/tags/suggestions")
    assert isinstance(data, list)
    assert len(data) == 0


def test_tag_suggestions_with_query(live_url, api_create_product):
    """GET /api/products/tags/suggestions?q=<prefix> returns matching tags."""
    product = api_create_product(name="TagSugProduct")
    pid = product["id"]
    # Create tags then assign them to the product via tagIds
    tag1 = _post(f"{live_url}/api/tags", {"label": "e2etagtest"})
    tag2 = _post(f"{live_url}/api/tags", {"label": "anothertag"})
    _put(f"{live_url}/api/products/{pid}", {"tagIds": [tag1["id"], tag2["id"]]})

    data = _get(f"{live_url}/api/products/tags/suggestions?q=e2etag")
    assert isinstance(data, list)
    assert "e2etagtest" in data


def test_tag_suggestions_no_match(live_url):
    """GET /api/products/tags/suggestions?q=zzzznonexist returns empty list."""
    data = _get(f"{live_url}/api/products/tags/suggestions?q=zzzznonexist")
    assert isinstance(data, list)
    assert len(data) == 0
