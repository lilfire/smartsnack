import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

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
    catEmoji: vi.fn(() => '\u{1F4E6}'),
    catLabel: vi.fn((t) => t),
    esc: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    safeDataUri: vi.fn((uri) => uri || ''),
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
  t: vi.fn((key, params) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  }),
}));

import { sortIndicator, applySorting, setSort, buildFilters, updateFilterToggle, toggleFilters, buildTypeSelect, rerender } from '../filters.js';
import { state } from '../state.js';
import { t } from '../i18n.js';

beforeEach(() => {
  state.currentFilter = [];
  state.sortCol = 'total_score';
  state.sortDir = 'desc';
  state.categories = [];
  state.cachedStats = null;
  state.cachedResults = [];
  document.body.innerHTML = '';
});

describe('sortIndicator', () => {
  it('returns dim arrow for non-active column', () => {
    state.sortCol = 'total_score';
    expect(sortIndicator('name')).toContain('dim');
    expect(sortIndicator('name')).toContain('↕');
  });

  it('returns up arrow for active ascending column', () => {
    state.sortCol = 'name';
    state.sortDir = 'asc';
    expect(sortIndicator('name')).toContain('↑');
    expect(sortIndicator('name')).not.toContain('dim');
  });

  it('returns down arrow for active descending column', () => {
    state.sortCol = 'name';
    state.sortDir = 'desc';
    expect(sortIndicator('name')).toContain('↓');
  });
});

describe('applySorting', () => {
  it('sorts strings ascending', () => {
    state.sortCol = 'name';
    state.sortDir = 'asc';
    const results = [{ name: 'Banana' }, { name: 'Apple' }, { name: 'Cherry' }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.name)).toEqual(['Apple', 'Banana', 'Cherry']);
  });

  it('sorts strings descending', () => {
    state.sortCol = 'name';
    state.sortDir = 'desc';
    const results = [{ name: 'Banana' }, { name: 'Apple' }, { name: 'Cherry' }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.name)).toEqual(['Cherry', 'Banana', 'Apple']);
  });

  it('sorts numbers ascending', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'asc';
    const results = [{ kcal: 300 }, { kcal: 100 }, { kcal: 200 }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.kcal)).toEqual([100, 200, 300]);
  });

  it('sorts numbers descending', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'desc';
    const results = [{ kcal: 300 }, { kcal: 100 }, { kcal: 200 }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.kcal)).toEqual([300, 200, 100]);
  });

  it('handles null values in ascending sort (nulls last)', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'asc';
    const results = [{ kcal: null }, { kcal: 100 }, { kcal: 200 }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.kcal)).toEqual([100, 200, null]);
  });

  it('handles null values in descending sort (nulls last)', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'desc';
    const results = [{ kcal: null }, { kcal: 100 }, { kcal: 200 }];
    const sorted = applySorting(results);
    expect(sorted.map((r) => r.kcal)).toEqual([200, 100, null]);
  });

  it('handles null string values', () => {
    state.sortCol = 'name';
    state.sortDir = 'asc';
    const results = [{ name: null }, { name: 'Apple' }];
    const sorted = applySorting(results);
    // null coerced to '' for comparison but original value stays null
    expect(sorted[0].name).toBeNull();
    expect(sorted[1].name).toBe('Apple');
  });

  it('does not mutate original array', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'asc';
    const results = [{ kcal: 200 }, { kcal: 100 }];
    const sorted = applySorting(results);
    expect(results[0].kcal).toBe(200);
    expect(sorted[0].kcal).toBe(100);
  });
});

describe('setSort', () => {
  it('toggles direction when same column', () => {
    state.sortCol = 'name';
    state.sortDir = 'desc';
    // setSort calls rerender which does a dynamic import; mock it
    vi.mock('../render.js', () => ({ renderResults: vi.fn() }));
    setSort('name');
    expect(state.sortDir).toBe('asc');
  });

  it('changes column and sets default direction (desc for non-name)', () => {
    state.sortCol = 'name';
    state.sortDir = 'asc';
    setSort('kcal');
    expect(state.sortCol).toBe('kcal');
    expect(state.sortDir).toBe('desc');
  });

  it('sets asc for name column', () => {
    state.sortCol = 'kcal';
    state.sortDir = 'desc';
    setSort('name');
    expect(state.sortCol).toBe('name');
    expect(state.sortDir).toBe('asc');
  });
});

