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
    esc: (s) => String(s),
    safeDataUri: (uri) => uri || '',
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

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((dataUri) => Promise.resolve(dataUri)),
}));

import { isValidEan, validateOffBtn, searchOFF, closeOffPicker, closeOffAddReview, estimateProteinQuality, updateEstimateBtn, submitToOff, lookupOFF, selectOffResult, offModalSearch, showOffAddReview, showDuplicateMergeModal, showEditDuplicateModal, showMergeConflictModal } from '../openfoodfacts.js';
import { state, api, showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
});

describe('isValidEan', () => {
  it('returns true for 8-digit EAN', () => {
    expect(isValidEan('12345678')).toBe(true);
  });

  it('returns true for 13-digit EAN', () => {
    expect(isValidEan('1234567890123')).toBe(true);
  });

  it('returns true for 10-digit code', () => {
    expect(isValidEan('1234567890')).toBe(true);
  });

  it('returns false for too short', () => {
    expect(isValidEan('1234567')).toBe(false);
  });

  it('returns false for too long', () => {
    expect(isValidEan('12345678901234')).toBe(false);
  });

  it('returns false for non-numeric', () => {
    expect(isValidEan('abcdefgh')).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isValidEan('')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isValidEan(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isValidEan(undefined)).toBe(false);
  });

  it('trims whitespace', () => {
    expect(isValidEan(' 12345678 ')).toBe(true);
  });
});

describe('validateOffBtn', () => {
  beforeEach(() => {
    const ean = document.createElement('input');
    ean.id = 'ed-ean';
    ean.value = '';
    document.body.appendChild(ean);
    const name = document.createElement('input');
    name.id = 'ed-name';
    name.value = '';
    document.body.appendChild(name);
    const btn = document.createElement('button');
    btn.id = 'ed-off-btn';
    btn.disabled = true;
    document.body.appendChild(btn);
  });

  it('enables button when EAN is valid', () => {
    document.getElementById('ed-ean').value = '1234567890123';
    validateOffBtn('ed');
    expect(document.getElementById('ed-off-btn').disabled).toBe(false);
  });

  it('enables button when name >= 2 chars', () => {
    document.getElementById('ed-name').value = 'Milk';
    validateOffBtn('ed');
    expect(document.getElementById('ed-off-btn').disabled).toBe(false);
  });

  it('disables button when no valid EAN and name < 2', () => {
    document.getElementById('ed-ean').value = '123';
    document.getElementById('ed-name').value = 'M';
    validateOffBtn('ed');
    expect(document.getElementById('ed-off-btn').disabled).toBe(true);
  });
});

describe('searchOFF', () => {
  it('returns filtered products from OFF API', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [
          { product_name: 'Milk', code: '123' },
          { product_name_no: 'Melk', code: '456' },
          { code: '789' }, // no name - should be filtered out
        ],
      }),
    });
    const results = await searchOFF('milk');
    expect(results.length).toBe(2);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/off/search',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('"q":"milk"'),
      })
    );
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await expect(searchOFF('test')).rejects.toThrow('Search failed');
  });

  it('sends nutrition and category when provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [{ product_name: 'Milk' }] }),
    });
    const nutrition = { kcal: 60, protein: 3.3 };
    await searchOFF('milk', nutrition, 'dairy');
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.nutrition).toEqual(nutrition);
    expect(body.category).toBe('dairy');
  });

  it('returns empty array when products field is missing', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    const results = await searchOFF('test');
    expect(results).toEqual([]);
  });
});

