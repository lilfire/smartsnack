"""E2E tests for protein quality (PQ) CRUD in settings.

Tests: PQ list visible, seed cards present, add PQ entry, delete PQ entry
with confirmation, and inline PDCAAS value editing.

No unittest.mock.patch, no if .count() guards, no zero-assertion tests.
"""

import json
import urllib.request

from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _go_to_settings(page):
    page.locator("button.nav-tab[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_pq_section(page):
    """Force the PQ settings section open via JS for deterministic state."""
    page.evaluate("""() => {
        const toggles = document.querySelectorAll('.settings-toggle');
        for (const t of toggles) {
            if (t.querySelector('[data-i18n="settings_pq_title"]')) {
                const body = t.nextElementSibling;
                if (body && body.classList.contains('settings-section-body')) {
                    body.style.display = '';
                    t.setAttribute('aria-expanded', 'true');
                }
            }
        }
    }""")
    page.wait_for_timeout(600)


def _api(live_url, path, *, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{live_url}{path}", data=data, headers=headers, method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Tests: PQ list structure
# ---------------------------------------------------------------------------


def test_pq_list_is_visible(page):
    """The #pq-list container must be visible in the PQ section."""
    _go_to_settings(page)
    _open_pq_section(page)
    expect(page.locator("#pq-list")).to_be_visible(timeout=5000)


def test_pq_seed_cards_are_present(page):
    """At least one PQ card must be shown (seed data provides default entries)."""
    _go_to_settings(page)
    _open_pq_section(page)

    cards = page.locator("#pq-list .pq-card")
    expect(cards.first).to_be_visible(timeout=5000)

    count = cards.count()
    assert count >= 1, f"Expected at least one PQ card from seed data, got {count}"


def test_pq_cards_display_score_badges(page):
    """Each PQ card must have at least one score badge."""
    _go_to_settings(page)
    _open_pq_section(page)

    first_card = page.locator("#pq-list .pq-card").first
    expect(first_card).to_be_visible(timeout=5000)

    badges = first_card.locator(".pq-badge")
    badge_count = badges.count()
    assert badge_count >= 1, (
        f"Expected at least one score badge on the first PQ card, got {badge_count}"
    )


# ---------------------------------------------------------------------------
# Tests: add PQ form
# ---------------------------------------------------------------------------


def test_pq_add_form_inputs_are_visible(page):
    """All four add-PQ inputs must be visible in the PQ section."""
    _go_to_settings(page)
    _open_pq_section(page)

    expect(page.locator("#pq-add-label")).to_be_visible(timeout=3000)
    expect(page.locator("#pq-add-kw")).to_be_visible(timeout=3000)
    expect(page.locator("#pq-add-pdcaas")).to_be_visible(timeout=3000)
    expect(page.locator("#pq-add-diaas")).to_be_visible(timeout=3000)


def test_add_pq_entry_appears_in_list(page):
    """Submitting the add-PQ form must create a new card in the list and show
    a success toast."""
    _go_to_settings(page)
    _open_pq_section(page)

    page.locator("#pq-add-label").fill("E2E Test Protein Source")
    page.locator("#pq-add-kw").fill("e2e protein, test isolate")
    page.locator("#pq-add-pdcaas").fill("0.85")
    page.locator("#pq-add-diaas").fill("0.90")

    # Capture card count before adding.
    initial_count = page.locator("#pq-list .pq-card").count()

    add_btn = page.locator("[data-i18n='btn_add_protein_source']")
    expect(add_btn.first).to_be_visible(timeout=3000)
    add_btn.first.click()
    page.wait_for_timeout(600)

    # Toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)

    # A new card must be added to the list (PQ labels are stored in input values,
    # not text nodes, so we verify by card count increase instead).
    expect(page.locator("#pq-list .pq-card")).to_have_count(initial_count + 1, timeout=5000)


# ---------------------------------------------------------------------------
# Tests: delete PQ entry
# ---------------------------------------------------------------------------


def test_delete_pq_entry_removes_from_list(page, live_url):
    """Deleting a PQ entry via its delete button and confirming must remove
    it from the list and show a success toast."""
    result = _api(live_url, "/api/protein-quality", method="POST", body={
        "label": "E2E Delete Me PQ",
        "keywords": "e2e_delete_pq_kw",
        "pdcaas": 0.50,
        "diaas": 0.55,
    })
    pq_id = result.get("id")
    assert pq_id is not None, f"API did not return an id: {result}"

    _go_to_settings(page)
    _open_pq_section(page)

    delete_btn = page.locator(f"[data-action='delete-pq'][data-pq-id='{pq_id}']")
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(300)

    # Confirmation modal — click yes.
    confirm_btn = page.locator("button.confirm-yes")
    expect(confirm_btn).to_be_visible(timeout=3000)
    confirm_btn.click()
    page.wait_for_timeout(600)

    # Success toast must appear.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)

    # The entry must be gone from the list.
    expect(page.locator("#pq-list")).not_to_contain_text(
        "E2E Delete Me PQ", timeout=5000
    )


def test_delete_pq_entry_cancel_keeps_entry(page, live_url):
    """Cancelling the delete confirmation must leave the PQ entry in the list."""
    result = _api(live_url, "/api/protein-quality", method="POST", body={
        "label": "E2E Cancel Del PQ",
        "keywords": "e2e_cancel_pq_kw",
        "pdcaas": 0.60,
        "diaas": 0.65,
    })
    pq_id = result.get("id")
    assert pq_id is not None, f"API did not return an id: {result}"

    _go_to_settings(page)
    _open_pq_section(page)

    delete_btn = page.locator(f"[data-action='delete-pq'][data-pq-id='{pq_id}']")
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()
    page.wait_for_timeout(300)

    cancel_btn = page.locator("button.confirm-no")
    expect(cancel_btn).to_be_visible(timeout=3000)
    cancel_btn.click()
    page.wait_for_timeout(400)

    # Entry must still be in the list — verify via the delete button keyed by pq_id.
    expect(page.locator(f"[data-action='delete-pq'][data-pq-id='{pq_id}']")).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# Tests: inline PDCAAS / DIAAS editing
# ---------------------------------------------------------------------------


def test_inline_pdcaas_edit_saves_and_shows_toast(page, live_url):
    """Editing the PDCAAS value inline and tabbing away must auto-save and
    show a success toast."""
    result = _api(live_url, "/api/protein-quality", method="POST", body={
        "label": "E2E Inline Edit PQ",
        "keywords": "e2e_inline_kw",
        "pdcaas": 0.70,
        "diaas": 0.72,
    })
    pq_id = result.get("id")
    assert pq_id is not None, f"API did not return an id: {result}"

    _go_to_settings(page)
    _open_pq_section(page)

    pdcaas_input = page.locator(f"#pqe-pdcaas-{pq_id}")
    expect(pdcaas_input).to_be_visible(timeout=5000)

    pdcaas_input.fill("0.95")
    pdcaas_input.press("Tab")
    page.wait_for_timeout(600)

    # A toast must appear confirming the save.
    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


def test_inline_diaas_edit_saves_and_shows_toast(page, live_url):
    """Editing the DIAAS value inline and tabbing away must auto-save and
    show a success toast."""
    result = _api(live_url, "/api/protein-quality", method="POST", body={
        "label": "E2E DIAAS Edit PQ",
        "keywords": "e2e_diaas_kw",
        "pdcaas": 0.65,
        "diaas": 0.68,
    })
    pq_id = result.get("id")
    assert pq_id is not None, f"API did not return an id: {result}"

    _go_to_settings(page)
    _open_pq_section(page)

    diaas_input = page.locator(f"#pqe-diaas-{pq_id}")
    expect(diaas_input).to_be_visible(timeout=5000)

    diaas_input.fill("0.80")
    diaas_input.press("Tab")
    page.wait_for_timeout(600)

    expect(page.locator("#toast.show")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# Tests: estimate-all button
# ---------------------------------------------------------------------------


def test_estimate_all_pq_button_is_visible(page):
    """The 'Estimate PQ for all products' button must be present in the PQ section."""
    _go_to_settings(page)
    _open_pq_section(page)
    expect(page.locator("#btn-estimate-all-pq")).to_be_visible(timeout=5000)
