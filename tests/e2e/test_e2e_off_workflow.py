"""End-to-end tests for ``blueprints/off.py`` and ``/api/off/search``.

Covers the LSO-1352 Phase 2A gaps for the OFF (Open Food Facts) blueprint:

- ``POST /api/off/search`` — upstream failure contract: both search backends
  in ``proxy_service.off_search`` are wrapped in catch-all try blocks that
  return empty results rather than 502. This file asserts that contract
  AND that the blueprint surfaces explicit RuntimeError as 502 when the
  service layer does raise.
- ``POST /api/off/add-product`` — full workflow coverage:
    (a) happy path: route calls ``off_service.add_product_to_off`` and
        ``product_crud.mark_product_synced_with_off`` and returns the
        documented response shape.
    (b) malformed payload (no JSON body) returns 400.
    (c) upstream failure (``RuntimeError`` from the service) returns 502
        with the error message.
    (d) "duplicate / already-imported" cases:
        - OFF API rejects with ``status != 1`` → service raises
          ``RuntimeError`` → route returns 502 with the upstream message.
        - Local product is already flagged ``is_synced_with_off`` → the
          re-post is idempotent and the response still reports
          ``synced_flag_set=true``.
    (e) image-upload failure on the existing product is recorded as a
        warning (does NOT fail the request).

External services are never reached: ``off_service`` callables are mocked
at the module boundary with ``unittest.mock.create_autospec`` so signature
drift breaks the test (Rule 8).
"""

import json
import urllib.error
import urllib.request
from unittest.mock import create_autospec, patch


def _post(url, payload, timeout=5, raw=False, content_type="application/json"):
    if raw:
        data = payload if isinstance(payload, (bytes, bytearray)) else payload.encode()
    else:
        data = json.dumps(payload).encode()
    headers = {"X-Requested-With": "SmartSnack"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"_raw": body.decode("utf-8", errors="replace")}


# ===========================================================================
# POST /api/off/search — upstream failure contract
# ===========================================================================


class TestOffSearchUpstreamErrors:
    """The blueprint's ``ValueError → 400 / RuntimeError → 502 / Exception →
    500`` mapping is asserted here; the underlying ``proxy_service.off_search``
    swallows backend HTTP failures, so we also assert that empty-result
    contract directly."""

    def test_short_query_returns_400(self, live_url):
        """ValueError from the service (query too short) surfaces as 400."""
        with patch(
            "services.proxy_service.off_search",
            side_effect=ValueError("Query too short"),
        ):
            status, body = _post(f"{live_url}/api/off/search", {"q": "a"})

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body.get("error") == "Query too short"

    def test_runtime_error_surfaces_as_502(self, live_url):
        """RuntimeError from the service surfaces as 502 with the upstream
        message (the blueprint's ``except RuntimeError`` branch).

        This is the contract the frontend relies on to distinguish a real
        upstream outage from a local validation error."""
        with patch(
            "services.proxy_service.off_search",
            side_effect=RuntimeError("OFF upstream unreachable"),
        ):
            status, body = _post(
                f"{live_url}/api/off/search", {"q": "kvarg"}
            )

        assert status == 502, f"Expected 502 on upstream RuntimeError, got {status}: {body}"
        assert body.get("error") == "OFF upstream unreachable"

    def test_unexpected_exception_returns_500(self, live_url):
        """A generic ``Exception`` from the service is logged and surfaced as
        500 with a fixed ``Search failed`` message — internal details are
        NOT leaked to the response body."""
        with patch(
            "services.proxy_service.off_search",
            side_effect=Exception("boom: stack trace leaks here"),
        ):
            status, body = _post(
                f"{live_url}/api/off/search", {"q": "kvarg"}
            )

        assert status == 500
        assert body.get("error") == "Search failed", (
            "Internal exception details must not leak to client"
        )

    def test_upstream_backend_failures_yield_empty_results_not_502(self, live_url):
        """When BOTH ``_off_search_a_licious`` and ``_off_search_classic``
        raise ``RuntimeError``, ``off_search`` catches each in its inner try
        and returns ``{products: [], count: 0}`` with status 200.

        This documents the actual implementation contract: a soft outage on
        the OFF API surfaces as "no results", not 502. A future refactor
        that flips this behaviour MUST update both this test and the
        frontend that currently treats empty results as "no matches".
        """
        with patch(
            "services.proxy_service._off_search_a_licious",
            side_effect=RuntimeError("a-licious down"),
        ), patch(
            "services.proxy_service._off_search_classic",
            side_effect=RuntimeError("classic down"),
        ):
            status, body = _post(
                f"{live_url}/api/off/search",
                {"q": "kvarg naturell"},
            )

        assert status == 200, (
            f"Backend HTTP failures must yield 200 + empty results per the "
            f"existing contract, got {status}: {body}"
        )
        assert body == {"products": [], "count": 0}


# ===========================================================================
# POST /api/off/add-product — happy path
# ===========================================================================


