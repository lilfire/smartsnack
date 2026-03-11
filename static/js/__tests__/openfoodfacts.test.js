import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedResults: [],
    categories: [],
    imageCache: {},
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    esc: (s) => String(s),
    safeDataUri: (uri) => uri || '',
    showToast: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((dataUri) => Promise.resolve(dataUri)),
}));

import { isValidEan, validateOffBtn, searchOFF, closeOffPicker, closeOffAddReview, estimateProteinQuality, updateEstimateBtn, submitToOff, lookupOFF, selectOffResult, offModalSearch, showOffAddReview } from '../openfoodfacts.js';
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

  it('shows error on network failure for EAN lookup', async () => {
    const { ean } = setupEdFields();
    ean.value = '1234567890123';
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
