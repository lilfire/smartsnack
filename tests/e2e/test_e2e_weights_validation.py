"""Direct-API validation tests for ``PUT /api/weights``.

LSO-1352 Phase 2D-1 audit gap **#7**. The route at
``blueprints/weights.py:16-23`` catches both ``ValueError`` and
``TypeError`` from ``services.weight_service.update_weights`` and maps
them to ``{"error": <str(exc)>}`` with status 400.

These subtests pin each documented validation branch:

- Non-JSON / missing body → ``_require_json`` ``ValueError``.
- Non-list body (dict, string, number) → ``"Expected array of weights"``.
- Invalid ``direction`` ('sideways', …) → ``"Invalid direction: ..."``.
- Invalid ``formula`` name → ``"Invalid formula: ..."``.
- Out-of-range ``weight`` (>1000, <0) → ``"Weight must be between 0 and 1000"``.
- Non-finite / non-castable ``formula_min`` / ``formula_max`` →
  ``"Invalid numeric value for formula_min"`` / ``"... for formula_max"``.

Conventions (Rules 16, 17, 18): no mocks needed — the service raises real
``ValueError`` instances and the route maps them faithfully. Every test
asserts the exact error message so a future refactor that swallows or
rewrites validator output breaks here, not in production.
"""

import json
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _put_raw(url, body_bytes, content_type="application/json", timeout=5):
    """PUT raw bytes (so we can craft invalid JSON or non-JSON content)."""
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": content_type,
            "X-Requested-With": "SmartSnack",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _put(url, payload, timeout=5):
    """PUT JSON payload to ``url`` and return ``(status, parsed_body)``."""
    return _put_raw(url, json.dumps(payload).encode(), timeout=timeout)


def _get_weights(live_url, timeout=5):
    """GET the current weights so post-state assertions are honest."""
    req = urllib.request.Request(
        f"{live_url}/api/weights",
        headers={"X-Requested-With": "SmartSnack"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _kcal_weight(weights):
    """Return the kcal weight dict from a GET /api/weights payload."""
    return next(w for w in weights if w["field"] == "kcal")


# ===========================================================================
# Missing body / wrong-type body
# ===========================================================================


class TestWeightsBodyShape:
    """Validation at the body-shape boundary.

    ``_require_json`` raises ``ValueError("Invalid or missing JSON body")``
    when there is no JSON at all; ``update_weights`` then raises
    ``ValueError("Expected array of weights")`` when the body is a dict,
    string, or any non-list value.
    """

    def test_empty_body_returns_400(self, live_url):
        """An empty request body trips the ``_require_json`` guard. The
        route maps the ValueError to 400 with the helper's message."""
        status, body = _put_raw(f"{live_url}/api/weights", b"")
        assert status == 400, f"Expected 400 for empty body, got {status}: {body}"
        assert body == {"error": "Invalid or missing JSON body"}, (
            f"Expected exact ValueError text from _require_json; got {body!r}"
        )

    def test_dict_body_rejected_as_non_list(self, live_url):
        """A JSON object (dict) is not a list → service raises with the
        exact message ``Expected array of weights``."""
        status, body = _put(f"{live_url}/api/weights", {"field": "kcal"})
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Expected array of weights"}, (
            f"Expected exact 'Expected array of weights'; got {body!r}"
        )

    def test_string_body_rejected_as_non_list(self, live_url):
        """A JSON string ("kcal") is also not a list."""
        status, body = _put(f"{live_url}/api/weights", "kcal")
        assert status == 400
        assert body == {"error": "Expected array of weights"}, (
            f"String body must produce non-list error; got {body!r}"
        )

    def test_number_body_rejected_as_non_list(self, live_url):
        """A JSON number is also not a list."""
        status, body = _put(f"{live_url}/api/weights", 42)
        assert status == 400
        assert body == {"error": "Expected array of weights"}, (
            f"Number body must produce non-list error; got {body!r}"
        )

    def test_empty_list_is_a_noop_and_returns_200(self, live_url):
        """Contrast case: an *empty* list is a valid body — ``update_weights``
        iterates zero items, commits, and the route returns 200. This pins
        the contract that ``[]`` is not an error, only non-list inputs are."""
        status, body = _put(f"{live_url}/api/weights", [])
        assert status == 200, f"Empty list must be a no-op, got {status}: {body}"
        assert body == {"ok": True, "message": "Weights updated"}


# ===========================================================================
# Invalid direction
# ===========================================================================


class TestWeightsDirectionValidation:
    """``direction`` is restricted to the frozenset ``{"lower", "higher"}``.

    Any other string raises ``ValueError(f"Invalid direction: {direction}")``
    in ``services/weight_service.py:70``. The route surfaces the exact
    message in a 400 body.
    """

    def test_sideways_rejected_with_specific_message(self, live_url):
        """The audit's named bad value, ``"sideways"``, must round-trip into
        the error string verbatim — that's the contract clients depend on
        for surfacing the offending value to users."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "sideways",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid direction: sideways"}, (
            f"Expected message including the bad value; got {body!r}"
        )

    def test_empty_direction_rejected(self, live_url):
        """Empty-string direction is also invalid and the route reports it
        verbatim — guards against accidental "fallback to default" logic."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400
        assert body == {"error": "Invalid direction: "}, (
            f"Empty direction must hit the same branch with its literal value; "
            f"got {body!r}"
        )

    def test_unknown_field_silently_skipped(self, live_url):
        """A field not in ``SCORE_CONFIG_MAP`` is *silently skipped* (the
        loop ``continue`` at ``weight_service.py:67``) — even if direction
        is invalid, validation never runs because the item is dropped. This
        pins that contract so a future strict-mode regression doesn't change
        behaviour without a deliberate test update."""
        weights_before = _get_weights(live_url)
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "definitely_not_a_real_field",
                "direction": "sideways",
                "formula": "polynomial",
                "weight": 99999,
            }],
        )
        assert status == 200, (
            f"Unknown field must short-circuit before validation, got {status}: {body}"
        )
        assert body == {"ok": True, "message": "Weights updated"}
        # And weights must not have moved.
        weights_after = _get_weights(live_url)
        assert weights_before == weights_after, (
            "Unknown field must be a no-op; weight state changed"
        )

    def test_invalid_direction_does_not_persist(self, live_url):
        """When a valid field's direction is rejected, the kcal weight must
        not have been updated. Asserts the rollback/short-circuit contract
        at the post-state level."""
        kcal_before = _kcal_weight(_get_weights(live_url))
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 777,
                "direction": "diagonal",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400
        assert body == {"error": "Invalid direction: diagonal"}
        kcal_after = _kcal_weight(_get_weights(live_url))
        assert kcal_before == kcal_after, (
            f"Failed validation must not persist; before={kcal_before} "
            f"after={kcal_after}"
        )


