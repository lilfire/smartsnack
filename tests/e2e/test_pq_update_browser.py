"""Browser-based e2e tests for Protein Quality settings UI.

Covers PQ list display, adding new protein sources,
and the bulk PQ estimation button.
"""

from playwright.sync_api import expect


def _go_to_settings(page):
    page.locator("button[data-view='settings']").click()
    expect(page.locator("#view-settings")).to_be_visible()
    page.wait_for_selector("#settings-content", state="visible", timeout=10000)


def _open_section(page, key):
    toggle = page.locator(f".settings-toggle:has(span[data-i18n='{key}'])").first
    toggle.click()
    page.wait_for_timeout(300)


class TestPqListBrowser:
    """Test protein quality list display in settings."""

    def test_pq_section_shows_list(self, page):
        """The PQ section should show the protein source list."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        expect(page.locator("#pq-list")).to_be_visible()

    def test_pq_add_form_fields(self, page):
        """The PQ add form should have label, keywords, and score fields."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        expect(page.locator("#pq-add-label")).to_be_visible()
        expect(page.locator("#pq-add-kw")).to_be_visible()
        expect(page.locator("#pq-add-pdcaas")).to_be_visible()
        expect(page.locator("#pq-add-diaas")).to_be_visible()


class TestPqAddBrowser:
    """Test adding a protein quality source via the UI."""

    def test_add_protein_source(self, page):
        """Adding a PQ source should update the list and show a toast."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")

        page.locator("#pq-add-label").fill("E2E Whey")
        page.locator("#pq-add-kw").fill("whey, whey protein")
        page.locator("#pq-add-pdcaas").fill("1.0")
        page.locator("#pq-add-diaas").fill("1.09")

        page.locator("button[data-i18n='btn_add_protein_source']").click()

        toast = page.locator(".toast")
        expect(toast.first).to_be_visible(timeout=5000)

    def test_added_source_appears_in_list(self, page):
        """A newly added PQ source should appear in the PQ list."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")

        # Capture card count before adding.
        initial_count = page.locator("#pq-list .pq-card").count()

        page.locator("#pq-add-label").fill("E2E Soy")
        page.locator("#pq-add-kw").fill("soy, soybean")
        page.locator("#pq-add-pdcaas").fill("0.91")
        page.locator("#pq-add-diaas").fill("0.90")

        page.locator("button[data-i18n='btn_add_protein_source']").click()
        page.wait_for_timeout(500)

        # A new card must be added (PQ labels live in input values, not text nodes).
        expect(page.locator("#pq-list .pq-card")).to_have_count(initial_count + 1, timeout=5000)


class TestPqScoreFields:
    """Test PQ score input field constraints."""

    def test_pdcaas_field_range(self, page):
        """PDCAAS field should have min=0, max=1."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        field = page.locator("#pq-add-pdcaas")
        assert field.get_attribute("min") == "0"
        assert field.get_attribute("max") == "1"

    def test_diaas_field_range(self, page):
        """DIAAS field should have min=0, max=1.2."""
        _go_to_settings(page)
        _open_section(page, "settings_pq_title")
        field = page.locator("#pq-add-diaas")
        assert field.get_attribute("min") == "0"
        assert field.get_attribute("max") == "1.2"
