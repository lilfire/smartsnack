"""E2E 404 tests for ``PUT`` / ``DELETE /api/products/<pid>/image``.

Phase 2D-2 of LSO-1352 (audit items 18–19). Phase 2C covered upload-payload
edges; the missing-product 404 branch was not pinned.

- Item 18 — ``PUT /api/products/<pid>/image`` — non-existent pid must return
  ``404 {"error": "Product not found"}`` (``image_service.set_image`` returns
  ``False`` when no row was updated).
- Item 19 — ``DELETE /api/products/<pid>/image`` — non-existent pid must return
  the same 404.

References: ``blueprints/images.py:27`` and ``blueprints/images.py:35``.
"""

import json
import urllib.error
import urllib.request


def _request(method, url, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-Requested-With": "SmartSnack"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


# A tiny but well-formed PNG data URI so the upload validator (Phase 2C) does
# not 400 before we reach the missing-product check. 1x1 transparent.
_TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class TestPutImageNotFound:
    """``PUT /api/products/<pid>/image`` 404s when product does not exist."""

    def test_put_image_unknown_pid_returns_404(self, live_url):
        """A valid data-URI payload + non-existent pid: ``image_service.set_image``
        runs ``UPDATE ... WHERE id=?`` against zero rows, returns ``False``,
        and the route surfaces ``404 {"error": "Product not found"}``."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/products/9999993/image",
            payload={"image": _TINY_PNG},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}

    def test_put_image_missing_image_field_unknown_pid_returns_400(self, live_url):
        """Edge: payload without an ``image`` field defaults to ``""`` which the
        validator rejects with ``Invalid image format`` (400) *before* the
        missing-product 404 path is reached. Pins the precedence order so a
        refactor that moves the lookup earlier is visible."""
        status, body = _request(
            "PUT",
            f"{live_url}/api/products/9999992/image",
            payload={},
        )
        assert status == 400, f"Expected 400 (validator first), got {status}: {body}"
        assert body == {"error": "Invalid image format"}


class TestDeleteImageNotFound:
    """``DELETE /api/products/<pid>/image`` 404s when product does not exist."""

    def test_delete_image_unknown_pid_returns_404(self, live_url):
        """``image_service.delete_image`` returns ``False`` -> 404."""
        status, body = _request(
            "DELETE", f"{live_url}/api/products/9999991/image"
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body == {"error": "Product not found"}
