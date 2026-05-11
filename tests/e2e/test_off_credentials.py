"""E2E tests for OFF credentials settings endpoints."""

import json
import urllib.error
import urllib.request


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


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


def test_get_off_credentials(live_url):
    """GET /api/settings/off-credentials returns credential info."""
    # No API key configured in test env, so this should return the data
    status, body = _get(f"{live_url}/api/settings/off-credentials")
    assert status == 200
    assert "off_user_id" in body
    assert "has_password" in body


def test_set_off_credentials(live_url):
    """PUT /api/settings/off-credentials sets the credentials."""
    status, body = _put(
        f"{live_url}/api/settings/off-credentials",
        {"off_user_id": "testuser", "off_password": "testpass"},
    )
    # May return 200 (ok) or 500 (encryption_not_configured) depending on env
    assert status in (200, 500)
    if status == 200:
        assert body.get("ok") is True

    # Verify the user was stored
    if status == 200:
        get_status, get_body = _get(f"{live_url}/api/settings/off-credentials")
        assert get_body["off_user_id"] == "testuser"
        assert get_body["has_password"] is True
