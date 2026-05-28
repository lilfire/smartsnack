"""End-to-end user-journey: OCR ingredients → LLM cleanup → save.

This covers gap **D** from the LSO-1354 audit (LSO-1352 Phase 2D-3): the
user opens a product, runs OCR on a label photo, the system cleans up
the raw OCR text with the LLM, the user edits as needed, and the
cleaned-up ingredient string is persisted on the product.

The chain asserted here:

1. ``POST /api/ocr/ingredients`` returns parsed text from the OCR
   provider. Both ``ocr_service.dispatch_ocr`` (the OCR call itself)
   and ``llm_cleanup_service.cleanup_ingredients`` (the post-LLM
   cleanup step) are mocked at the module boundary — no real provider
   is ever contacted.
2. ``PUT /api/products/<pid>`` persists the cleaned-up ingredient
   string on an existing product.
3. ``GET /api/products/<pid>`` returns the saved ingredients verbatim.

Rules:
- 17 (deterministic): mocks are synchronous; no sleeps.
- 18 (assertion of correctness): every step verifies persisted/returned
  state, not just response codes. The cleaned text is asserted at the
  PUT response shape AND on the downstream GET.
- 8 (mock shape): both mocks return the exact documented dict shapes
  (``{"text": ..., "provider": ..., "fallback": ...}`` for OCR;
  ``{"text": ..., "llm_cleanup_skipped": ...}`` for cleanup).
"""

import json
import urllib.error
import urllib.request
from unittest.mock import patch


def _post(url, payload, timeout=5):
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


def _put(url, payload, timeout=5):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "SmartSnack",
        },
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


# Minimal 1×1 PNG payload (8-byte header + IHDR + IDAT + IEND), base64-
# encoded. This is exactly the kind of payload the frontend posts when
# uploading a captured photo: a ``data:image/png;base64,...`` URI. The
# OCR service is mocked so the bytes never actually need to decode to a
# real image — but using a real PNG header keeps the test honest if the
# blueprint ever starts validating magic bytes before dispatching.
_MIN_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

_RAW_OCR_TEXT = (
    "ingrediensr:  pasturisert melk, mlkesyre kultur,, fldekrem  (kan ihholde spr av nott)"
)
_CLEANED_OCR_TEXT = (
    "Ingredienser: Pasteurisert melk, melkesyrekultur, fløtekrem "
    "(kan inneholde spor av nøtter)"
)


def test_ocr_then_save_persists_cleaned_ingredients(live_url, api_create_product):
    """Full chain: OCR → cleanup → save → re-read.

    The OCR service returns intentionally garbled text. The LLM cleanup
    step is mocked to return a clean string. The clean string is then
    persisted via PUT and verified via GET — proving the cleaned text
    survives the round-trip, not the raw OCR text.
    """
    # Seed an existing product so we have an id to PUT to. Start with
    # an empty ingredients field so the PUT proves the update happened.
    created = api_create_product(name="OCR-D-target", ingredients="")
    pid = created["id"]

    # Pre-state sanity check: ingredients are empty before the journey.
    status, before = _get(f"{live_url}/api/products/{pid}")
    assert status == 200
    assert (before.get("ingredients") or "") == "", (
        f"Pre-state must have empty ingredients, got {before.get('ingredients')!r}"
    )

    # ──────────────────────────────────────────────────────────────────
    # Step 1: OCR returns raw text, LLM cleanup polishes it.
    # ``dispatch_ocr`` handles the JSON body path (data-URI input).
    # ──────────────────────────────────────────────────────────────────
    ocr_return = {
        "text": _RAW_OCR_TEXT,
        "provider": "groq",
        "fallback": False,
    }
    cleanup_return = {
        "text": _CLEANED_OCR_TEXT,
        "llm_cleanup_skipped": False,
    }

    with patch(
        "services.ocr_service.dispatch_ocr",
        return_value=ocr_return,
    ) as mock_ocr, patch(
        "services.llm_cleanup_service.cleanup_ingredients",
        return_value=cleanup_return,
    ) as mock_cleanup:
        status, body = _post(
            f"{live_url}/api/ocr/ingredients",
            {"image": _MIN_PNG_DATA_URI, "lang": "no"},
        )

    assert status == 200, f"OCR endpoint must return 200, got {status}: {body}"
    assert body["text"] == _CLEANED_OCR_TEXT, (
        f"Response must contain the LLM-cleaned text, not the raw OCR text. "
        f"Got: {body.get('text')!r}"
    )
    assert body["llm_cleanup_skipped"] is False, (
        f"Cleanup must NOT be skipped when mocked to succeed; got "
        f"llm_cleanup_skipped={body.get('llm_cleanup_skipped')!r}"
    )
    assert body["provider"] == "groq"
    assert body["fallback"] is False

    # Mock-shape checks (Rule 8).
    assert mock_ocr.call_count == 1, (
        f"dispatch_ocr must be called exactly once, got {mock_ocr.call_count}"
    )
    # The JSON path forwards the raw data URI string to dispatch_ocr.
    assert mock_ocr.call_args[0][0] == _MIN_PNG_DATA_URI
    assert mock_cleanup.call_count == 1, (
        f"cleanup_ingredients must run after dispatch_ocr returned text, "
        f"got {mock_cleanup.call_count} calls"
    )
    # cleanup_ingredients(raw_text, lang)
    assert mock_cleanup.call_args[0][0] == _RAW_OCR_TEXT
    assert mock_cleanup.call_args[0][1] == "no"

    # ──────────────────────────────────────────────────────────────────
    # Step 2: persist the cleaned text via PUT.
    # ──────────────────────────────────────────────────────────────────
    status, put_body = _put(
        f"{live_url}/api/products/{pid}",
        {"ingredients": body["text"]},
    )
    assert status == 200, f"PUT must return 200, got {status}: {put_body}"
    assert put_body.get("ok") is True

    # ──────────────────────────────────────────────────────────────────
    # Step 3: re-read the product — the saved ingredients must match
    # the cleaned text verbatim (not the raw OCR text).
    # ──────────────────────────────────────────────────────────────────
    status, after = _get(f"{live_url}/api/products/{pid}")
    assert status == 200, f"GET must return 200, got {status}: {after}"
    assert after["ingredients"] == _CLEANED_OCR_TEXT, (
        f"Persisted ingredients must be the cleaned text. "
        f"Got: {after['ingredients']!r}"
    )
    # Negative assertion: the raw OCR garble must NOT survive — proves
    # the update went through the cleaned value, not the raw one.
    assert after["ingredients"] != _RAW_OCR_TEXT