describe('buildFilters', () => {
  beforeEach(() => {
    const row = document.createElement('div');
    row.id = 'filter-row';
    document.body.appendChild(row);
    const tog = document.createElement('div');
    tog.id = 'filter-toggle';
    document.body.appendChild(tog);
    const label = document.createElement('span');
    label.id = 'filter-toggle-label';
    document.body.appendChild(label);
  });

  it('does nothing without cachedStats', () => {
    state.cachedStats = null;
    buildFilters();
    expect(document.getElementById('filter-row').children.length).toBe(0);
  });

  it('creates All button and category pills', () => {
    state.cachedStats = { total: 5, type_counts: { dairy: 3, meat: 2 } };
    state.categories = [
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
    ];
    buildFilters();
    const buttons = document.getElementById('filter-row').querySelectorAll('button');
    expect(buttons.length).toBe(3); // All + 2 categories
    expect(buttons[0].textContent).toContain('filter_all');
    expect(buttons[1].textContent).toContain('Dairy');
    expect(buttons[2].textContent).toContain('Meat');
  });

  it('marks All button active when no filters', () => {
    state.cachedStats = { total: 5, type_counts: {} };
    state.categories = [];
    state.currentFilter = [];
    buildFilters();
    const allBtn = document.getElementById('filter-row').querySelector('button');
    expect(allBtn.className).toContain('active');
  });

  it('marks category pill active when filter active', () => {
    state.cachedStats = { total: 5, type_counts: { dairy: 3 } };
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    state.currentFilter = ['dairy'];
    buildFilters();
    const pills = document.getElementById('filter-row').querySelectorAll('button');
    expect(pills[0].className).not.toContain('active'); // All not active
    expect(pills[1].className).toContain('active'); // Dairy active
  });
});

describe('updateFilterToggle', () => {
  beforeEach(() => {
    const tog = document.createElement('div');
    tog.id = 'filter-toggle';
    document.body.appendChild(tog);
    const label = document.createElement('span');
    label.id = 'filter-toggle-label';
    document.body.appendChild(label);
  });

  it('shows filter_all when no filters active', () => {
    state.currentFilter = [];
    updateFilterToggle();
    expect(document.getElementById('filter-toggle-label').textContent).toBe('filter_all');
  });

  it('shows category names when 1-2 filters active', () => {
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    state.currentFilter = ['dairy'];
    updateFilterToggle();
    expect(document.getElementById('filter-toggle-label').textContent).toContain('Dairy');
  });

  it('shows count when more than 2 filters active', () => {
    state.categories = [
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
      { name: 'snack', emoji: '🍿', label: 'Snack' },
    ];
    state.currentFilter = ['dairy', 'meat', 'snack'];
    updateFilterToggle();
    expect(document.getElementById('filter-toggle-label').textContent).toContain('filter_count');
  });

  it('adds has-filter class when filters active', () => {
    state.currentFilter = ['dairy'];
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    updateFilterToggle();
    expect(document.getElementById('filter-toggle').classList.contains('has-filter')).toBe(true);
  });

  it('removes has-filter class when no filters', () => {
    const tog = document.getElementById('filter-toggle');
    tog.classList.add('has-filter');
    state.currentFilter = [];
    updateFilterToggle();
    expect(tog.classList.contains('has-filter')).toBe(false);
  });
});

describe('toggleFilters', () => {
  it('toggles open class on filter row and toggle', () => {
    const row = document.createElement('div');
    row.id = 'filter-row';
    const tog = document.createElement('div');
    tog.id = 'filter-toggle';
    document.body.appendChild(row);
    document.body.appendChild(tog);

    toggleFilters();
    expect(row.classList.contains('open')).toBe(true);
    expect(tog.classList.contains('open')).toBe(true);

    toggleFilters();
    expect(row.classList.contains('open')).toBe(false);
    expect(tog.classList.contains('open')).toBe(false);
  });
});

describe('buildTypeSelect', () => {
  it('populates select with sorted categories', () => {
    const sel = document.createElement('select');
    sel.id = 'f-type';
    document.body.appendChild(sel);
    state.categories = [
      { name: 'meat', emoji: '🥩', label: 'Meat' },
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
    ];
    buildTypeSelect();
    const options = sel.querySelectorAll('option');
    expect(options.length).toBe(2);
    expect(options[0].textContent).toContain('Dairy');
    expect(options[1].textContent).toContain('Meat');
  });

  it('preserves previous selection', () => {
    const sel = document.createElement('select');
    sel.id = 'f-type';
    document.body.appendChild(sel);
    state.categories = [
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
    ];
    buildTypeSelect();
    sel.value = 'meat';
    buildTypeSelect();
    expect(sel.value).toBe('meat');
  });

  it('does nothing if select not found', () => {
    expect(() => buildTypeSelect()).not.toThrow();
  });
});

describe('rerender', () => {
  it('calls renderResults via dynamic import', async () => {
    const mockRenderResults = vi.fn();
    // Intercept the dynamic import by mocking it at module level
    vi.doMock('../render.js', () => ({ renderResults: mockRenderResults }));

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    searchInput.value = 'query';
    document.body.appendChild(searchInput);
    state.cachedResults = [{ id: 1, name: 'Milk' }];

    rerender();

    // Wait for the dynamic import promise to resolve
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockRenderResults).toHaveBeenCalledWith(state.cachedResults, 'query');
  });

  it('uses empty string when search-input not present', async () => {
    const mockRenderResults = vi.fn();
    vi.doMock('../render.js', () => ({ renderResults: mockRenderResults }));

    document.body.innerHTML = '';
    state.cachedResults = [];

    rerender();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockRenderResults).toHaveBeenCalledWith([], '');
  });
});
