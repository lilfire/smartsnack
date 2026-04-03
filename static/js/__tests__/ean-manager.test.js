import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: { total: 5, types: 2, categories: [] },
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({ total: 5, types: 2 }),
    NUTRI_IDS: ['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'],
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
    upgradeSelect: vi.fn(),
    announceStatus: vi.fn(),
    trapFocus: vi.fn(() => vi.fn()),
    esc: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    buildFilters: vi.fn(),
    rerender: vi.fn(),
    buildTypeSelect: vi.fn(),
  };
});

vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
  getFlagConfig: vi.fn(() => ({})),
}));

vi.mock('../settings-weights.js', () => ({
  loadSettings: vi.fn(),
}));

vi.mock('../openfoodfacts.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
  validateOffBtn: vi.fn(),
  showDuplicateMergeModal: vi.fn(),
  showMergeConflictModal: vi.fn(),
  showEditDuplicateModal: vi.fn(),
  showOffAddReview: vi.fn(),
}));

import { loadEanManager, addEan, deleteEan, setEanPrimary } from '../products.js';
import { api, showToast } from '../state.js';
import { t } from '../i18n.js';
import { isValidEan } from '../openfoodfacts.js';

const PRODUCT_ID = 42;
const MOCK_EANS_TWO = [
  { id: 1, ean: '7038010069307', is_primary: true },
  { id: 2, ean: '5000000000001', is_primary: false },
];
const MOCK_EANS_ONE = [
  { id: 1, ean: '7038010069307', is_primary: true },
];
const MOCK_EANS_THREE = [
  { id: 1, ean: '7038010069307', is_primary: true },
  { id: 2, ean: '5000000000001', is_primary: false },
  { id: 3, ean: '8901234567890', is_primary: false },
];

function setupDom() {
  document.body.innerHTML = '';
  const container = document.createElement('div');
  container.id = 'ean-manager-' + PRODUCT_ID;
  document.body.appendChild(container);
  const hiddenEan = document.createElement('input');
  hiddenEan.id = 'ed-ean';
  document.body.appendChild(hiddenEan);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  setupDom();
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  document.body.innerHTML = '';
});

// ── EAN Manager Render ──────────────────────────────

describe('EAN manager render', () => {
  it('renders both EANs when product has two', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    expect(items.length).toBe(2);

    const values = document.querySelectorAll('.ean-value');
    expect(values[0].textContent).toBe('7038010069307');
    expect(values[1].textContent).toBe('5000000000001');
  });

  it('shows primary badge on primary EAN only', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const badges = document.querySelectorAll('.ean-badge-primary');
    expect(badges.length).toBe(1);
    expect(badges[0].textContent).toBe('label_ean_primary');

    // Secondary EAN has no badge but has "set primary" button
    const setPrimaryBtns = document.querySelectorAll('[data-ean-action="set-primary"]');
    expect(setPrimaryBtns.length).toBe(1);
    expect(setPrimaryBtns[0].dataset.eanId).toBe('2');
  });

  it('hides delete button when only one EAN is present', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_ONE);
    await loadEanManager(PRODUCT_ID);

    const deleteBtns = document.querySelectorAll('[data-ean-action="delete-ean"]');
    expect(deleteBtns.length).toBe(0);
  });

  it('shows delete buttons when two or more EANs are present', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const deleteBtns = document.querySelectorAll('[data-ean-action="delete-ean"]');
    expect(deleteBtns.length).toBe(2);
  });

  it('syncs hidden ed-ean field with primary EAN value', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const hiddenEan = document.getElementById('ed-ean');
    expect(hiddenEan.value).toBe('7038010069307');
  });
});

// ── Add EAN ─────────────────────────────────────────

describe('Add EAN', () => {
  async function setupRenderedManager() {
    api.mockResolvedValueOnce(MOCK_EANS_ONE);
    await loadEanManager(PRODUCT_ID);
    api.mockClear();
  }

  it('calls POST /api/products/<pid>/eans with valid EAN', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '5000000000001';

    // Mock the POST success and the subsequent loadEanManager GET
    api.mockResolvedValueOnce({ id: 2, ean: '5000000000001', is_primary: false });
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    await addEan(PRODUCT_ID);

    expect(api).toHaveBeenCalledWith(
      '/api/products/' + PRODUCT_ID + '/eans',
      { method: 'POST', body: JSON.stringify({ ean: '5000000000001' }) }
    );
  });

  it('shows validation error for invalid EAN without making network request', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = 'abc123';

    await addEan(PRODUCT_ID);

    expect(api).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith('toast_invalid_ean', 'error');
  });

  it('shows validation error for EAN with wrong length', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '123';

    await addEan(PRODUCT_ID);

    expect(api).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith('toast_invalid_ean', 'error');
  });

  it('re-renders list and shows toast on API success (201)', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '5000000000001';

    api.mockResolvedValueOnce({ id: 2, ean: '5000000000001', is_primary: false });
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    await addEan(PRODUCT_ID);

    // Input should be cleared after success
    expect(input.value).toBe('');
    // Toast shown
    expect(showToast).toHaveBeenCalledWith('toast_ean_added', 'success');
    // List re-rendered with two items
    const items = document.querySelectorAll('.ean-item');
    expect(items.length).toBe(2);
  });

  it('shows error_ean_already_exists message on 409 conflict', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '7038010069307';

    const error = new Error('Conflict');
    error.data = { error: 'error_ean_already_exists' };
    api.mockRejectedValueOnce(error);

    await addEan(PRODUCT_ID);

    const errorEl = document.getElementById('ean-error-' + PRODUCT_ID);
    expect(errorEl.textContent).toBe('error_ean_already_exists');
    expect(errorEl.style.display).toBe('');
  });

  it('does nothing when input is empty', async () => {
    await setupRenderedManager();

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '';

    await addEan(PRODUCT_ID);

    expect(api).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
  });
});

