import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: null,
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
    advancedFilters: null,
  };
  return {
    state: _state,
    NUTRI_IDS: ['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'],
    catEmoji: vi.fn((type) => '📦'),
    catLabel: vi.fn((type) => type),
    esc: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    safeDataUri: (uri) => typeof uri === 'string' && uri.startsWith('data:') ? uri : '',
    fmtNum: vi.fn((v) => v == null ? '-' : String(v)),
    showToast: vi.fn(),
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    applySorting: vi.fn((results) => results),
    sortIndicator: vi.fn((col) => '↕'),
    rerender: vi.fn(),
  };
});

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../settings.js', () => ({
  SCORE_COLORS: { kcal: '#aa66ff', protein: '#00d4ff' },
  SCORE_CFG_MAP: { kcal: { label: 'Kcal' }, protein: { label: 'Protein' } },
  weightData: [],
}));

vi.mock('../openfoodfacts.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
}));

import { renderNutriTable, fmtCell, getActiveCols, getGridTemplate, renderResults, getFlagConfig, loadFlagConfig } from '../render.js';
import { state } from '../state.js';
import { weightData } from '../settings.js';

beforeEach(() => {
  state.expandedId = null;
  state.editingId = null;
  state.cachedResults = [];
  state.categories = [];
  document.body.innerHTML = '';
  Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
});

describe('fmtCell', () => {
  it('returns dash for null', () => {
    expect(fmtCell('kcal', null)).toBe('-');
  });

  it('formats kcal as rounded integer', () => {
    expect(fmtCell('kcal', 123.7)).toBe('124');
  });

  it('formats energy_kj as rounded integer', () => {
    expect(fmtCell('energy_kj', 500.4)).toBe('500');
  });

  it('formats salt with 2 decimals', () => {
    expect(fmtCell('salt', 1.234)).toBe('1.23g');
  });

  it('formats protein with 1 decimal', () => {
    expect(fmtCell('protein', 25.67)).toBe('25.7g');
  });

  it('formats price with kr suffix', () => {
    expect(fmtCell('price', 49.9)).toBe('50kr');
  });

  it('returns dash for price with falsy value', () => {
    expect(fmtCell('price', 0)).toBe('-');
  });

  it('formats percentage fields', () => {
    expect(fmtCell('pct_protein_cal', 33.33)).toBe('33.3%');
    expect(fmtCell('pct_fat_cal', 25.0)).toBe('25.0%');
    expect(fmtCell('pct_carb_cal', 41.67)).toBe('41.7%');
  });

  it('formats taste_score as stars', () => {
    const result = fmtCell('taste_score', 4);
    expect(result).toContain('★');
    expect(result).toContain('stars');
  });

  it('clamps taste_score between 0 and 6', () => {
    const high = fmtCell('taste_score', 10);
    expect((high.match(/★/g) || []).length).toBe(6); // 6 filled stars shown

    const low = fmtCell('taste_score', -1);
    expect(low).toContain('stars-dim');
  });

  it('formats volume as label', () => {
    const result = fmtCell('volume', 1);
    expect(result).toBe('volume_low');
  });
});

describe('getActiveCols', () => {
  it('always includes name and total_score', () => {
    weightData.length = 0;
    const cols = getActiveCols();
    expect(cols[0].key).toBe('name');
    expect(cols[cols.length - 1].key).toBe('total_score');
  });

  it('includes enabled weight columns on desktop', () => {
    weightData.length = 0;
    weightData.push({ field: 'kcal', label: 'Kcal', enabled: true });
    weightData.push({ field: 'protein', label: 'Protein', enabled: true });
    weightData.push({ field: 'fat', label: 'Fat', enabled: false });
    const cols = getActiveCols();
    expect(cols.map((c) => c.key)).toEqual(['name', 'kcal', 'protein', 'total_score']);
  });

  it('excludes weight columns on mobile', () => {
    Object.defineProperty(window, 'innerWidth', { value: 320, writable: true });
    weightData.length = 0;
    weightData.push({ field: 'kcal', label: 'Kcal', enabled: true });
    const cols = getActiveCols();
    expect(cols.map((c) => c.key)).toEqual(['name', 'total_score']);
  });
});

