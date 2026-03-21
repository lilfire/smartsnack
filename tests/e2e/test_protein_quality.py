"""E2E tests for protein quality management — API and UI."""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Settings navigation helpers (mirrors test_settings.py)
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    """Navigate to settings and wait for content to load."""
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    """Open a settings section by its data-i18n key."""
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_get(live_url, path):
    """Send a GET request and return the parsed JSON body."""
    with urllib.request.urlopen(f"{live_url}{path}", timeout=5) as resp:
        return json.loads(resp.read())


def _api_post(live_url, path, payload):
    """Send a POST request with JSON payload and return (status_code, body)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{live_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.request.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _api_delete(live_url, path):
    """Send a DELETE request and return (status_code, body)."""
    req = urllib.request.Request(
        f"{live_url}{path}",
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.request.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def test_pq_api_list(live_url):
    """GET /api/protein-quality returns a non-empty list with seed data."""
    entries = _api_get(live_url, "/api/protein-quality")

    assert isinstance(entries, list), "Response should be a list"
    assert len(entries) > 0, "Seed data should produce at least one entry"

    first = entries[0]
    assert "id" in first
    assert "label" in first
    assert "keywords" in first
    assert "pdcaas" in first
    assert "diaas" in first

    names = [e.get("name") for e in entries]
    assert "whey" in names, "Seed entry 'whey' should be present"
    assert "egg" in names, "Seed entry 'egg' should be present"


def test_pq_api_add_and_delete(live_url):
    """POST a new PQ entry, verify it appears in the list, then DELETE it."""
    payload = {
        "label": "E2E Test Source",
        "keywords": ["e2etestsource", "e2e test"],
        "pdcaas": 0.72,
        "diaas": 0.68,
    }

    # Add the entry
    status, body = _api_post(live_url, "/api/protein-quality", payload)
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert body.get("ok") is True
    new_id = body.get("id")
    assert isinstance(new_id, int) and new_id > 0, "Response must include a valid id"

    # Verify the entry appears in the list
    entries = _api_get(live_url, "/api/protein-quality")
    ids = [e["id"] for e in entries]
    assert new_id in ids, "Newly created entry should appear in the list"

    # Delete the entry
    del_status, del_body = _api_delete(live_url, f"/api/protein-quality/{new_id}")
    assert del_status == 200, f"Expected 200, got {del_status}: {del_body}"
    assert del_body.get("ok") is True

    # Verify the entry is gone
    entries_after = _api_get(live_url, "/api/protein-quality")
    ids_after = [e["id"] for e in entries_after]
    assert new_id not in ids_after, "Deleted entry must not appear in subsequent list"


def test_pq_estimate_api(live_url):
    """POST /api/estimate-protein-quality returns est_pdcaas, est_diaas, sources."""
    status, body = _api_post(
        live_url,
        "/api/estimate-protein-quality",
        {"ingredients": "milk, oats"},
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "est_pdcaas" in body, "Response must include 'est_pdcaas'"
    assert "est_diaas" in body, "Response must include 'est_diaas'"
    assert "sources" in body, "Response must include 'sources'"
    assert isinstance(body["sources"], list), "'sources' must be a list"


# ---------------------------------------------------------------------------
# UI tests
# ---------------------------------------------------------------------------


def test_pq_add_via_ui(page, live_url):
    """Open the PQ section in settings, fill the add form, and verify a toast."""
    _go_to_settings(page)
    _open_section(page, "settings_pq_title")

    # Wait for the PQ list container to be visible
    expect(page.locator("#pq-list")).to_be_visible(timeout=5000)

    # Fill in the add form fields
    page.locator("#pq-add-label").fill("E2E UI Source")
    page.locator("#pq-add-kw").fill("e2euisource, e2e ui")
    page.locator("#pq-add-pdcaas").fill("0.65")
    page.locator("#pq-add-diaas").fill("0.60")

    # Click the add button
    page.locator("[data-i18n='btn_add_protein_source']").first.click()

    # A toast notification should appear confirming success
    toast = page.locator(".toast")
    expect(toast.first).to_be_visible(timeout=5000)


def test_pq_list_shown_in_ui(page, live_url):
    """Opening the PQ section in settings shows .pq-card elements."""
    _go_to_settings(page)
    _open_section(page, "settings_pq_title")

    # The list container must be visible
    expect(page.locator("#pq-list")).to_be_visible(timeout=5000)

    # At least one PQ card should be rendered from seed data
    page.wait_for_selector(".pq-card", state="visible", timeout=5000)
    cards = page.locator(".pq-card")
    assert cards.count() > 0, "There should be at least one .pq-card from seed data"


def test_estimate_all_button_visible(page, live_url):
    """Opening the PQ section in settings shows the estimate-all button."""
    _go_to_settings(page)
    _open_section(page, "settings_pq_title")

    expect(page.locator("#pq-list")).to_be_visible(timeout=5000)

    btn = page.locator("#btn-estimate-all-pq")
    expect(btn).to_be_visible(timeout=5000)
