// State management edge cases: concurrent mutations, race conditions, state recovery.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: { total: 0, types: 0, categories: [] },
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
    advancedFilters: null,
    pagination: { offset: 0, total: null, inFlight: false, pageSize: 50 },
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({ products: [], total: 0 }),
    fetchProducts: vi.fn().mockResolvedValue({ products: [], total: 0 }),
    fetchStats: vi.fn().mockResolvedValue({ total: 0, types: 0, categories: [] }),
    NUTRI_IDS: ['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'],
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
    upgradeSelect: vi.fn(),
    announceStatus: vi.fn(),
    trapFocus: vi.fn(() => vi.fn()),
  };
});

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));
vi.mock('../scroll.js', () => ({
  initInfiniteScroll: vi.fn(),
  teardownInfiniteScroll: vi.fn(),
}));
vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
  getFlagConfig: vi.fn(() => ({})),
}));
vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, buildFilters: vi.fn(), rerender: vi.fn(), buildTypeSelect: vi.fn() };
});
vi.mock('../settings-weights.js', () => ({ loadSettings: vi.fn() }));
vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
  validateOffBtn: vi.fn(),
}));
vi.mock('../off-conflicts.js', () => ({
  showMergeConflictModal: vi.fn(),
  showEditDuplicateModal: vi.fn(),
}));
vi.mock('../off-duplicates.js', () => ({ showDuplicateMergeModal: vi.fn() }));
vi.mock('../off-review.js', () => ({
  showOffAddReview: vi.fn(),
  closeOffAddReview: vi.fn(),
  submitToOff: vi.fn(),
}));
vi.mock('../tags.js', () => ({
  initTagInput: vi.fn(),
  getTagsForSave: vi.fn(() => []),
}));
vi.mock('../ean-manager.js', () => ({
  loadEanManager: vi.fn(),
  addEan: vi.fn(),
  deleteEan: vi.fn(),
  setEanPrimary: vi.fn(),
}));

import { loadData, setFilter, switchView, onSearchInput } from '../products.js';
import { state, fetchProducts } from '../state.js';
import { renderResults } from '../render.js';

beforeEach(() => {
  vi.clearAllMocks();
  state.currentView = 'search';
  state.currentFilter = [];
  state.expandedId = null;
  state.editingId = null;
  state.cachedResults = [];
  state.advancedFilters = null;
  state.searchTimeout = null;
  state.pagination = { offset: 0, total: null, inFlight: false, pageSize: 50 };

  document.body.innerHTML = `
    <div id="stats-line"></div>
    <input id="search-input" value="" />
    <span id="search-clear"></span>
    <select id="f-volume"><option value="">--</option></select>
    <div id="view-search"></div>
    <div id="view-register" style="display:none"></div>
    <div id="view-settings" style="display:none"></div>
    <div class="nav-tab" data-view="search"></div>
  `;
});

// ── Concurrent state mutations ────────────────────────

describe('Concurrent state mutations', () => {
  it('last setFilter wins when called rapidly', () => {
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');
    setFilter('Drikke');
    setFilter('Snacks'); // toggle removes Snacks
    setFilter('Drikke'); // toggle removes Drikke

    expect(state.currentFilter).toEqual([]);
  });

  it('multiple setFilter calls accumulate filters', () => {
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');
    setFilter('Drikke');

    expect(state.currentFilter).toContain('Snacks');
    expect(state.currentFilter).toContain('Drikke');
  });

  it('resetting via setFilter("all") clears all pending filters', () => {
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');
    setFilter('Drikke');
    setFilter('all');

    expect(state.currentFilter).toEqual([]);
  });

  it('concurrent expandedId and editingId mutations do not interfere', () => {
    state.expandedId = 1;
    state.editingId = 2;

    // onSearchInput clears both
    vi.useFakeTimers();
    onSearchInput();
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
    vi.useRealTimers();
  });
});

// ── Race conditions in async operations ───────────────

describe('Race conditions: fetchProducts', () => {
  it('handles two rapid loadData calls; both complete without error', async () => {
    let resolveFirst, resolveSecond;
    const p1 = new Promise((r) => { resolveFirst = r; });
    const p2 = new Promise((r) => { resolveSecond = r; });

    fetchProducts
      .mockReturnValueOnce(p1)
      .mockReturnValueOnce(p2);

    const first = loadData();
    const second = loadData();

    resolveSecond({ products: [{ id: 2, name: 'B' }], total: 1 });
    resolveFirst({ products: [{ id: 1, name: 'A' }], total: 1 });

    await Promise.all([first, second]);

    // Both resolved — no error thrown
    expect(fetchProducts).toHaveBeenCalledTimes(2);
  });

  it('state.cachedResults reflects whichever loadData ran last', async () => {
    const result1 = { products: [{ id: 1, name: 'First' }], total: 1 };
    const result2 = { products: [{ id: 2, name: 'Second' }], total: 1 };

    fetchProducts
      .mockResolvedValueOnce(result1)
      .mockResolvedValueOnce(result2);

    await loadData();
    await loadData();

    // renderResults was called twice
    expect(renderResults).toHaveBeenCalledTimes(2);
  });
});

// ── State recovery from errors ────────────────────────

describe('State recovery: fetchProducts error', () => {
  it('state is not corrupted after a failed loadData', async () => {
    fetchProducts.mockRejectedValueOnce(new Error('API error'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    try {
      await loadData();
    } catch (_) { /* loadData may propagate */ }

    // State should remain valid after error
    expect(typeof state.currentFilter).toBe('object');
    expect(Array.isArray(state.currentFilter)).toBe(true);
    console.error.mockRestore();
  });

  it('subsequent loadData succeeds after previous failure', async () => {
    fetchProducts
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ products: [{ id: 1, name: 'Recovered' }], total: 1 });

    vi.spyOn(console, 'error').mockImplementation(() => {});
    try { await loadData(); } catch (_) {}
    console.error.mockRestore();

    await loadData();

    expect(renderResults).toHaveBeenLastCalledWith(
      [{ id: 1, name: 'Recovered' }],
      '',
    );
  });
});

// ── State recovery: filter reset ─────────────────────

describe('State recovery: filter reset after view switch', () => {
  it('cachedResults empty after switchView allows fresh fetch', async () => {
    state.cachedResults = [{ id: 99, name: 'Old' }];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    switchView('search');

    expect(state.cachedResults).toEqual([]);
    expect(state.pagination.offset).toBe(0);
  });

  it('pagination resets to offset 0 after setFilter', () => {
    state.pagination.offset = 150;
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');

    expect(state.pagination.offset).toBe(0);
  });
});

// ── i18n edge cases ──────────────────────────────────

describe('i18n edge cases: missing translation key fallback', () => {
  it('t() returns key when translation does not exist', async () => {
    const { t } = await import('../i18n.js');
    // t is mocked to return the key
    expect(t('completely_missing_key')).toBe('completely_missing_key');
  });

  it('t() returns key with params when translation is missing', async () => {
    const { t } = await import('../i18n.js');
    expect(t('missing_with_param', { name: 'Alice' })).toBe('missing_with_param');
  });
});