describe('closeOffPicker', () => {
  it('removes modal from DOM', () => {
    const bg = document.createElement('div');
    bg.id = 'off-modal-bg';
    document.body.appendChild(bg);
    document.body.style.overflow = 'hidden';
    closeOffPicker();
    expect(document.getElementById('off-modal-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });

  it('does nothing when no modal exists', () => {
    expect(() => closeOffPicker()).not.toThrow();
  });
});

describe('closeOffAddReview', () => {
  it('removes review modal from DOM', () => {
    const bg = document.createElement('div');
    bg.id = 'off-add-review-bg';
    document.body.appendChild(bg);
    closeOffAddReview();
    expect(document.getElementById('off-add-review-bg')).toBeNull();
  });
});

describe('updateEstimateBtn', () => {
  it('shows wrap when ingredients present', () => {
    const ing = document.createElement('textarea');
    ing.id = 'ed-ingredients';
    ing.value = 'milk, sugar';
    document.body.appendChild(ing);
    const wrap = document.createElement('div');
    wrap.id = 'ed-protein-quality-wrap';
    wrap.style.display = 'none';
    document.body.appendChild(wrap);
    updateEstimateBtn('ed');
    expect(wrap.style.display).toBe('');
  });

  it('hides wrap when ingredients empty', () => {
    const ing = document.createElement('textarea');
    ing.id = 'ed-ingredients';
    ing.value = '';
    document.body.appendChild(ing);
    const wrap = document.createElement('div');
    wrap.id = 'ed-protein-quality-wrap';
    wrap.style.display = '';
    document.body.appendChild(wrap);
    updateEstimateBtn('ed');
    expect(wrap.style.display).toBe('none');
  });
});

describe('estimateProteinQuality', () => {
  beforeEach(() => {
    const els = [
      { tag: 'textarea', id: 'ed-ingredients', value: 'milk, whey protein' },
      { tag: 'button', id: 'ed-estimate-btn' },
      { tag: 'div', id: 'ed-pq-result' },
      { tag: 'span', id: 'ed-pdcaas-val' },
      { tag: 'span', id: 'ed-diaas-val' },
      { tag: 'div', id: 'ed-pq-sources' },
      { tag: 'input', id: 'ed-est_pdcaas', value: '' },
      { tag: 'input', id: 'ed-est_diaas', value: '' },
    ];
    els.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      if (value !== undefined) el.value = value;
      document.body.appendChild(el);
    });
  });

  it('posts ingredients and updates DOM on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: 0.85, est_diaas: 0.92, sources: ['whey'] }),
    });
    await estimateProteinQuality('ed');
    expect(document.getElementById('ed-pdcaas-val').textContent).toBe('0.85');
    expect(document.getElementById('ed-diaas-val').textContent).toBe('0.92');
    expect(document.getElementById('ed-est_pdcaas').value).toBe('0.85');
    expect(document.getElementById('ed-est_diaas').value).toBe('0.92');
    expect(showToast).toHaveBeenCalledWith('toast_protein_estimated', 'success');
  });

  it('shows error when ingredients empty', async () => {
    document.getElementById('ed-ingredients').value = '';
    await estimateProteinQuality('ed');
    expect(showToast).toHaveBeenCalledWith('toast_ingredients_missing', 'error');
  });

  it('shows error on network failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    await estimateProteinQuality('ed');
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });

  it('shows error when no sources found', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: null, est_diaas: null, sources: [] }),
    });
    await estimateProteinQuality('ed');
    expect(showToast).toHaveBeenCalledWith('toast_no_protein_sources', 'error');
  });

  it('re-enables button after completion', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: 0.85, est_diaas: 0.92, sources: [] }),
    });
    const btn = document.getElementById('ed-estimate-btn');
    await estimateProteinQuality('ed');
    expect(btn.disabled).toBe(false);
    expect(btn.classList.contains('loading')).toBe(false);
  });

  it('shows error when API returns error field', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ error: 'Some error' }),
    });
    await estimateProteinQuality('ed');
    expect(showToast).toHaveBeenCalledWith('toast_error_prefix', 'error');
  });

  it('handles fetch exception', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network fail'));
    await estimateProteinQuality('ed');
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    const btn = document.getElementById('ed-estimate-btn');
    expect(btn.disabled).toBe(false);
  });

  it('displays dash when pdcaas/diaas are null', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: null, est_diaas: null, sources: [] }),
    });
    await estimateProteinQuality('ed');
    expect(document.getElementById('ed-pdcaas-val').textContent).toBe('\u2013');
    expect(document.getElementById('ed-diaas-val').textContent).toBe('\u2013');
    expect(document.getElementById('ed-est_pdcaas').value).toBe('');
    expect(document.getElementById('ed-est_diaas').value).toBe('');
  });
});