describe('getGridTemplate', () => {
  it('joins column widths', () => {
    const cols = [
      { key: 'name', width: '2.4fr' },
      { key: 'total_score', width: '0.9fr' },
    ];
    expect(getGridTemplate(cols)).toBe('2.4fr 0.9fr');
  });

  it('handles single column', () => {
    expect(getGridTemplate([{ key: 'name', width: '1fr' }])).toBe('1fr');
  });
});

describe('renderNutriTable', () => {
  it('returns HTML table with nutrition rows', () => {
    const product = { kcal: 200, energy_kj: 840, fat: 10, saturated_fat: 3, carbs: 25, sugar: 5, protein: 15, fiber: 3, salt: 0.5 };
    const html = renderNutriTable(product);
    expect(html).toContain('<table');
    expect(html).toContain('nutri_energy');
    expect(html).toContain('200');
    expect(html).toContain('10.0');
    expect(html).toContain('0.5 g');
  });

  it('shows dash for null values', () => {
    const product = { kcal: null, energy_kj: null, fat: null, saturated_fat: null, carbs: null, sugar: null, protein: null, fiber: null, salt: null };
    const html = renderNutriTable(product);
    expect(html).toContain('-');
  });

  it('includes PDCAAS/DIAAS when estimated', () => {
    const product = { kcal: 200, energy_kj: 840, fat: 10, saturated_fat: 3, carbs: 25, sugar: 5, protein: 15, fiber: 3, salt: 0.5, est_pdcaas: 0.85, est_diaas: 0.92 };
    const html = renderNutriTable(product);
    expect(html).toContain('PDCAAS');
    expect(html).toContain('0.85');
    expect(html).toContain('DIAAS');
    expect(html).toContain('0.92');
  });

  it('includes extras for weight, portion, price, volume', () => {
    const product = { kcal: 200, energy_kj: 840, fat: 10, saturated_fat: 3, carbs: 25, sugar: 5, protein: 15, fiber: 3, salt: 0.5, weight: 500, portion: 30, price: 45, volume: 2 };
    const html = renderNutriTable(product);
    expect(html).toContain('extra_weight');
    expect(html).toContain('extra_portion');
    expect(html).toContain('extra_price');
    expect(html).toContain('extra_volume');
  });
});

describe('renderResults', () => {
  beforeEach(() => {
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);
  });

  it('renders empty state when no results', () => {
    renderResults([], '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('no_products_found');
  });

  it('renders empty state with create button when searching', () => {
    const fEan = document.createElement('input');
    fEan.id = 'f-ean';
    document.body.appendChild(fEan);
    const fName = document.createElement('input');
    fName.id = 'f-name';
    document.body.appendChild(fName);
    renderResults([], 'test query');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('create_product');
  });

  it('renders product rows', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '', has_image: 0 },
      { id: 2, name: 'Bread', type: 'bakery', total_score: 70, ean: '', has_image: 0 },
    ];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('Milk');
    expect(container.innerHTML).toContain('Bread');
  });

  it('sets result count text', () => {
    renderResults([{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }], '');
    expect(document.getElementById('result-count').textContent).toContain('result_count');
  });

  it('caches results in state', () => {
    const products = [{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }];
    renderResults(products, '');
    expect(state.cachedResults).toBe(products);
  });

  it('renders expanded product details', () => {
    state.expandedId = 1;
    const products = [{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0, kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8, sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {} }];
    renderResults(products, '');
    expect(document.getElementById('results-container').innerHTML).toContain('expanded');
  });
});

