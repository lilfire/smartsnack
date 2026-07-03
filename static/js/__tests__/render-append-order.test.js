// Regression tests for LSO-1700 Bug 2: appendResults must preserve the
// server-provided page order. Re-sorting each page independently produces a
// sawtooth ordering across infinite-scroll pages.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
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
    catEmoji: vi.fn(() => '📦'),
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

vi.mock('../i18n.js', () => ({ t: vi.fn((key) => key) }));

// applySorting actually sorts here, so any (unwanted) re-sort inside
// appendResults visibly reorders the rows.
vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    applySorting: vi.fn((results) => [...results].sort((a, b) => (b.total_score || 0) - (a.total_score || 0))),
    sortIndicator: vi.fn(() => '↕'),
    rerender: vi.fn(),
  };
});

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../settings-weights.js', () => ({
  SCORE_COLORS: { kcal: '#aa66ff', protein: '#00d4ff' },
  SCORE_CFG_MAP: { kcal: { label: 'Kcal' }, protein: { label: 'Protein' } },
  weightData: [],
}));

vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
}));

import { appendResults } from '../render.js';
import { applySorting } from '../filters.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '<div id="results-container"><div class="table-wrap"></div></div>';
  Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true, configurable: true });
});

function rowIds() {
  return Array.from(document.querySelectorAll('#results-container .table-row'))
    .map((r) => Number(r.dataset.productId));
}

describe('appendResults ordering', () => {
  it('preserves the incoming (server) order instead of re-sorting the page', () => {
    // Server order for this page: not sorted by total_score
    const page = [
      { id: 1, name: 'A', type: 'snack', total_score: 3.2 },
      { id: 2, name: 'B', type: 'snack', total_score: 9.9 },
      { id: 3, name: 'C', type: 'snack', total_score: 1.1 },
    ];
    appendResults(page);
    expect(rowIds()).toEqual([1, 2, 3]);
    expect(applySorting).not.toHaveBeenCalled();
  });

  it('keeps global ordering across successive pages', () => {
    // Two server-sorted pages; page 2 continues where page 1 ended.
    appendResults([
      { id: 10, name: 'P1a', type: 'snack', total_score: 9.0 },
      { id: 11, name: 'P1b', type: 'snack', total_score: 8.0 },
    ]);
    appendResults([
      { id: 12, name: 'P2a', type: 'snack', total_score: 7.0 },
      { id: 13, name: 'P2b', type: 'snack', total_score: 6.0 },
    ]);
    expect(rowIds()).toEqual([10, 11, 12, 13]);
  });

  it('does nothing when the table wrap is missing', () => {
    document.body.innerHTML = '';
    expect(() => appendResults([{ id: 1, name: 'A', type: 'snack' }])).not.toThrow();
  });
});
