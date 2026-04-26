import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../scroll.js', () => ({
  initInfiniteScroll: vi.fn(),
  teardownInfiniteScroll: vi.fn(),
  showScrollLoader: vi.fn(),
  hideScrollLoader: vi.fn(),
}));

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: { total: 5, types: 2, categories: [] },
    cachedResults: [
      { id: 1, name: 'Milk', type: 'dairy' },
      { id: 2, name: 'Bread', type: 'bakery' },
    ],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
    pagination: { offset: 0, total: null, inFlight: false, pageSize: 50 },
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

vi.mock('../images.js', () => ({
  clearPendingImage: vi.fn(),
  triggerImageUpload: vi.fn(),
  removeProductImage: vi.fn(),
  captureProductImage: vi.fn(),
  resizeImage: vi.fn(),
  loadProductImage: vi.fn(),
  viewProductImage: vi.fn(),
}));

import { startEdit, saveProduct, deleteProduct, unlockEan, setFilter, toggleExpand, switchView, onSearchInput, clearSearch, registerProduct, loadData } from '../products.js';
import { state, api, showConfirmModal, showToast, fetchStats, fetchProducts } from '../state.js';
import { rerender } from '../filters.js';
import { renderResults, getFlagConfig } from '../render.js';
import { showDuplicateMergeModal } from '../off-duplicates.js';
import { initInfiniteScroll } from '../scroll.js';

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  state.currentView = 'search';
  state.currentFilter = [];
  state.expandedId = null;
  state.editingId = null;
  state.pagination = { offset: 0, total: null, inFlight: false, pageSize: 50 };
  state.cachedResults = [
    { id: 1, name: 'Milk', type: 'dairy' },
    { id: 2, name: 'Bread', type: 'bakery' },
  ];
  document.body.innerHTML = '';
  // Set up minimal DOM needed by most functions
  const elements = [
    { tag: 'div', id: 'view-search' },
    { tag: 'div', id: 'view-register' },
    { tag: 'div', id: 'view-settings' },
    { tag: 'input', id: 'search-input' },
    { tag: 'div', id: 'search-clear' },
    { tag: 'div', id: 'stats-line' },
    { tag: 'div', id: 'result-count' },
    { tag: 'div', id: 'results-container' },
    { tag: 'select', id: 'f-volume' },
  ];
  elements.forEach(({ tag, id }) => {
    const el = document.createElement(tag);
    el.id = id;
    document.body.appendChild(el);
  });
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('startEdit', () => {
  it('sets editingId and calls rerender', () => {
    startEdit(42);
    expect(state.editingId).toBe(42);
    expect(rerender).toHaveBeenCalled();
  });

  it('scrolls edit form into view and focuses first input after rerender', () => {
    const form = document.createElement('div');
    form.className = 'edit-form';
    const input = document.createElement('input');
    input.id = 'ed-name';
    form.appendChild(input);
    document.body.appendChild(form);

    const scrollIntoViewMock = vi.fn();
    form.scrollIntoView = scrollIntoViewMock;
    const focusMock = vi.fn();
    input.focus = focusMock;

    startEdit(99);
    vi.runAllTicks();
    // flush requestAnimationFrame
    vi.runAllTimers();

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' });
    expect(focusMock).toHaveBeenCalled();
  });

  it('does not throw if edit form is absent after rerender', () => {
    // No .edit-form in DOM
    expect(() => {
      startEdit(7);
      vi.runAllTimers();
    }).not.toThrow();
  });
});

