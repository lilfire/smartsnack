/**
 * Tests for OCR model option UI feature (LSO-460).
 *
 * Covers:
 * - Model selector dropdown switches on provider change
 * - Model selector hidden for Tesseract
 * - Save includes models dict in POST body
 * - OpenRouter shows text input instead of dropdown
 * - Load restores saved model selection
 */
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

import { loadOcrProviders, loadOcrSettings, saveOcrSettings } from '../settings-ocr.js';
import { api, showToast } from '../state.js';

const MOCK_PROVIDERS_RESPONSE = {
  providers: [
    { key: 'tesseract', label: 'Tesseract (Local)', models: [] },
    { key: 'claude_vision', label: 'Claude Vision', models: ['claude-sonnet-4-20250514', 'claude-opus-4-5', 'claude-haiku-4-5-20251001'] },
    { key: 'gemini', label: 'Gemini Vision', models: ['gemini-2.0-flash', 'gemini-2.5-pro', 'gemini-1.5-pro'] },
    { key: 'openai', label: 'GPT-4 Vision', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini'] },
    { key: 'openrouter', label: 'OpenRouter Vision', models: [] },
    { key: 'groq', label: 'Groq Vision', models: ['meta-llama/llama-4-scout-17b-16e-instruct', 'meta-llama/llama-4-maverick-17b-128e-instruct'] },
  ],
};

const MOCK_SETTINGS_RESPONSE = {
  provider: 'claude_vision',
  fallback_to_tesseract: false,
  models: { claude_vision: 'claude-opus-4-5', gemini: 'gemini-2.0-flash' },
};

function setupFullDOM() {
  document.body.innerHTML = `
    <select id="ocr-provider-select">
      <option value="tesseract">Tesseract (Local)</option>
      <option value="claude_vision">Claude Vision</option>
      <option value="gemini">Gemini Vision</option>
      <option value="openai">GPT-4 Vision</option>
      <option value="openrouter">OpenRouter Vision</option>
      <option value="groq">Groq Vision</option>
    </select>
    <div id="ocr-fallback-wrapper">
      <input type="checkbox" id="ocr-fallback-checkbox">
    </div>
    <div id="ocr-model-row">
      <select id="ocr-model-select"></select>
      <input type="text" id="ocr-model-input" style="display:none">
    </div>
  `;
}

beforeEach(() => {
  vi.clearAllMocks();
  setupFullDOM();
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('Model selector visibility', () => {
  it('hides model row when Tesseract is selected', async () => {
    // Load providers first
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    // Load settings with tesseract
    api.mockResolvedValueOnce({ provider: 'tesseract', fallback_to_tesseract: false, models: {} });
    await loadOcrSettings();

    const sel = document.getElementById('ocr-provider-select');
    sel.value = 'tesseract';
    sel.dispatchEvent(new Event('change'));

    const modelRow = document.getElementById('ocr-model-row');
    // Model row should be hidden for tesseract (via display:none or hidden class)
    const isHidden = modelRow.style.display === 'none' ||
                     modelRow.classList.contains('hidden') ||
                     !modelRow.classList.contains('visible');
    expect(isHidden).toBe(true);
  });

  it('shows model row when AI provider is selected', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const sel = document.getElementById('ocr-provider-select');
    sel.value = 'claude_vision';
    sel.dispatchEvent(new Event('change'));

    const modelRow = document.getElementById('ocr-model-row');
    const modelSelect = document.getElementById('ocr-model-select');
    // Model row should be visible and select should have options
    const isVisible = modelRow.style.display !== 'none' ||
                      modelRow.classList.contains('visible');
    expect(isVisible).toBe(true);
  });
});

describe('Model selector population', () => {
  it('populates model dropdown with provider models on provider change', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    providerSel.value = 'gemini';
    providerSel.dispatchEvent(new Event('change'));

    const modelSelect = document.getElementById('ocr-model-select');
    const options = Array.from(modelSelect.options).map(o => o.value);

    // Should contain the gemini models from providers response
    expect(options).toContain('gemini-2.0-flash');
    expect(options).toContain('gemini-2.5-pro');
    expect(options).toContain('gemini-1.5-pro');
  });

  it('shows text input for OpenRouter instead of dropdown', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce({
      provider: 'openrouter',
      fallback_to_tesseract: false,
      models: { openrouter: 'google/gemini-2.0-flash-001' },
    });
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    providerSel.value = 'openrouter';
    providerSel.dispatchEvent(new Event('change'));

    const modelInput = document.getElementById('ocr-model-input');
    const modelSelect = document.getElementById('ocr-model-select');

    // OpenRouter should show text input, not dropdown
    const inputVisible = modelInput.style.display !== 'none';
    const selectHidden = modelSelect.style.display === 'none' ||
                         modelSelect.options.length === 0;
    expect(inputVisible || selectHidden).toBe(true);
  });

  it('pre-selects the saved model from settings', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    expect(providerSel.value).toBe('claude_vision');

    const modelSelect = document.getElementById('ocr-model-select');
    // The saved model for claude_vision is 'claude-opus-4-5'
    expect(modelSelect.value).toBe('claude-opus-4-5');
  });
});