class TestAddProductHappyPath:
    """The route stitches together OFF post + optional image upload + local
    flag update. This class asserts the happy-path response shape and that
    each downstream callable was invoked with the right arguments."""

    def test_minimal_payload_returns_ok_with_status_verbose(self, live_url):
        """A request with just ``code`` + ``product_name`` and no
        ``product_id`` returns ``ok=True`` with the upstream status_verbose
        and no image upload or sync flag set."""
        from services import off_service

        spec = create_autospec(off_service.add_product_to_off, spec_set=True)
        spec.return_value = {"status": 1, "status_verbose": "fields saved"}
        with patch("services.off_service.add_product_to_off", spec):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {"code": "7310865004703", "product_name": "Kvarg Naturell"},
            )

        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["ok"] is True
        assert body["status_verbose"] == "fields saved"
        assert body["image_uploaded"] is False
        assert body["image_warning"] is None
        # No product_id → mark_product_synced_with_off NOT called → flag False.
        assert body["synced_flag_set"] is False
        assert spec.call_count == 1
        # The service receives the request body unchanged.
        sent = spec.call_args[0][0]
        assert sent["code"] == "7310865004703"
        assert sent["product_name"] == "Kvarg Naturell"

    def test_product_id_triggers_image_upload_and_sync_flag(self, live_url):
        """With ``product_id`` present and a stored image, the route uploads
        the image to OFF and sets the local ``is_synced_with_off`` flag."""
        from services import image_service, off_service, product_crud

        add_spec = create_autospec(off_service.add_product_to_off, spec_set=True)
        add_spec.return_value = {"status": 1, "status_verbose": "fields saved"}
        upload_spec = create_autospec(off_service.upload_image_to_off, spec_set=True)
        upload_spec.return_value = {"status": "status ok"}
        image_spec = create_autospec(image_service.get_image, spec_set=True)
        image_spec.return_value = (
            "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/"
        )
        sync_spec = create_autospec(
            product_crud.mark_product_synced_with_off, spec_set=True
        )

        with patch(
            "services.off_service.add_product_to_off", add_spec
        ), patch(
            "services.off_service.upload_image_to_off", upload_spec
        ), patch(
            "services.image_service.get_image", image_spec
        ), patch(
            "services.product_crud.mark_product_synced_with_off", sync_spec
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {
                    "code": "7310865004703",
                    "product_name": "Kvarg Naturell",
                    "product_id": 42,
                },
            )

        assert status == 200
        assert body["ok"] is True
        assert body["image_uploaded"] is True
        assert body["image_warning"] is None
        assert body["synced_flag_set"] is True

        # Each callable invoked once with the expected args.
        assert add_spec.call_count == 1
        assert image_spec.call_count == 1
        assert image_spec.call_args[0][0] == 42
        assert upload_spec.call_count == 1
        # upload_image_to_off(code, image_data_uri[, imagefield])
        upload_args = upload_spec.call_args
        assert upload_args[0][0] == "7310865004703"
        assert upload_args[0][1].startswith("data:image/jpeg")
        assert sync_spec.call_count == 1
        assert sync_spec.call_args[0][0] == 42
        assert sync_spec.call_args[0][1] == "7310865004703"

    def test_image_upload_failure_is_recorded_as_warning_not_502(self, live_url):
        """If ``upload_image_to_off`` raises ValueError/RuntimeError the
        route still returns 200 with ``image_warning`` populated — image
        upload is best-effort, not a hard requirement."""
        from services import image_service, off_service, product_crud

        with patch(
            "services.off_service.add_product_to_off",
            return_value={"status": 1, "status_verbose": "fields saved"},
        ), patch(
            "services.image_service.get_image",
            return_value="data:image/png;base64,iVBORw0KGgo=",
        ), patch(
            "services.off_service.upload_image_to_off",
            side_effect=RuntimeError("off_err_network"),
        ), patch(
            "services.product_crud.mark_product_synced_with_off"
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {
                    "code": "7310865004703",
                    "product_name": "Kvarg Naturell",
                    "product_id": 42,
                },
            )

        assert status == 200, (
            f"Image upload failure must NOT fail the parent request: {status} {body}"
        )
        assert body["ok"] is True
        assert body["image_uploaded"] is False
        assert body["image_warning"] == "off_err_network"
        # Sync flag should still be set — image failure doesn't block flagging.
        assert body["synced_flag_set"] is True


# ===========================================================================
# POST /api/off/add-product — error paths
# ===========================================================================