# ===========================================================================
# Invalid formula
# ===========================================================================


class TestWeightsFormulaValidation:
    """``formula`` is restricted to ``{"minmax", "direct"}``.

    Anything else raises ``ValueError(f"Invalid formula: {formula}")``.
    """

    def test_unknown_formula_rejected(self, live_url):
        """A clearly bogus formula name must produce the exact error string."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "lower",
                "formula": "polynomial",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid formula: polynomial"}, (
            f"Expected message naming the bad formula; got {body!r}"
        )

    def test_capitalised_formula_rejected(self, live_url):
        """The validator is case-sensitive — ``"MinMax"`` is invalid."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "lower",
                "formula": "MinMax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400
        assert body == {"error": "Invalid formula: MinMax"}, (
            f"Validator must be case-sensitive; got {body!r}"
        )


# ===========================================================================
# Weight out of range
# ===========================================================================


class TestWeightsWeightRange:
    """``weight`` is clamped to ``0 <= weight <= 1000`` in
    ``weight_service.update_weights``. Values outside that range raise
    ``ValueError("Weight must be between 0 and 1000")``.
    """

    def test_weight_above_max_rejected(self, live_url):
        """A weight of 1500 must trip the upper bound."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 1500,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Weight must be between 0 and 1000"}, (
            f"Expected exact range error; got {body!r}"
        )

    def test_weight_below_zero_rejected(self, live_url):
        """Negative weight values must trip the lower bound."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": -1,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400
        assert body == {"error": "Weight must be between 0 and 1000"}, (
            f"Negative weight must produce the same range error; got {body!r}"
        )

    def test_weight_at_boundary_accepted(self, live_url):
        """Exactly 0 and exactly 1000 are inclusive bounds and must be
        accepted — contrast case to prove the rejection is the range, not
        e.g. an arbitrary "no large numbers" check."""
        for boundary in (0, 1000):
            status, body = _put(
                f"{live_url}/api/weights",
                [{
                    "field": "kcal",
                    "enabled": True,
                    "weight": boundary,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }],
            )
            assert status == 200, (
                f"Weight={boundary} must be accepted (inclusive bound), "
                f"got {status}: {body}"
            )

    def test_invalid_weight_type_rejected(self, live_url):
        """A non-numeric weight ("heavy") is rejected by ``_safe_float`` with
        a labelled message — pins the helper's contract at the HTTP layer."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": "heavy",
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": 0,
            }],
        )
        assert status == 400
        assert body == {"error": "Invalid numeric value for weight"}, (
            f"Expected _safe_float's labelled error; got {body!r}"
        )


# ===========================================================================
# Out-of-range / non-finite formula_min and formula_max
# ===========================================================================


class TestWeightsFormulaBounds:
    """``formula_min`` and ``formula_max`` go through ``_safe_float``.

    The helper raises:
    - ``ValueError("Invalid numeric value for formula_min")`` for non-castable
      input (e.g. ``"abc"``).
    - ``ValueError("Non-finite numeric value for formula_min")`` for
      ``Infinity`` / ``NaN`` (which is what the audit calls "out-of-range").

    Both arms hit the route's 400 handler. The matching tests exist for
    ``formula_max``.
    """

    def test_formula_min_non_castable_rejected(self, live_url):
        """A string like ``"abc"`` is rejected with the labelled helper error."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": "abc",
                "formula_max": 100,
            }],
        )
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert body == {"error": "Invalid numeric value for formula_min"}, (
            f"Expected labelled helper error for formula_min; got {body!r}"
        )

    def test_formula_max_non_castable_rejected(self, live_url):
        """Same contract for ``formula_max`` — both bounds go through the
        same helper, so the labelled error must include the right field name."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 0,
                "formula_max": "xyz",
            }],
        )
        assert status == 400
        assert body == {"error": "Invalid numeric value for formula_max"}, (
            f"Expected labelled helper error for formula_max; got {body!r}"
        )

    def test_formula_min_non_finite_rejected(self, live_url):
        """Python's ``float('inf')`` is castable but not finite — the helper
        emits the "Non-finite" variant. Sent as the JSON literal ``Infinity``
        which Python's json module accepts in non-strict mode."""
        # urllib doesn't accept Infinity in standard JSON; build the body
        # manually so we can include the non-finite token.
        body_bytes = (
            b'[{"field":"kcal","enabled":true,"weight":100,'
            b'"direction":"lower","formula":"minmax",'
            b'"formula_min":Infinity,"formula_max":100}]'
        )
        status, body = _put_raw(f"{live_url}/api/weights", body_bytes)

        assert status == 400, f"Expected 400 for Infinity, got {status}: {body}"
        assert body == {"error": "Non-finite numeric value for formula_min"}, (
            f"Expected non-finite error for formula_min; got {body!r}"
        )

    def test_formula_max_nan_rejected(self, live_url):
        """``NaN`` for ``formula_max`` must also be rejected as non-finite."""
        body_bytes = (
            b'[{"field":"kcal","enabled":true,"weight":100,'
            b'"direction":"lower","formula":"minmax",'
            b'"formula_min":0,"formula_max":NaN}]'
        )
        status, body = _put_raw(f"{live_url}/api/weights", body_bytes)
        assert status == 400
        assert body == {"error": "Non-finite numeric value for formula_max"}, (
            f"Expected non-finite error for formula_max; got {body!r}"
        )

    def test_finite_in_range_values_accepted(self, live_url):
        """Contrast case: finite, castable values across the full
        ``formula_min`` / ``formula_max`` surface are accepted and persist
        — proves the rejections above are caused by the bound violations,
        not an unrelated guard."""
        status, body = _put(
            f"{live_url}/api/weights",
            [{
                "field": "kcal",
                "enabled": True,
                "weight": 100,
                "direction": "lower",
                "formula": "minmax",
                "formula_min": 5,
                "formula_max": 95,
            }],
        )
        assert status == 200, f"Expected 200 for valid bounds, got {status}: {body}"
        assert body == {"ok": True, "message": "Weights updated"}

        kcal = _kcal_weight(_get_weights(live_url))
        assert float(kcal["formula_min"]) == 5.0
        assert float(kcal["formula_max"]) == 95.0
        assert float(kcal["weight"]) == 100.0