describe('saveProduct', () => {
  beforeEach(() => {
    // Create form fields for edit
    const fields = [
      { tag: 'input', id: 'ed-name', value: 'Test Product' },
      { tag: 'select', id: 'ed-type', value: 'dairy' },
      { tag: 'input', id: 'ed-ean', value: '' },
      { tag: 'input', id: 'ed-brand', value: '' },
      { tag: 'input', id: 'ed-stores', value: '' },
      { tag: 'textarea', id: 'ed-ingredients', value: '' },
      { tag: 'input', id: 'ed-smak', value: '' },
      { tag: 'input', id: 'ed-kcal', value: '' },
      { tag: 'input', id: 'ed-energy_kj', value: '' },
      { tag: 'input', id: 'ed-fat', value: '' },
      { tag: 'input', id: 'ed-saturated_fat', value: '' },
      { tag: 'input', id: 'ed-carbs', value: '' },
      { tag: 'input', id: 'ed-sugar', value: '' },
      { tag: 'input', id: 'ed-protein', value: '' },
      { tag: 'input', id: 'ed-fiber', value: '' },
      { tag: 'input', id: 'ed-salt', value: '' },
      { tag: 'input', id: 'ed-weight', value: '' },
      { tag: 'input', id: 'ed-portion', value: '' },
      { tag: 'input', id: 'ed-volume', value: '' },
      { tag: 'input', id: 'ed-price', value: '' },
      { tag: 'input', id: 'ed-est_pdcaas', value: '' },
      { tag: 'input', id: 'ed-est_diaas', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
  });

  it('saves product with valid name', async () => {
    api.mockResolvedValueOnce({});
    await saveProduct(1);
    expect(api).toHaveBeenCalledWith('/api/products/1', expect.objectContaining({ method: 'PUT' }));
    expect(state.editingId).toBeNull();
    expect(showToast).toHaveBeenCalledWith('toast_product_updated', 'success');
  });

  it('shows error when name is empty', async () => {
    document.getElementById('ed-name').value = '';
    await saveProduct(1);
    expect(showToast).toHaveBeenCalledWith('toast_name_required', 'error');
    expect(api).not.toHaveBeenCalled();
  });

  it('shows error when EAN is invalid', async () => {
    document.getElementById('ed-ean').value = '123';
    await saveProduct(1);
    expect(showToast).toHaveBeenCalledWith('toast_invalid_ean', 'error');
  });

  it('accepts valid EAN', async () => {
    document.getElementById('ed-ean').value = '1234567890123';
    api.mockResolvedValueOnce({});
    await saveProduct(1);
    expect(api).toHaveBeenCalled();
  });

  it('forwards from_off and from_off_ean when a per-row OFF fetch targeted a secondary', async () => {
    // Simulate state left behind by ean-manager._fetchEanOff: hidden #ed-ean
    // remains on the primary, while the targeted EAN is stashed on window.
    document.getElementById('ed-ean').value = '1111111111111'; // primary
    window._pendingOFFSync = true;
    window._pendingOFFEan = '2222222222222'; // the fetched secondary
    api.mockResolvedValueOnce({});

    await saveProduct(1);

    const putCall = api.mock.calls.find((c) => c[0] === '/api/products/1');
    expect(putCall).toBeDefined();
    const body = JSON.parse(putCall[1].body);
    expect(body.ean).toBe('1111111111111');
    expect(body.from_off).toBe(true);
    expect(body.from_off_ean).toBe('2222222222222');
    expect(window._pendingOFFSync).toBeNull();
    expect(window._pendingOFFEan).toBeNull();
  });

  it('omits from_off_ean when no per-row fetch targeted a specific EAN', async () => {
    document.getElementById('ed-ean').value = '1111111111111';
    window._pendingOFFSync = true;
    window._pendingOFFEan = null;
    api.mockResolvedValueOnce({});

    await saveProduct(1);

    const putCall = api.mock.calls.find((c) => c[0] === '/api/products/1');
    const body = JSON.parse(putCall[1].body);
    expect(body.from_off).toBe(true);
    expect('from_off_ean' in body).toBe(false);
  });
});

describe('deleteProduct', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

  it('deletes product after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    const promise = deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(0);
    await promise;
    expect(showConfirmModal).toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_product_deleted'), 'success', expect.objectContaining({ onUndo: expect.any(Function) }));
    await vi.advanceTimersByTimeAsync(5000);
    await vi.advanceTimersByTimeAsync(0);
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
  });

  it('does nothing when confirmation cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    const promise = deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(0);
    await promise;
    expect(api).not.toHaveBeenCalled();
  });

  it('looks up name from cachedResults when not provided', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    const promise = deleteProduct(1);
    await vi.advanceTimersByTimeAsync(0);
    await promise;
    expect(showConfirmModal).toHaveBeenCalledWith(expect.any(String), 'Milk', expect.any(String), expect.any(String), expect.any(String), true);
  });

  it('cleans up state after deletion', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    const promise = deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(0);
    await promise;
    expect(state.imageCache[1]).toBeUndefined();
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
  });

  it('shows network error on API failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    showConfirmModal.mockResolvedValue(true);
    api.mockReset();
    api.mockImplementation(() => Promise.reject(new Error('network fail')));
    showToast.mockClear();
    const promise = deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(0);
    await promise;
    await vi.runAllTimersAsync();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    api.mockReset();
    api.mockResolvedValue({});
    console.error.mockRestore();
  });

  it('executes onUndo callback to restore deleted product', async () => {
    state.cachedResults = [{ id: 1, name: 'Milk' }];
    showConfirmModal.mockResolvedValue(true);

    const promise = deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(0);
    await promise;

    // Grab the onUndo callback from the showToast mock
    const toastCall = showToast.mock.calls.find((c) => c[1] === 'success' && c[2] && c[2].onUndo);
    expect(toastCall).toBeTruthy();
    const { onUndo } = toastCall[2];

    // Product should be removed from cachedResults before undo
    expect(state.cachedResults.find((p) => p.id === 1)).toBeUndefined();

    // Invoke the undo
    onUndo();

    // Product should be restored
    expect(state.cachedResults.find((p) => p.id === 1)).toBeTruthy();
    expect(showToast).toHaveBeenCalledWith('toast_delete_undone', 'info');
  });
});

describe('setFilter', () => {
  it('clears filters when "all" is passed', () => {
    state.currentFilter = ['dairy', 'meat'];
    setFilter('all');
    expect(state.currentFilter).toEqual([]);
  });

  it('adds filter when not present', () => {
    state.currentFilter = [];
    setFilter('dairy');
    expect(state.currentFilter).toEqual(['dairy']);
  });

  it('removes filter when already present', () => {
    state.currentFilter = ['dairy', 'meat'];
    setFilter('dairy');
    expect(state.currentFilter).toEqual(['meat']);
  });
});

describe('toggleExpand', () => {
  it('sets expandedId when collapsed', () => {
    state.expandedId = null;
    toggleExpand(1);
    expect(state.expandedId).toBe(1);
    expect(state.editingId).toBeNull();
    expect(rerender).toHaveBeenCalled();
  });

  it('collapses when same id clicked', () => {
    state.expandedId = 1;
    toggleExpand(1);
    expect(state.expandedId).toBeNull();
  });

  it('switches to different product', () => {
    state.expandedId = 1;
    toggleExpand(2);
    expect(state.expandedId).toBe(2);
  });
});

