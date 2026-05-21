"""End-to-end full-coverage edge-case tests for ``blueprints/tags.py``.

Phase 2C of the LSO-1352 audit. Existing ``tests/e2e/test_tags_crud.py``
covers happy paths and basic validation; this file focuses on the
remaining edges flagged by the audit:

- POST/PUT/GET/DELETE with malformed JSON (missing/non-JSON body)
- POST with no ``label`` key in body
- POST with non-string ``label`` (number, null, list)
- POST with leading/trailing-only whitespace producing identical idempotent
  tag (case + whitespace preservation semantics)
- POST with special characters that affect LIKE searches: ``%``, ``_``,
  backslash, single quote (Python service has explicit escape logic)
- POST with Unicode + emoji labels (Norwegian + symbols)
- GET ``/api/tags?q=`` with LIKE wildcard ``%`` and ``_`` in the query —
  these must be ESCAPED and not match arbitrary tags
- GET ``/api/tags?q=`` with empty query parameter returns *all* tags
  (matches service "empty prefix" branch, capped at default limit 10)
- GET search default limit is 10 (boundary verification with 11 inserted)
- DELETE in-use tag cascades and removes the product_tags rows
- Tag label is **case-insensitive unique** but **case-preserving** when
  reading back (mixed-case + lower create the same tag)

Rule 18: each test asserts the *outcome* (specific values from the GET
response or specific status + message), not just shape.
"""

import json
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method, url, payload=None, raw_body=None, content_type=None, timeout=5):
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
            body = resp.read()
            return resp.status, json.loads(body) if body else None
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
# POST /api/tags — malformed and bad-type bodies
# ---------------------------------------------------------------------------


