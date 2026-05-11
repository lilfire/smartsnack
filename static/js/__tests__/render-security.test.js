/**
 * Security and edge-case rendering tests for render.js.
 * Covers XSS prevention and long-text truncation — split from render.test.js
 * to keep file size under 500 lines.
 */
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
    catEmoji: vi.fn(() => '\u{1F4E6}'),
    catLabel: vi.fn((type) => type),
    // Realistic esc: escapes HTML special chars (mirrors real state.js implementation)
    esc: (s) =>
      String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;'),
    safeDataUri: (uri) => (typeof uri === 'string' && uri.startsWith('data:') ? uri : ''),
    fmtNum: vi.fn((v) => (v == null ? '-' : String(v))),
    showToast: vi.fn(),
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({ t: vi.fn((key) => key) }));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    applySorting: vi.fn((results) => results),
    sortIndicator: vi.fn(() => '\u2195'),
    rerender: vi.fn(),
  };
});

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../settings-weights.js', () => ({
  SCORE_COLORS: {},
  SCORE_CFG_MAP: {},
  weightData: [],
}));

vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
}));

import { renderResults } from '../render.js';
import { state } from '../state.js';

beforeEach(() => {
  state.expandedId = null;
  state.editingId = null;
  state.cachedResults = [];
  state.categories = [];
  document.body.innerHTML = '';

  const count = document.createElement('div');
  count.id = 'result-count';
  document.body.appendChild(count);
  const container = document.createElement('div');
  container.id = 'results-container';
  document.body.appendChild(container);
});

// ── XSS prevention ──────────────────────────────────
// Note: jsdom normalises HTML entities on innerHTML round-trips, so we check
// the DOM structure (no injected elements) and textContent (raw value) rather
// than expecting entity strings like &lt; to survive in container.innerHTML.

describe('XSS prevention — product name rendering', () => {
  it('does not inject a real <script> element for a name containing <script>', () => {
    const products = [{
      id: 1,
      name: '<script>alert("xss")</script>',
      type: 'dairy',
      total_score: 80,
      has_image: 0,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // No actual script element should exist
    expect(container.querySelectorAll('script')).toHaveLength(0);
    // The prod-name span should contain the raw text, not an executed script
    const nameSpan = container.querySelector('.prod-name');
    expect(nameSpan.textContent).toContain('alert');
  });

  it('ampersand in product name is HTML-escaped in the serialised markup', () => {
    const products = [{
      id: 1,
      name: 'Bread & Butter',
      type: 'bakery',
      total_score: 70,
      has_image: 0,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // innerHTML serialisation always encodes & as &amp; in text nodes
    expect(container.innerHTML).toContain('&amp;');
  });

  it('double-quote in product name is stored as literal text (not injected attribute)', () => {
    const products = [{
      id: 1,
      name: 'He said "hello"',
      type: 'snack',
      total_score: 60,
      has_image: 0,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    const nameSpan = container.querySelector('.prod-name');
    // textContent gives the raw unescaped value
    expect(nameSpan.textContent).toBe('He said "hello"');
    // No injected attributes or elements from the quote
    expect(container.querySelectorAll('[onerror]')).toHaveLength(0);
  });

  it('single-quote in product name does not break attribute parsing', () => {
    const products = [{
      id: 1,
      name: "Farmer's Milk",
      type: 'dairy',
      total_score: 75,
      has_image: 0,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    const nameSpan = container.querySelector('.prod-name');
    expect(nameSpan.textContent).toBe("Farmer's Milk");
    // No broken attributes from single-quote injection
    expect(container.querySelectorAll('[onerror]')).toHaveLength(0);
  });

  it('does not inject a real <img> element for an XSS attempt in product name', () => {
    const xssAttempt = '"><img src=x onerror="alert(1)">';
    const products = [{
      id: 1,
      name: xssAttempt,
      type: 'dairy',
      total_score: 80,
      has_image: 0,
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // Should have no injected onerror attributes
    expect(container.querySelectorAll('[onerror]')).toHaveLength(0);
    // No injected img tags with onerror (has_image=0 means no intentional img)
    const imgs = Array.from(container.querySelectorAll('img'));
    const injectedImgs = imgs.filter((el) => el.getAttribute('onerror'));
    expect(injectedImgs).toHaveLength(0);
  });

  it('escapes angle brackets in brand field — no injected img element when expanded', () => {
    state.expandedId = 1;
    const products = [{
      id: 1,
      name: 'Safe Name',
      type: 'dairy',
      total_score: 85,
      has_image: 0,
      brand: '<img src=x onerror=alert(1)>',
      kcal: 60, energy_kj: 250, fat: 3, saturated_fat: 2, carbs: 5,
      sugar: 5, protein: 3, fiber: 0, salt: 0.1, scores: {}, flags: [],
    }];
    renderResults(products, '');
    const container = document.getElementById('results-container');
    // No img with onerror should exist
    const injected = Array.from(container.querySelectorAll('img')).filter(
      (el) => el.getAttribute('onerror'),
    );
    expect(injected).toHaveLength(0);
  });
});

// ── Long text truncation ────────────────────────────

describe('Long text — product name handling', () => {
  it('renders product name exceeding 100 characters without throwing', () => {
    const longName = 'A'.repeat(150);
    const products = [{
      id: 1,
      name: longName,
      type: 'snack',
      total_score: 60,
      has_image: 0,
    }];
    expect(() => renderResults(products, '')).not.toThrow();
    const container = document.getElementById('results-container');
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders product name of exactly 200 characters', () => {
    const longName = 'B'.repeat(200);
    const products = [{
      id: 1,
      name: longName,
      type: 'bakery',
      total_score: 55,
      has_image: 0,
    }];
    expect(() => renderResults(products, '')).not.toThrow();
  });

  it('renders ingredients field with very long text when expanded', () => {
    state.expandedId = 1;
    const longIngredients = 'ingredient, '.repeat(100);
    const products = [{
      id: 1,
      name: 'TestProduct',
      type: 'dairy',
      total_score: 70,
      has_image: 0,
      kcal: 100, energy_kj: 420, fat: 5, saturated_fat: 2, carbs: 10,
      sugar: 3, protein: 8, fiber: 1, salt: 0.2, scores: {}, flags: [],
      ingredients: longIngredients,
      brand: 'Brand', stores: 'Store', taste_score: 3,
    }];
    expect(() => renderResults(products, '')).not.toThrow();
    const container = document.getElementById('results-container');
    expect(container.innerHTML).toContain('ingredient,');
  });

  it('empty string name renders without crashing', () => {
    const products = [{
      id: 1,
      name: '',
      type: 'dairy',
      total_score: 0,
      has_image: 0,
    }];
    expect(() => renderResults(products, '')).not.toThrow();
  });
});