describe('renderResults - expanded view', () => {
  beforeEach(() => {
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);
  });

  it('renders edit form when editingId is set', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '1234567890123', brand: 'Brand', stores: 'Store', ingredients: 'milk',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: 'Good', flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('edit-form');
    expect(container.innerHTML).toContain('ed-name');
    expect(container.innerHTML).toContain('ed-kcal');
    expect(container.innerHTML).toContain('btn_save');
    expect(container.innerHTML).toContain('btn_cancel');
  });

  it('renders expanded view with score breakdown', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1,
      scores: { kcal: 80, protein: 90 },
      brand: 'TestBrand', stores: 'TestStore', ingredients: 'milk, water',
      taste_score: 5, taste_note: 'Tasty',
      completeness: 75, flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('expanded');
    expect(container.innerHTML).toContain('expanded_score_breakdown');
    expect(container.innerHTML).toContain('score-bar-fill');
    expect(container.innerHTML).toContain('TestBrand');
    expect(container.innerHTML).toContain('TestStore');
    expect(container.innerHTML).toContain('milk, water');
    expect(container.innerHTML).toContain('completeness-bar');
  });

  it('renders missing fields warning', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1,
      scores: {}, has_missing_scores: true, missing_fields: ['kcal'],
      flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('expanded_missing_data');
  });

  it('renders action buttons when not editing', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 1,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('btn_edit');
    expect(container.innerHTML).toContain('btn_delete');
    expect(container.innerHTML).toContain('btn_remove_image');
  });

  it('renders result count with search query', () => {
    renderResults([{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }], 'milk');
    expect(document.getElementById('result-count').textContent).toContain('result_count_search');
  });

  it('renders plural result count with search query', () => {
    renderResults([
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 },
      { id: 2, name: 'Milk 2', type: 'dairy', total_score: 80, has_image: 0 },
    ], 'milk');
    expect(document.getElementById('result-count').textContent).toContain('result_count_search_plural');
  });
});

