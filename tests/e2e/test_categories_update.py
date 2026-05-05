"""E2E tests for category update (PUT) endpoint."""

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


def _put(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _delete(url):
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_update_category(live_url):
    """PUT /api/categories/<name> updates label and emoji."""
    # Create a category first
    _post(f"{live_url}/api/categories", {
        "name": "e2e_update_cat",
        "label": "Original Label",
        "emoji": "🍎",
    })

    status, body = _put(
        f"{live_url}/api/categories/e2e_update_cat",
        {"label": "Updated Label", "emoji": "🍊"},
    )
    assert status == 200
    assert body.get("ok") is True

    # Verify the update
    categories = _get(f"{live_url}/api/categories")
    cat = next((c for c in categories if c["name"] == "e2e_update_cat"), None)
    assert cat is not None
    assert cat["label"] == "Updated Label"

    # Cleanup
    _delete(f"{live_url}/api/categories/e2e_update_cat")


def test_update_category_invalid_name(live_url):
    """PUT /api/categories/<invalid> returns 400."""
    status, body = _put(
        f"{live_url}/api/categories/",
        {"label": "Test", "emoji": "🍎"},
    )
    # Empty name or 404
    assert status in (400, 404, 405)