describe('switchView', () => {
  beforeEach(() => {
    // Add nav tabs
    ['search', 'register', 'settings'].forEach((v) => {
      const tab = document.createElement('div');
      tab.className = 'nav-tab';
      tab.dataset.view = v;
      document.body.appendChild(tab);
    });
  });

  it('sets current view and resets state', () => {
    state.expandedId = 5;
    state.editingId = 3;
    switchView('register');
    expect(state.currentView).toBe('register');
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
  });

  it('shows correct view and hides others', () => {
    switchView('register');
    expect(document.getElementById('view-register').style.display).toBe('');
    expect(document.getElementById('view-search').style.display).toBe('none');
    expect(document.getElementById('view-settings').style.display).toBe('none');
  });

  it('activates correct nav tab', () => {
    switchView('register');
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach((tab) => {
      if (tab.dataset.view === 'register') {
        expect(tab.classList.contains('active')).toBe(true);
      } else {
        expect(tab.classList.contains('active')).toBe(false);
      }
    });
  });
});

describe('onSearchInput', () => {
  it('shows clear button when text present', () => {
    document.getElementById('search-input').value = 'test';
    onSearchInput();
    expect(document.getElementById('search-clear').classList.contains('visible')).toBe(true);
  });

  it('hides clear button when empty', () => {
    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.add('visible');
    onSearchInput();
    expect(document.getElementById('search-clear').classList.contains('visible')).toBe(false);
  });

  it('resets expanded and editing state', () => {
    state.expandedId = 1;
    state.editingId = 2;
    document.getElementById('search-input').value = 'x';
    onSearchInput();
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
  });

  it('debounces loadData call', () => {
    document.getElementById('search-input').value = 'x';
    onSearchInput();
    expect(state.searchTimeout).not.toBeNull();
  });
});

describe('clearSearch', () => {
  it('clears search input and reloads data', () => {
    document.getElementById('search-input').value = 'test';
    document.getElementById('search-clear').classList.add('visible');
    clearSearch();
    expect(document.getElementById('search-input').value).toBe('');
    expect(document.getElementById('search-clear').classList.contains('visible')).toBe(false);
  });
});

