"""E2E tests for protein quality update (PUT) endpoint."""

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


def test_update_protein_quality(live_url):
    """PUT /api/protein-quality/<id> updates the entry."""
    # Create an entry
    status, body = _post(f"{live_url}/api/protein-quality", {
        "label": "E2E PQ Update",
        "keywords": ["e2epqupdate"],
        "pdcaas": 0.50,
        "diaas": 0.45,
    })
    assert status == 201
    entry_id = body["id"]

    # Update it
    status, body = _put(f"{live_url}/api/protein-quality/{entry_id}", {
        "label": "E2E PQ Updated",
        "keywords": ["e2epqupdated"],
        "pdcaas": 0.80,
        "diaas": 0.75,
    })
    assert status == 200
    assert body.get("ok") is True

    # Verify
    entries = _get(f"{live_url}/api/protein-quality")
    entry = next((e for e in entries if e["id"] == entry_id), None)
    assert entry is not None
    assert entry["label"] == "E2E PQ Updated"

    # Cleanup
    _delete(f"{live_url}/api/protein-quality/{entry_id}")


def test_update_protein_quality_not_found(live_url):
    """PUT /api/protein-quality/999999 returns 404."""
    status, body = _put(f"{live_url}/api/protein-quality/999999", {
        "label": "Ghost",
        "keywords": ["ghost"],
        "pdcaas": 0.5,
        "diaas": 0.5,
    })
    assert status == 404
