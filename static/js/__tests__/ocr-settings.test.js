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

const MOCK_OCR_RESPONSE = {
  active: 'easyocr',
  backends: [
    { id: 'easyocr', name: 'EasyOCR', available: true },
    { id: 'google_vision', name: 'Google Vision', available: false },
    { id: 'tesseract', name: 'Tesseract', available: true },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '<div id="ocr-backends"></div>';
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('loadOcrSettings', () => {
  it('fetches backends and renders radio buttons', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/settings/ocr');
    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    expect(radios).toHaveLength(3);
    expect(radios[0].value).toBe('easyocr');
    expect(radios[1].value).toBe('google_vision');
    expect(radios[2].value).toBe('tesseract');
  });

  it('selects the active backend', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    expect(radios[0].checked).toBe(true);
    expect(radios[1].checked).toBe(false);
    expect(radios[2].checked).toBe(false);
  });

  it('disables unavailable backends', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    expect(radios[0].disabled).toBe(false);
    expect(radios[1].disabled).toBe(true);
    expect(radios[2].disabled).toBe(false);
  });

  it('shows unavailable label for disabled backends', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    const unavailLabels = document.querySelectorAll('[data-i18n="settings_ocr_unavailable"]');
    expect(unavailLabels).toHaveLength(1);
    expect(t).toHaveBeenCalledWith('settings_ocr_unavailable');
  });

  it('displays backend names', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    const labels = document.querySelectorAll('#ocr-backends label');
    expect(labels[0].textContent).toContain('EasyOCR');
    expect(labels[1].textContent).toContain('Google Vision');
    expect(labels[2].textContent).toContain('Tesseract');
  });

  it('shows error toast on API failure', async () => {
    api.mockRejectedValueOnce(new Error('network'));
    await loadOcrSettings();

    expect(showToast).toHaveBeenCalledWith('settings_ocr_error', 'error');
  });

  it('does nothing when container is missing', async () => {
    document.body.innerHTML = '';
    await loadOcrSettings();

    expect(api).not.toHaveBeenCalled();
  });

  it('handles empty backends array', async () => {
    api.mockResolvedValueOnce({ active: '', backends: [] });
    await loadOcrSettings();

    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    expect(radios).toHaveLength(0);
  });
});

describe('saveOcrSettings', () => {
  it('sends selected backend to API and shows success toast', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/settings/ocr', {
      method: 'PUT',
      body: JSON.stringify({ active: 'easyocr' }),
    });
    expect(showToast).toHaveBeenCalledWith('settings_ocr_saved', 'success');
  });

  it('sends newly selected backend', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    // Select tesseract
    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    radios[0].checked = false;
    radios[2].checked = true;

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    expect(api).toHaveBeenCalledWith('/api/settings/ocr', {
      method: 'PUT',
      body: JSON.stringify({ active: 'tesseract' }),
    });
  });

  it('shows error toast on save failure', async () => {
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    api.mockRejectedValueOnce(new Error('save failed'));
    await saveOcrSettings();

    expect(showToast).toHaveBeenCalledWith('settings_ocr_error', 'error');
  });

  it('does nothing when no radio is selected', async () => {
    document.body.innerHTML = '<div id="ocr-backends"></div>';
    // No radios rendered
    await saveOcrSettings();

    expect(api).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
  });
});

describe('OCR settings E2E flow', () => {
  it('load → select different backend → save → reload persists selection', async () => {
    // Initial load
    api.mockResolvedValueOnce(MOCK_OCR_RESPONSE);
    await loadOcrSettings();

    // User selects tesseract
    const radios = document.querySelectorAll('input[name="ocr-backend"]');
    radios[0].checked = false;
    radios[2].checked = true;

    // Save
    api.mockResolvedValueOnce({});
    await saveOcrSettings();
    expect(showToast).toHaveBeenCalledWith('settings_ocr_saved', 'success');

    // Reload with new active
    const updatedResponse = {
      ...MOCK_OCR_RESPONSE,
      active: 'tesseract',
    };
    api.mockResolvedValueOnce(updatedResponse);
    await loadOcrSettings();

    const reloadedRadios = document.querySelectorAll('input[name="ocr-backend"]');
    expect(reloadedRadios[0].checked).toBe(false);
    expect(reloadedRadios[2].checked).toBe(true);
  });
});
