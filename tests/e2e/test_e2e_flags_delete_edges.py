"""End-to-end edge-case tests for ``blueprints/flags.py``.

Phase 2C of the LSO-1352 audit. Closes the remaining gaps for the flags
blueprint:

- ``DELETE /api/flags/<name>`` — system-flag rejection (400 + post-state
  verification that the flag still exists in the list)
- ``DELETE /api/flags/<name>`` — non-existent flag (404 + specific error)
- ``DELETE /api/flags/<name>`` — happy path (verify the flag is gone from
  /api/flags AND from /api/flag-config, and product associations are
  scrubbed via product_flags)
- ``PUT /api/flags/<name>`` — system-flag rejection (400, label preserved)
- ``PUT /api/flags/<name>`` — non-existent flag (404)
- ``PUT /api/flags/<name>`` — missing/empty label (400)
- ``PUT /api/flags/<name>`` — malformed JSON body (400)
- ``POST /api/flags`` — invalid flag-name pattern (400)
- ``POST /api/flags`` — name length boundary (200-char rejected, 100-char
  accepted at limit)
- ``POST /api/flags`` — malformed JSON body / missing fields (400)
- ``GET /api/flags`` — count field reflects product associations (post-state
  numeric verification, not just "is an int")
- ``GET /api/flag-config`` — system flag has labelKey + system type marker

Rule 18: every test asserts the *outcome* (response body fields, post-state
DB shape via subsequent GET), not just the status code.

System flag rejection is *intentionally* not asserted to return 409 — the
service contract is documented as 400 ("Cannot delete/edit system flags")
and the audit asked for "appropriate rejection status + error message per
service contract" (not a contract change).
"""

import json
import urllib.error
import urllib.request