describe('registerProduct', () => {
  beforeEach(() => {
    const fields = [
      { tag: 'input', id: 'f-name', value: 'New Product' },
      { tag: 'select', id: 'f-type', value: 'dairy' },
      { tag: 'input', id: 'f-ean', value: '' },
      { tag: 'input', id: 'f-brand', value: '' },
      { tag: 'input', id: 'f-stores', value: '' },
      { tag: 'textarea', id: 'f-ingredients', value: '' },
      { tag: 'input', id: 'f-taste_note', value: '' },
      { tag: 'input', id: 'f-smak', value: '3' },
      { tag: 'input', id: 'f-kcal', value: '' },
      { tag: 'input', id: 'f-energy_kj', value: '' },
      { tag: 'input', id: 'f-fat', value: '' },
      { tag: 'input', id: 'f-saturated_fat', value: '' },
      { tag: 'input', id: 'f-carbs', value: '' },
      { tag: 'input', id: 'f-sugar', value: '' },
      { tag: 'input', id: 'f-protein', value: '' },
      { tag: 'input', id: 'f-fiber', value: '' },
      { tag: 'input', id: 'f-salt', value: '' },
      { tag: 'input', id: 'f-weight', value: '' },
      { tag: 'input', id: 'f-portion', value: '' },
      { tag: 'select', id: 'f-volume', value: '' },
      { tag: 'input', id: 'f-price', value: '' },
      { tag: 'input', id: 'f-est_pdcaas', value: '' },
      { tag: 'input', id: 'f-est_diaas', value: '' },
      { tag: 'button', id: 'btn-submit', value: '' },
      { tag: 'span', id: 'smak-val', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      if (!document.getElementById(id)) {
        const el = document.createElement(tag);
        el.id = id;
        el.value = value;
        if (tag === 'span') el.textContent = value;
        document.body.appendChild(el);
      }
    });
    // Add nav tabs
    ['search', 'register', 'settings'].forEach((v) => {
      if (!document.querySelector(`.nav-tab[data-view="${v}"]`)) {
        const tab = document.createElement('div');
        tab.className = 'nav-tab';
        tab.dataset.view = v;
        document.body.appendChild(tab);
      }
    });
  });

  it('shows error when name is empty', async () => {
    document.getElementById('f-name').value = '';
    await registerProduct();
    expect(showToast).toHaveBeenCalledWith('toast_product_name_required', 'error');
  });

  it('shows error when EAN is invalid', async () => {
    document.getElementById('f-ean').value = '123';
    await registerProduct();
    expect(showToast).toHaveBeenCalledWith('toast_invalid_ean', 'error');
  });

  it('registers product with valid data', async () => {
    api.mockResolvedValueOnce({ id: 99 });
    await registerProduct();
    expect(api).toHaveBeenCalledWith('/api/products', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_product_added'), 'success');
  });

  it('disables submit button during save', async () => {
    const btn = document.getElementById('btn-submit');
    api.mockImplementation(() => {
      expect(btn.disabled).toBe(true);
      return Promise.resolve({ id: 99 });
    });
    await registerProduct();
    expect(btn.disabled).toBe(false);
  });
});

describe('loadData', () => {
  beforeEach(() => {
    // Ensure DOM elements required by loadData are present
    if (!document.getElementById('stats-line')) {
      const statsLine = document.createElement('div');
      statsLine.id = 'stats-line';
      document.body.appendChild(statsLine);
    }
    // Make cachedStats available after fetchStats resolves
    fetchStats.mockResolvedValue({ total: 10, types: 3 });
    state.cachedStats = { total: 10, types: 3 };
  });

  it('calls fetchStats, buildFilters, fetchProducts, and renderResults in sequence', async () => {
    fetchProducts.mockResolvedValue([{ id: 1, name: 'Milk', type: 'dairy', total_score: 80, has_image: 0 }]);
    await loadData();
    expect(fetchStats).toHaveBeenCalled();
    const { buildFilters } = await import('../filters.js');
    expect(buildFilters).toHaveBeenCalled();
    expect(fetchProducts).toHaveBeenCalled();
    expect(renderResults).toHaveBeenCalled();
  });

  it('shows error toast when fetchStats fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    fetchStats.mockRejectedValueOnce(new Error('network fail'));
    await loadData();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    console.error.mockRestore();
  });

  it('passes a search getter to initInfiniteScroll when more results may exist', async () => {
    fetchProducts.mockResolvedValue({ products: [{ id: 1 }], total: 100 });
    state.currentView = 'search';

    // Add a search input so the getter can read it
    if (!document.getElementById('search-input')) {
      const si = document.createElement('input');
      si.id = 'search-input';
      si.value = 'oat';
      document.body.appendChild(si);
    } else {
      document.getElementById('search-input').value = 'oat';
    }

    await loadData();

    // initInfiniteScroll should have been called with a function
    expect(initInfiniteScroll).toHaveBeenCalledWith(expect.any(Function));

    // Invoke the callback to cover lines 258-259
    const getSearch = initInfiniteScroll.mock.calls[initInfiniteScroll.mock.calls.length - 1][0];
    const result = getSearch();
    expect(result).toBe('oat');
  });

  it('search getter returns empty string when view is not search', async () => {
    fetchProducts.mockResolvedValue({ products: [{ id: 1 }], total: 100 });
    state.currentView = 'register'; // not search view

    await loadData();

    const getSearch = initInfiniteScroll.mock.calls[initInfiniteScroll.mock.calls.length - 1][0];
    const result = getSearch();
    expect(result).toBe('');
  });

  it('scrolls and highlights first result row when search has results', async () => {
    document.getElementById('search-input').value = 'milk';
    state.currentView = 'search';
    fetchProducts.mockResolvedValue([{ id: 1, name: 'Milk', type: 'dairy' }]);

    const rowEl = document.createElement('div');
    rowEl.className = 'table-row';
    rowEl.dataset.productId = '1';
    rowEl.scrollIntoView = vi.fn();
    document.body.appendChild(rowEl);

    await loadData();
    // Advance past rAF (~16ms) but not past the 5000ms highlight removal timer
    vi.advanceTimersByTime(20);

    expect(rowEl.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' });
    expect(rowEl.classList.contains('scan-highlight')).toBe(true);

    vi.advanceTimersByTime(5000);
    expect(rowEl.classList.contains('scan-highlight')).toBe(false);
  });

  it('does not scroll or highlight when search is empty', async () => {
    document.getElementById('search-input').value = '';
    state.currentView = 'search';
    fetchProducts.mockResolvedValue([{ id: 1, name: 'Milk', type: 'dairy' }]);

    const rowEl = document.createElement('div');
    rowEl.className = 'table-row';
    rowEl.dataset.productId = '1';
    rowEl.scrollIntoView = vi.fn();
    document.body.appendChild(rowEl);

    await loadData();
    vi.advanceTimersByTime(20);

    expect(rowEl.scrollIntoView).not.toHaveBeenCalled();
    expect(rowEl.classList.contains('scan-highlight')).toBe(false);
  });

  it('does not scroll or highlight when results are empty', async () => {
    document.getElementById('search-input').value = 'milk';
    state.currentView = 'search';
    fetchProducts.mockResolvedValue([]);

    const rowEl = document.createElement('div');
    rowEl.className = 'table-row';
    rowEl.dataset.productId = '1';
    rowEl.scrollIntoView = vi.fn();
    document.body.appendChild(rowEl);

    await loadData();
    vi.advanceTimersByTime(20);

    expect(rowEl.scrollIntoView).not.toHaveBeenCalled();
    expect(rowEl.classList.contains('scan-highlight')).toBe(false);
  });

  it('does not throw when no .table-row is in the DOM', async () => {
    document.getElementById('search-input').value = 'milk';
    state.currentView = 'search';
    fetchProducts.mockResolvedValue([{ id: 1, name: 'Milk', type: 'dairy' }]);
    // No .table-row element added to DOM

    await expect(async () => {
      await loadData();
      vi.advanceTimersByTime(20);
    }).not.toThrow();
  });
});

describe('switchView settings', () => {
  beforeEach(() => {
    ['search', 'register', 'settings'].forEach((v) => {
      const tab = document.createElement('div');
      tab.className = 'nav-tab';
      tab.dataset.view = v;
      document.body.appendChild(tab);
    });
  });

  it('lazy-imports settings module for settings view', async () => {
    switchView('settings');
    expect(document.getElementById('view-settings').style.display).toBe('');
    expect(state.currentView).toBe('settings');
  });

  it('focuses search input when switching to search view', () => {
    const si = document.getElementById('search-input');
    const spy = vi.spyOn(si, 'focus');
    switchView('search');
    expect(spy).toHaveBeenCalled();
  });
});

describe('saveProduct duplicate handling', () => {
  beforeEach(() => {
    const fields = [
      { tag: 'input', id: 'ed-name', value: 'Test Product' },
      { tag: 'select', id: 'ed-type', value: 'dairy' },
      { tag: 'input', id: 'ed-ean', value: '1234567890123' },
      { tag: 'input', id: 'ed-brand', value: '' },
      { tag: 'input', id: 'ed-stores', value: '' },
      { tag: 'textarea', id: 'ed-ingredients', value: '' },
      { tag: 'input', id: 'ed-taste_note', value: '' },
      { tag: 'input', id: 'ed-smak', value: '' },
      { tag: 'input', id: 'ed-kcal', value: '100' },
      { tag: 'input', id: 'ed-energy_kj', value: '' },
      { tag: 'input', id: 'ed-fat', value: '' },
      { tag: 'input', id: 'ed-saturated_fat', value: '' },
      { tag: 'input', id: 'ed-carbs', value: '' },
      { tag: 'input', id: 'ed-sugar', value: '' },
      { tag: 'input', id: 'ed-protein', value: '' },
      { tag: 'input', id: 'ed-fiber', value: '' },
      { tag: 'input', id: 'ed-salt', value: '' },
      { tag: 'input', id: 'ed-weight', value: '' },
      { tag: 'input', id: 'ed-portion', value: '' },
      { tag: 'input', id: 'ed-volume', value: '' },
      { tag: 'input', id: 'ed-price', value: '' },
      { tag: 'input', id: 'ed-est_pdcaas', value: '' },
      { tag: 'input', id: 'ed-est_diaas', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
  });

  it('handles b_synced scenario - merges into duplicate', async () => {
    api
      .mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean', a_is_synced_with_off: false }, a_is_synced_with_off: false })
      .mockResolvedValueOnce({});
    showDuplicateMergeModal.mockResolvedValueOnce({ scenario: 'b_synced', choices: { kcal: 100 } });
    await saveProduct(1);
    expect(api).toHaveBeenCalledWith('/api/products/2/merge', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith('toast_duplicate_merged', 'success');
    expect(state.editingId).toBeNull();
  });

  it('handles a_synced scenario - merges into current', async () => {
    api
      .mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean' }, a_is_synced_with_off: true })
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});
    showDuplicateMergeModal.mockResolvedValueOnce({ scenario: 'a_synced', choices: { protein: 20 } });
    await saveProduct(1);
    expect(api).toHaveBeenCalledWith('/api/products/1/merge', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith('toast_duplicate_merged', 'success');
  });

  it('handles neither_synced scenario', async () => {
    api
      .mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean' }, a_is_synced_with_off: false })
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});
    showDuplicateMergeModal.mockResolvedValueOnce({ scenario: 'neither', choices: { fat: 5 } });
    await saveProduct(1);
    expect(api).toHaveBeenCalledWith('/api/products/1/merge', expect.objectContaining({ method: 'POST' }));
  });

  it('cancels when user dismisses duplicate modal', async () => {
    api.mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean' }, a_is_synced_with_off: false });
    showDuplicateMergeModal.mockResolvedValueOnce(null);
    await saveProduct(1);
    // Should not call PUT or merge
    expect(api).toHaveBeenCalledTimes(1); // Only the check-duplicate call
  });

  it('shows network error when duplicate check fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await saveProduct(1);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('handles save error after merge', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api
      .mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean' }, a_is_synced_with_off: false })
      .mockResolvedValueOnce({}) // merge succeeds
      .mockRejectedValueOnce(new Error('save fail')); // PUT fails
    showDuplicateMergeModal.mockResolvedValueOnce({ scenario: 'a_synced', choices: {} });
    await saveProduct(1);
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
    console.error.mockRestore();
  });

  it('includes OFF applied fields in b_synced merge', async () => {
    window._offAppliedFields = ['kcal', 'protein'];
    api
      .mockResolvedValueOnce({ duplicate: { id: 2, name: 'Dup', match_type: 'ean' }, a_is_synced_with_off: false })
      .mockResolvedValueOnce({});
    showDuplicateMergeModal.mockResolvedValueOnce({ scenario: 'b_synced', choices: {} });
    await saveProduct(1);
    const mergeBody = JSON.parse(api.mock.calls[1][1].body);
    expect(mergeBody.choices.kcal).toBe(100);
    window._offAppliedFields = null;
  });
});