describe('submitToOff', () => {
  it('sends product data to API', async () => {
    // Set up form fields that _offReviewFields expects
    const fields = [
      { id: 'ed-name', value: 'Test Milk' },
      { id: 'ed-brand', value: 'Brand' },
      { id: 'ed-stores', value: '' },
      { id: 'ed-ingredients', value: 'milk' },
      { id: 'ed-kcal', value: '60' },
      { id: 'ed-energy_kj', value: '250' },
      { id: 'ed-fat', value: '3.5' },
      { id: 'ed-saturated_fat', value: '2.3' },
      { id: 'ed-carbs', value: '4.8' },
      { id: 'ed-sugar', value: '4.8' },
      { id: 'ed-protein', value: '3.3' },
      { id: 'ed-fiber', value: '0' },
      { id: 'ed-salt', value: '0.1' },
      { id: 'ed-weight', value: '1000' },
      { id: 'ed-portion', value: '250' },
    ];
    fields.forEach(({ id, value }) => {
      const el = document.createElement('input');
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    const btn = document.createElement('button');
    btn.id = 'off-submit-btn';
    document.body.appendChild(btn);

    api.mockResolvedValueOnce({ status: 'ok' });
    await submitToOff('1234567890123');
    expect(api).toHaveBeenCalledWith('/api/off/add-product', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith('toast_off_product_added', 'success');
  });

  it('shows error on API error response', async () => {
    const btn = document.createElement('button');
    btn.id = 'off-submit-btn';
    document.body.appendChild(btn);

    api.mockRejectedValueOnce(new Error('off_err_no_credentials'));
    await submitToOff('1234567890123');
    expect(showToast).toHaveBeenCalledWith('off_err_no_credentials', 'error');
    expect(btn.disabled).toBe(false);
  });

  it('shows generic error when error message is not translatable', async () => {
    const btn = document.createElement('button');
    btn.id = 'off-submit-btn';
    document.body.appendChild(btn);

    // When t(msg) === msg (not translated), falls back to message
    api.mockRejectedValueOnce(new Error('some_unknown_error'));
    await submitToOff('1234567890123');
    expect(showToast).toHaveBeenCalledWith('some_unknown_error', 'error');
  });

  it('appends g unit to quantity and serving_size', async () => {
    // Set up _offCtx by calling lookupOFF with EAN to set prefix to 'ed'
    const ean = document.createElement('input');
    ean.id = 'ed-ean';
    ean.value = '1234567890123';
    document.body.appendChild(ean);
    const nameEl = document.createElement('input');
    nameEl.id = 'ed-name';
    nameEl.value = 'Test';
    document.body.appendChild(nameEl);
    const offBtn = document.createElement('button');
    offBtn.id = 'ed-off-btn';
    document.body.appendChild(offBtn);

    // Trigger lookupOFF to set _offCtx.prefix = 'ed'
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 1, product: { product_name: 'Test', nutriments: {} } }),
    });
    await lookupOFF('ed', null);
    vi.clearAllMocks();

    const fields = [
      { id: 'ed-brand', value: '' },
      { id: 'ed-stores', value: '' },
      { id: 'ed-ingredients', value: '' },
      { id: 'ed-kcal', value: '' },
      { id: 'ed-energy_kj', value: '' },
      { id: 'ed-fat', value: '' },
      { id: 'ed-saturated_fat', value: '' },
      { id: 'ed-carbs', value: '' },
      { id: 'ed-sugar', value: '' },
      { id: 'ed-protein', value: '' },
      { id: 'ed-fiber', value: '' },
      { id: 'ed-salt', value: '' },
      { id: 'ed-weight', value: '500' },
      { id: 'ed-portion', value: '30' },
    ];
    fields.forEach(({ id, value }) => {
      if (!document.getElementById(id)) {
        const el = document.createElement('input');
        el.id = id;
        el.value = value;
        document.body.appendChild(el);
      } else {
        document.getElementById(id).value = value;
      }
    });
    const btn = document.createElement('button');
    btn.id = 'off-submit-btn';
    document.body.appendChild(btn);

    api.mockResolvedValueOnce({ status: 'ok' });
    await submitToOff('1234567890123');
    const callBody = JSON.parse(api.mock.calls[0][1].body);
    expect(callBody.quantity).toBe('500 g');
    expect(callBody.serving_size).toBe('30 g');
  });
});