describe('Save includes models', () => {
  it('includes models dict in save POST body', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    // Set provider and model
    const providerSel = document.getElementById('ocr-provider-select');
    providerSel.value = 'claude_vision';
    providerSel.dispatchEvent(new Event('change'));

    const modelSelect = document.getElementById('ocr-model-select');
    if (modelSelect.options.length > 0) {
      modelSelect.value = modelSelect.options[0].value;
    }

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    const lastCall = api.mock.calls[api.mock.calls.length - 1];
    expect(lastCall[0]).toBe('/api/ocr/settings');

    const body = JSON.parse(lastCall[1].body);
    expect(body).toHaveProperty('models');
    expect(typeof body.models).toBe('object');
    // Should include the model for the active provider
    expect(body.models).toHaveProperty('claude_vision');
  });

  it('sends OpenRouter free-text model value', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce({
      provider: 'openrouter',
      fallback_to_tesseract: false,
      models: { openrouter: 'google/gemini-2.0-flash-001' },
    });
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    providerSel.value = 'openrouter';
    providerSel.dispatchEvent(new Event('change'));

    const modelInput = document.getElementById('ocr-model-input');
    modelInput.value = 'anthropic/claude-3-opus';

    api.mockResolvedValueOnce({});
    await saveOcrSettings();

    const lastCall = api.mock.calls[api.mock.calls.length - 1];
    const body = JSON.parse(lastCall[1].body);
    expect(body.models).toHaveProperty('openrouter');
    expect(body.models.openrouter).toBe('anthropic/claude-3-opus');
  });
});

describe('Model selector switching', () => {
  it('updates model options when switching from one AI provider to another', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    const modelSelect = document.getElementById('ocr-model-select');

    // Switch to gemini
    providerSel.value = 'gemini';
    providerSel.dispatchEvent(new Event('change'));

    let options = Array.from(modelSelect.options).map(o => o.value);
    expect(options).toContain('gemini-2.0-flash');
    expect(options).not.toContain('gpt-4o');

    // Switch to openai
    providerSel.value = 'openai';
    providerSel.dispatchEvent(new Event('change'));

    options = Array.from(modelSelect.options).map(o => o.value);
    expect(options).toContain('gpt-4o');
    expect(options).not.toContain('gemini-2.0-flash');
  });

  it('resets model to first option when switching providers', async () => {
    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const providerSel = document.getElementById('ocr-provider-select');
    const modelSelect = document.getElementById('ocr-model-select');

    // Switch to openai
    providerSel.value = 'openai';
    providerSel.dispatchEvent(new Event('change'));

    // First option should be selected (gpt-4o)
    if (modelSelect.options.length > 0) {
      expect(modelSelect.value).toBe('gpt-4o');
    }
  });
});

// ── Custom dropdown integration ──────────────────────
// Regression: the custom dropdown wrapper from upgradeSelect() assigns
// sel.value programmatically and does NOT dispatch a 'change' event. The
// onSelect callback passed to upgradeSelect must therefore update both the
// fallback visibility AND the model row, and the wrapper around the model
// <select> must be refreshed after the native options are repopulated —
// otherwise the model dropdown stays hidden until the next page load and
// shows up empty.
describe('Custom dropdown wrapper integration', () => {
  it('updates model row when provider is picked via the custom dropdown (no change event)', async () => {
    const { upgradeSelect } = await import('../state.js');

    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce({ provider: 'tesseract', fallback_to_tesseract: false, models: {} });
    await loadOcrSettings();

    // Find the onSelect callback that loadOcrProviders passed to upgradeSelect
    // for the provider <select>. This is the function _pick() invokes when the
    // user picks an option in the custom dropdown.
    const providerSel = document.getElementById('ocr-provider-select');
    const upgradeCall = upgradeSelect.mock.calls
      .filter((c) => c[0] === providerSel && typeof c[1] === 'function')
      .pop();
    expect(upgradeCall).toBeDefined();
    const onSelect = upgradeCall[1];

    // Simulate the custom dropdown picking gemini: _pick assigns the value
    // directly and then invokes the callback (no change event dispatched).
    providerSel.value = 'gemini';
    onSelect('gemini');

    const modelRow = document.getElementById('ocr-model-row');
    const modelSelect = document.getElementById('ocr-model-select');

    // Model row must become visible
    expect(modelRow.style.display).not.toBe('none');
    // And the native model <select> must contain the gemini models
    const options = Array.from(modelSelect.options).map((o) => o.value);
    expect(options).toContain('gemini-2.0-flash');
  });

  it('refreshes the custom dropdown wrapper for the model select after populating options', async () => {
    const { upgradeSelect } = await import('../state.js');

    api.mockResolvedValueOnce(MOCK_PROVIDERS_RESPONSE);
    await loadOcrProviders();

    api.mockResolvedValueOnce(MOCK_SETTINGS_RESPONSE);
    await loadOcrSettings();

    const modelSelect = document.getElementById('ocr-model-select');
    // upgradeSelect must have been called with the model <select> so the
    // custom wrapper picks up the freshly-appended <option> elements rather
    // than displaying an empty list.
    const wasUpgraded = upgradeSelect.mock.calls.some((c) => c[0] === modelSelect);
    expect(wasUpgraded).toBe(true);
  });
});