describe('registerProduct advanced paths', () => {
  beforeEach(() => {
    const fields = [
      { tag: 'input', id: 'f-name', value: 'New Product' },
      { tag: 'select', id: 'f-type', value: 'dairy' },
      { tag: 'input', id: 'f-ean', value: '' },
      { tag: 'input', id: 'f-brand', value: '' },
      { tag: 'input', id: 'f-stores', value: '' },
      { tag: 'textarea', id: 'f-ingredients', value: '' },
      { tag: 'input', id: 'f-taste_note', value: '' },
      { tag: 'input', id: 'f-smak', value: '3' },
      { tag: 'input', id: 'f-kcal', value: '' },
      { tag: 'input', id: 'f-energy_kj', value: '' },
      { tag: 'input', id: 'f-fat', value: '' },
      { tag: 'input', id: 'f-saturated_fat', value: '' },
      { tag: 'input', id: 'f-carbs', value: '' },
      { tag: 'input', id: 'f-sugar', value: '' },
      { tag: 'input', id: 'f-protein', value: '' },
      { tag: 'input', id: 'f-fiber', value: '' },
      { tag: 'input', id: 'f-salt', value: '' },
      { tag: 'input', id: 'f-weight', value: '' },
      { tag: 'input', id: 'f-portion', value: '' },
      { tag: 'select', id: 'f-volume', value: '' },
      { tag: 'input', id: 'f-price', value: '' },
      { tag: 'input', id: 'f-est_pdcaas', value: '' },
      { tag: 'input', id: 'f-est_diaas', value: '' },
      { tag: 'button', id: 'btn-submit', value: '' },
      { tag: 'span', id: 'smak-val', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      if (!document.getElementById(id)) {
        const el = document.createElement(tag);
        el.id = id;
        el.value = value;
        if (tag === 'span') el.textContent = value;
        document.body.appendChild(el);
      }
    });
    ['search', 'register', 'settings'].forEach((v) => {
      if (!document.querySelector(`.nav-tab[data-view="${v}"]`)) {
        const tab = document.createElement('div');
        tab.className = 'nav-tab';
        tab.dataset.view = v;
        document.body.appendChild(tab);
      }
    });
  });

  it('sets from_off flag when _pendingOFFSync is set', async () => {
    window._pendingOFFSync = true;
    api.mockResolvedValueOnce({ id: 99 });
    await registerProduct();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.from_off).toBe(true);
    expect(window._pendingOFFSync).toBeNull();
  });

  it('uploads pending image after registration', async () => {
    window._pendingImage = 'data:image/png;base64,abc';
    api.mockResolvedValueOnce({ id: 99 }).mockResolvedValueOnce({});
    await registerProduct();
    expect(api).toHaveBeenCalledWith('/api/products/99/image', expect.objectContaining({ method: 'PUT' }));
    expect(window._pendingImage).toBeNull();
  });

  it('shows image upload error toast on failure', async () => {
    window._pendingImage = 'data:image/png;base64,abc';
    api.mockResolvedValueOnce({ id: 99 }).mockRejectedValueOnce(new Error('upload fail'));
    await registerProduct();
    expect(showToast).toHaveBeenCalledWith('toast_image_upload_error', 'error');
  });

  it('shows merged toast when result has merged flag', async () => {
    api.mockResolvedValueOnce({ id: 99, merged: true });
    await registerProduct();
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_product_merged'), 'success');
  });

  it('shows save error on general exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('server error'));
    await registerProduct();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
    console.error.mockRestore();
  });

  it('clears form fields after successful registration', async () => {
    document.getElementById('f-name').value = 'New Product';
    document.getElementById('f-brand').value = 'Brand X';
    document.getElementById('f-stores').value = 'Store A';
    document.getElementById('f-ean').value = '';
    api.mockResolvedValueOnce({ id: 99 });
    await registerProduct();
    expect(document.getElementById('f-name').value).toBe('');
    expect(document.getElementById('f-brand').value).toBe('');
    expect(document.getElementById('f-stores').value).toBe('');
    expect(document.getElementById('f-smak').value).toBe('3');
    expect(document.getElementById('smak-val').textContent).toBe('3');
    expect(document.getElementById('f-price').value).toBe('');
  });

  it('opens filter row and scrolls to new product after registration', async () => {
    // Add filter-row and filter-toggle elements (without 'open' class)
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterTog = document.createElement('div');
    filterTog.id = 'filter-toggle';
    document.body.appendChild(filterTog);

    api.mockResolvedValueOnce({ id: 42 });
    await registerProduct();

    // Filter row should be opened
    expect(filterRow.classList.contains('open')).toBe(true);
    expect(filterTog.classList.contains('open')).toBe(true);

    // Simulate the product row existing in the DOM for the setTimeout callback
    const rowEl = document.createElement('div');
    rowEl.className = 'table-row';
    rowEl.dataset.productId = '42';
    rowEl.scrollIntoView = vi.fn();
    document.body.appendChild(rowEl);

    // Advance the 500ms setTimeout for scroll/highlight
    vi.advanceTimersByTime(500);
    expect(rowEl.classList.contains('scan-highlight')).toBe(true);
    expect(rowEl.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });

    // Advance the 5000ms setTimeout to remove highlight
    vi.advanceTimersByTime(5000);
    expect(rowEl.classList.contains('scan-highlight')).toBe(false);
  });

  it('hides protein quality wrap and result after registration', async () => {
    const pqw = document.createElement('div');
    pqw.id = 'f-protein-quality-wrap';
    pqw.style.display = 'block';
    document.body.appendChild(pqw);
    const pqr = document.createElement('div');
    pqr.id = 'f-pq-result';
    pqr.style.display = 'block';
    document.body.appendChild(pqr);

    api.mockResolvedValueOnce({ id: 99 });
    await registerProduct();

    expect(pqw.style.display).toBe('none');
    expect(pqr.style.display).toBe('none');
  });

  it('handles 409 with synced duplicate - shows modal and returns', async () => {
    const dupError = new Error('Conflict');
    dupError.status = 409;
    dupError.data = { duplicate: { id: 5, name: 'Dup', match_type: 'ean', is_synced_with_off: true } };
    api.mockRejectedValueOnce(dupError);
    const registerPromise = registerProduct();
    // Wait for microtasks so the modal is appended to DOM
    await vi.advanceTimersByTimeAsync(0);
    // For synced duplicates, only the OK button is shown (confirm-yes class)
    const okBtn = document.querySelector('.scan-modal-btn-register.confirm-yes');
    expect(okBtn).not.toBeNull();
    okBtn.click();
    await registerPromise;
    // Should not call api again (no merge/create), button re-enabled
    const btn = document.getElementById('btn-submit');
    expect(btn.disabled).toBe(false);
  });

  it('handles 409 with unsynced duplicate - cancel choice', async () => {
    const dupError = new Error('Conflict');
    dupError.status = 409;
    dupError.data = { duplicate: { id: 5, name: 'Dup', match_type: 'ean', is_synced_with_off: false } };
    api.mockRejectedValueOnce(dupError);
    // _showDuplicateModal creates DOM elements; we need to resolve it
    // Since _showDuplicateModal appends to document.body, we can click the cancel button
    // But it's a private function called internally. Let's trigger it by letting the modal render
    // and then clicking the cancel button.
    const registerPromise = registerProduct();
    // Wait for microtasks to settle so the modal is appended
    await vi.advanceTimersByTimeAsync(0);
    const cancelBtn = document.querySelector('.scan-modal-btn-cancel');
    if (cancelBtn) cancelBtn.click();
    await registerPromise;
    const btn = document.getElementById('btn-submit');
    expect(btn.disabled).toBe(false);
  });

  it('handles 409 with unsynced duplicate - overwrite choice', async () => {
    const dupError = new Error('Conflict');
    dupError.status = 409;
    dupError.data = { duplicate: { id: 5, name: 'Dup', match_type: 'ean', is_synced_with_off: false } };
    api.mockRejectedValueOnce(dupError);
    api.mockResolvedValueOnce({ id: 5 }); // overwrite result

    const registerPromise = registerProduct();
    await vi.advanceTimersByTimeAsync(0);
    // Click the merge/overwrite button (first button with confirm-yes class)
    const mergeBtn = document.querySelector('.scan-modal-btn-register.confirm-yes');
    if (mergeBtn) mergeBtn.click();
    await registerPromise;
    expect(api).toHaveBeenCalledWith('/api/products', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"on_duplicate":"overwrite"'),
    }));
  });

  it('handles 409 with unsynced duplicate - create_new choice', async () => {
    const dupError = new Error('Conflict');
    dupError.status = 409;
    dupError.data = { duplicate: { id: 5, name: 'Dup', match_type: 'ean', is_synced_with_off: false } };
    api.mockRejectedValueOnce(dupError);
    api.mockResolvedValueOnce({ id: 10 }); // create_new result

    const registerPromise = registerProduct();
    await vi.advanceTimersByTimeAsync(0);
    // Click the "create new" button (second .scan-modal-btn-register without confirm-yes)
    const buttons = document.querySelectorAll('.scan-modal-btn-register');
    const createBtn = buttons[1]; // second button is create new
    if (createBtn) createBtn.click();
    await registerPromise;
    expect(api).toHaveBeenCalledWith('/api/products', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"on_duplicate":"allow_duplicate"'),
    }));
  });
});