describe('lookupOFF', () => {
  function setupEdFields() {
    const ean = document.createElement('input');
    ean.id = 'ed-ean';
    ean.value = '';
    document.body.appendChild(ean);
    const name = document.createElement('input');
    name.id = 'ed-name';
    name.value = '';
    document.body.appendChild(name);
    const btn = document.createElement('button');
    btn.id = 'ed-off-btn';
    document.body.appendChild(btn);
    // Add nutrition fields for _gatherNutrition
    ['kcal', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt'].forEach((f) => {
      const el = document.createElement('input');
      el.id = 'ed-' + f;
      el.value = '';
      document.body.appendChild(el);
    });
    // Add type field for category
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    const opt = document.createElement('option');
    opt.value = 'dairy';
    typeEl.appendChild(opt);
    document.body.appendChild(typeEl);
    return { ean, name, btn };
  }

  it('looks up product by EAN', async () => {
    const { ean } = setupEdFields();
    ean.value = '1234567890123';
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        status: 1,
        product: { product_name: 'Test Milk', nutriments: {} },
      }),
    });
    await lookupOFF('ed', null);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/off/product/1234567890123'),
      expect.any(Object)
    );
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('shows empty results when EAN not found', async () => {
    const { ean } = setupEdFields();
    ean.value = '1234567890123';
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 0, product: null }),
    });
    await lookupOFF('ed', null);
    // Should create off-modal-bg for the picker
    expect(document.getElementById('off-modal-bg')).not.toBeNull();
  });

  it('shows error when EAN fetch response is not ok', async () => {
    const { ean } = setupEdFields();
    ean.value = '1234567890123';
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });
    await lookupOFF('ed', null);
    // Should create modal and show error
    expect(document.getElementById('off-modal-bg')).not.toBeNull();
  });

  it('searches by name when no valid EAN', async () => {
    const { name } = setupEdFields();
    name.value = 'Milk';
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [{ product_name: 'Milk', code: '123' }] }),
    });
    await lookupOFF('ed', null);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/off/search',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('searches by name with nutrition data and category', async () => {
    const { name } = setupEdFields();
    name.value = 'Milk';
    document.getElementById('ed-kcal').value = '60';
    document.getElementById('ed-protein').value = '3.3';
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [{ product_name: 'Milk', code: '123' }] }),
    });
    await lookupOFF('ed', null);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/off/search',
      expect.objectContaining({ method: 'POST' })
    );
    // Verify body includes nutrition
    const callBody = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(callBody.nutrition).toBeDefined();
    expect(callBody.nutrition.kcal).toBe(60);
  });

  it('shows error on network failure for EAN lookup', async () => {
    const { ean } = setupEdFields();
    ean.value = '1234567890123';
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    await lookupOFF('ed', null);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });

  it('shows error on network failure for name search', async () => {
    const { name } = setupEdFields();
    name.value = 'Milk';
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    await lookupOFF('ed', null);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });
});

describe('offModalSearch', () => {
  it('does nothing for short queries', async () => {
    const origFetch = global.fetch;
    delete global.fetch;
    const input = document.createElement('input');
    input.id = 'off-search-input';
    input.value = 'a';
    document.body.appendChild(input);
    await offModalSearch();
    // No fetch should have been attempted
    expect(showToast).not.toHaveBeenCalled();
    if (origFetch) global.fetch = origFetch;
  });

  it('searches and updates picker results on valid query', async () => {
    // Set up the off-modal structure needed by offModalSearch
    const input = document.createElement('input');
    input.id = 'off-search-input';
    input.value = 'Milk';
    document.body.appendChild(input);
    const btn = document.createElement('button');
    btn.id = 'off-search-btn';
    document.body.appendChild(btn);
    const body = document.createElement('div');
    body.id = 'off-results-body';
    document.body.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'off-result-count';
    document.body.appendChild(cnt);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ products: [{ product_name: 'Milk', code: '123' }] }),
    });

    await offModalSearch();
    expect(global.fetch).toHaveBeenCalled();
  });

  it('shows error on network failure', async () => {
    const input = document.createElement('input');
    input.id = 'off-search-input';
    input.value = 'Milk';
    document.body.appendChild(input);
    const btn = document.createElement('button');
    btn.id = 'off-search-btn';
    document.body.appendChild(btn);
    const body = document.createElement('div');
    body.id = 'off-results-body';
    document.body.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'off-result-count';
    document.body.appendChild(cnt);

    global.fetch = vi.fn().mockRejectedValue(new Error('fail'));
    await offModalSearch();
    // Should have tried to update results with error
    expect(body.innerHTML).not.toBe('');
  });
});

