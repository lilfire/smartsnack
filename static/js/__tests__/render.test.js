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
  };
  return {
    state: _state,
    esc: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    safeDataUri: (uri) => typeof uri === 'string' && uri.startsWith('data:') ? uri : '',
    catEmoji: vi.fn((type) => '📦'),
    catLabel: vi.fn((type) => type),
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  applySorting: vi.fn((results) => results),
  sortIndicator: vi.fn((col) => '↕'),
}));

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

describe('getFlagConfig', () => {
  it('returns an object', () => {
    const cfg = getFlagConfig();
    expect(cfg).toBeTypeOf('object');
    expect(cfg).not.toBeNull();
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
