import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MOCK_OCR_SETTINGS } from './mock-shapes.js';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({ provider: 'tesseract', fallback_to_tesseract: false, models: {} }),
  showToast: vi.fn(),
  upgradeSelect: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

import { loadOcrProviders, loadOcrSettings, saveOcrSettings } from '../settings-ocr.js';
import { api, showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  api.mockResolvedValue(MOCK_OCR_SETTINGS);
});

function setupOcrDOM(provider = 'tesseract', fallback = false) {
  document.body.innerHTML = `
    <select id="ocr-provider-select">
      <option value="tesseract">Tesseract OCR</option>
    </select>
    <div id="ocr-fallback-wrapper"></div>
    <input id="ocr-fallback-checkbox" type="checkbox" ${fallback ? 'checked' : ''}>`;
  document.getElementById('ocr-provider-select').value = provider;
}

// ── loadOcrProviders ─────────────────────────────────
describe('loadOcrProviders', () => {
  it('does nothing if select element missing', async () => {
    await loadOcrProviders();
    expect(api).not.toHaveBeenCalled();
  });

  it('populates select with providers', async () => {
    setupOcrDOM();
    api.mockResolvedValue({
      providers: [
        { key: 'tesseract', label: 'Tesseract OCR' },
        { key: 'openai', label: 'OpenAI Vision' },
      ],
    });
    await loadOcrProviders();
    const sel = document.getElementById('ocr-provider-select');
    expect(sel.querySelectorAll('option').length).toBe(2);
    expect(sel.querySelector('option[value="openai"]')).not.toBeNull();
  });

  it('falls back to tesseract option on API failure', async () => {
    setupOcrDOM();
    const sel = document.getElementById('ocr-provider-select');
    sel.innerHTML = ''; // empty it first
    api.mockRejectedValue(new Error('fail'));
    await loadOcrProviders();
    expect(sel.querySelector('option[value="tesseract"]')).not.toBeNull();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('does not add fallback option if options already present on failure', async () => {
    setupOcrDOM(); // already has one option
    api.mockRejectedValue(new Error('fail'));
    await loadOcrProviders();
    // No additional option should be added since one already exists
    const sel = document.getElementById('ocr-provider-select');
    expect(sel.querySelectorAll('option').length).toBe(1);
  });
});

// ── loadOcrSettings ──────────────────────────────────
describe('loadOcrSettings', () => {
  it('does nothing if select element missing', async () => {
    await loadOcrSettings();
    expect(api).not.toHaveBeenCalled();
  });

  it('sets select value from settings', async () => {
    setupOcrDOM();
    const sel = document.getElementById('ocr-provider-select');
    const opt = document.createElement('option');
    opt.value = 'openai';
    sel.appendChild(opt);
    api.mockResolvedValue({ provider: 'openai', fallback_to_tesseract: false });
    await loadOcrSettings();
    expect(sel.value).toBe('openai');
  });

  it('sets fallback checkbox from settings', async () => {
    setupOcrDOM();
    const sel = document.getElementById('ocr-provider-select');
    const opt = document.createElement('option');
    opt.value = 'openai';
    sel.appendChild(opt);
    api.mockResolvedValue({ provider: 'openai', fallback_to_tesseract: true });
    await loadOcrSettings();
    expect(document.getElementById('ocr-fallback-checkbox').checked).toBe(true);
  });

  it('hides fallback wrapper for tesseract provider', async () => {
    setupOcrDOM('tesseract');
    api.mockResolvedValue({ provider: 'tesseract' });
    await loadOcrSettings();
    const wrapper = document.getElementById('ocr-fallback-wrapper');
    expect(wrapper.classList.contains('visible')).toBe(false);
  });

  it('shows fallback wrapper for non-tesseract provider', async () => {
    setupOcrDOM('openai');
    const sel = document.getElementById('ocr-provider-select');
    const opt = document.createElement('option');
    opt.value = 'openai';
    sel.appendChild(opt);
    api.mockResolvedValue({ provider: 'openai' });
    await loadOcrSettings();
    const wrapper = document.getElementById('ocr-fallback-wrapper');
    expect(wrapper.classList.contains('visible')).toBe(true);
  });

  it('does not throw on API failure (uses defaults)', async () => {
    setupOcrDOM();
    api.mockRejectedValue(new Error('fail'));
    await expect(loadOcrSettings()).resolves.not.toThrow();
  });
});

// ── saveOcrSettings ──────────────────────────────────
describe('saveOcrSettings', () => {
  it('does nothing if select missing', async () => {
    await saveOcrSettings();
    expect(api).not.toHaveBeenCalled();
  });

  it('calls api with selected provider', async () => {
    setupOcrDOM('tesseract', false);
    await saveOcrSettings();
    expect(api).toHaveBeenCalledWith(
      '/api/ocr/settings',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"provider":"tesseract"'),
      }),
    );
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('includes fallback_to_tesseract in body', async () => {
    setupOcrDOM('tesseract', true);
    document.getElementById('ocr-fallback-checkbox').checked = true;
    await saveOcrSettings();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.fallback_to_tesseract).toBe(true);
  });

  it('shows error on API failure', async () => {
    setupOcrDOM();
    api.mockRejectedValue(new Error('fail'));
    await saveOcrSettings();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('does nothing when select value is empty', async () => {
    setupOcrDOM();
    document.getElementById('ocr-provider-select').value = '';
    await saveOcrSettings();
    expect(api).not.toHaveBeenCalled();
  });
});