describe('selectOffResult', () => {
  function setupSelectContext() {
    // Set up DOM fields needed by applyOffProduct
    ['ean', 'name', 'kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'portion', 'weight', 'brand', 'stores', 'ingredients'].forEach((f) => {
      const el = document.createElement('input');
      el.id = 'ed-' + f;
      el.value = '';
      document.body.appendChild(el);
    });
    const btn = document.createElement('button');
    btn.id = 'ed-off-btn';
    document.body.appendChild(btn);
    const wrap = document.createElement('div');
    wrap.id = 'ed-protein-quality-wrap';
    wrap.style.display = 'none';
    document.body.appendChild(wrap);
  }

  it('returns early when no products after closing picker', async () => {
    // Close picker sets _offPickerProducts to null
    closeOffPicker();
    await selectOffResult(0);
    // No toast_off_fetched should be called (only possibly from prior state)
    expect(showToast).not.toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('applies product without code directly', async () => {
    setupSelectContext();
    // Trigger lookupOFF to set _offCtx and _offPickerProducts via name search
    document.getElementById('ed-name').value = 'Milk';
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    document.body.appendChild(typeEl);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [
          { product_name: 'Milk A', nutriments: { 'energy-kcal_100g': 60 } },
          { product_name: 'Milk B', code: '123', nutriments: {} },
        ],
      }),
    });
    await lookupOFF('ed', null);
    // Now select index 0 (no code)
    vi.clearAllMocks();
    await selectOffResult(0);
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('fetches detailed product when code exists and response ok', async () => {
    setupSelectContext();
    document.getElementById('ed-name').value = 'Milk';
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    document.body.appendChild(typeEl);

    // First search
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [{ product_name: 'Milk', code: '9999', nutriments: {} }],
      }),
    });
    await lookupOFF('ed', null);

    // Now select product with code - fetch will return detailed product
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        status: 1,
        product: { product_name: 'Detailed Milk', nutriments: { 'energy-kcal_100g': 50 }, code: '9999' },
      }),
    });
    await selectOffResult(0);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/off/product/9999'), expect.any(Object));
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('falls back to selected product when fetch returns non-ok', async () => {
    setupSelectContext();
    document.getElementById('ed-name').value = 'Milk';
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    document.body.appendChild(typeEl);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [{ product_name: 'Milk', code: '9999', nutriments: {} }],
      }),
    });
    await lookupOFF('ed', null);

    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await selectOffResult(0);
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('falls back to selected product when detailed fetch has status !== 1', async () => {
    setupSelectContext();
    document.getElementById('ed-name').value = 'Milk';
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    document.body.appendChild(typeEl);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [{ product_name: 'Milk', code: '9999', nutriments: {} }],
      }),
    });
    await lookupOFF('ed', null);

    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 0, product: null }),
    });
    await selectOffResult(0);
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_off_fetched'), 'success');
  });

  it('falls back on fetch error and shows network error toast', async () => {
    setupSelectContext();
    document.getElementById('ed-name').value = 'Milk';
    const typeEl = document.createElement('select');
    typeEl.id = 'ed-type';
    document.body.appendChild(typeEl);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        products: [{ product_name: 'Milk', code: '9999', nutriments: {} }],
      }),
    });
    await lookupOFF('ed', null);

    vi.clearAllMocks();
    global.fetch = vi.fn().mockRejectedValue(new Error('Network fail'));
    await selectOffResult(0);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });
});

describe('showOffAddReview', () => {
  it('creates review modal with filled fields', () => {
    // Set up form fields
    const fields = [
      { id: 'ed-name', value: 'Test Milk' },
      { id: 'ed-brand', value: 'Brand' },
      { id: 'ed-stores', value: '' },
      { id: 'ed-ingredients', value: 'milk' },
      { id: 'ed-kcal', value: '60' },
      { id: 'ed-energy_kj', value: '' },
      { id: 'ed-fat', value: '' },
      { id: 'ed-saturated_fat', value: '' },
      { id: 'ed-carbs', value: '' },
      { id: 'ed-sugar', value: '' },
      { id: 'ed-protein', value: '' },
      { id: 'ed-fiber', value: '' },
      { id: 'ed-salt', value: '' },
      { id: 'ed-weight', value: '' },
      { id: 'ed-portion', value: '' },
    ];
    fields.forEach(({ id, value }) => {
      const el = document.createElement('input');
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });

    // Set _offCtx.prefix by calling lookupOFF setup
    const ean = document.createElement('input');
    ean.id = 'ed-ean';
    ean.value = '1234567890123';
    document.body.appendChild(ean);
    const btn = document.createElement('button');
    btn.id = 'ed-off-btn';
    document.body.appendChild(btn);

    // We need to set context first - trigger lookupOFF to set _offCtx
    // Since _offCtx is private, we'll use lookupOFF with a short-circuit
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 0, product: null }),
    });

    showOffAddReview('1234567890123');
    const modal = document.getElementById('off-add-review-bg');
    expect(modal).not.toBeNull();
    expect(modal.innerHTML).toContain('1234567890123');
  });
});

