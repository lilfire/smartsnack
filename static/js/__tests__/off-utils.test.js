import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  state: { imageCache: {} },
  api: vi.fn().mockResolvedValue({}),
  esc: (s) => String(s),
  safeDataUri: (u) => u || '',
  showToast: vi.fn(),
  trapFocus: vi.fn(() => vi.fn()),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((d) => Promise.resolve(d)),
}));

import {
  OFF_FETCH_TIMEOUT,
  _FIELD_LABEL_KEYS,
  _fieldLabel,
  _VOLUME_LABELS,
  _volumeLabel,
  fetchWithTimeout,
  isValidEan,
  validateOffBtn,
  offState,
  _nutritionCompareFields,
  _gatherNutrition,
  _numericFields,
  _formatNumeric,
  _detectConflicts,
  _esc,
  isValidImageUrl,
  updateEstimateBtn,
  estimateProteinQuality,
} from '../off-utils.js';
import { t } from '../i18n.js';
import { showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  global.fetch = vi.fn();
});

// ── isValidEan ───────────────────────────────────────
describe('isValidEan', () => {
  it('accepts 8-digit EAN', () => expect(isValidEan('12345678')).toBe(true));
  it('accepts 13-digit EAN', () => expect(isValidEan('1234567890123')).toBe(true));
  it('accepts 10-digit code', () => expect(isValidEan('1234567890')).toBe(true));
  it('rejects 7-digit', () => expect(isValidEan('1234567')).toBe(false));
  it('rejects 14-digit', () => expect(isValidEan('12345678901234')).toBe(false));
  it('rejects non-numeric', () => expect(isValidEan('abcdefgh')).toBe(false));
  it('rejects empty', () => expect(isValidEan('')).toBe(false));
  it('rejects null', () => expect(isValidEan(null)).toBe(false));
  it('rejects undefined', () => expect(isValidEan(undefined)).toBe(false));
  it('trims whitespace', () => expect(isValidEan(' 12345678 ')).toBe(true));
});

// ── validateOffBtn ───────────────────────────────────
describe('validateOffBtn', () => {
  function setup(ean = '', name = '') {
    document.body.innerHTML = `
      <input id="p-ean" value="${ean}">
      <input id="p-name" value="${name}">
      <button id="p-off-btn" disabled></button>`;
  }

  it('enables btn for valid EAN', () => {
    setup('12345678', '');
    validateOffBtn('p');
    expect(document.getElementById('p-off-btn').disabled).toBe(false);
  });

  it('enables btn for name >= 2 chars', () => {
    setup('', 'ab');
    validateOffBtn('p');
    expect(document.getElementById('p-off-btn').disabled).toBe(false);
  });

  it('disables btn for invalid EAN and short name', () => {
    setup('123', 'a');
    validateOffBtn('p');
    expect(document.getElementById('p-off-btn').disabled).toBe(true);
  });

  it('handles missing button gracefully', () => {
    document.body.innerHTML = `<input id="p-ean" value=""><input id="p-name" value="">`;
    expect(() => validateOffBtn('p')).not.toThrow();
  });
});

// ── _fieldLabel ──────────────────────────────────────
describe('_fieldLabel', () => {
  it('calls t() with known key', () => {
    t.mockReturnValue('Name');
    expect(_fieldLabel('name')).toBe('Name');
    expect(t).toHaveBeenCalledWith('label_name');
  });

  it('falls back to field name for unknown key', () => {
    t.mockReturnValue('');
    expect(_fieldLabel('unknown_field')).toBe('unknown_field');
  });
});

// ── _volumeLabel ─────────────────────────────────────
describe('_volumeLabel', () => {
  it('returns t() for known volume value', () => {
    t.mockImplementation((k) => k);
    expect(_volumeLabel(1)).toBe('volume_low');
    expect(_volumeLabel(2)).toBe('volume_medium');
    expect(_volumeLabel(3)).toBe('volume_high');
  });

  it('returns raw value for unknown', () => {
    expect(_volumeLabel(99)).toBe(99);
  });
});

