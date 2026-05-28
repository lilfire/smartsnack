"""End-to-end direct-API error/edge tests for ``blueprints/backup.py``.

Closes the LSO-1352 Phase 2D-1 audit gaps for the backup blueprint:

- ``POST /api/restore``  — 400 on ``ValueError`` and 500 on ``OSError`` /
  ``RuntimeError`` (audit items #1 and #2; catch sites at
  ``blueprints/backup.py:46-50``).
- ``POST /api/import``   — 400 on ``ValueError`` and 500 on ``OSError`` /
  ``RuntimeError`` (audit items #3 and #4; catch sites at
  ``blueprints/backup.py:71-75``).
- ``POST /api/restore`` + ``POST /api/import`` — happy-path body shape
  (audit item #28). Assert the ``message`` contains the count(s) per the
  service-layer contracts in ``services/backup_core.py`` and
  ``services/import_service.py``.
- ``GET /api/backup?images=false`` (audit item #29) — assert the response
  body does NOT carry image data URIs while the default (or explicit
  ``images=true``) does.

Conventions (Rules 8, 16, 17, 18):
- Live Flask server via the ``live_url`` fixture; no browser.
- External services are mocked at the module boundary using
  ``unittest.mock.create_autospec`` against the real service callables so
  signature drift breaks the test.
- Every assertion is *specific* about status, error message, and (where
  applicable) post-state. "Didn't crash" is never a passing signal.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import create_autospec, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(url, payload, timeout=5):
    """POST JSON to ``url`` and return ``(status, parsed_body)``.

    Args:
        url: Full URL to post to.
        payload: Object that will be JSON-encoded as the request body.
        timeout: Socket timeout in seconds.
    """
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get_json(url, timeout=10):
    """GET ``url`` and return ``(status, parsed_body)``."""
    req = urllib.request.Request(url, headers={"X-Requested-With": "SmartSnack"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ===========================================================================
# POST /api/restore  —  error paths
# ===========================================================================


class TestRestoreErrorPaths:
    """Direct-API error coverage for the ``POST /api/restore`` route.

    The blueprint at ``blueprints/backup.py:43-50`` maps ``ValueError`` to
    400 (the error message is surfaced as-is) and ``OSError`` /
    ``RuntimeError`` to 500 with the *generic* message ``"Restore failed"``.
    These tests exercise both branches at the route boundary, asserting on
    the specific status code and body shape.
    """

    def test_value_error_returns_400_with_specific_message(self, live_url):
        """A backup payload missing the required ``products`` key triggers
        ``_validate_backup`` → ``ValueError("Invalid backup file")``. The route
        must surface that message verbatim in a 400 response."""
        # No mock: drive the real validator with a real bad-schema payload so
        # the test also guards against the service contract being silently
        # weakened. This is the "bad schema, missing required key" case from
        # the audit.
        status, body = _post(
            f"{live_url}/api/restore",
            {"version": "1.0", "categories": []},
        )

        assert status == 400, (
            f"Expected 400 for missing 'products' key, got {status}: {body}"
        )
        assert body == {"error": "Invalid backup file"}, (
            f"Route must surface the exact ValueError message; got {body!r}"
        )

    def test_value_error_non_list_products_returns_400(self, live_url):
        """When ``products`` is present but not a list,
        ``_validate_backup`` raises ``ValueError('products must be an array')``.
        Asserts the specific error string so a wrong-message regression
        (e.g. swapping to a generic "invalid payload") breaks the test."""
        status, body = _post(
            f"{live_url}/api/restore",
            {"products": "not-a-list"},
        )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "products must be an array"}, (
            f"Expected exact validator message; got {body!r}"
        )

    def test_value_error_propagates_from_service(self, live_url):
        """Monkeypatch the service to raise a custom ``ValueError`` and assert
        the route forwards the message string verbatim. Guards against the
        route swallowing or rewriting service-level validation errors."""
        from services import backup_core

        spec = create_autospec(backup_core.restore_backup, spec_set=True)
        spec.side_effect = ValueError("score_weights must be an array")
        with patch("services.backup_core.restore_backup", spec):
            status, body = _post(
                f"{live_url}/api/restore",
                {"products": []},
            )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "score_weights must be an array"}, (
            f"Route must surface str(exc); got {body!r}"
        )
        assert spec.call_count == 1, "Service must be invoked exactly once"

    def test_runtime_error_returns_500_with_generic_message(self, live_url):
        """``RuntimeError`` raised from the service must hit the 500 branch
        at ``backup.py:48``. The route logs the exception and returns the
        *generic* ``{"error": "Restore failed"}`` body (it deliberately does
        NOT leak the original message to clients)."""
        from services import backup_core

        spec = create_autospec(backup_core.restore_backup, spec_set=True)
        spec.side_effect = RuntimeError("disk on fire, do not surface me")
        with patch("services.backup_core.restore_backup", spec):
            status, body = _post(
                f"{live_url}/api/restore",
                {"products": []},
            )

        assert status == 500, f"Expected 500 on RuntimeError, got {status}: {body}"
        assert body == {"error": "Restore failed"}, (
            f"Route must return the *generic* error to avoid leaking internals; "
            f"got {body!r}"
        )
        assert spec.call_count == 1

    def test_os_error_returns_500_with_generic_message(self, live_url):
        """``OSError`` (e.g. disk full / file unreadable) must also map to
        the generic 500. This guards the second arm of the union catch at
        ``backup.py:48``."""
        from services import backup_core

        spec = create_autospec(backup_core.restore_backup, spec_set=True)
        spec.side_effect = OSError("No space left on device")
        with patch("services.backup_core.restore_backup", spec):
            status, body = _post(
                f"{live_url}/api/restore",
                {"products": []},
            )

        assert status == 500, f"Expected 500 on OSError, got {status}: {body}"
        assert body == {"error": "Restore failed"}, (
            f"OSError must map to the generic Restore-failed body; got {body!r}"
        )


# ===========================================================================
# POST /api/import  —  error paths
# ===========================================================================


class TestImportErrorPaths:
    """Direct-API error coverage for the ``POST /api/import`` route.

    Mirror of ``TestRestoreErrorPaths`` for the import endpoint. The route
    at ``blueprints/backup.py:60-75`` maps ``ValueError`` → 400 (message
    surfaced) and ``OSError`` / ``RuntimeError`` → 500 with the generic
    ``"Import failed"`` body.
    """

    def test_value_error_missing_products_returns_400(self, live_url):
        """``import_products`` raises ``ValueError('Invalid import file')``
        when ``products`` is missing — assert the route maps to 400 with the
        verbatim message."""
        status, body = _post(
            f"{live_url}/api/import",
            {"categories": [], "match_criteria": "both"},
        )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid import file"}, (
            f"Expected exact service-layer error; got {body!r}"
        )

    def test_value_error_propagates_from_service(self, live_url):
        """Monkeypatch the import service to raise a custom ``ValueError``
        (e.g. a per-product text-length violation) and assert the route
        forwards the message string."""
        from services import import_service

        spec = create_autospec(import_service.import_products, spec_set=True)
        spec.side_effect = ValueError("name exceeds max length of 200")
        with patch("services.import_service.import_products", spec):
            status, body = _post(
                f"{live_url}/api/import",
                {"products": [{"name": "X"}]},
            )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "name exceeds max length of 200"}, (
            f"Route must surface str(exc); got {body!r}"
        )

    def test_runtime_error_returns_500_with_generic_message(self, live_url):
        """``RuntimeError`` from the import service must hit the 500 branch
        at ``backup.py:73``. The route returns ``{"error": "Import failed"}``
        — the original message must NOT leak."""
        from services import import_service

        spec = create_autospec(import_service.import_products, spec_set=True)
        spec.side_effect = RuntimeError("upstream cache imploded")
        with patch("services.import_service.import_products", spec):
            status, body = _post(
                f"{live_url}/api/import",
                {"products": []},
            )

        assert status == 500, f"Expected 500 on RuntimeError, got {status}: {body}"
        assert body == {"error": "Import failed"}, (
            f"Route must return generic 'Import failed'; got {body!r}"
        )

    def test_os_error_returns_500_with_generic_message(self, live_url):
        """``OSError`` from the import service must also map to the generic
        500 body. Guards the second arm of the union catch."""
        from services import import_service

        spec = create_autospec(import_service.import_products, spec_set=True)
        spec.side_effect = OSError("Permission denied: translations/no.json")
        with patch("services.import_service.import_products", spec):
            status, body = _post(
                f"{live_url}/api/import",
                {"products": []},
            )

        assert status == 500
        assert body == {"error": "Import failed"}, (
            f"OSError must map to generic Import-failed body; got {body!r}"
        )


# ===========================================================================
# Audit item #28  —  happy-path message content
# ===========================================================================


class TestRestoreAndImportMessageContent:
    """Happy-path response-body coverage for restore + import.

    Audit item #28 calls for asserting that the returned ``message`` carries
    the count(s) per the service contract:

    - ``backup_core.restore_backup``  returns
      ``f"Restored {len(data['products'])} products successfully"``.
    - ``import_service.import_products`` returns
      ``f"Imported {added} products"`` with optional ``", N merged"``,
      ``", N overwritten"``, ``", N skipped as duplicates"`` suffixes.

    These tests pin both contracts at the HTTP layer.
    """

    def test_restore_message_contains_product_count(self, live_url):
        """A restore that writes N products must echo N back in the message.
        Picks N=3 so the assertion catches off-by-one regressions (e.g. a
        change that prints len(data) instead of len(products))."""
        snapshot = {
            "version": "1.0",
            "exported_at": "2026-05-21T00:00:00Z",
            "score_weights": [],
            "categories": [],
            "protein_quality": [],
            "flag_definitions": [],
            "products": [
                {"type": "Snacks", "name": "RestoreMsg-A", "kcal": 100},
                {"type": "Snacks", "name": "RestoreMsg-B", "kcal": 200},
                {"type": "Snacks", "name": "RestoreMsg-C", "kcal": 300},
            ],
        }
        status, body = _post(f"{live_url}/api/restore", snapshot)

        assert status == 200, f"Expected 200 for valid restore, got {status}: {body}"
        assert body.get("ok") is True, f"Expected ok=True, got {body!r}"
        # Service contract: "Restored N products successfully" — assert the
        # exact format so a future refactor that drops the count breaks here.
        assert body.get("message") == "Restored 3 products successfully", (
            f"Expected exact service contract message, got {body.get('message')!r}"
        )

    def test_restore_empty_products_message_is_zero(self, live_url):
        """An empty product list still produces a count-bearing message."""
        status, body = _post(
            f"{live_url}/api/restore",
            {"products": []},
        )

        assert status == 200
        assert body.get("message") == "Restored 0 products successfully", (
            f"Empty restore must report 0 products in the message; got "
            f"{body.get('message')!r}"
        )

    def test_import_message_contains_added_count(self, live_url, unique_name):
        """An import of brand-new products echoes the added-count back."""
        names = [unique_name("ImpAdd-A"), unique_name("ImpAdd-B")]
        body_payload = {
            "products": [
                {"type": "Snacks", "name": names[0], "kcal": 100},
                {"type": "Snacks", "name": names[1], "kcal": 150},
            ],
            "match_criteria": "name",
            "on_duplicate": "skip",
        }
        status, body = _post(f"{live_url}/api/import", body_payload)

        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("ok") is True
        # Both products are new → "Imported 2 products" with no suffix.
        assert body.get("message") == "Imported 2 products", (
            f"Expected exact 'Imported 2 products', got {body.get('message')!r}"
        )

    def test_import_message_reports_skipped_count(self, live_url, api_create_product, unique_name):
        """When a duplicate is skipped under ``on_duplicate='skip'``, the
        message must include ``", N skipped as duplicates"``. This is the
        suffix branch in ``import_service.import_products`` at
        ``services/import_service.py:358``."""
        name_existing = unique_name("ImpSkip-Existing")
        api_create_product(name=name_existing, kcal=100)

        body_payload = {
            "products": [
                {"type": "Snacks", "name": name_existing, "kcal": 999},
            ],
            "match_criteria": "name",
            "on_duplicate": "skip",
        }
        status, body = _post(f"{live_url}/api/import", body_payload)

        assert status == 200
        assert body.get("ok") is True
        msg = body.get("message", "")
        # Exact match: nothing was added, one skipped.
        assert msg == "Imported 0 products, 1 skipped as duplicates", (
            f"Expected the full skipped-suffix message, got {msg!r}"
        )

    def test_import_message_reports_overwritten_count(self, live_url, api_create_product, unique_name):
        """When ``on_duplicate='overwrite'``, the message gains
        ``", N overwritten"`` (see ``import_service.py:356``)."""
        name_existing = unique_name("ImpOver-Existing")
        api_create_product(name=name_existing, kcal=100)

        body_payload = {
            "products": [
                {"type": "Snacks", "name": name_existing, "kcal": 250},
            ],
            "match_criteria": "name",
            "on_duplicate": "overwrite",
        }
        status, body = _post(f"{live_url}/api/import", body_payload)

        assert status == 200
        msg = body.get("message", "")
        assert msg == "Imported 0 products, 1 overwritten", (
            f"Expected overwrite-suffix message, got {msg!r}"
        )

    def test_import_message_reports_merged_count(self, live_url, api_create_product, unique_name):
        """When ``on_duplicate='merge'``, the message gains ``", N merged"``."""
        name_existing = unique_name("ImpMerge-Existing")
        api_create_product(name=name_existing, kcal=100)

        body_payload = {
            "products": [
                {"type": "Snacks", "name": name_existing, "brand": "NewBrand"},
            ],
            "match_criteria": "name",
            "on_duplicate": "merge",
            "merge_priority": "use_imported",
        }
        status, body = _post(f"{live_url}/api/import", body_payload)

        assert status == 200
        msg = body.get("message", "")
        assert msg == "Imported 0 products, 1 merged", (
            f"Expected merge-suffix message, got {msg!r}"
        )


# ===========================================================================
# Audit item #29  —  GET /api/backup?images=false
# ===========================================================================


class TestBackupImagesQueryParam:
    """``GET /api/backup`` must omit image data when ``images=false``.

    The blueprint at ``blueprints/backup.py:24`` parses the query string and
    forwards ``include_images`` to ``backup_core.create_backup``; the service
    builds two different SELECT statements depending on the flag (see
    ``services/backup_core.py:120-149``). Without these tests the false
    branch is silently covered by integration but never asserted at the
    HTTP layer.
    """

    # 1×1 transparent PNG, base64-encoded as a data URI.
    _IMAGE_DATA_URI = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgA"
        "AIAAAUAAen63NgAAAAASUVORK5CYII="
    )

    def _seed_product_with_image(self, live_url, api_create_product, unique_name):
        """Create a product and attach a known data URI as its image."""
        name = unique_name("BackupImageEdge")
        created = api_create_product(name=name)
        pid = created["id"]
        req = urllib.request.Request(
            f"{live_url}/api/products/{pid}/image",
            data=json.dumps({"image": self._IMAGE_DATA_URI}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "SmartSnack",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ack = json.loads(resp.read())
        assert ack.get("ok") is True, f"Image PUT failed: {ack}"
        return name, pid

    def test_images_false_strips_image_field(
        self, live_url, api_create_product, unique_name
    ):
        """``GET /api/backup?images=false`` must not carry the ``image`` key
        (the SELECT in the false branch omits the column entirely)."""
        name, _pid = self._seed_product_with_image(live_url, api_create_product, unique_name)

        status, body = _get_json(f"{live_url}/api/backup?images=false")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert "products" in body, f"Backup must carry 'products'; got keys {list(body)}"

        match = next((p for p in body["products"] if p.get("name") == name), None)
        assert match is not None, (
            f"Seeded product {name!r} missing from backup; names: "
            f"{[p.get('name') for p in body['products']]}"
        )
        # The image column is not selected at all in the images=false branch.
        assert "image" not in match, (
            f"images=false must omit the 'image' key entirely; got "
            f"{list(match.keys())!r} (image field leaked through)"
        )
        # Defence in depth: no data URI lurking in any other field, in case
        # someone copy-pastes the image into ingredients or similar by accident.
        raw = json.dumps(match)
        assert "data:image/" not in raw, (
            f"images=false response must not contain any 'data:image/' URI; "
            f"found in serialised product: {raw[:200]}..."
        )

    def test_images_true_includes_image_field(
        self, live_url, api_create_product, unique_name
    ):
        """The default (``images=true``) branch MUST still serialise the
        data URI byte-for-byte. This is the contrast case for
        ``test_images_false_strips_image_field`` — the two together prove the
        query param actually toggles behaviour."""
        name, _pid = self._seed_product_with_image(live_url, api_create_product, unique_name)

        status, body = _get_json(f"{live_url}/api/backup?images=true")
        assert status == 200, f"Expected 200, got {status}: {body}"
        match = next((p for p in body["products"] if p.get("name") == name), None)
        assert match is not None, f"Product {name!r} missing from images=true backup"
        assert match.get("image") == self._IMAGE_DATA_URI, (
            f"images=true must return the exact data URI; got len="
            f"{len(match.get('image') or '')}, expected len="
            f"{len(self._IMAGE_DATA_URI)}"
        )

    def test_default_includes_image_field(
        self, live_url, api_create_product, unique_name
    ):
        """No ``images`` query param → default to ``true``. This pins the
        default-to-include contract at the route level."""
        name, _pid = self._seed_product_with_image(live_url, api_create_product, unique_name)

        status, body = _get_json(f"{live_url}/api/backup")
        assert status == 200
        match = next((p for p in body["products"] if p.get("name") == name), None)
        assert match is not None, f"Product {name!r} missing from default backup"
        assert match.get("image") == self._IMAGE_DATA_URI, (
            f"Default (no images=) must include the image data URI; got "
            f"len={len(match.get('image') or '')}"
        )