describe('showDuplicateMergeModal', () => {
  afterEach(() => {
    document.querySelectorAll('.scan-modal-bg').forEach(el => el.remove());
  });

  it('shows field choices when A and B have different taste_score and price (neither synced)', async () => {
    const formData = { taste_score: 0.5, price: 123, brand: 'X', kcal: 100 };
    const duplicate = {
      id: 99, name: 'Dup Product', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 3, price: 1000, brand: 'X', kcal: 100,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    // Modal should be visible with conflict options
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    const modal = bg.querySelector('.conflict-modal');
    expect(modal).not.toBeNull();

    // Should contain field choice rows for taste_score and price
    const fieldLabels = modal.querySelectorAll('.conflict-row-label');
    const labelTexts = Array.from(fieldLabels).map(el => el.textContent);
    expect(labelTexts).toContain('adv_field_taste_score');
    expect(labelTexts).toContain('adv_field_price');

    // Should show conflict option values (price uses click options, taste uses slider)
    const optionValues = modal.querySelectorAll('.conflict-option-value');
    const values = Array.from(optionValues).map(el => el.textContent);
    expect(values).toContain('123');
    expect(values).toContain('1000');
    // Taste score uses a slider with labeled values
    const tasteValues = modal.querySelectorAll('.conflict-taste-value');
    const tValues = Array.from(tasteValues).map(el => el.textContent);
    expect(tValues).toContain('0.5');
    expect(tValues).toContain('3');

    // Click confirm to resolve the promise
    const confirmBtn = modal.querySelector('.conflict-apply-btn');
    confirmBtn.click();
    const result = await promise;
    expect(result).not.toBeNull();
    expect(result.scenario).toBe('neither');
    // Default: taste_score is avg rounded to nearest 0.5, price defaults to A
    expect(result.choices.taste_score).toBe(2); // avg(0.5, 3) = 1.75 → rounded to 2
    expect(result.choices.price).toBe(123);
  });

  it('shows dialog even with no conflicts (all values equal)', async () => {
    const formData = { taste_score: 3, price: 100 };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'name',
      is_synced_with_off: false,
      taste_score: 3, price: 100,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    // Dialog should still show for confirmation
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();

    // But no field choice rows
    const fieldLabels = bg.querySelectorAll('.conflict-row-label');
    expect(fieldLabels.length).toBe(0);

    // Confirm
    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.scenario).toBe('neither');
    expect(result.choices).toEqual({});
  });

  it('only shows user-only fields when B is synced with OFF', async () => {
    const formData = { taste_score: 0.5, price: 123, kcal: 200, brand: 'Local' };
    const duplicate = {
      id: 99, name: 'OFF Product', match_type: 'ean',
      is_synced_with_off: true,
      taste_score: 3, price: 1000, kcal: 300, brand: 'OFF Brand',
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    const fieldLabels = bg.querySelectorAll('.conflict-row-label');
    const labelTexts = Array.from(fieldLabels).map(el => el.textContent);

    // taste_score and price should show (user-only fields)
    expect(labelTexts).toContain('adv_field_taste_score');
    expect(labelTexts).toContain('adv_field_price');
    // kcal and brand should NOT show (OFF-provided fields)
    expect(labelTexts).not.toContain('adv_field_kcal');
    expect(labelTexts).not.toContain('adv_field_brand');

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.scenario).toBe('b_synced');
  });

  it('only shows user-only fields when A is synced with OFF', async () => {
    const formData = { taste_score: 0.5, price: 123, kcal: 200 };
    const duplicate = {
      id: 99, name: 'Other', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 3, price: 1000, kcal: 300,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, true);

    const bg = document.querySelector('.scan-modal-bg');
    const fieldLabels = bg.querySelectorAll('.conflict-row-label');
    const labelTexts = Array.from(fieldLabels).map(el => el.textContent);

    expect(labelTexts).toContain('adv_field_taste_score');
    expect(labelTexts).toContain('adv_field_price');
    expect(labelTexts).not.toContain('adv_field_kcal');

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.scenario).toBe('a_synced');
  });

  it('allows user to pick B values by clicking and sliding', async () => {
    const formData = { taste_score: 0.5, price: 123, name: 'Product A' };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 3, price: 1000,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    // Click the B option for price (standard click option)
    const optionBs = bg.querySelectorAll('.conflict-option:not(.selected)');
    optionBs.forEach(opt => opt.click());

    // Slide taste_score slider to B's value (3)
    const slider = bg.querySelector('.conflict-taste-range');
    slider.value = '3';
    slider.dispatchEvent(new Event('input'));

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.choices.taste_score).toBe(3);
    expect(result.choices.price).toBe(1000);
  });

  it('returns null when user cancels', async () => {
    const formData = { taste_score: 0.5 };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 3,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.confirm-no').click();
    const result = await promise;
    expect(result).toBeNull();
  });

  it('auto-resolves fields where only one side has a value', async () => {
    const formData = { taste_score: 0.5, price: null, volume: 2 };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 3, price: 1000, volume: null,
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    // Only taste_score should show as conflict (price and volume auto-resolve)
    const fieldLabels = bg.querySelectorAll('.conflict-row-label');
    const labelTexts = Array.from(fieldLabels).map(el => el.textContent);
    expect(labelTexts).toContain('adv_field_taste_score');
    expect(labelTexts).not.toContain('adv_field_price');
    expect(labelTexts).not.toContain('adv_field_volume');

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    // Auto-resolved values should be in choices
    expect(result.choices.price).toBe(1000);  // from B (A was null)
    expect(result.choices.volume).toBe(2);     // from A (B was null)
    expect(result.choices.taste_score).toBe(2); // default: avg(0.5, 3) = 1.75 → rounded to 2
  });

  it('selects all A values when keepAllA is clicked', async () => {
    const formData = { taste_score: 1, price: 100, brand: 'A-Brand' };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 5, price: 999, brand: 'B-Brand',
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    // First bulk button = keep all A
    bulkBtns[0].click();

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.choices.taste_score).toBe(1);
    expect(result.choices.price).toBe(100);
    expect(result.choices.brand).toBe('A-Brand');
  });

  it('selects all B values when keepAllB is clicked', async () => {
    const formData = { taste_score: 1, price: 100, brand: 'A-Brand' };
    const duplicate = {
      id: 99, name: 'Dup', match_type: 'ean',
      is_synced_with_off: false,
      taste_score: 5, price: 999, brand: 'B-Brand',
    };
    const promise = showDuplicateMergeModal(formData, duplicate, false);

    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    // Second bulk button = keep all B
    bulkBtns[1].click();

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.choices.taste_score).toBe(5);
    expect(result.choices.price).toBe(999);
    expect(result.choices.brand).toBe('B-Brand');
  });
});

