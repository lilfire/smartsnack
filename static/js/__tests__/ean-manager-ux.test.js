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

vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
  validateOffBtn: vi.fn(),
}));
vi.mock('../off-conflicts.js', () => ({
  showMergeConflictModal: vi.fn(),
  showEditDuplicateModal: vi.fn(),
}));
vi.mock('../off-duplicates.js', () => ({
  showDuplicateMergeModal: vi.fn(),
}));
vi.mock('../off-review.js', () => ({
  showOffAddReview: vi.fn(),
  closeOffAddReview: vi.fn(),
  submitToOff: vi.fn(),
}));
vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn().mockResolvedValue({}),
}));

import { loadEanManager } from '../ean-manager.js';
import { api } from '../state.js';

const PRODUCT_ID = 42;
const MOCK_EANS_TWO = [
  { id: 1, ean: '7038010069307', is_primary: true },
  { id: 2, ean: '5000000000001', is_primary: false },
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
  setupDom();
});

afterEach(() => {
  document.body.innerHTML = '';
});

// ── OFF Badge Rendering ─────────────────────────────

describe('OFF badge rendering', () => {
  it('primary EAN row renders .ean-badge-off badge when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    const badges = document.querySelectorAll('.ean-badge-off');
    expect(badges.length).toBe(1);
    expect(badges[0].textContent).toBe('OFF');
    const primaryItem = badges[0].closest('.ean-item');
    expect(primaryItem.querySelector('.ean-badge-primary')).not.toBeNull();
  });

  it('secondary EAN rows do NOT render .ean-badge-off', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_THREE);
    await loadEanManager(PRODUCT_ID, false);

    const items = document.querySelectorAll('.ean-item');
    expect(items[1].querySelector('.ean-badge-off')).toBeNull();
    expect(items[2].querySelector('.ean-badge-off')).toBeNull();
    expect(items[0].querySelector('.ean-badge-off')).not.toBeNull();
  });
});

// ── Per-EAN OFF Fetch Button ────────────────────────

describe('Per-EAN OFF fetch button', () => {
  it('secondary EAN rows render .btn-ean-off button when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_THREE);
    await loadEanManager(PRODUCT_ID, false);

    const offBtns = document.querySelectorAll('.btn-ean-off');
    expect(offBtns.length).toBe(2);
    expect(offBtns[0].dataset.eanAction).toBe('fetch-ean-off');
    expect(offBtns[1].dataset.eanAction).toBe('fetch-ean-off');
  });

  it('primary EAN row does NOT render .btn-ean-off', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    const items = document.querySelectorAll('.ean-item');
    expect(items[0].querySelector('.btn-ean-off')).toBeNull();
    expect(items[1].querySelector('.btn-ean-off')).not.toBeNull();
  });
});

// ── Locked State ────────────────────────────────────

describe('Locked state (is_synced_with_off present)', () => {
  it('does not render add input when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    expect(document.querySelector('.ean-add-input')).toBeNull();
    expect(document.getElementById('ean-add-input-' + PRODUCT_ID)).toBeNull();
  });

  it('does not render delete buttons when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    const deleteBtns = document.querySelectorAll('[data-ean-action="delete-ean"]');
    expect(deleteBtns.length).toBe(0);
  });

  it('does not render set-primary buttons when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    const setPrimaryBtns = document.querySelectorAll('[data-ean-action="set-primary"]');
    expect(setPrimaryBtns.length).toBe(0);
  });

  it('does not render OFF fetch buttons when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    const offBtns = document.querySelectorAll('.btn-ean-off');
    expect(offBtns.length).toBe(0);
  });

  it('does not render OFF badge when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    const offBadges = document.querySelectorAll('.ean-badge-off');
    expect(offBadges.length).toBe(0);
  });

  it('renders .ean-lock-notice when locked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, true);

    const lockNotice = document.querySelector('.ean-lock-notice');
    expect(lockNotice).not.toBeNull();
    expect(lockNotice.textContent).toContain('ean_locked_notice');
  });
});

// ── Unlocked State ──────────────────────────────────

describe('Unlocked state (is_synced_with_off absent)', () => {
  it('renders add input when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    expect(document.querySelector('.ean-add-input')).not.toBeNull();
  });

  it('renders delete buttons when unlocked with multiple EANs', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    const deleteBtns = document.querySelectorAll('[data-ean-action="delete-ean"]');
    expect(deleteBtns.length).toBe(2);
  });

  it('renders set-primary button on secondary EANs when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    const setPrimaryBtns = document.querySelectorAll('[data-ean-action="set-primary"]');
    expect(setPrimaryBtns.length).toBe(1);
    expect(setPrimaryBtns[0].dataset.eanId).toBe('2');
  });

  it('renders OFF fetch buttons on secondary EANs when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    const offBtns = document.querySelectorAll('.btn-ean-off');
    expect(offBtns.length).toBe(1);
    expect(offBtns[0].dataset.eanId).toBe('2');
  });

  it('does not render .ean-lock-notice when unlocked', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);

    expect(document.querySelector('.ean-lock-notice')).toBeNull();
  });
});

// ── Error Handling ──────────────────────────────────

describe('Error handling', () => {
  it('loadEanManager shows error when API fails', async () => {
    api.mockRejectedValueOnce(new Error('Network error'));
    await loadEanManager(PRODUCT_ID, false);

    const container = document.getElementById('ean-manager-' + PRODUCT_ID);
    expect(container.querySelector('.field-error')).not.toBeNull();
  });

  it('loadEanManager exits early when container is missing', async () => {
    document.body.innerHTML = '';
    await loadEanManager(PRODUCT_ID, false);
    expect(api).not.toHaveBeenCalled();
  });
});