class TestAddProductErrors:
    """Error contracts: missing JSON → 400, missing creds → 400,
    upstream failure → 502, duplicate/upstream rejection → 502."""

    def test_missing_json_body_returns_400(self, live_url):
        """Sending no body with Content-Type application/json triggers
        ``_require_json`` to raise ValueError → 400.

        The underlying ``off_service.add_product_to_off`` MUST NOT be
        invoked when the request body is malformed."""
        with patch("services.off_service.add_product_to_off") as mock_add:
            status, body = _post(
                f"{live_url}/api/off/add-product", b"", raw=True
            )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "json" in body["error"].lower()
        assert mock_add.call_count == 0

    def test_non_json_body_returns_400(self, live_url):
        """A body that fails to parse as JSON also triggers 400."""
        with patch("services.off_service.add_product_to_off") as mock_add:
            status, body = _post(
                f"{live_url}/api/off/add-product",
                "not valid json",
                raw=True,
            )

        assert status == 400, f"Expected 400, got {status}: {body}"
        assert mock_add.call_count == 0

    def test_missing_credentials_returns_400(self, live_url):
        """Service raises ``ValueError('off_err_no_credentials')`` when no
        OFF user/password is configured. Route surfaces as 400."""
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=ValueError("off_err_no_credentials"),
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {"code": "7310865004703", "product_name": "Kvarg"},
            )

        assert status == 400
        assert body.get("error") == "off_err_no_credentials"

    def test_missing_name_returns_400(self, live_url):
        """Service raises ``ValueError('off_err_no_name')`` for empty name."""
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=ValueError("off_err_no_name"),
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {"code": "7310865004703", "product_name": ""},
            )

        assert status == 400
        assert body.get("error") == "off_err_no_name"

    def test_upstream_runtime_error_returns_502(self, live_url):
        """``RuntimeError`` from the service (network/HTTP failure) is
        surfaced as 502 with the error code in the body."""
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=RuntimeError("off_err_network"),
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {"code": "7310865004703", "product_name": "Kvarg"},
            )

        assert status == 502
        assert body.get("error") == "off_err_network"

    def test_upstream_status_not_one_surfaces_as_502(self, live_url):
        """When the OFF API responds with ``status != 1`` (e.g. validation
        failure, duplicate product, missing required field), the service
        raises ``RuntimeError(status_verbose)`` and the route returns 502.

        This is the "OFF rejected our submission" case the task description
        calls out as ``duplicate / already-imported`` — OFF does not
        distinguish "duplicate" from other rejections; the verbose message
        is the only signal."""
        with patch(
            "services.off_service.add_product_to_off",
            side_effect=RuntimeError("product already exists in OFF"),
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {"code": "7310865004703", "product_name": "Kvarg"},
            )

        assert status == 502, (
            "Service contract: OFF status!=1 → RuntimeError → 502 from route"
        )
        assert body.get("error") == "product already exists in OFF"


# ===========================================================================
# POST /api/off/add-product — "already imported" idempotency
# ===========================================================================


class TestAddProductAlreadyImported:
    """When the local product is already flagged ``is_synced_with_off``, the
    re-post must be idempotent: the OFF API call still happens (allows
    field updates), the sync flag is re-set, and the response is 200."""

    def test_already_synced_local_product_is_idempotent(self, live_url):
        """``mark_product_synced_with_off`` uses ``INSERT OR IGNORE`` so
        re-flagging a product that's already synced is a no-op at the DB
        level. The route always reports ``synced_flag_set=True`` after a
        successful call, regardless of whether the flag existed before.

        We invoke the route twice in a row to exercise the idempotency.
        """
        from services import off_service

        add_spec = create_autospec(off_service.add_product_to_off, spec_set=True)
        add_spec.return_value = {"status": 1, "status_verbose": "fields saved"}

        with patch(
            "services.off_service.add_product_to_off", add_spec
        ), patch(
            "services.image_service.get_image", return_value=None
        ), patch(
            "services.product_crud.mark_product_synced_with_off"
        ) as sync_mock:
            for _ in range(2):
                status, body = _post(
                    f"{live_url}/api/off/add-product",
                    {
                        "code": "7310865004703",
                        "product_name": "Kvarg",
                        "product_id": 99,
                    },
                )
                assert status == 200
                assert body["ok"] is True
                assert body["synced_flag_set"] is True

        # Both calls hit the OFF service and the local flag function.
        assert add_spec.call_count == 2
        assert sync_mock.call_count == 2
        # Both invocations passed the same product_id and EAN.
        for call in sync_mock.call_args_list:
            assert call[0][0] == 99
            assert call[0][1] == "7310865004703"

    def test_sync_flag_failure_is_swallowed_not_502(self, live_url):
        """If ``mark_product_synced_with_off`` raises (e.g. a transient DB
        error), the route logs the failure but still returns 200 with
        ``synced_flag_set=False``. The OFF submission is what matters; the
        local flag is a secondary marker."""
        with patch(
            "services.off_service.add_product_to_off",
            return_value={"status": 1, "status_verbose": "fields saved"},
        ), patch(
            "services.image_service.get_image", return_value=None
        ), patch(
            "services.product_crud.mark_product_synced_with_off",
            side_effect=RuntimeError("flag table locked"),
        ):
            status, body = _post(
                f"{live_url}/api/off/add-product",
                {
                    "code": "7310865004703",
                    "product_name": "Kvarg",
                    "product_id": 99,
                },
            )

        assert status == 200, (
            f"Sync-flag failure must NOT cause 5xx: {status} {body}"
        )
        assert body["ok"] is True
        assert body["synced_flag_set"] is False
