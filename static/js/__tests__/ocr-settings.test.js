import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: { total: 5, types: 2, categories: [] },
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
  t: vi.fn((key) => key),
  getCurrentLang: vi.fn(() => 'no'),
  changeLanguage: vi.fn(),
}));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

vi.mock('../emoji-picker.js', () => ({
  initEmojiPicker: vi.fn(),
  resetEmojiPicker: vi.fn(),
}));

vi.mock('../render.js', () => ({ loadFlagConfig: vi.fn(), getFlagConfig: vi.fn(() => ({})) }));

import { loadOcrSettings, saveOcrSettings } from '../settings.js';
import { api, showToast } from '../state.js';
import { t } from '../i18n.js';

const MOCK_SETTINGS_RESPONSE = {
  provider: 'google_vision',
  fallback_to_tesseract: true,
};

function setupDropdownDOM() {
  document.body.innerHTML = `
    <select id="ocr-provider-select">
      <option value="tesseract">Tesseract OCR</option>
      <option value="google_vision">Google Vision</option>
      <option value="easyocr">EasyOCR</option>
    </select>
    <div id="ocr-fallback-wrapper">
      <input type="checkbox" id="ocr-fallback-checkbox">
    </div>
  `;
}

beforeEach(() => {
  vi.clearAllMocks();
  setupDropdownDOM();
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('loadOcrSettings', () => {
  it('fetches settings and sets dropdown value', async () => {
    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/ocr/settings');
    const sel = document.getElementById('ocr-provider-select');
    expect(sel.value).toBe('google_vision');
  });

  it('sets fallback checkbox when enabled', async () => {
    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const cb = document.getElementById('ocr-fallback-checkbox');
    expect(cb.checked).toBe(true);
  });

  it('unchecks fallback when disabled', async () => {
    api.mockResolvedValueOnce({ provider: 'easyocr', fallback_to_tesseract: false });
    await loadOcrSettings();

    const cb = document.getElementById('ocr-fallback-checkbox');
    expect(cb.checked).toBe(false);
  });

  it('defaults to tesseract when provider not set', async () => {
    api.mockResolvedValueOnce({});
    await loadOcrSettings();

    const sel = document.getElementById('ocr-provider-select');
    expect(sel.value).toBe('tesseract');
  });

  it('does nothing when select element is missing', async () => {
    document.body.innerHTML = '';
    await loadOcrSettings();

    expect(api).not.toHaveBeenCalled();
  });

  it('silently handles API failure', async () => {
    api.mockRejectedValueOnce(new Error('network'));
    await loadOcrSettings();

    // loadOcrSettings swallows errors (defaults are fine)
    expect(showToast).not.toHaveBeenCalled();
  });
});

describe('saveOcrSettings', () => {
  it('sends selected provider and fallback to API', async () => {
    const sel = document.getElementById('ocr-provider-select');
    sel.value = 'google_vision';
    const cb = document.getElementById('ocr-fallback-checkbox');
    cb.checked = true;

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/ocr/settings', {
      method: 'POST',
      body: JSON.stringify({ provider: 'google_vision', fallback_to_tesseract: true }),
    });
    expect(showToast).toHaveBeenCalledWith('toast_ocr_settings_saved', 'success');
  });

  it('sends fallback_to_tesseract as false when unchecked', async () => {
    const sel = document.getElementById('ocr-provider-select');
    sel.value = 'easyocr';
    const cb = document.getElementById('ocr-fallback-checkbox');
    cb.checked = false;

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/ocr/settings', {
      method: 'POST',
      body: JSON.stringify({ provider: 'easyocr', fallback_to_tesseract: false }),
    });
  });

  it('shows error toast on save failure', async () => {
    const sel = document.getElementById('ocr-provider-select');
    sel.value = 'google_vision';

    api.mockRejectedValueOnce(new Error('save failed'));
    await saveOcrSettings();

    expect(showToast).toHaveBeenCalledWith('toast_ocr_settings_error', 'error');
  });

  it('does nothing when select is missing', async () => {
    document.body.innerHTML = '';
    await saveOcrSettings();

    expect(api).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
  });
});

describe('OCR settings E2E flow', () => {
  it('load → change provider → save → reload persists selection', async () => {
    // Initial load with google_vision
    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const sel = document.getElementById('ocr-provider-select');
    expect(sel.value).toBe('google_vision');

    // User changes to easyocr
    sel.value = 'easyocr';

    // Save
    api.mockResolvedValueOnce({});
    await saveOcrSettings();
    expect(showToast).toHaveBeenCalledWith('toast_ocr_settings_saved', 'success');

    // Reload with new provider
    api.mockResolvedValueOnce({ provider: 'easyocr', fallback_to_tesseract: false });
    await loadOcrSettings();

    expect(sel.value).toBe('easyocr');
  });
});