// ── _gatherNutrition ─────────────────────────────────
describe('_gatherNutrition', () => {
  it('returns null when no nutrition fields set', () => {
    document.body.innerHTML = '<input id="p-kcal" value="">';
    expect(_gatherNutrition('p')).toBeNull();
  });

  it('gathers numeric nutrition values', () => {
    const fields = _nutritionCompareFields.map((f) => `<input id="p-${f}" value="">`).join('');
    document.body.innerHTML = fields;
    document.getElementById('p-kcal').value = '100';
    document.getElementById('p-protein').value = '5.5';
    const result = _gatherNutrition('p');
    expect(result).toEqual(expect.objectContaining({ kcal: 100, protein: 5.5 }));
  });

  it('ignores non-numeric values', () => {
    document.body.innerHTML = '<input id="p-kcal" value="abc">';
    expect(_gatherNutrition('p')).toBeNull();
  });
});

// ── _formatNumeric ───────────────────────────────────
describe('_formatNumeric', () => {
  it('rounds kcal', () => expect(_formatNumeric('kcal', 123.7)).toBe('124'));
  it('rounds energy_kj', () => expect(_formatNumeric('energy_kj', 500.6)).toBe('501'));
  it('rounds weight', () => expect(_formatNumeric('weight', 250.9)).toBe('251'));
  it('rounds portion', () => expect(_formatNumeric('portion', 30.4)).toBe('30'));
  it('formats salt to 2 decimals', () => expect(_formatNumeric('salt', 1.234)).toBe('1.23'));
  it('formats fat to 1 decimal', () => expect(_formatNumeric('fat', 5.678)).toBe('5.7'));
  it('formats protein to 1 decimal', () => expect(_formatNumeric('protein', 10)).toBe('10.0'));
});

