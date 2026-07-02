import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedResults: [],
    imageCache: {},
  };
  return {
    state: _state,
    catEmoji: vi.fn(() => '📦'),
    catLabel: vi.fn((t) => t),
    esc: (s) => String(s),
    safeDataUri: vi.fn((u) => u || ''),
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue({ products: [], total: 0 }),
    trapFocus: vi.fn(() => vi.fn()),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  buildFilters: vi.fn(),
  rerender: vi.fn(),
}));

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../products.js', () => ({
  showToast: vi.fn(),
  switchView: vi.fn(),
  loadData: vi.fn().mockResolvedValue(),
}));

vi.mock('../off-utils.js', () => ({
  validateOffBtn: vi.fn(),
}));
vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn(),
}));

import { showScanProductPicker, scanPickerSelect, closeScanPicker } from '../scan-picker.js';
import { api } from '../state.js';
import { showToast } from '../products.js';

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  document.body.innerHTML = '';
  document.body.style.overflow = '';
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  document.body.innerHTML = '';
});

// H6 regression (LSO-1684): the GET /api/products/:id payload includes the
// computed `has_image` column, which update_product rejects with 400
// "Invalid field". The PUT body must never echo computed fields back.
describe('scanPickerSelect strips computed fields (H6)', () => {
  const gotProduct = {
    id: 5, name: 'Melkesjokolade', type: 'Snacks', ean: '',
    brand: 'Freia', kcal: 530, protein: 8, has_image: 1,
  };

  it('does not include has_image in the PUT body', async () => {
    showScanProductPicker('7038010000000');
    api.mockResolvedValueOnce({ ...gotProduct }) // GET product
       .mockResolvedValueOnce({});               // PUT product
    await scanPickerSelect(5);

    const putCall = api.mock.calls.find((c) => c[1] && c[1].method === 'PUT');
    expect(putCall).toBeDefined();
    expect(putCall[0]).toBe('/api/products/5');
    const body = JSON.parse(putCall[1].body);
    expect('has_image' in body).toBe(false);
  });

  it('sets the scanned EAN on the PUT body and keeps real fields', async () => {
    showScanProductPicker('7038010000000');
    api.mockResolvedValueOnce({ ...gotProduct })
       .mockResolvedValueOnce({});
    await scanPickerSelect(5);

    const putCall = api.mock.calls.find((c) => c[1] && c[1].method === 'PUT');
    const body = JSON.parse(putCall[1].body);
    expect(body.ean).toBe('7038010000000');
    expect(body.name).toBe('Melkesjokolade');
    expect(body.kcal).toBe(530);
  });

  it('shows success toast and the OFF confirm modal after saving', async () => {
    showScanProductPicker('7038010000000');
    api.mockResolvedValueOnce({ ...gotProduct })
       .mockResolvedValueOnce({});
    await scanPickerSelect(5);

    expect(showToast).toHaveBeenCalledWith('toast_ean_saved', 'success');
    expect(document.getElementById('scan-off-confirm-bg')).not.toBeNull();
  });

  it('shows error toast and no OFF confirm modal when the PUT fails', async () => {
    showScanProductPicker('7038010000000');
    api.mockResolvedValueOnce({ ...gotProduct })
       .mockRejectedValueOnce(new Error('400 Invalid field'));
    await scanPickerSelect(5);

    expect(showToast).toHaveBeenCalledWith('toast_ean_save_error', 'error');
    expect(document.getElementById('scan-off-confirm-bg')).toBeNull();
  });

  it('shows error toast when the GET fails', async () => {
    showScanProductPicker('7038010000000');
    api.mockRejectedValueOnce(new Error('network down'));
    await scanPickerSelect(5);

    expect(showToast).toHaveBeenCalledWith('toast_ean_save_error', 'error');
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('does nothing when no picker EAN is active', async () => {
    closeScanPicker();
    await scanPickerSelect(5);
    expect(api).not.toHaveBeenCalled();
  });
});