describe('onSearchInput disabled', () => {
  it('returns early when input is disabled', () => {
    const el = document.getElementById('search-input');
    el.disabled = true;
    el.value = 'test';
    state.expandedId = 5;
    onSearchInput();
    // Should not change state since it returned early
    expect(state.expandedId).toBe(5);
  });
});

describe('clearSearch resets state', () => {
  it('resets expandedId and editingId', () => {
    state.expandedId = 10;
    state.editingId = 20;
    clearSearch();
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
  });

  it('focuses the search input', () => {
    const si = document.getElementById('search-input');
    const spy = vi.spyOn(si, 'focus');
    clearSearch();
    expect(spy).toHaveBeenCalled();
  });
});

describe('collectFormFields with flags', () => {
  beforeEach(() => {
    getFlagConfig.mockReturnValue({
      vegan: { type: 'user', label: 'Vegan' },
      organic: { type: 'user', label: 'Organic' },
      computed_flag: { type: 'computed', label: 'Auto' },
    });
    const fields = [
      { tag: 'input', id: 'f-name', value: 'Test' },
      { tag: 'select', id: 'f-type', value: 'snack' },
      { tag: 'input', id: 'f-ean', value: '' },
      { tag: 'input', id: 'f-brand', value: '' },
      { tag: 'input', id: 'f-stores', value: '' },
      { tag: 'textarea', id: 'f-ingredients', value: '' },
      { tag: 'input', id: 'f-taste_note', value: '' },
      { tag: 'input', id: 'f-smak', value: '' },
      { tag: 'input', id: 'f-kcal', value: '' },
      { tag: 'input', id: 'f-energy_kj', value: '' },
      { tag: 'input', id: 'f-fat', value: '' },
      { tag: 'input', id: 'f-saturated_fat', value: '' },
      { tag: 'input', id: 'f-carbs', value: '' },
      { tag: 'input', id: 'f-sugar', value: '' },
      { tag: 'input', id: 'f-protein', value: '' },
      { tag: 'input', id: 'f-fiber', value: '' },
      { tag: 'input', id: 'f-salt', value: '' },
      { tag: 'input', id: 'f-weight', value: '' },
      { tag: 'input', id: 'f-portion', value: '' },
      { tag: 'select', id: 'f-volume', value: '' },
      { tag: 'input', id: 'f-price', value: '' },
      { tag: 'input', id: 'f-est_pdcaas', value: '' },
      { tag: 'input', id: 'f-est_diaas', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      if (!document.getElementById(id)) {
        const el = document.createElement(tag);
        el.id = id;
        el.value = value;
        document.body.appendChild(el);
      }
    });
    // Add flag checkboxes
    const veganCb = document.createElement('input');
    veganCb.type = 'checkbox';
    veganCb.id = 'f-flag-vegan';
    veganCb.checked = true;
    document.body.appendChild(veganCb);
    const organicCb = document.createElement('input');
    organicCb.type = 'checkbox';
    organicCb.id = 'f-flag-organic';
    organicCb.checked = false;
    document.body.appendChild(organicCb);
  });

  it('collects checked user flags and ignores unchecked and computed flags', async () => {
    // Register triggers collectFormFields('f') internally
    api.mockResolvedValueOnce({ id: 50 });
    // Add remaining required elements
    if (!document.getElementById('btn-submit')) {
      const btn = document.createElement('button');
      btn.id = 'btn-submit';
      document.body.appendChild(btn);
    }
    if (!document.getElementById('smak-val')) {
      const sv = document.createElement('span');
      sv.id = 'smak-val';
      document.body.appendChild(sv);
    }
    ['search', 'register', 'settings'].forEach((v) => {
      if (!document.querySelector(`.nav-tab[data-view="${v}"]`)) {
        const tab = document.createElement('div');
        tab.className = 'nav-tab';
        tab.dataset.view = v;
        document.body.appendChild(tab);
      }
    });
    await registerProduct();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.flags).toContain('vegan');
    expect(body.flags).not.toContain('organic');
    expect(body.flags).not.toContain('computed_flag');
  });
});

