import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

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
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  buildFilters: vi.fn(),
  rerender: vi.fn(),
  buildTypeSelect: vi.fn(),
}));

vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
  getFlagConfig: vi.fn(() => ({})),
}));

vi.mock('../openfoodfacts.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
  validateOffBtn: vi.fn(),
}));

import { startEdit, saveProduct, deleteProduct, setFilter, toggleExpand, switchView, onSearchInput, clearSearch, registerProduct, loadData } from '../products.js';
import { state, api, showConfirmModal, showToast, fetchStats, fetchProducts } from '../state.js';
import { rerender } from '../filters.js';
import { renderResults } from '../render.js';

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  state.currentView = 'search';
  state.currentFilter = [];
  state.expandedId = null;
  state.editingId = null;
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
  vi.useRealTimers();
});

describe('startEdit', () => {
  it('sets editingId and calls rerender', () => {
    startEdit(42);
    expect(state.editingId).toBe(42);
    expect(rerender).toHaveBeenCalled();
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
});

describe('deleteProduct', () => {
  it('deletes product after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    await deleteProduct(1, 'Milk');
    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_product_deleted'), 'success');
  });

  it('does nothing when confirmation cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deleteProduct(1, 'Milk');
    expect(api).not.toHaveBeenCalled();
  });

  it('looks up name from cachedResults when not provided', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    await deleteProduct(1);
    expect(showConfirmModal).toHaveBeenCalledWith(expect.any(String), 'Milk', expect.any(String), expect.any(String), expect.any(String));
  });

  it('cleans up state after deletion', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    await deleteProduct(1, 'Milk');
    expect(state.imageCache[1]).toBeUndefined();
    expect(state.expandedId).toBeNull();
    expect(state.editingId).toBeNull();
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
});