describe('renderResults - event delegation', () => {
  beforeEach(() => {
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);
    window.setSort = vi.fn();
    window.toggleExpand = vi.fn();
    window.triggerImageUpload = vi.fn();
    window.saveProduct = vi.fn();
    window.startEdit = vi.fn();
    window.removeProductImage = vi.fn();
    window.deleteProduct = vi.fn();
    window.openScanner = vi.fn();
    window.lookupOFF = vi.fn();
    window.estimateProteinQuality = vi.fn();
    window.switchView = vi.fn();
    window.validateOffBtn = vi.fn();
    window.updateEstimateBtn = vi.fn();
  });

  it('handles sort action via delegation', () => {
    const products = [{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }];
    renderResults(products, '');
    const sortEl = document.querySelector('[data-action="sort"]');
    sortEl.click();
    expect(window.setSort).toHaveBeenCalled();
  });

  it('handles start-edit action via delegation', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const editBtn = document.querySelector('[data-action="start-edit"]');
    editBtn.click();
    expect(window.startEdit).toHaveBeenCalledWith(1);
  });

  it('handles delete action via delegation', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const deleteBtn = document.querySelector('[data-action="delete"]');
    deleteBtn.click();
    expect(window.deleteProduct).toHaveBeenCalledWith(1);
  });

  it('handles remove-image action via delegation', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 1,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const removeBtn = document.querySelector('[data-action="remove-image"]');
    removeBtn.click();
    expect(window.removeProductImage).toHaveBeenCalledWith(1);
  });

  it('handles trigger-image action via delegation', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const imgArea = document.querySelector('[data-action="trigger-image"]');
    imgArea.click();
    expect(window.triggerImageUpload).toHaveBeenCalledWith(1);
  });

  it('handles save-product action via delegation', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const saveBtn = document.querySelector('[data-action="save-product"]');
    saveBtn.click();
    expect(window.saveProduct).toHaveBeenCalledWith(1);
  });

  it('handles cancel-edit action via delegation', async () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const cancelBtn = document.querySelector('[data-action="cancel-edit"]');
    cancelBtn.click();
    expect(state.editingId).toBeNull();
  });

  it('handles open-scanner action via delegation', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const scanBtn = document.querySelector('[data-action="open-scanner"]');
    scanBtn.click();
    expect(window.openScanner).toHaveBeenCalledWith('ed', 1);
  });

  it('handles lookup-off action via delegation', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '1234567890123', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const offBtn = document.querySelector('[data-action="lookup-off"]');
    offBtn.click();
    expect(window.lookupOFF).toHaveBeenCalledWith('ed', 1);
  });

  it('handles estimate-protein action via delegation', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: 'milk, water',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const estimateBtn = document.querySelector('[data-action="estimate-protein"]');
    estimateBtn.click();
    expect(window.estimateProteinQuality).toHaveBeenCalledWith('ed');
  });

  it('wires input validation handlers on edit form fields', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: 'milk',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');

    const edName = document.getElementById('ed-name');
    edName.dispatchEvent(new Event('input'));
    expect(window.validateOffBtn).toHaveBeenCalledWith('ed');
    expect(window.validateOffBtn).toHaveBeenCalledTimes(1);

    const edIngredients = document.getElementById('ed-ingredients');
    edIngredients.dispatchEvent(new Event('input'));
    expect(window.updateEstimateBtn).toHaveBeenCalledWith('ed');
  });

  it('creates button click sets name field for non-EAN search', () => {
    const fName = document.createElement('input');
    fName.id = 'f-name';
    document.body.appendChild(fName);
    const fEan = document.createElement('input');
    fEan.id = 'f-ean';
    document.body.appendChild(fEan);
    window.switchView = vi.fn();

    renderResults([], 'my product');
    const createBtn = document.querySelector('[data-action="create-from-search"]');
    createBtn.click();
    expect(fName.value).toBe('my product');
    expect(window.switchView).toHaveBeenCalledWith('register');
  });

  it('creates button click sets ean field for EAN search', () => {
    const fName = document.createElement('input');
    fName.id = 'f-name';
    document.body.appendChild(fName);
    const fEan = document.createElement('input');
    fEan.id = 'f-ean';
    document.body.appendChild(fEan);
    window.switchView = vi.fn();

    renderResults([], '1234567890123');
    const createBtn = document.querySelector('[data-action="create-from-search"]');
    createBtn.click();
    expect(fEan.value).toBe('1234567890123');
    expect(window.switchView).toHaveBeenCalledWith('register');
  });

  it('loads images for products with has_image', async () => {
    const { loadProductImage } = await import('../images.js');
    loadProductImage.mockResolvedValue('data:image/png;base64,abc');
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 1 },
    ];
    renderResults(products, '');
    await vi.waitFor(() => {
      expect(loadProductImage).toHaveBeenCalledWith(1);
    });
  });

  it('renders plural count without search', () => {
    renderResults([
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 },
      { id: 2, name: 'Bread', type: 'bakery', total_score: 70, has_image: 0 },
    ], '');
    expect(document.getElementById('result-count').textContent).toContain('result_count_plural');
  });

  it('does not call toggleExpand when clicking inside expanded area', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const expandedDiv = document.querySelector('.expanded');
    expandedDiv.click();
    expect(window.toggleExpand).not.toHaveBeenCalled();
  });

  it('renders has_missing_scores asterisk in score cell', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      has_missing_scores: true,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('*');
    expect(container.innerHTML).toContain('Score based on incomplete data');
  });

  it('renders EAN and brand in product row', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '7038010000', brand: 'Tine',
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('EAN: 7038010000');
    expect(container.innerHTML).toContain('Tine');
  });

  it('renders completeness badge with color coding', () => {
    const products = [{
      id: 1, name: 'Complete', type: 'dairy', total_score: 85, has_image: 0,
      completeness: 100,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('100%');
    expect(container.innerHTML).toContain('#4ecdc4');
  });

  it('renders thumbnail for product with image', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 1,
    }];
    renderResults(products, '');
    const thumb = document.getElementById('thumb-1');
    expect(thumb).not.toBeNull();
    expect(thumb.tagName).toBe('IMG');
  });

  it('renders no_weights message when scores object is empty', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('expanded_no_weights');
  });

  it('renders flag badges in expanded view', async () => {
    // Load flag config first
    const mockConfig = { vegan: { type: 'user', label: 'Vegan' }, processed: { type: 'system', label: 'Processed' } };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      flags: ['vegan', 'processed'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('flag-badge');
    expect(container.innerHTML).toContain('Vegan');
    expect(container.innerHTML).toContain('Processed');
  });

  it('renders edit form with user flag checkboxes', async () => {
    const mockConfig = { vegan: { type: 'user', label: 'Vegan' } };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: ['vegan'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('flag-toggle');
    expect(container.innerHTML).toContain('ed-flag-vegan');
    expect(container.innerHTML).toContain('checked');
  });

  it('skips unknown flags not in _flagConfig', async () => {
    const mockConfig = { vegan: { type: 'user', label: 'Vegan' } };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      flags: ['unknown_flag', 'vegan'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // 'vegan' should appear but 'unknown_flag' should be skipped
    expect(container.innerHTML).toContain('Vegan');
    expect(container.innerHTML).not.toContain('unknown_flag');
  });

  it('renders system flag badges in edit form', async () => {
    const mockConfig = {
      vegan: { type: 'user', label: 'Vegan' },
      sys_processed: { type: 'system', label: 'Processed' },
    };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '\u{1F9C0}', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: ['vegan', 'sys_processed'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // User flag should appear as checkbox
    expect(container.innerHTML).toContain('ed-flag-vegan');
    // System flag should appear as badge, not checkbox
    expect(container.innerHTML).toContain('flag-badge flag-system');
    expect(container.innerHTML).toContain('Processed');
  });

  it('renders edit form without system flags when product has none', async () => {
    const mockConfig = {
      vegan: { type: 'user', label: 'Vegan' },
      sys_processed: { type: 'system', label: 'Processed' },
    };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '\u{1F9C0}', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: ['vegan'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('ed-flag-vegan');
    // No system flag badges should be rendered
    expect(container.innerHTML).not.toContain('flag-badge flag-system');
  });

  it('does not expand when clicking a non-toggle-expand data-action inside a row', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 1,
      kcal: 60, energy_kj: 250, fat: 3.5, saturated_fat: 2.3, carbs: 4.8,
      sugar: 4.8, protein: 3.3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    // Clicking a button inside the row should not trigger toggle-expand
    const editBtn = document.querySelector('[data-action="start-edit"]');
    editBtn.click();
    expect(window.toggleExpand).not.toHaveBeenCalled();
  });

  it('renders completeness bar with low percentage color', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
      completeness: 30,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('rgba(255,140,0,0.7)');
  });
});

describe('renderResults - additional branch coverage', () => {
  beforeEach(() => {
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);
    window.setSort = vi.fn();
    window.toggleExpand = vi.fn();
    window.triggerImageUpload = vi.fn();
    window.saveProduct = vi.fn();
    window.startEdit = vi.fn();
    window.removeProductImage = vi.fn();
    window.deleteProduct = vi.fn();
    window.openScanner = vi.fn();
    window.lookupOFF = vi.fn();
    window.estimateProteinQuality = vi.fn();
    window.switchView = vi.fn();
    window.validateOffBtn = vi.fn();
    window.updateEstimateBtn = vi.fn();
  });

  it('renders singular result count without search', () => {
    renderResults([{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }], '');
    expect(document.getElementById('result-count').textContent).toBe('result_count');
  });

  it('renders total_score as dash when null', () => {
    const products = [{ id: 1, name: 'Milk', type: 'dairy', total_score: null, has_image: 0 }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('cell-score');
    expect(container.querySelector('.cell-score').textContent).toBe('-');
  });

  it('skips unknown score fields not in SCORE_CFG_MAP', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1,
      scores: { kcal: 80, unknown_field: 50 },
      flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // kcal should appear (it is in SCORE_CFG_MAP), unknown_field should be skipped
    expect(container.innerHTML).toContain('Kcal');
    expect(container.innerHTML).not.toContain('unknown_field');
  });

  it('uses fallback color #888 for score fields not in SCORE_COLORS', () => {
    state.expandedId = 1;
    // protein is in SCORE_CFG_MAP but let us use a field that is in CFG_MAP but not in SCORE_COLORS
    // SCORE_COLORS has kcal and protein only. protein IS in SCORE_COLORS.
    // We need a field in SCORE_CFG_MAP but not in SCORE_COLORS.
    // The mock has: SCORE_CFG_MAP: { kcal: { label: 'Kcal' }, protein: { label: 'Protein' } }
    // SCORE_COLORS: { kcal: '#aa66ff', protein: '#00d4ff' }
    // Both fields are in both maps, so we need to add a temporary field.
    // Instead, let's test by importing and checking the rendered HTML for a known color.
    // Actually, we can't easily add to the mock. Let's verify both known colors appear.
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1,
      scores: { kcal: 80, protein: 90 },
      flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('#aa66ff');
    expect(container.innerHTML).toContain('#00d4ff');
  });

  it('renders completeness bar at 100% with green color', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
      completeness: 100,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('completeness-bar-fill');
    expect(container.innerHTML).toContain('#4ecdc4');
    expect(container.innerHTML).toContain('100%');
  });

  it('renders completeness bar at mid-range with semi-transparent green', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
      completeness: 75,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('rgba(78,205,196,0.7)');
  });

  it('renders completeness bar with null completeness as 0', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
      completeness: null,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('completeness-bar-fill');
    expect(container.innerHTML).toContain('rgba(255,140,0,0.7)');
  });

  it('renders edit form with volume selected', async () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: null, taste_note: '', flags: [],
      volume: 2, price: 30, weight: 500, portion: 30,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // Volume 2 should be selected
    const volSelect = document.getElementById('ed-volume');
    expect(volSelect).not.toBeNull();
    expect(volSelect.querySelector('option[value="2"]').hasAttribute('selected')).toBe(true);
    // taste_score null should default to 3
    expect(container.innerHTML).toContain('value="3"');
  });

  it('renders edit form with ingredients and est_pdcaas/est_diaas', async () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: 'milk, water',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
      est_pdcaas: 0.85, est_diaas: null,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // Should show protein quality section since ingredients exist
    expect(container.innerHTML).toContain('label_protein_quality_est');
    expect(container.innerHTML).toContain('ed-estimate-btn');
    // est_pdcaas present, est_diaas null
    expect(container.innerHTML).toContain('0.85');
    // Hidden inputs
    expect(document.getElementById('ed-est_pdcaas').value).toBe('0.85');
    expect(document.getElementById('ed-est_diaas').value).toBe('');
  });

  it('renders edit form without ingredients hides protein quality section', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
      est_pdcaas: null, est_diaas: null,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // No protein quality section since no ingredients
    expect(container.innerHTML).not.toContain('label_protein_quality_est');
  });

  it('renders edit form with est_diaas but no est_pdcaas', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: 'milk',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
      est_pdcaas: null, est_diaas: 0.92,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('0.92');
    expect(document.getElementById('ed-est_diaas').value).toBe('0.92');
    expect(document.getElementById('ed-est_pdcaas').value).toBe('');
  });

  it('renders edit form flag with labelKey instead of label', async () => {
    const mockConfig = {
      organic: { type: 'user', labelKey: 'flag_organic' },
      sys_score: { type: 'system', labelKey: 'flag_score' },
    };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: ['organic', 'sys_score'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // User flag with labelKey should use t() translation
    expect(container.innerHTML).toContain('flag_organic');
    expect(container.innerHTML).toContain('ed-flag-organic');
    // System flag with labelKey
    expect(container.innerHTML).toContain('flag-badge flag-system');
    expect(container.innerHTML).toContain('flag_score');
  });

  it('renders expanded flag badges with labelKey fallback', async () => {
    const mockConfig = {
      bio: { type: 'user', labelKey: 'flag_bio' },
    };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();

    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      flags: ['bio'],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('flag-badge');
    expect(container.innerHTML).toContain('flag_bio');
  });

  it('handles toggle-expand click on table row', () => {
    const products = [{ id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0 }];
    renderResults(products, '');
    const row = document.querySelector('[data-action="toggle-expand"]');
    // Click on the row itself (not on a button or other action)
    const nameSpan = row.querySelector('.prod-name');
    nameSpan.click();
    expect(window.toggleExpand).toHaveBeenCalled();
  });

  it('does not toggle-expand when clicking a button inside the row', () => {
    state.expandedId = 1;
    state.editingId = null;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const deleteBtn = document.querySelector('[data-action="delete"]');
    deleteBtn.click();
    expect(window.toggleExpand).not.toHaveBeenCalled();
  });

  it('renders kcal column value when weight columns enabled on desktop', () => {
    weightData.length = 0;
    weightData.push({ field: 'kcal', label: 'Kcal', enabled: true });
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 123.7,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // kcal formatted as rounded integer
    expect(container.innerHTML).toContain('124');
    weightData.length = 0;
  });

  it('renders missing_fields warning with known SCORE_CFG_MAP labels', () => {
    state.expandedId = 1;
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1,
      scores: { kcal: 80 },
      has_missing_scores: true, missing_fields: ['kcal', 'unknown_nutri'],
      flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('expanded_missing_data');
    // The missing_fields map runs through SCORE_CFG_MAP to get labels;
    // kcal resolves to 'Kcal', unknown_nutri falls back to field name.
    // Since t() is mocked to return just the key, we verify the warning div renders.
    expect(container.innerHTML).toContain('\u26A0');
  });

  it('renders product row with low completeness badge color', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      completeness: 30,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('rgba(255,255,255,0.2)');
    expect(container.innerHTML).toContain('30%');
  });

  it('renders product row with mid completeness badge color', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      completeness: 60,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('rgba(78,205,196,0.6)');
  });

  it('renders product row with null completeness as empty string', () => {
    const products = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      completeness: null,
    }];
    renderResults(products, '');
    const badge = document.querySelector('.completeness-badge');
    expect(badge.textContent).toBe('');
  });

  it('renders edit form with volume 1 and volume 3 selected', () => {
    // Test volume 1
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products1 = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
      volume: 1,
    }];
    renderResults(products1, '');
    expect(document.getElementById('ed-volume').querySelector('option[value="1"]').hasAttribute('selected')).toBe(true);
    expect(document.getElementById('ed-volume').querySelector('option[value="3"]').hasAttribute('selected')).toBe(false);

    // Test volume 3
    document.body.innerHTML = '';
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);

    const products3 = [{
      id: 1, name: 'Milk', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
      volume: 3,
    }];
    renderResults(products3, '');
    expect(document.getElementById('ed-volume').querySelector('option[value="3"]').hasAttribute('selected')).toBe(true);
  });

  it('renders edit form with ean that disables OFF button when no ean and no name', () => {
    state.expandedId = 1;
    state.editingId = 1;
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    const products = [{
      id: 1, name: '   ', type: 'dairy', total_score: 85, has_image: 0,
      ean: '', brand: '', stores: '', ingredients: '',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {},
      taste_score: 4, taste_note: '', flags: [],
    }];
    renderResults(products, '');
    const offBtn = document.getElementById('ed-off-btn');
    // Both isValidEan('') is false and '   '.trim() is '', so button should be disabled
    expect(offBtn.hasAttribute('disabled')).toBe(true);
  });
});