describe('showMergeConflictModal', () => {
  afterEach(() => {
    document.querySelectorAll('.scan-modal-bg').forEach(el => el.remove());
  });

  it('resolves immediately when no conflicts exist', async () => {
    const formData = { kcal: 100, protein: 5 };
    const duplicate = { kcal: 100, protein: 5 };
    const result = await showMergeConflictModal(formData, duplicate, null);
    expect(result).toEqual({});
  });

  it('shows conflict modal when fields differ', async () => {
    const formData = { kcal: 100, protein: 5 };
    const duplicate = { kcal: 200, protein: 10 };
    const promise = showMergeConflictModal(formData, duplicate, null);

    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    const modal = bg.querySelector('.conflict-modal');
    expect(modal).not.toBeNull();

    // Default is to keep form (current) values
    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.kcal).toBe(100);
    expect(result.protein).toBe(5);
  });

  it('returns null when cancelled', async () => {
    const formData = { kcal: 100 };
    const duplicate = { kcal: 200 };
    const promise = showMergeConflictModal(formData, duplicate, null);

    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.confirm-no').click();
    const result = await promise;
    expect(result).toBeNull();
  });

  it('allows picking duplicate values', async () => {
    const formData = { brand: 'A', stores: 'Store A' };
    const duplicate = { brand: 'B', stores: 'Store B' };
    const promise = showMergeConflictModal(formData, duplicate, null);

    const bg = document.querySelector('.scan-modal-bg');
    // Click all "other" (dup) options
    const dupOptions = bg.querySelectorAll('.conflict-option:not(.selected)');
    dupOptions.forEach(opt => opt.click());

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.brand).toBe('B');
    expect(result.stores).toBe('Store B');
  });

  it('uses bulk keep-all-current button', async () => {
    const formData = { kcal: 100, protein: 5 };
    const duplicate = { kcal: 200, protein: 10 };
    const promise = showMergeConflictModal(formData, duplicate, null);

    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    // First = keep all current
    bulkBtns[0].click();
    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.kcal).toBe(100);
    expect(result.protein).toBe(5);
  });

  it('uses bulk keep-all-other button', async () => {
    const formData = { kcal: 100, protein: 5 };
    const duplicate = { kcal: 200, protein: 10 };
    const promise = showMergeConflictModal(formData, duplicate, null);

    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    // Second = keep all other
    bulkBtns[1].click();
    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.kcal).toBe(200);
    expect(result.protein).toBe(10);
  });

  it('auto-resolves OFF-applied fields to form values', async () => {
    const formData = { kcal: 150, protein: 8, brand: 'X' };
    const duplicate = { kcal: 200, protein: 10, brand: 'Y' };
    const offApplied = new Set(['kcal', 'protein']);
    const promise = showMergeConflictModal(formData, duplicate, offApplied);

    const bg = document.querySelector('.scan-modal-bg');
    // Only brand should be a conflict row (kcal and protein auto-resolved)
    const labels = bg.querySelectorAll('.conflict-row-label');
    expect(labels.length).toBe(1);
    expect(labels[0].textContent).toContain('brand');

    bg.querySelector('.conflict-apply-btn').click();
    const result = await promise;
    expect(result.kcal).toBe(150);
    expect(result.protein).toBe(8);
    expect(result.brand).toBe('X');
  });
});

