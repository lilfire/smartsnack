import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MOCK_OFF_SEARCH_RESULTS } from './mock-shapes.js';

vi.mock('../state.js', () => ({
  showToast: vi.fn(),
  api: vi.fn().mockResolvedValue({ products: [], total: 0 }),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../off-utils.js', () => ({
  fetchWithTimeout: vi.fn(),
  isValidEan: vi.fn((v) => !!(v && /^\d{8,13}$/.test(String(v).replace(/\s/g, '')))),
  offState: { ctx: { prefix: 'p', productId: null, autoClose: false } },
  _gatherNutrition: vi.fn(() => null),
  applyOffProduct: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../off-picker.js', () => ({
  showOffPickerLoading: vi.fn(),
  updateOffPickerResults: vi.fn(),
  closeOffPicker: vi.fn(),
}));

import { lookupOFF, searchOFF } from '../off-api.js';
import { showToast } from '../state.js';
import { fetchWithTimeout, isValidEan, offState, applyOffProduct } from '../off-utils.js';
import { showOffPickerLoading, updateOffPickerResults, closeOffPicker } from '../off-picker.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
});

// ── searchOFF ────────────────────────────────────────
describe('searchOFF', () => {
  it('sends query and returns filtered products', async () => {
    const products = [
      { product_name: 'Chicken', nutriments: {} },
      { product_name: '', product_name_no: '', nutriments: {} }, // filtered out
    ];
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products }),
    });
    const result = await searchOFF('chicken', null, '');
    expect(result).toHaveLength(1);
    expect(result[0].product_name).toBe('Chicken');
  });

  it('sends nutrition and category when provided', async () => {
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [] }),
    });
    await searchOFF('test', { kcal: 100 }, 'dairy');
    expect(fetchWithTimeout).toHaveBeenCalledWith(
      '/api/off/search',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"kcal":100'),
      }),
    );
  });

  it('throws when response not ok', async () => {
    fetchWithTimeout.mockResolvedValue({ ok: false, status: 500 });
    await expect(searchOFF('test', null, '')).rejects.toThrow('Search failed: 500');
  });

  it('returns empty array when no products key', async () => {
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    const result = await searchOFF('test', null, '');
    expect(result).toEqual([]);
  });

  it('omits nutrition from body when null', async () => {
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [] }),
    });
    await searchOFF('test', null, '');
    const call = fetchWithTimeout.mock.calls[0][1];
    const body = JSON.parse(call.body);
    expect(body).not.toHaveProperty('nutrition');
  });
});

// ── searchOFF — nutriments and filtering ─────────────
describe('searchOFF — nutriments shape', () => {
  it('preserves full nutriments object on returned products', async () => {
    const products = [
      {
        product_name: 'Chicken',
        nutriments: {
          'energy-kcal_100g': 165,
          'fat_100g': 3.6,
          'carbohydrates_100g': 0,
          'proteins_100g': 31.0,
          'salt_100g': 0.17,
          'fiber_100g': 0,
        },
      },
    ];
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products }),
    });
    const result = await searchOFF('chicken', null, '');
    expect(result[0].nutriments).toMatchObject({
      'energy-kcal_100g': 165,
      'proteins_100g': 31.0,
    });
  });

  it('filters out products with empty product_name and product_name_no', async () => {
    const products = [
      { product_name: 'ValidProduct', nutriments: {} },
      { product_name: '', product_name_no: null, nutriments: {} },
      { product_name: '', product_name_no: 'NorwegianProduct', nutriments: {} },
    ];
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products }),
    });
    const result = await searchOFF('test', null, '');
    // Only products with at least one non-empty name field
    expect(result.some((p) => p.product_name === 'ValidProduct')).toBe(true);
    expect(result.some((p) => p.product_name_no === 'NorwegianProduct')).toBe(true);
    expect(result.length).toBe(2);
  });

  it('sends category in body when provided', async () => {
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [] }),
    });
    await searchOFF('yogurt', null, 'dairy');
    const call = fetchWithTimeout.mock.calls[0][1];
    const body = JSON.parse(call.body);
    expect(body.category).toBe('dairy');
  });

  it('omits category from body when empty string provided', async () => {
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [] }),
    });
    await searchOFF('test', null, '');
    const call = fetchWithTimeout.mock.calls[0][1];
    const body = JSON.parse(call.body);
    expect(body.category).toBeUndefined();
  });
});

// ── lookupOFF ────────────────────────────────────────
describe('lookupOFF', () => {
  function setupDOM(ean = '', name = '') {
    document.body.innerHTML = `
      <input id="p-ean" value="${ean}">
      <input id="p-name" value="${name}">
      <input id="p-type" value="">`;
  }

  it('shows loading when valid EAN and calls applyOffProduct on success', async () => {
    setupDOM('12345678', '');
    const product = { product_name: 'Test' };
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 1, product }),
    });
    await lookupOFF('p', null, {});
    expect(showOffPickerLoading).toHaveBeenCalled();
    expect(applyOffProduct).toHaveBeenCalledWith(product, 'p', null, false);
    expect(closeOffPicker).toHaveBeenCalled();
  });

  it('shows updateOffPickerResults with error when product not found', async () => {
    setupDOM('12345678', '');
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 0, product: null }),
    });
    await lookupOFF('p', null, {});
    expect(updateOffPickerResults).toHaveBeenCalledWith([], expect.any(String), '12345678');
  });

  it('shows network error when fetch fails for EAN lookup', async () => {
    setupDOM('12345678', '');
    fetchWithTimeout.mockRejectedValue(new Error('Network'));
    await lookupOFF('p', null, {});
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls searchOFF when valid name provided (no valid EAN)', async () => {
    setupDOM('', 'chicken');
    fetchWithTimeout.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [] }),
    });
    isValidEan.mockReturnValueOnce(false);
    await lookupOFF('p', null, {});
    expect(showOffPickerLoading).toHaveBeenCalled();
    expect(updateOffPickerResults).toHaveBeenCalled();
  });

  it('does nothing when neither valid EAN nor name', async () => {
    setupDOM('', 'a');
    isValidEan.mockReturnValueOnce(false);
    await lookupOFF('p', null, {});
    expect(showOffPickerLoading).not.toHaveBeenCalled();
  });

  it('shows updateOffPickerResults with error on non-ok response for EAN', async () => {
    setupDOM('12345678', '');
    fetchWithTimeout.mockResolvedValue({ ok: false });
    await lookupOFF('p', null, {});
    expect(updateOffPickerResults).toHaveBeenCalledWith([], expect.any(String));
  });
});
