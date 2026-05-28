"""End-to-end user-journey: per-category weight override propagates to score.

Covers gap **H** from the LSO-1354 audit (LSO-1352 Phase 2D-3): the
user opens category-weight settings, applies a per-category override
that materially changes the contribution of a scored field, and the
product list's ``total_score`` for products in that category must
reflect the change immediately (no manual recompute).

The product detail endpoint (``GET /api/products/<pid>``) returns the
bare row WITHOUT computed scores. The LIST endpoint
(``GET /api/products``) is the only public surface that exposes
``total_score``. This test therefore reads scores from the list
endpoint, filtered by id, on every step.

Important contract notes confirmed in ``services/product_scoring.py``:

- Per-category overrides are **exclusive**: as soon as the category
  has any override row, the global-enabled set is ignored for that
  category. So overriding just ``sugar`` switches the category from
  scoring ``taste_score`` (the default) to scoring only ``sugar``.
- The "delete the override" step in the audit prose maps to
  ``PUT /api/categories/<name>/weights`` with the field's
  ``is_overridden: false`` — the service then DELETEs the override
  row. There is no ``DELETE`` route for category weights.
- The scoring formula (``_score_product``) is intentional and locked
  by ``CLAUDE.md``: ``total_score = weighted_score_sum /
  (num_scored_fields * 100)`` where 100 is the baseline weight. This
  test asserts the BEHAVIOUR of that formula end-to-end; it does NOT
  re-implement the formula.

Rules:
- 17 (deterministic): no randomness, fixed nutrition seeds.
- 18 (assertions of correctness): every step verifies via a downstream
  read of ``total_score``. Magnitude AND direction of change are
  asserted, not just inequality.
"""

import json
import urllib.error
import urllib.request