describe('unlockEan', () => {
  beforeEach(() => {
    state.cachedResults = [{ id: 1, name: 'Milk', flags: ['is_synced_with_off'] }];
    state.imageCache = {};
  });

  it('calls unsync API and shows success toast', async () => {
    api.mockResolvedValueOnce({});
    await unlockEan(1);
    expect(api).toHaveBeenCalledWith('/api/products/1/unsync', { method: 'POST' });
    expect(showToast).toHaveBeenCalledWith('toast_ean_unlocked', 'success');
  });

  it('removes is_synced_with_off flag from cached product', async () => {
    api.mockResolvedValueOnce({});
    await unlockEan(1);
    expect(state.cachedResults[0].flags).not.toContain('is_synced_with_off');
  });

  it('handles product not in cachedResults gracefully', async () => {
    api.mockResolvedValueOnce({});
    await unlockEan(999); // ID not in cachedResults
    expect(showToast).toHaveBeenCalledWith('toast_ean_unlocked', 'success');
  });

  it('shows error toast on API failure', async () => {
    api.mockRejectedValueOnce(new Error('network error'));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await unlockEan(1);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('handles product with no flags array', async () => {
    state.cachedResults = [{ id: 1, name: 'Milk' }]; // no flags property
    api.mockResolvedValueOnce({});
    await unlockEan(1);
    expect(showToast).toHaveBeenCalledWith('toast_ean_unlocked', 'success');
  });
});

describe('registerProduct - OFF prompt branches', () => {
  let showOffAddReview;

  beforeEach(async () => {
    vi.useFakeTimers();
    const offReview = await import('../off-review.js');
    showOffAddReview = offReview.showOffAddReview;

    const fields = [
      { tag: 'input', id: 'f-name', value: 'Product With EAN' },
      { tag: 'select', id: 'f-type', value: 'dairy' },
      { tag: 'input', id: 'f-ean', value: '1234567890123' },
      { tag: 'input', id: 'f-brand', value: '' },
      { tag: 'input', id: 'f-stores', value: '' },
      { tag: 'textarea', id: 'f-ingredients', value: '' },
      { tag: 'input', id: 'f-taste_note', value: '' },
      { tag: 'input', id: 'f-smak', value: '3' },
      { tag: 'input', id: 'f-kcal', value: '' },
      { tag: 'input', id: 'f-energy_kj', value: '' },
      { tag: 'input', id: 'f-fat', value: '' },
      { tag: 'input', id: 'f-saturated_fat', value: '' },
      { tag: 'input', id: 'f-carbs', value: '' },
      { tag: 'input', id: 'f-sugar', value: '' },
      { tag: 'input', id: 'f-protein', value: '' },
      { tag: 'input', id: 'f-fiber', value: '' },
      { tag: 'input', id: 'f-salt', value: '' },
      { tag: 'input', id: 'f-weight', value: '' },
      { tag: 'input', id: 'f-portion', value: '' },
      { tag: 'select', id: 'f-volume', value: '' },
      { tag: 'input', id: 'f-price', value: '' },
      { tag: 'input', id: 'f-est_pdcaas', value: '' },
      { tag: 'input', id: 'f-est_diaas', value: '' },
      { tag: 'button', id: 'btn-submit', value: '' },
      { tag: 'span', id: 'smak-val', value: '' },
      { tag: 'input', id: 'search-input', value: '' },
      { tag: 'span', id: 'search-clear', value: '' },
    ];
    fields.forEach(({ tag, id, value }) => {
      if (!document.getElementById(id)) {
        const el = document.createElement(tag);
        el.id = id;
        el.value = value;
        if (tag === 'span') el.textContent = value;
        document.body.appendChild(el);
      }
    });
    ['search', 'register', 'settings'].forEach((v) => {
      if (!document.querySelector(`.nav-tab[data-view="${v}"]`)) {
        const tab = document.createElement('div');
        tab.className = 'nav-tab';
        tab.dataset.view = v;
        document.body.appendChild(tab);
      }
    });
    window._pendingOFFSync = false;
    window._pendingImage = null;
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    window._pendingOFFSync = false;
    window._pendingImage = null;
  });

  it('asks about OFF when EAN present and not from_off, user accepts', async () => {
    api.mockResolvedValueOnce({ id: 42 });
    showConfirmModal.mockResolvedValueOnce(true); // wantsOff = true
    fetchStats.mockResolvedValue({ total: 0, types: 0, categories: [] });
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    const p = registerProduct();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    expect(showOffAddReview).toHaveBeenCalledWith('1234567890123', 'f', 42);
  });

  it('does not call showOffAddReview when user declines OFF prompt', async () => {
    api.mockResolvedValueOnce({ id: 42 });
    showConfirmModal.mockResolvedValueOnce(false); // wantsOff = false
    fetchStats.mockResolvedValue({ total: 0, types: 0, categories: [] });
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    const p = registerProduct();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    expect(showOffAddReview).not.toHaveBeenCalled();
  });

  it('does not show OFF prompt when registered from_off', async () => {
    window._pendingOFFSync = true;
    api.mockResolvedValueOnce({ id: 42 });
    fetchStats.mockResolvedValue({ total: 0, types: 0, categories: [] });
    fetchProducts.mockResolvedValue({ products: [], total: 0 });

    const p = registerProduct();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    // showConfirmModal may be called for other reasons but showOffAddReview should not
    expect(showOffAddReview).not.toHaveBeenCalled();
  });
});