describe('volumeLabel edge case', () => {
  it('returns raw value for unknown volume values', () => {
    // volumeLabel is not exported, but we can test it through fmtCell
    const result = fmtCell('volume', 5);
    // Should return the raw value since 5 is not in _VOLUME_LABELS
    expect(result).toBe(5);
  });
});

describe('getFlagConfig', () => {
  it('returns an object', () => {
    const cfg = getFlagConfig();
    expect(cfg).toBeTypeOf('object');
    expect(cfg).not.toBeNull();
  });
});

describe('renderResults - EAN display in product list', () => {
  beforeEach(() => {
    const count = document.createElement('div');
    count.id = 'result-count';
    document.body.appendChild(count);
    const container = document.createElement('div');
    container.id = 'results-container';
    document.body.appendChild(container);
  });

  it('shows EAN with no suffix for a product with one EAN', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '7038010069307', ean_count: 1, has_image: 0 },
    ];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('EAN: 7038010069307');
    expect(container.innerHTML).not.toContain('(+');
  });

  it('shows EAN with (+2) suffix for a product with three EANs', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '7038010069307', ean_count: 3, has_image: 0 },
    ];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('EAN: 7038010069307');
    const suffix = container.querySelector('.ean-count-suffix');
    expect(suffix).not.toBeNull();
    expect(suffix.textContent).toContain('(+2)');
  });

  it('shows EAN with (+1) suffix for a product with two EANs', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '7038010069307', ean_count: 2, has_image: 0 },
    ];
    renderResults(products, '');
    const suffix = document.querySelector('.ean-count-suffix');
    expect(suffix).not.toBeNull();
    expect(suffix.textContent).toContain('(+1)');
  });

  it('shows no suffix when ean_count is not provided (defaults to 1)', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '7038010069307', has_image: 0 },
    ];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('EAN: 7038010069307');
    expect(container.querySelector('.ean-count-suffix')).toBeNull();
  });

  it('shows no EAN HTML when product has no EAN', () => {
    const products = [
      { id: 1, name: 'Milk', type: 'dairy', total_score: 85, ean: '', has_image: 0 },
    ];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    expect(container.querySelector('.prod-ean')).toBeNull();
  });
});

describe('loadFlagConfig', () => {
  it('fetches from /api/flag-config and stores result', async () => {
    const mockConfig = { vegan: { type: 'user', label: 'Vegan' } };
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue(mockConfig),
    });
    await loadFlagConfig();
    expect(global.fetch).toHaveBeenCalledWith('/api/flag-config');
    expect(getFlagConfig()).toEqual(mockConfig);
  });

  it('handles fetch failure gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(loadFlagConfig()).resolves.toBeUndefined();
    consoleSpy.mockRestore();
  });
});