def test_ocr_skipped_cleanup_still_persists_through_put(
    live_url, api_create_product
):
    """When the LLM cleanup is skipped (e.g. ANTHROPIC_API_KEY missing in
    prod, or a soft failure), the route returns the raw OCR text with
    ``llm_cleanup_skipped: True``. The user can still edit and save
    manually — this test asserts that the PUT/GET chain works in that
    degraded mode.
    """
    created = api_create_product(name="OCR-D-skip", ingredients="")
    pid = created["id"]
    user_edited_text = "Sukker, hvete, salt"  # User typed this after OCR

    with patch(
        "services.ocr_service.dispatch_ocr",
        return_value={
            "text": _RAW_OCR_TEXT,
            "provider": "tesseract",
            "fallback": True,
        },
    ), patch(
        "services.llm_cleanup_service.cleanup_ingredients",
        return_value={"text": _RAW_OCR_TEXT, "llm_cleanup_skipped": True},
    ):
        status, body = _post(
            f"{live_url}/api/ocr/ingredients",
            {"image": _MIN_PNG_DATA_URI, "lang": "no"},
        )

    assert status == 200
    assert body["llm_cleanup_skipped"] is True, (
        "Cleanup skipped mode must propagate to the response"
    )
    # User edits the text in-browser and submits something different.
    status, _ = _put(
        f"{live_url}/api/products/{pid}",
        {"ingredients": user_edited_text},
    )
    assert status == 200

    status, after = _get(f"{live_url}/api/products/{pid}")
    assert status == 200
    assert after["ingredients"] == user_edited_text, (
        f"Whatever the user typed should be saved verbatim; got "
        f"{after['ingredients']!r}"
    )


def test_ocr_no_text_response_does_not_call_cleanup(live_url, api_create_product):
    """If OCR returns empty ``text`` (e.g. blurry image), the blueprint
    short-circuits before calling cleanup. The route still returns 200
    with ``text: ""`` and ``error_type: "no_text"``. We assert that the
    cleanup mock was NOT invoked — Rule 18 (assert what the code does,
    not just that it didn't crash).
    """
    api_create_product(name="OCR-D-notext")
    with patch(
        "services.ocr_service.dispatch_ocr",
        return_value={"text": "", "provider": "groq", "fallback": False},
    ), patch(
        "services.llm_cleanup_service.cleanup_ingredients",
    ) as mock_cleanup:
        status, body = _post(
            f"{live_url}/api/ocr/ingredients",
            {"image": _MIN_PNG_DATA_URI, "lang": "no"},
        )

    assert status == 200
    assert body["text"] == ""
    assert body["error_type"] == "no_text"
    assert body["llm_cleanup_skipped"] is True, (
        "When OCR returns no text, the blueprint must skip cleanup AND "
        "report llm_cleanup_skipped=True so the frontend doesn't treat "
        "the empty string as cleaned text"
    )
    assert mock_cleanup.call_count == 0, (
        f"cleanup_ingredients must NOT be called when OCR returned no "
        f"text, but it was called {mock_cleanup.call_count} times"
    )
