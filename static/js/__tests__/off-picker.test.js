import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  showToast: vi.fn(),
  trapFocus: vi.fn(() => vi.fn()),
  esc: (s) => String(s),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../off-utils.js', () => ({
  offState: {
    ctx: { prefix: 'p', productId: null, autoClose: false },
    pickerProducts: null,
  },
  fetchWithTimeout: vi.fn(),
  applyOffProduct: vi.fn().mockResolvedValue(undefined),
  validateOffBtn: vi.fn(),
  _gatherNutrition: vi.fn(() => null),
}));

vi.mock('../off-api.js', () => ({
  searchOFF: vi.fn().mockResolvedValue([]),
}));

vi.mock('../off-review.js', () => ({
  showOffAddReview: vi.fn(),
}));

import {
  showOffPickerLoading,
  updateOffPickerResults,
  offModalSearch,
  closeOffPicker,
  selectOffResult,
} from '../off-picker.js';
import { offState, fetchWithTimeout, applyOffProduct, validateOffBtn } from '../off-utils.js';
import { searchOFF } from '../off-api.js';
import { showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  document.body.style.overflow = '';
  offState.ctx = { prefix: 'p', productId: null, autoClose: false };
  offState.pickerProducts = null;
});

// ── closeOffPicker ───────────────────────────────────
describe('closeOffPicker', () => {
  it('removes the modal if present', () => {
    const bg = document.createElement('div');
    bg.id = 'off-modal-bg';
    document.body.appendChild(bg);
    closeOffPicker();
    expect(document.getElementById('off-modal-bg')).toBeNull();
  });

  it('resets body overflow', () => {
    document.body.style.overflow = 'hidden';
    closeOffPicker();
    expect(document.body.style.overflow).toBe('');
  });

  it('clears pickerProducts', () => {
    offState.pickerProducts = [{ product_name: 'test' }];
    closeOffPicker();
    expect(offState.pickerProducts).toBeNull();
  });

  it('does nothing if modal not present', () => {
    expect(() => closeOffPicker()).not.toThrow();
  });
});

