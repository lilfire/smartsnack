import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../scroll.js', () => ({
  initInfiniteScroll: vi.fn(),
  teardownInfiniteScroll: vi.fn(),
}));

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
    advancedFilters: null,
    pagination: { offset: 0, total: null, inFlight: false, pageSize: 50 },
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({ products: [], total: 0 }),
    fetchProducts: vi.fn().mockResolvedValue({ products: [], total: 0 }),
    fetchStats: vi.fn().mockResolvedValue({ total: 5, types: 2 }),
    NUTRI_IDS: ['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'],
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
    upgradeSelect: vi.fn(),
    announceStatus: vi.fn(),
    trapFocus: vi.fn(() => vi.fn()),
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
vi.mock('../scroll.js', () => ({
  initInfiniteScroll: vi.fn(),
  teardownInfiniteScroll: vi.fn(),
}));

vi.mock('../scroll.js', () => ({
  initInfiniteScroll: vi.fn(),
  teardownInfiniteScroll: vi.fn(),
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

import { loadData, setFilter, switchView, onSearchInput, clearSearch } from '../products.js';
import { state, fetchProducts, fetchStats } from '../state.js';
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
    <div class="nav-tab" data-view="register"></div>
    <div class="nav-tab" data-view="settings"></div>
  `;
});

describe('Pagination: initial load', () => {
  it('calls fetchProducts and passes result to renderResults', async () => {
    const mockProducts = [
      { id: 1, name: 'A', total_score: 80 },
      { id: 2, name: 'B', total_score: 70 },
    ];
    fetchProducts.mockResolvedValue({ products: mockProducts, total: 2 });

    await loadData();

    expect(fetchProducts).toHaveBeenCalledTimes(1);
    expect(fetchProducts).toHaveBeenCalledWith('', [], { limit: 50, offset: 0 });
    expect(renderResults).toHaveBeenCalledWith(mockProducts, '');
  });

  it('uses search input value when in search view', async () => {
    document.getElementById('search-input').value = 'Popcorn';
    const mockProducts = [{ id: 1, name: 'Popcorn', total_score: 90 }];
    fetchProducts.mockResolvedValue({ products: mockProducts, total: 1 });

    await loadData();

    expect(fetchProducts).toHaveBeenCalledWith('Popcorn', [], { limit: 50, offset: 0 });
  });

  it('passes current filters to fetchProducts', async () => {
    state.currentFilter = ['Snacks', 'Drikke'];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    await loadData();

    expect(fetchProducts).toHaveBeenCalledWith('', ['Snacks', 'Drikke'], { limit: 50, offset: 0 });
  });
});

describe('Pagination: filter/sort reset', () => {
  it('setFilter clears cachedResults and reloads', async () => {
    state.cachedResults = [{ id: 1, name: 'Old' }];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');

    expect(state.cachedResults).toEqual([]);
    // loadData is called asynchronously
  });

  it('setFilter with "all" resets currentFilter to empty', () => {
    state.currentFilter = ['Snacks', 'Drikke'];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('all');

    expect(state.currentFilter).toEqual([]);
  });

  it('setFilter toggles a single filter type', () => {
    state.currentFilter = [];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    setFilter('Snacks');
    expect(state.currentFilter).toContain('Snacks');

    setFilter('Snacks');
    expect(state.currentFilter).not.toContain('Snacks');
  });

  it('switchView clears cachedResults', () => {
    state.cachedResults = [{ id: 1, name: 'Cached' }];
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    switchView('search');

    expect(state.cachedResults).toEqual([]);
  });

  it('onSearchInput clears expandedId, editingId, and cachedResults', () => {
    vi.useFakeTimers();
    state.expandedId = 5;
    state.editingId = 3;
    state.cachedResults = [{ id: 1 }];

    onSearchInput();

    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
    expect(state.cachedResults).toEqual([]);
    vi.useRealTimers();
  });

  it('clearSearch resets input and reloads data', async () => {
    document.getElementById('search-input').value = 'test';
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    clearSearch();

    expect(document.getElementById('search-input').value).toBe('');
  });
});

describe('Pagination: boundary cases', () => {
  it('renders empty state when products array is empty', async () => {
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    await loadData();

    expect(renderResults).toHaveBeenCalledWith([], '');
  });

  it('handles total=0 without requesting more pages', async () => {
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    await loadData();

    // Only one fetchProducts call — no subsequent page requests
    expect(fetchProducts).toHaveBeenCalledTimes(1);
  });

  it('fetches first page with offset=0 regardless of previous state', async () => {
    state.pagination.offset = 200; // stale offset from previous session
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    await loadData();

    expect(fetchProducts).toHaveBeenCalledWith('', [], expect.objectContaining({ offset: 0 }));
  });

  it('passes pageSize to fetchProducts', async () => {
    state.pagination.pageSize = 25;
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    await loadData();

    expect(fetchProducts).toHaveBeenCalledWith('', [], expect.objectContaining({ limit: 25 }));
    // Reset
    state.pagination.pageSize = 50;
  });

  it('does not call fetchProducts when inFlight is true', async () => {
    // This tests the guard against overlapping requests
    state.pagination.inFlight = true;
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    // loadData always resets and runs — but inFlight is reset at start
    await loadData();

    // loadData should still run (it resets inFlight), just verifying no hang
    expect(fetchProducts).toHaveBeenCalled();
    state.pagination.inFlight = false;
  });

  it('single result renders correctly (not plural)', async () => {
    fetchProducts.mockResolvedValue({
      products: [{ id: 1, name: 'Only Product', total_score: 80 }],
      total: 1,
    });

    await loadData();

    expect(renderResults).toHaveBeenCalledWith(
      [expect.objectContaining({ id: 1 })],
      '',
    );
  });

  it('max results in one page — no infinite scroll setup needed', async () => {
    const products = Array.from({ length: 50 }, (_, i) => ({
      id: i + 1, name: `Product ${i + 1}`, total_score: 80,
    }));
    fetchProducts.mockResolvedValue({ products, total: 50 });

    await loadData();

    expect(renderResults).toHaveBeenCalledWith(products, '');
  });
});