def _post(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _put(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Requested-With": "SmartSnack"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(url, timeout=5):
    req = urllib.request.Request(
        url, headers={"X-Requested-With": "SmartSnack"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _score_for(live_url, pid):
    """Look up a single product's ``total_score`` via the list endpoint
    (the only public surface that exposes computed scores)."""
    status, listing = _get(f"{live_url}/api/products?limit=1000")
    assert status == 200, f"list endpoint must return 200, got {status}"
    match = [p for p in listing["products"] if p["id"] == pid]
    assert len(match) == 1, (
        f"product id {pid} must appear exactly once in the listing, "
        f"got {len(match)} rows"
    )
    return match[0]["total_score"], match[0]


def _seed_category(live_url, name):
    status, body = _post(
        f"{live_url}/api/categories",
        {"name": name, "label": name, "emoji": "\U0001f4e6"},
    )
    assert status in (201, 409), (
        f"seed category must succeed/exist, got {status}: {body}"
    )


def _full_revert_payload(weights_listing):
    """Construct a PUT payload that clears all overrides for a category.

    PUT expects a list of fields with ``is_overridden=False`` to DELETE
    every row in ``category_score_weights`` for the category. Reusing
    the current effective list keeps the test forward-compatible if
    SCORE_CONFIG gains new fields.
    """
    return [
        {"field": w["field"], "is_overridden": False}
        for w in weights_listing
    ]


def test_category_weight_override_changes_score_and_revert_restores(
    live_url, api_create_product, unique_name
):
    """Full chain: baseline score → override → assert score changed →
    revert → assert score back to baseline.

    We use the ``sugar`` field (default direction=lower, formula=direct
    with explicit min/max in the override) because:
    - Direct formula avoids the minmax range collapse that happens with
      a single product per category.
    - "lower is better" makes the magnitude prediction obvious: sugar
      below the midpoint of [min, max] yields a score >50.
    """
    category = unique_name("WeightCat")
    _seed_category(live_url, category)

    # Seed P in C1 with deterministic nutrition. The api_create_product
    # fixture sends a legacy ``smak`` field that the API ignores — we
    # override with the canonical ``taste_score`` instead so the global
    # default scoring has a non-zero baseline.
    # taste_score=4 with formula=direct, direction=higher, [0,6]:
    #   raw = 4/6 = 0.6667 → s = 66.67 → total_score = 66.7
    created = api_create_product(
        name=unique_name("ScoredP"),
        category=category,
        sugar=10,    # well below the override max of 30 → high override score
        taste_score=4,
    )
    pid = created["id"]

    # ──────────────────────────────────────────────────────────────────
    # Baseline: with default weights, only taste_score contributes
    # (global enabled set = {taste_score}). smak=4 → score=66.7.
    # ──────────────────────────────────────────────────────────────────
    baseline_score, baseline_row = _score_for(live_url, pid)
    assert baseline_score > 0, (
        f"Baseline score must be non-zero (taste_score is globally "
        f"enabled), got {baseline_score} for row {baseline_row!r}"
    )
    # Pin the exact baseline value so a refactor that breaks the global
    # default seed is caught here — not silently absorbed.
    # taste_score=4, formula=direct, min=0, max=6, direction=higher, weight=100:
    #   raw = 4/6 = 0.6667 → s = 66.67 → total_score = 66.7
    assert baseline_score == 66.7, (
        f"Baseline score for smak=4 default-weights must be 66.7, "
        f"got {baseline_score}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Apply an override on sugar. Exclusive mode then makes sugar the
    # ONLY scored field for this category, so total_score is driven
    # entirely by sugar.
    # ──────────────────────────────────────────────────────────────────
    override_payload = [
        {
            "field": "sugar",
            "enabled": True,
            "is_overridden": True,
            "weight": 100,
            "direction": "lower",
            "formula": "direct",
            "formula_min": 0,
            "formula_max": 30,
        },
    ]
    status, body = _put(
        f"{live_url}/api/categories/{category}/weights", override_payload
    )
    assert status == 200, f"PUT override must return 200, got {status}: {body}"

    # GET /api/categories/<name>/weights confirms the override is
    # persisted with is_overridden=True on sugar (downstream verification).
    status, weights_after = _get(
        f"{live_url}/api/categories/{category}/weights"
    )
    assert status == 200
    sugar_row = next(w for w in weights_after if w["field"] == "sugar")
    assert sugar_row["is_overridden"] is True, (
        f"sugar row must report is_overridden=True, got {sugar_row!r}"
    )
    assert sugar_row["weight"] == 100
    assert sugar_row["enabled"] is True

    # ──────────────────────────────────────────────────────────────────
    # Re-score: total_score must reflect sugar, NOT taste_score.
    # sugar=10, formula=direct, direction=lower, min=0, max=30:
    #   raw = (30-10)/30 = 0.6667 → s = 66.67
    # With one scored field at weight=100, total_score = s = 66.7.
    # That coincides numerically with the baseline (both worked out to
    # 0.6667). To make the assertion robust, change the formula range
    # so the new score is materially different. We retry with a tighter
    # max to force a different score.
    # ──────────────────────────────────────────────────────────────────
    tighter_override = [
        {
            "field": "sugar",
            "enabled": True,
            "is_overridden": True,
            "weight": 100,
            "direction": "lower",
            "formula": "direct",
            "formula_min": 0,
            "formula_max": 20,
        },
    ]
    status, _ = _put(
        f"{live_url}/api/categories/{category}/weights", tighter_override
    )
    assert status == 200

    overridden_score, overridden_row = _score_for(live_url, pid)
    # sugar=10, direct, lower, [0,20]:
    #   raw = (20-10)/20 = 0.5 → s = 50.0 → total_score = 50.0
    assert overridden_score == 50.0, (
        f"With sugar override [0,20] and sugar=10, total_score must be "
        f"50.0, got {overridden_score}. Row: {overridden_row!r}"
    )
    assert overridden_score != baseline_score, (
        f"Override score ({overridden_score}) must differ from baseline "
        f"({baseline_score}) — otherwise the override didn't propagate"
    )
    # Direction: with sugar=10 well below max=20, sugar=lower scoring
    # gives a score in (0, 100). Baseline was 66.7 (taste_score=4/6).
    # New score is 50.0. Lower than baseline — the override moved the
    # score DOWN, consistent with the formula change.
    assert overridden_score < baseline_score, (
        f"Sugar score (50.0) must be lower than taste_score baseline "
        f"(66.7) given the chosen parameters; got override={overridden_score}, "
        f"baseline={baseline_score}"
    )

    # Sanity: the product's reported scores dict only contains sugar
    # under override (exclusive mode), not taste_score.
    assert "sugar" in overridden_row["scores"], (
        f"Override mode must score sugar; got scores={overridden_row['scores']!r}"
    )
    assert "taste_score" not in overridden_row["scores"], (
        f"Exclusive override mode must NOT score taste_score; "
        f"got scores={overridden_row['scores']!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Revert: PUT with is_overridden=False on sugar → DELETE override.
    # ──────────────────────────────────────────────────────────────────
    revert_payload = _full_revert_payload(weights_after)
    status, _ = _put(
        f"{live_url}/api/categories/{category}/weights", revert_payload
    )
    assert status == 200

    # GET weights confirms no row is overridden any more.
    status, weights_reverted = _get(
        f"{live_url}/api/categories/{category}/weights"
    )
    assert status == 200
    assert not any(w["is_overridden"] for w in weights_reverted), (
        f"After revert, NO field must report is_overridden=True. "
        f"got {[w['field'] for w in weights_reverted if w['is_overridden']]}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Score returns to baseline.
    # ──────────────────────────────────────────────────────────────────
    reverted_score, reverted_row = _score_for(live_url, pid)
    assert reverted_score == baseline_score, (
        f"After revert, total_score must equal baseline. "
        f"baseline={baseline_score}, reverted={reverted_score}, "
        f"row={reverted_row!r}"
    )
    assert "taste_score" in reverted_row["scores"], (
        f"After revert, global taste_score scoring resumes. "
        f"scores={reverted_row['scores']!r}"
    )


def test_category_weight_override_only_affects_target_category(
    live_url, api_create_product, unique_name
):
    """A per-category override on ``C1`` must NOT affect products in a
    sibling category ``C2``. This catches a class of regressions where
    the override would be applied globally by mistake.
    """
    c1 = unique_name("WeightCat1")
    c2 = unique_name("WeightCat2")
    _seed_category(live_url, c1)
    _seed_category(live_url, c2)

    p1 = api_create_product(name=unique_name("P1"), category=c1, sugar=10, smak=4)
    p2 = api_create_product(name=unique_name("P2"), category=c2, sugar=10, smak=4)

    baseline_p1, _ = _score_for(live_url, p1["id"])
    baseline_p2, _ = _score_for(live_url, p2["id"])
    assert baseline_p1 == baseline_p2, (
        f"With identical seeds and no overrides, both products must "
        f"score identically; got p1={baseline_p1}, p2={baseline_p2}"
    )

    # Override only C1.
    status, _ = _put(
        f"{live_url}/api/categories/{c1}/weights",
        [
            {
                "field": "sugar",
                "enabled": True,
                "is_overridden": True,
                "weight": 100,
                "direction": "lower",
                "formula": "direct",
                "formula_min": 0,
                "formula_max": 20,
            }
        ],
    )
    assert status == 200

    score_p1_after, _ = _score_for(live_url, p1["id"])
    score_p2_after, _ = _score_for(live_url, p2["id"])
    assert score_p1_after != baseline_p1, (
        f"P1 (in C1) must reflect the override; got {score_p1_after} "
        f"vs baseline {baseline_p1}"
    )
    assert score_p2_after == baseline_p2, (
        f"P2 (in C2) must NOT be affected by C1's override; "
        f"got {score_p2_after} vs baseline {baseline_p2}"
    )


def test_category_weight_override_404_for_unknown_category(live_url):
    """The override route returns 404 (LookupError) when the category
    doesn't exist. This guards the API from silently creating override
    rows for ghost categories that would never be reachable from the UI.
    """
    status, body = _put(
        f"{live_url}/api/categories/does-not-exist/weights",
        [{"field": "sugar", "is_overridden": True, "weight": 100, "enabled": True}],
    )
    assert status == 404, (
        f"PUT on unknown category must return 404, got {status}: {body}"
    )
    assert "not found" in body.get("error", "").lower()