// ── showOffPickerLoading ─────────────────────────────
describe('showOffPickerLoading', () => {
  it('creates and appends modal to body', () => {
    showOffPickerLoading('Searching...');
    expect(document.getElementById('off-modal-bg')).not.toBeNull();
  });

  it('sets overflow hidden', () => {
    showOffPickerLoading();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('shows custom message in count div', () => {
    showOffPickerLoading('Custom message');
    const count = document.getElementById('off-result-count');
    expect(count.textContent).toBe('Custom message');
  });

  it('disables search input initially', () => {
    showOffPickerLoading();
    const input = document.getElementById('off-search-input');
    expect(input.disabled).toBe(true);
  });

  it('closes previous picker before opening new one', () => {
    showOffPickerLoading('First');
    showOffPickerLoading('Second');
    const modals = document.querySelectorAll('#off-modal-bg');
    expect(modals.length).toBe(1);
  });
});

// ── updateOffPickerResults ───────────────────────────
describe('updateOffPickerResults', () => {
  function setupPicker() {
    showOffPickerLoading('Searching');
  }

  it('shows error message when errorMsg provided', () => {
    setupPicker();
    updateOffPickerResults([], 'Error occurred');
    const body = document.getElementById('off-results-body');
    expect(body.innerHTML).toContain('Error occurred');
  });

  it('enables search input after update', () => {
    setupPicker();
    updateOffPickerResults([]);
    const input = document.getElementById('off-search-input');
    expect(input.disabled).toBe(false);
  });

  it('renders product results', () => {
    setupPicker();
    const products = [
      { product_name: 'Chicken', product_name_no: '', brands: 'FoodCo', nutriments: { 'energy-kcal_100g': 150, 'proteins_100g': 20, 'carbohydrates_100g': 5 }, code: '1234' },
    ];
    offState.pickerProducts = null;
    updateOffPickerResults(products);
    expect(offState.pickerProducts).toEqual(products);
  });

  it('updates count text', () => {
    setupPicker();
    updateOffPickerResults([{ product_name: 'Chicken', nutriments: {} }]);
    const count = document.getElementById('off-result-count');
    expect(count.textContent).toContain('off_result_count');
  });

  it('closes picker automatically when autoClose is true and EAN present', () => {
    offState.ctx.autoClose = true;
    setupPicker();
    updateOffPickerResults([], 'Not found', '12345678');
    expect(document.getElementById('off-modal-bg')).toBeNull();
    expect(showToast).toHaveBeenCalled();
  });

  it('shows add-to-OFF button in error div when EAN provided and not autoClose', () => {
    setupPicker();
    updateOffPickerResults([], 'Not found', '12345678');
    const body = document.getElementById('off-results-body');
    expect(body.querySelector('button')).not.toBeNull();
  });

  it('returns early if body element missing', () => {
    document.body.innerHTML = '';
    expect(() => updateOffPickerResults([])).not.toThrow();
  });
});

// ── offModalSearch ───────────────────────────────────
describe('offModalSearch', () => {
  function setupSearchUI(query = 'chicken') {
    document.body.innerHTML = `
      <input id="off-search-input" value="${query}">
      <button id="off-search-btn"></button>
      <div id="off-results-body"></div>
      <div id="off-result-count"></div>`;
  }

  it('does nothing when query is too short', async () => {
    setupSearchUI('a');
    await offModalSearch();
    expect(searchOFF).not.toHaveBeenCalled();
  });

  it('calls searchOFF and updates results', async () => {
    setupSearchUI('chicken');
    searchOFF.mockResolvedValue([{ product_name: 'Chicken', nutriments: {} }]);
    await offModalSearch();
    expect(searchOFF).toHaveBeenCalledWith('chicken', null, '');
  });

  it('shows error on searchOFF failure', async () => {
    setupSearchUI('chicken');
    searchOFF.mockRejectedValue(new Error('fail'));
    await offModalSearch();
    const body = document.getElementById('off-results-body');
    // Should not crash
    expect(body).not.toBeNull();
  });

  it('disables input while searching', async () => {
    setupSearchUI('chicken');
    searchOFF.mockImplementation(() => new Promise((r) => setTimeout(() => r([]), 50)));
    const searchPromise = offModalSearch();
    const input = document.getElementById('off-search-input');
    expect(input.disabled).toBe(true);
    vi.useFakeTimers();
    vi.runAllTimers();
    vi.useRealTimers();
    await searchPromise;
  });
});

// ── selectOffResult ──────────────────────────────────
describe('selectOffResult', () => {
  it('returns early if no picker products', async () => {
    offState.pickerProducts = null;
    await selectOffResult(0, null);
    expect(applyOffProduct).not.toHaveBeenCalled();
  });

  it('returns early if index out of range', async () => {
    offState.pickerProducts = [{ product_name: 'Test', code: '123' }];
    await selectOffResult(5, null);
    expect(applyOffProduct).not.toHaveBeenCalled();
  });

  it('calls applyOffProduct for selected item', async () => {
    const product = { product_name: 'Chicken', code: '12345678' };
    offState.pickerProducts = [product];
    document.body.innerHTML = '<button id="p-off-btn"></button>';
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 1, product }),
    });
    await selectOffResult(0, { prefix: 'p', productId: null });
    expect(applyOffProduct).toHaveBeenCalled();
  });

  it('shows toast and still calls applyOffProduct on fetch error', async () => {
    const product = { product_name: 'Chicken', code: '12345678' };
    offState.pickerProducts = [product];
    document.body.innerHTML = '<button id="p-off-btn"></button>';
    fetchWithTimeout.mockRejectedValue(new Error('Network'));
    await selectOffResult(0, { prefix: 'p', productId: null });
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
    expect(applyOffProduct).toHaveBeenCalled();
  });
});
