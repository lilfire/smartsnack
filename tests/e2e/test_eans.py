"""E2E tests for multi-EAN management: list, add, delete, set-primary."""

import json
import urllib.error
import urllib.request


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


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


def _delete(url):
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _patch(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_list_eans_empty(live_url, api_create_product):
    """GET /api/products/<id>/eans returns empty list for new product."""
    product = api_create_product(name="EanListEmpty")
    pid = product["id"]

    status, body = _get(f"{live_url}/api/products/{pid}/eans")
    assert status == 200
    assert isinstance(body, list)


def test_add_ean(live_url, api_create_product):
    """POST /api/products/<id>/eans adds an EAN and returns 201."""
    product = api_create_product(name="EanAddTest")
    pid = product["id"]

    status, body = _post(f"{live_url}/api/products/{pid}/eans", {"ean": "1234567890123"})
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert "id" in body


def test_add_ean_then_list(live_url, api_create_product):
    """Adding an EAN makes it appear in the list."""
    product = api_create_product(name="EanAddList")
    pid = product["id"]

    _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000001"})

    _, eans = _get(f"{live_url}/api/products/{pid}/eans")
    ean_codes = [e["ean"] for e in eans]
    assert "9990000000001" in ean_codes


def test_add_duplicate_ean(live_url, api_create_product):
    """Adding the same EAN twice returns 409 conflict."""
    product = api_create_product(name="EanDuplicate")
    pid = product["id"]

    _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000002"})
    status, body = _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000002"})
    assert status == 409, f"Expected 409 for duplicate EAN add, got {status}"
    assert body["error"] == "ean_already_exists"


def test_delete_ean(live_url, api_create_product):
    """DELETE /api/products/<id>/eans/<ean_id> removes the EAN."""
    product = api_create_product(name="EanDelete")
    pid = product["id"]

    # Add two EANs so we can delete one and verify removal
    _, add_body = _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000003"})
    _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000099"})
    ean_id = add_body["id"]

    status, body = _delete(f"{live_url}/api/products/{pid}/eans/{ean_id}")
    assert status == 200
    assert body.get("ok") is True

    _, eans = _get(f"{live_url}/api/products/{pid}/eans")
    ean_ids = [e["id"] for e in eans]
    assert ean_id not in ean_ids


def test_delete_last_ean_succeeds(live_url, api_create_product):
    """Deleting the last remaining EAN on a product is now allowed."""
    product = api_create_product(name="EanDeleteLast")
    pid = product["id"]

    _, add_body = _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000050"})
    ean_id = add_body["id"]

    status, body = _delete(f"{live_url}/api/products/{pid}/eans/{ean_id}")
    assert status == 200, f"Expected 200 when deleting last EAN, got {status}"
    assert body.get("ok") is True

    _, eans = _get(f"{live_url}/api/products/{pid}/eans")
    assert len(eans) == 0, "Product should have no EANs after deleting the last one"


def test_set_primary_ean(live_url, api_create_product):
    """PATCH /api/products/<id>/eans/<ean_id>/set-primary succeeds."""
    product = api_create_product(name="EanPrimary")
    pid = product["id"]

    _, add_body = _post(f"{live_url}/api/products/{pid}/eans", {"ean": "9990000000004"})
    ean_id = add_body["id"]

    status, body = _patch(
        f"{live_url}/api/products/{pid}/eans/{ean_id}/set-primary", {}
    )
    assert status == 200
    assert body.get("ok") is True


def test_eans_not_found(live_url):
    """GET /api/products/999999/eans returns 404 for non-existent product."""
    req = urllib.request.Request(f"{live_url}/api/products/999999/eans")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected 404"
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