// ── Delete EAN ──────────────────────────────────────

describe('Delete EAN', () => {
  async function setupRenderedManager() {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);
    api.mockClear();
    showToast.mockClear();
  }

  it('calls DELETE /api/products/<pid>/eans/<ean_id> for non-primary EAN', async () => {
    await setupRenderedManager();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(MOCK_EANS_ONE);

    await deleteEan(PRODUCT_ID, 2);

    expect(api).toHaveBeenCalledWith(
      '/api/products/' + PRODUCT_ID + '/eans/2',
      { method: 'DELETE' }
    );
  });

  it('removes EAN from rendered list on success', async () => {
    await setupRenderedManager();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(MOCK_EANS_ONE);

    await deleteEan(PRODUCT_ID, 2);

    const items = document.querySelectorAll('.ean-item');
    expect(items.length).toBe(1);
    expect(document.querySelector('.ean-value').textContent).toBe('7038010069307');
  });

  it('shows toast_ean_removed on success', async () => {
    await setupRenderedManager();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(MOCK_EANS_ONE);

    await deleteEan(PRODUCT_ID, 2);

    expect(showToast).toHaveBeenCalledWith('toast_ean_removed', 'success');
  });

  it('shows error_cannot_remove_only_ean on 400 error', async () => {
    await setupRenderedManager();

    const error = new Error('Bad Request');
    error.data = { error: 'error_cannot_remove_only_ean' };
    api.mockRejectedValueOnce(error);

    await deleteEan(PRODUCT_ID, 1);

    expect(showToast).toHaveBeenCalledWith('error_cannot_remove_only_ean', 'error');
  });
});

// ── Set Primary ─────────────────────────────────────

describe('Set primary', () => {
  async function setupRenderedManager() {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);
    api.mockClear();
    showToast.mockClear();
  }

  it('calls PATCH /api/products/<pid>/eans/<ean_id>/set-primary', async () => {
    await setupRenderedManager();

    api.mockResolvedValueOnce({});
    const updatedEans = [
      { id: 1, ean: '7038010069307', is_primary: false },
      { id: 2, ean: '5000000000001', is_primary: true },
    ];
    api.mockResolvedValueOnce(updatedEans);

    await setEanPrimary(PRODUCT_ID, 2);

    expect(api).toHaveBeenCalledWith(
      '/api/products/' + PRODUCT_ID + '/eans/2/set-primary',
      { method: 'PATCH' }
    );
  });

  it('updates primary badge after success', async () => {
    await setupRenderedManager();

    const updatedEans = [
      { id: 1, ean: '7038010069307', is_primary: false },
      { id: 2, ean: '5000000000001', is_primary: true },
    ];
    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(updatedEans);

    await setEanPrimary(PRODUCT_ID, 2);

    // After re-render, EAN 2 should have the primary badge
    const badges = document.querySelectorAll('.ean-badge-primary');
    expect(badges.length).toBe(1);
    expect(badges[0].closest('.ean-item').querySelector('.ean-value').textContent).toBe('5000000000001');

    // EAN 1 should now have a "set primary" button
    const setPrimaryBtns = document.querySelectorAll('[data-ean-action="set-primary"]');
    expect(setPrimaryBtns.length).toBe(1);
    expect(setPrimaryBtns[0].dataset.eanId).toBe('1');
  });

  it('shows toast_ean_set_primary on success', async () => {
    await setupRenderedManager();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    await setEanPrimary(PRODUCT_ID, 2);

    expect(showToast).toHaveBeenCalledWith('toast_ean_set_primary', 'success');
  });

  it('syncs hidden ed-ean to new primary after set-primary', async () => {
    await setupRenderedManager();

    const updatedEans = [
      { id: 1, ean: '7038010069307', is_primary: false },
      { id: 2, ean: '5000000000001', is_primary: true },
    ];
    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(updatedEans);

    await setEanPrimary(PRODUCT_ID, 2);

    expect(document.getElementById('ed-ean').value).toBe('5000000000001');
  });
});