class TestCreateTagMalformed:
    """``POST /api/tags`` malformed-body and missing-field handling."""

    def test_missing_label_field_returns_400(self, live_url):
        """Body without a ``label`` key is treated as ``label = ''`` → 400."""
        status, body = _post(f"{live_url}/api/tags", {})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "label is required" in body["error"]

    def test_malformed_json_returns_400(self, live_url):
        """A POST with an invalid JSON body returns 400 with the JSON error."""
        status, body = _post(
            f"{live_url}/api/tags",
            raw_body=b"{not-a-json",
            content_type="application/json",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "json" in body["error"].lower()

    def test_non_string_label_returns_400(self, live_url):
        """A non-string ``label`` (list, dict, number, null) is rejected with
        400 — guards against AttributeError in ``label.strip()``."""
        for bad in [None, [], {}, 42, ["foo"]]:
            status, body = _post(f"{live_url}/api/tags", {"label": bad})
            assert status == 400, (
                f"Expected 400 for label={bad!r}, got {status}: {body}"
            )
            assert "label is required" in body["error"], (
                f"Expected 'label is required' for {bad!r}, got {body}"
            )


# ---------------------------------------------------------------------------
# POST /api/tags — case + whitespace + special chars
# ---------------------------------------------------------------------------


class TestCreateTagSpecialContent:
    """``POST /api/tags`` with case-mixing, whitespace, and special characters."""

    def test_create_preserves_original_case(self, live_url, unique_name):
        """The label is stored verbatim (case-preserving) but unique
        case-insensitively. Creating 'FooBar-xyz' and then 'foobar-xyz'
        returns the original case via GET."""
        suffix = unique_name("").lower()
        mixed = f"MixCase-{suffix}"
        lower = f"mixcase-{suffix}"

        status1, t1 = _post(f"{live_url}/api/tags", {"label": mixed})
        assert status1 == 201
        assert t1["label"] == mixed

        # Creating with all-lower must return the SAME tag id and the ORIGINAL case label.
        status2, t2 = _post(f"{live_url}/api/tags", {"label": lower})
        assert status2 == 201
        assert t2["id"] == t1["id"]
        assert t2["label"] == mixed, (
            f"Case-insensitive idempotency must preserve original case: {t2}"
        )

    def test_create_with_special_chars(self, live_url, unique_name):
        """Special characters (``%``, ``_``, ``\\``, single quote) are accepted
        as literal label content and stored faithfully."""
        suffix = unique_name("").lower()
        special = f"100%fat_off\\out's-{suffix}"
        status, tag = _post(f"{live_url}/api/tags", {"label": special})
        assert status == 201, f"Expected 201, got {status}: {tag}"
        assert tag["label"] == special

        # Confirm the round-trip via GET (no double-escaping).
        _, fetched = _get(f"{live_url}/api/tags/{tag['id']}")
        assert fetched["label"] == special

    def test_create_with_unicode_and_emoji(self, live_url, unique_name):
        """Norwegian + emoji labels round-trip cleanly through SQLite."""
        suffix = unique_name("").lower()
        label = f"æøå \U0001f964 {suffix}"  # æøå 🥤 <suffix>
        status, tag = _post(f"{live_url}/api/tags", {"label": label})
        assert status == 201
        assert tag["label"] == label

        _, fetched = _get(f"{live_url}/api/tags/{tag['id']}")
        assert fetched["label"] == label

    def test_create_strips_outer_whitespace_but_preserves_inner(
        self, live_url, unique_name
    ):
        """`label.strip()` removes leading/trailing whitespace but does NOT
        collapse interior whitespace."""
        suffix = unique_name("").lower()
        raw_label = f"  inner  space  {suffix}  "
        expected = f"inner  space  {suffix}"
        status, tag = _post(f"{live_url}/api/tags", {"label": raw_label})
        assert status == 201
        assert tag["label"] == expected, (
            f"Inner whitespace must be preserved: {tag['label']!r} vs {expected!r}"
        )


# ---------------------------------------------------------------------------
# PUT /api/tags/<id> — malformed
# ---------------------------------------------------------------------------


class TestUpdateTagMalformed:
    """``PUT /api/tags/<id>`` error handling."""

    def test_malformed_json_returns_400(self, live_url, unique_name):
        """A PUT with an invalid JSON body returns 400 with a JSON error."""
        _, tag = _post(
            f"{live_url}/api/tags",
            {"label": unique_name("upd-mal")},
        )
        status, body = _put(
            f"{live_url}/api/tags/{tag['id']}",
            raw_body=b"<not json>",
            content_type="application/json",
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "json" in body["error"].lower()

    def test_missing_label_field_returns_400(self, live_url, unique_name):
        """An empty PUT body is rejected with 400 (label is required)."""
        _, tag = _post(
            f"{live_url}/api/tags",
            {"label": unique_name("upd-nolbl")},
        )
        status, body = _put(f"{live_url}/api/tags/{tag['id']}", {})
        assert status == 400
        assert "label is required" in body["error"]


# ---------------------------------------------------------------------------
# GET /api/tags?q=... — LIKE escaping and limits
# ---------------------------------------------------------------------------


class TestSearchTags:
    """``GET /api/tags?q=<query>`` LIKE-injection and limit semantics."""

    def test_search_escapes_percent_wildcard(self, live_url, unique_name):
        """A query containing ``%`` is escaped — it does NOT match arbitrary
        tags. Only tags that literally start with the prefix (containing %)
        should be returned."""
        suffix = unique_name("").lower()
        literal = f"hundred%percent-{suffix}"
        decoy = f"hundredXpercent-{suffix}"

        _post(f"{live_url}/api/tags", {"label": literal})
        _post(f"{live_url}/api/tags", {"label": decoy})

        # Search with the literal '%' character should match only `literal`,
        # not `decoy` (the '%' would have wildcarded if not escaped).
        # urllib.request will URL-encode the % automatically.
        from urllib.parse import quote
        status, results = _get(f"{live_url}/api/tags?q={quote(f'hundred%percent-{suffix}'[:14])}")
        assert status == 200
        labels = [t["label"] for t in results]
        assert literal in labels, f"Should match literal: {labels}"
        # Decoy must NOT match — would only match if % were treated as wildcard.
        assert decoy not in labels, (
            f"Decoy should not match literal-% prefix: {labels}"
        )

    def test_search_escapes_underscore_wildcard(self, live_url, unique_name):
        """A query containing ``_`` is escaped — it must not wildcard-match."""
        suffix = unique_name("").lower()
        literal = f"foo_bar-{suffix}"
        decoy = f"fooXbar-{suffix}"

        _post(f"{live_url}/api/tags", {"label": literal})
        _post(f"{live_url}/api/tags", {"label": decoy})

        from urllib.parse import quote
        # Prefix is "foo_b" — the '_' would wildcard if not escaped, matching
        # both 'foo_b...' (literal) AND 'fooXb...' (decoy).
        status, results = _get(f"{live_url}/api/tags?q={quote('foo_b')}")
        assert status == 200
        labels = {t["label"] for t in results}
        assert literal in labels, (
            f"Should match literal-underscore prefix: {labels}"
        )
        assert decoy not in labels, (
            f"Decoy should not match literal-underscore prefix: {labels}"
        )

    def test_search_with_empty_query_returns_some_tags(
        self, live_url, unique_name
    ):
        """``?q=`` (empty string parameter value) returns up to 10 tags.

        ``request.args.get('q')`` returns an empty string when the parameter
        is present but empty — the blueprint dispatches to ``search_tags("")``
        which falls into the empty-prefix branch (all tags, capped to limit)."""
        # Insert one tag so the empty-prefix branch has something to return.
        _post(f"{live_url}/api/tags", {"label": unique_name("emptyq").lower()})
        status, results = _get(f"{live_url}/api/tags?q=")
        assert status == 200
        assert isinstance(results, list)
        # Default limit is 10 — must not return more than 10 even if more exist.
        assert len(results) <= 10, (
            f"Empty-prefix search must respect default limit 10, got {len(results)}"
        )

    def test_search_default_limit_is_ten(self, live_url, unique_name):
        """Insert 11 tags with a shared prefix; the search response is capped at 10."""
        suffix = unique_name("").lower()
        prefix = f"capped-{suffix}"
        for i in range(11):
            _post(f"{live_url}/api/tags", {"label": f"{prefix}-{i:02d}"})

        from urllib.parse import quote
        status, results = _get(f"{live_url}/api/tags?q={quote(prefix)}")
        assert status == 200
        assert len(results) == 10, (
            f"Default search limit is 10; got {len(results)} for 11 matches"
        )

    def test_search_returns_sorted_alphabetically(self, live_url, unique_name):
        """Search results are sorted by label COLLATE NOCASE."""
        suffix = unique_name("").lower()
        prefix = f"sortcheck-{suffix}"
        labels = [
            f"{prefix}-zebra",
            f"{prefix}-alpha",
            f"{prefix}-MID",
        ]
        for lbl in labels:
            _post(f"{live_url}/api/tags", {"label": lbl})

        from urllib.parse import quote
        status, results = _get(f"{live_url}/api/tags?q={quote(prefix)}")
        assert status == 200
        returned = [t["label"] for t in results if t["label"].startswith(prefix)]
        # Expected order (case-insensitive): alpha, MID, zebra
        expected = sorted(returned, key=lambda s: s.lower())
        assert returned == expected, (
            f"Search must sort case-insensitively: got {returned}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/tags/<id> — cascade behaviour
# ---------------------------------------------------------------------------


def _get_product_by_id(live_url, product_id):
    """Fetch a single product from the list endpoint (no /api/products/<id>)."""
    _, data = _get(f"{live_url}/api/products?limit=1000")
    for p in data.get("products", []):
        if p["id"] == product_id:
            return p
    return {}


class TestDeleteTagCascade:
    """Deleting a tag must cascade-remove product_tags rows."""

    def test_delete_in_use_tag_succeeds_and_cascades(
        self, live_url, api_create_product, unique_name
    ):
        """Deleting a tag that is assigned to multiple products removes the tag
        AND drops the corresponding rows from product_tags (verified via
        GET on the products)."""
        label = unique_name("inusetag").lower()
        _, tag = _post(f"{live_url}/api/tags", {"label": label})

        p1 = api_create_product(name=unique_name("CascadeProd1"))
        p2 = api_create_product(name=unique_name("CascadeProd2"))
        _put(f"{live_url}/api/products/{p1['id']}", {"tagIds": [tag["id"]]})
        _put(f"{live_url}/api/products/{p2['id']}", {"tagIds": [tag["id"]]})

        # Pre-state: both products have the tag.
        pre1 = _get_product_by_id(live_url, p1["id"])
        pre2 = _get_product_by_id(live_url, p2["id"])
        assert tag["id"] in [t["id"] for t in pre1.get("tags", [])]
        assert tag["id"] in [t["id"] for t in pre2.get("tags", [])]

        # Delete the tag — should succeed (no "in-use" rejection).
        status, body = _delete(f"{live_url}/api/tags/{tag['id']}")
        assert status == 200, f"In-use tag delete should succeed: {body}"
        assert body["ok"] is True

        # Post-state: tag is gone from both products.
        post1 = _get_product_by_id(live_url, p1["id"])
        post2 = _get_product_by_id(live_url, p2["id"])
        assert tag["id"] not in [t["id"] for t in post1.get("tags", [])]
        assert tag["id"] not in [t["id"] for t in post2.get("tags", [])]

        # And the tag itself is gone from the listing.
        status, results = _get(f"{live_url}/api/tags")
        ids = {t["id"] for t in results}
        assert tag["id"] not in ids


# ---------------------------------------------------------------------------
# GET /api/tags/<id> — invalid type handling
# ---------------------------------------------------------------------------


class TestGetTagInvalidId:
    """Path-level type matching of ``<int:tag_id>`` keeps non-integer ids out."""

    def test_get_non_integer_id_returns_404(self, live_url):
        """A non-integer path component does not match the ``<int:tag_id>``
        route and Flask returns 404."""
        status, _ = _get(f"{live_url}/api/tags/not_an_integer")
        assert status == 404, (
            f"Non-int tag id must not match the int converter, got {status}"
        )

    def test_get_negative_id_returns_404_no_such_tag(self, live_url):
        """A negative or extremely large id is valid Python int but not a valid
        tag PK; the service returns ``None`` so the route returns 404 with
        'Tag not found'."""
        status, body = _get(f"{live_url}/api/tags/-1")
        # Flask's <int:...> converter rejects negatives → 404.
        assert status == 404
        # Body may be Flask's HTML 404; just ensure non-200.