// ── _detectConflicts ─────────────────────────────────
describe('_detectConflicts', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <input id="p-kcal" value="100">
      <input id="p-name" value="Existing">
      <input id="p-brand" value="">`;
  });

  it('auto-applies OFF value when field exists', () => {
    const { autoApply } = _detectConflicts({ kcal: 200 }, 'p');
    expect(autoApply.kcal).toBe('200');
  });

  it('skips OFF zero numeric value', () => {
    const { autoApply } = _detectConflicts({ kcal: 0 }, 'p');
    expect(autoApply.kcal).toBeUndefined();
  });

  it('auto-applies text field', () => {
    const { autoApply } = _detectConflicts({ brand: 'Acme' }, 'p');
    expect(autoApply.brand).toBe('Acme');
  });

  it('skips empty OFF text field', () => {
    const { autoApply } = _detectConflicts({ brand: '' }, 'p');
    expect(autoApply.brand).toBeUndefined();
  });

  it('skips missing DOM element', () => {
    const { autoApply } = _detectConflicts({ nonexistent: 'x' }, 'p');
    expect(autoApply.nonexistent).toBeUndefined();
  });
});

// ── _esc ─────────────────────────────────────────────
describe('_esc', () => {
  it('escapes HTML characters', () => {
    expect(_esc('<b>test</b>')).toBe('&lt;b&gt;test&lt;/b&gt;');
    expect(_esc('"quoted"')).toBe('"quoted"');
    expect(_esc("it's")).toBe("it's");
  });

  it('handles plain text', () => {
    expect(_esc('hello world')).toBe('hello world');
  });
});

// ── isValidImageUrl ──────────────────────────────────
describe('isValidImageUrl', () => {
  it('accepts https URLs', () => expect(isValidImageUrl('https://example.com/img.jpg')).toBe(true));
  it('accepts http URLs', () => expect(isValidImageUrl('http://example.com/img.jpg')).toBe(true));
  it('rejects data URIs', () => expect(isValidImageUrl('data:image/png;base64,abc')).toBe(false));
  it('rejects invalid strings', () => expect(isValidImageUrl('not-a-url')).toBe(false));
  it('rejects empty string', () => expect(isValidImageUrl('')).toBe(false));
});

// ── updateEstimateBtn ────────────────────────────────
describe('updateEstimateBtn', () => {
  it('shows wrap when ingredients non-empty', () => {
    document.body.innerHTML = `
      <input id="p-ingredients" value="chicken, rice">
      <div id="p-protein-quality-wrap" style="display:none"></div>`;
    updateEstimateBtn('p');
    expect(document.getElementById('p-protein-quality-wrap').style.display).toBe('');
  });

  it('hides wrap when ingredients empty', () => {
    document.body.innerHTML = `
      <input id="p-ingredients" value="">
      <div id="p-protein-quality-wrap" style="display:''"></div>`;
    updateEstimateBtn('p');
    expect(document.getElementById('p-protein-quality-wrap').style.display).toBe('none');
  });

  it('handles missing elements gracefully', () => {
    document.body.innerHTML = '';
    expect(() => updateEstimateBtn('p')).not.toThrow();
  });
});

// ── estimateProteinQuality ───────────────────────────
describe('estimateProteinQuality', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <input id="p-ingredients" value="chicken breast">
      <button id="p-estimate-btn"></button>
      <div id="p-pq-result" style="display:none"></div>
      <div id="p-pdcaas-val"></div>
      <div id="p-diaas-val"></div>
      <div id="p-pq-sources"></div>
      <input id="p-est_pdcaas" value="">
      <input id="p-est_diaas" value="">`;
  });

  it('shows toast error when ingredients missing', async () => {
    document.getElementById('p-ingredients').value = '';
    await estimateProteinQuality('p');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls fetch and populates result on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: 0.85, est_diaas: 0.9, sources: ['chicken'] }),
    });
    await estimateProteinQuality('p');
    expect(document.getElementById('p-pdcaas-val').textContent).toBe('0.85');
    expect(document.getElementById('p-diaas-val').textContent).toBe('0.90');
    expect(document.getElementById('p-pq-result').style.display).toBe('');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error toast on fetch failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    await estimateProteinQuality('p');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows error toast on API error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ error: 'some_error' }),
    });
    await estimateProteinQuality('p');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows no_protein_sources toast when both null', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ est_pdcaas: null, est_diaas: null, sources: [] }),
    });
    await estimateProteinQuality('p');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows error toast on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    await estimateProteinQuality('p');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── OFF_FETCH_TIMEOUT constant ───────────────────────
describe('OFF_FETCH_TIMEOUT', () => {
  it('is 45000ms', () => expect(OFF_FETCH_TIMEOUT).toBe(45000));
});

// ── offState ─────────────────────────────────────────
describe('offState', () => {
  it('has expected default shape', () => {
    expect(offState).toHaveProperty('ctx');
    expect(offState).toHaveProperty('pickerProducts');
    expect(offState).toHaveProperty('reviewResolve');
  });
});

// ── _numericFields ───────────────────────────────────
describe('_numericFields', () => {
  it('contains expected nutrition fields', () => {
    expect(_numericFields.has('kcal')).toBe(true);
    expect(_numericFields.has('protein')).toBe(true);
    expect(_numericFields.has('salt')).toBe(true);
    expect(_numericFields.has('name')).toBe(false);
  });
});

// ── fetchWithTimeout ─────────────────────────────────
describe('fetchWithTimeout', () => {
  it('calls fetch with signal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
    vi.useFakeTimers();
    const p = fetchWithTimeout('/test');
    vi.runAllTimers();
    await p;
    expect(global.fetch).toHaveBeenCalledWith('/test', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    vi.useRealTimers();
  });

  it('forwards options to fetch', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
    vi.useFakeTimers();
    const p = fetchWithTimeout('/test', { method: 'POST' });
    vi.runAllTimers();
    await p;
    expect(global.fetch).toHaveBeenCalledWith('/test', expect.objectContaining({ method: 'POST' }));
    vi.useRealTimers();
  });
});