describe('showEditDuplicateModal', () => {
  afterEach(() => {
    document.querySelectorAll('.scan-modal-bg').forEach(el => el.remove());
  });

  it('shows merge button for unsynced duplicate', async () => {
    const duplicate = { id: 1, name: 'Test', match_type: 'ean', is_synced_with_off: false };
    const promise = showEditDuplicateModal(duplicate);

    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    const mergeBtn = bg.querySelector('.confirm-yes');
    expect(mergeBtn.textContent).toBe('duplicate_action_merge_into');

    mergeBtn.click();
    const result = await promise;
    expect(result).toBe('merge');
  });

  it('shows delete button for synced duplicate', async () => {
    const duplicate = { id: 1, name: 'Test', match_type: 'ean', is_synced_with_off: true };
    const promise = showEditDuplicateModal(duplicate);

    const bg = document.querySelector('.scan-modal-bg');
    const deleteBtn = bg.querySelector('.confirm-yes');
    expect(deleteBtn.textContent).toBe('duplicate_action_delete');

    deleteBtn.click();
    const result = await promise;
    expect(result).toBe('delete');
  });

  it('returns cancel when cancel button clicked', async () => {
    const duplicate = { id: 1, name: 'Test', match_type: 'ean', is_synced_with_off: false };
    const promise = showEditDuplicateModal(duplicate);

    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.confirm-no').click();
    const result = await promise;
    expect(result).toBe('cancel');
  });
});

describe('showOffAddReview without name', () => {
  it('shows name required warning when no name is filled', () => {
    // Set up _offCtx by triggering lookupOFF context
    const eanEl = document.createElement('input');
    eanEl.id = 'ed-ean';
    eanEl.value = '1234567890123';
    document.body.appendChild(eanEl);
    const nameEl = document.createElement('input');
    nameEl.id = 'ed-name';
    nameEl.value = '';
    document.body.appendChild(nameEl);
    const offBtn = document.createElement('button');
    offBtn.id = 'ed-off-btn';
    document.body.appendChild(offBtn);

    // Set _offCtx.prefix via lookupOFF
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 0, product: null }),
    });
    lookupOFF('ed', null);

    // Set up all review fields with empty values (no name)
    const fields = [
      'brand', 'stores', 'ingredients', 'kcal', 'energy_kj',
      'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt',
      'weight', 'portion',
    ];
    fields.forEach((f) => {
      if (!document.getElementById('ed-' + f)) {
        const el = document.createElement('input');
        el.id = 'ed-' + f;
        el.value = '';
        document.body.appendChild(el);
      }
    });

    showOffAddReview('9999999999999');
    const modal = document.getElementById('off-add-review-bg');
    expect(modal).not.toBeNull();
    // Should contain the name required warning
    expect(modal.innerHTML).toContain('off_add_name_required');
  });
});