from services.flag_service import _MAX_FLAG_NAME_LEN


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method, url, payload=None, timeout=5, raw_body=None, content_type=None):
    """Make an HTTP request and return ``(status, parsed_body)``.

    ``payload`` is JSON-encoded; ``raw_body`` is sent verbatim. Pass at most
    one of the two.
    """
    headers = {"X-Requested-With": "SmartSnack"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        data = raw_body
        if content_type is not None:
            headers["Content-Type"] = content_type
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"_raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def _get(url):
    return _request("GET", url)


def _post(url, payload=None, raw_body=None, content_type=None):
    return _request("POST", url, payload=payload, raw_body=raw_body, content_type=content_type)


def _put(url, payload=None, raw_body=None, content_type=None):
    return _request("PUT", url, payload=payload, raw_body=raw_body, content_type=content_type)


def _delete(url):
    return _request("DELETE", url)


# ---------------------------------------------------------------------------
# DELETE /api/flags/<name>
# ---------------------------------------------------------------------------


class TestDeleteFlagEdgeCases:
    """Edge cases for ``DELETE /api/flags/<name>``."""

    def test_delete_system_flag_rejected_with_400(self, live_url):
        """System flag deletion is rejected by the service with a 400.

        Service raises ``ValueError('Cannot delete system flags')`` which the
        blueprint surfaces as 400. The flag must remain in the listing after
        the rejected delete (post-state verification, not just status check).
        """
        status, body = _delete(f"{live_url}/api/flags/is_synced_with_off")
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
        assert "system" in body["error"].lower()

        # The system flag must still be present.
        list_status, flags = _get(f"{live_url}/api/flags")
        assert list_status == 200
        names = {f["name"] for f in flags}
        assert "is_synced_with_off" in names, (
            "System flag must remain in the listing after rejected DELETE"
        )

        # And in flag-config.
        cfg_status, cfg = _get(f"{live_url}/api/flag-config")
        assert cfg_status == 200
        assert "is_synced_with_off" in cfg
        assert cfg["is_synced_with_off"]["type"] == "system"

    def test_delete_nonexistent_flag_returns_404(self, live_url):
        """Deleting a flag that does not exist returns 404 with 'Flag not found'.

        Implementation contract (LSO-1357): ``flag_service.delete_flag``
        raises ``LookupError('Flag not found')`` which the blueprint surfaces
        as 404 — REST 'absent resource' convention.
        """
        status, body = _delete(f"{live_url}/api/flags/__never_existed_xyz__")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body.get("error") == "Flag not found"

    def test_delete_user_flag_happy_path_removes_from_list_and_config(
        self, live_url, unique_name
    ):
        """Successful DELETE removes the flag from /api/flags AND /api/flag-config."""
        raw = unique_name("delflag").replace("-", "_").lower()
        create_status, _ = _post(
            f"{live_url}/api/flags",
            {"name": raw, "label": "Delete Me"},
        )
        assert create_status == 201

        # Pre-state: flag exists in both endpoints.
        _, flags_before = _get(f"{live_url}/api/flags")
        assert raw in {f["name"] for f in flags_before}
        _, cfg_before = _get(f"{live_url}/api/flag-config")
        assert raw in cfg_before

        status, body = _delete(f"{live_url}/api/flags/{raw}")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("ok") is True
        assert body.get("message") == "Flag deleted"
        # No products were tagged with this flag, so removed_from is 0.
        assert body.get("removed_from") == 0

        # Post-state: flag is gone from both endpoints.
        _, flags_after = _get(f"{live_url}/api/flags")
        assert raw not in {f["name"] for f in flags_after}
        _, cfg_after = _get(f"{live_url}/api/flag-config")
        assert raw not in cfg_after

    def test_delete_user_flag_scrubs_product_associations(
        self, live_url, api_create_product, unique_name
    ):
        """Deleting a user flag also removes product_flags rows tied to that flag.

        Verified by setting the flag on a product, deleting the flag, then
        reading the product and confirming the flag key is no longer set.
        ``removed_from`` is the number of (product, flag) pairs deleted.
        """
        raw = unique_name("scrub").replace("-", "_").lower()
        create_status, _ = _post(
            f"{live_url}/api/flags",
            {"name": raw, "label": "Scrub Me"},
        )
        assert create_status == 201

        product = api_create_product(name=unique_name("FlagScrubProduct"))
        # Set the flag on the product via PUT /api/products/<id> (flags is a list).
        put_status, _ = _put(
            f"{live_url}/api/products/{product['id']}",
            {"flags": [raw]},
        )
        assert put_status in (200, 204), f"Setting flag failed: {put_status}"

        # Sanity-check the flag is set BEFORE deleting the flag definition.
        _, pre_listing = _get(f"{live_url}/api/products?limit=1000")
        pre = next(p for p in pre_listing["products"] if p["id"] == product["id"])
        assert raw in pre.get("flags", []), (
            f"Setup failed: flag {raw} not set on product: {pre.get('flags')}"
        )

        # Now delete the flag and confirm removed_from == 1.
        status, body = _delete(f"{live_url}/api/flags/{raw}")
        assert status == 200
        assert body["removed_from"] == 1, (
            f"Expected removed_from == 1, got {body['removed_from']}"
        )

        # Product must no longer carry the flag.
        _, listing = _get(f"{live_url}/api/products?limit=1000")
        prod = next(p for p in listing["products"] if p["id"] == product["id"])
        assert raw not in prod.get("flags", []), (
            f"Flag {raw} should be cleared from product after flag DELETE: {prod.get('flags')}"
        )


# ---------------------------------------------------------------------------
# PUT /api/flags/<name>
# ---------------------------------------------------------------------------


class TestPutFlagEdgeCases:
    """Edge cases for ``PUT /api/flags/<name>``."""

    def test_update_system_flag_rejected_with_400(self, live_url):
        """System flag label cannot be updated; rejected with 400 and a 'system' error."""
        # Capture original label so we can prove the rejection didn't change it.
        _, before = _get(f"{live_url}/api/flag-config")
        original_label = before["is_synced_with_off"]["label"]

        status, body = _put(
            f"{live_url}/api/flags/is_synced_with_off",
            {"label": "Hacked label"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "system" in body["error"].lower()

        _, after = _get(f"{live_url}/api/flag-config")
        assert after["is_synced_with_off"]["label"] == original_label, (
            "System flag label must not have changed after rejected PUT"
        )

    def test_update_nonexistent_flag_returns_404(self, live_url):
        """PUT against a flag that does not exist returns 404 with 'Flag not found'."""
        status, body = _put(
            f"{live_url}/api/flags/__never_existed_xyz__",
            {"label": "Whatever"},
        )
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert body.get("error") == "Flag not found"

    def test_update_empty_label_returns_400(self, live_url, unique_name):
        """An empty ``label`` is rejected with 400 (label is required)."""
        raw = unique_name("emptylbl").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Initial"})

        status, body = _put(f"{live_url}/api/flags/{raw}", {"label": ""})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "label is required" in body["error"].lower()

        # The original label must still be intact.
        _, cfg = _get(f"{live_url}/api/flag-config")
        assert cfg[raw]["label"] == "Initial"

    def test_update_whitespace_label_returns_400(self, live_url, unique_name):
        """A whitespace-only label is stripped to '' and rejected with 400."""
        raw = unique_name("wslbl").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Initial"})

        status, body = _put(f"{live_url}/api/flags/{raw}", {"label": "   \t   "})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "label is required" in body["error"].lower()

    def test_update_missing_label_field_returns_400(self, live_url, unique_name):
        """Body without a ``label`` key is treated as empty label → 400."""
        raw = unique_name("nolbl").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Initial"})

        status, body = _put(f"{live_url}/api/flags/{raw}", {})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "label is required" in body["error"].lower()

    def test_update_malformed_json_returns_400(self, live_url, unique_name):
        """A request with an invalid JSON body returns 400 with the JSON error."""
        raw = unique_name("badjson").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Initial"})

        status, body = _put(
            f"{live_url}/api/flags/{raw}",
            raw_body=b"not-a-json-object",
            content_type="application/json",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "json" in body["error"].lower()

    def test_update_user_flag_happy_path_reflects_in_config(self, live_url, unique_name):
        """Successful PUT updates the label visible via /api/flag-config."""
        raw = unique_name("updlbl").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Before"})

        status, body = _put(f"{live_url}/api/flags/{raw}", {"label": "After"})
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body.get("ok") is True

        _, cfg = _get(f"{live_url}/api/flag-config")
        assert cfg[raw]["label"] == "After"


# ---------------------------------------------------------------------------
# POST /api/flags
# ---------------------------------------------------------------------------


class TestPostFlagEdgeCases:
    """Edge cases for ``POST /api/flags``."""

    def test_create_with_invalid_name_pattern_returns_400(self, live_url):
        """Names not matching ``^[a-z][a-z0-9_]*$`` are rejected with 400."""
        invalid_names = [
            "1starts_with_digit",
            "Starts_With_Capital",
            "has-dash",
            "has space",
            "has.dot",
            "_starts_with_underscore",
            "uppercase_END",
        ]
        for name in invalid_names:
            status, body = _post(
                f"{live_url}/api/flags",
                {"name": name, "label": "X"},
            )
            assert status == 400, (
                f"Expected 400 for {name!r}, got {status}: {body}"
            )
            assert "error" in body
            assert (
                "flag name" in body["error"].lower()
                or "invalid" in body["error"].lower()
            )

    def test_create_with_empty_name_returns_400(self, live_url):
        """An empty ``name`` field is rejected with 'name and label are required'."""
        status, body = _post(
            f"{live_url}/api/flags",
            {"name": "", "label": "Label"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "required" in body["error"].lower()

    def test_create_with_empty_label_returns_400(self, live_url):
        """An empty ``label`` field is rejected with 'name and label are required'."""
        status, body = _post(
            f"{live_url}/api/flags",
            {"name": "valid_name", "label": ""},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "required" in body["error"].lower()

    def test_create_with_oversize_name_returns_400(self, live_url):
        """A name longer than ``_MAX_FLAG_NAME_LEN`` is rejected with 400."""
        # Start with 'a' so the regex pattern technically matches if length didn't trip.
        long_name = "a" + "b" * _MAX_FLAG_NAME_LEN
        assert len(long_name) > _MAX_FLAG_NAME_LEN

        status, body = _post(
            f"{live_url}/api/flags",
            {"name": long_name, "label": "Whatever"},
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "invalid flag name" in body["error"].lower()

    def test_create_at_name_length_limit_succeeds(self, live_url):
        """A name with exactly ``_MAX_FLAG_NAME_LEN`` chars is accepted."""
        at_limit = "z" + "a" * (_MAX_FLAG_NAME_LEN - 1)
        assert len(at_limit) == _MAX_FLAG_NAME_LEN

        status, body = _post(
            f"{live_url}/api/flags",
            {"name": at_limit, "label": "At limit"},
        )
        assert status == 201, f"Expected 201, got {status}: {body}"

        # Confirm it shows up in the listing.
        _, flags = _get(f"{live_url}/api/flags")
        names = {f["name"] for f in flags}
        assert at_limit in names

    def test_create_malformed_json_returns_400(self, live_url):
        """A POST with an invalid JSON body returns 400 with the JSON error."""
        status, body = _post(
            f"{live_url}/api/flags",
            raw_body=b"{this-is-not-json",
            content_type="application/json",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "json" in body["error"].lower()


# ---------------------------------------------------------------------------
# GET /api/flags and GET /api/flag-config — shape verification
# ---------------------------------------------------------------------------


class TestGetFlagsAndConfig:
    """Shape and count assertions for the read endpoints."""

    def test_list_flags_count_reflects_product_associations(
        self, live_url, api_create_product, unique_name
    ):
        """``count`` on each flag entry must equal the number of products that
        actually carry the flag, and update when a product is added or removed.

        Tests both 0 → 1 (new flag, then one product) and 1 → 2 transitions.
        """
        raw = unique_name("cntflag").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "Count Test"})

        # Initially, count should be 0.
        _, flags = _get(f"{live_url}/api/flags")
        entry = next(f for f in flags if f["name"] == raw)
        assert entry["count"] == 0, f"New flag should have count 0, got {entry['count']}"

        # Add the flag to one product (flags is a list of flag names).
        p1 = api_create_product(name=unique_name("CntProd1"))
        _put(f"{live_url}/api/products/{p1['id']}", {"flags": [raw]})

        _, flags = _get(f"{live_url}/api/flags")
        entry = next(f for f in flags if f["name"] == raw)
        assert entry["count"] == 1, f"Flag should have count 1, got {entry['count']}"

        # Add to a second product.
        p2 = api_create_product(name=unique_name("CntProd2"))
        _put(f"{live_url}/api/products/{p2['id']}", {"flags": [raw]})

        _, flags = _get(f"{live_url}/api/flags")
        entry = next(f for f in flags if f["name"] == raw)
        assert entry["count"] == 2, f"Flag should have count 2, got {entry['count']}"

    def test_flag_config_distinguishes_system_from_user(self, live_url, unique_name):
        """``/api/flag-config`` entries have ``type`` of 'system' or 'user'."""
        raw = unique_name("usrflag").replace("-", "_").lower()
        _post(f"{live_url}/api/flags", {"name": raw, "label": "User"})

        _, cfg = _get(f"{live_url}/api/flag-config")
        # Required system flag (seeded by init_db).
        assert cfg["is_synced_with_off"]["type"] == "system"
        # The user flag we just created.
        assert cfg[raw]["type"] == "user"
        assert cfg[raw]["label"] == "User"
        # Every entry has the three required keys.
        for name, entry in cfg.items():
            assert "type" in entry, f"Entry {name} missing 'type'"
            assert "labelKey" in entry, f"Entry {name} missing 'labelKey'"
            assert "label" in entry, f"Entry {name} missing 'label'"
            assert entry["type"] in ("system", "user")

    def test_list_flags_sorted_by_type_then_name(self, live_url, unique_name):
        """Flags are returned sorted by type ASC, then name ASC.

        Service contract:
            ORDER BY fd.type ASC, fd.name ASC
        ('system' < 'user' lexically). We assert relative ordering rather than
        absolute positions so seeded flag changes don't break the test.
        """
        # Create two user flags whose names sort differently.
        a = "a" + unique_name("").replace("-", "_").lower()[:6]
        z = "z" + unique_name("").replace("-", "_").lower()[:6]
        _post(f"{live_url}/api/flags", {"name": a, "label": "A"})
        _post(f"{live_url}/api/flags", {"name": z, "label": "Z"})

        _, flags = _get(f"{live_url}/api/flags")
        types = [f["type"] for f in flags]
        # All 'system' entries must precede any 'user' entries.
        if "system" in types and "user" in types:
            last_system = max(i for i, t in enumerate(types) if t == "system")
            first_user = min(i for i, t in enumerate(types) if t == "user")
            assert last_system < first_user, (
                "All system flags must sort before all user flags"
            )

        # Within user flags, a must come before z.
        names = [f["name"] for f in flags if f["type"] == "user"]
        assert names.index(a) < names.index(z), (
            f"User flag {a!r} must sort before {z!r}"
        )
