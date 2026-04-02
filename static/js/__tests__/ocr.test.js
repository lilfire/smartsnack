import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

import { scanIngredients } from '../ocr.js';
import { api, showToast } from '../state.js';
import { t } from '../i18n.js';

function createDOM(prefix) {
  const textarea = document.createElement('textarea');
  textarea.id = prefix + '-ingredients';
  document.body.appendChild(textarea);

  const btn = document.createElement('button');
  btn.id = prefix + '-ocr-btn';
  const spin = document.createElement('span');
  spin.className = 'ocr-spin';
  spin.style.display = 'none';
  btn.appendChild(spin);
  document.body.appendChild(btn);

  return { textarea, btn, spin };
}

function createFile(sizeBytes = 100) {
  return new File([new Uint8Array(sizeBytes)], 'photo.jpg', { type: 'image/jpeg' });
}

describe('scanIngredients', () => {
  let prefix;

  beforeEach(() => {
    prefix = 'reg';
    document.body.innerHTML = '';
    vi.clearAllMocks();
  });

  it('does nothing if textarea not found', () => {
    scanIngredients('nonexistent');
    // No error thrown, no elements created
  });

  it('creates a file input and clicks it', () => {
    createDOM(prefix);
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {});
    scanIngredients(prefix);
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it('shows error toast for files over 10 MB', async () => {
    const { textarea } = createDOM(prefix);
    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    const bigFile = new File([new Uint8Array(11 * 1024 * 1024)], 'big.jpg', { type: 'image/jpeg' });
    Object.defineProperty(fileInput, 'files', { value: [bigFile], writable: false });
    fileInput.onchange();

    expect(showToast).toHaveBeenCalledWith('toast_image_too_large', 'error');
  });

  it('does nothing if no files selected', async () => {
    createDOM(prefix);
    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [], writable: false });
    fileInput.onchange();

    expect(api).not.toHaveBeenCalled();
  });

  it('calls API and sets textarea value on success', async () => {
    const { textarea, btn, spin } = createDOM(prefix);
    api.mockResolvedValueOnce({ text: 'sukker, mel, vann' });

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    const file = createFile();
    Object.defineProperty(fileInput, 'files', { value: [file], writable: false });

    // Trigger onchange — this starts FormData upload
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith('/api/ocr/ingredients', expect.objectContaining({
        method: 'POST',
      }));
    }, { timeout: 2000 });

    await vi.waitFor(() => {
      expect(textarea.value).toBe('sukker, mel, vann');
      expect(showToast).toHaveBeenCalledWith('toast_ocr_success_provider', 'success', { title: 'toast_ocr_title_success', duration: 3000 });
    }, { timeout: 2000 });
  });

  it('shows error toast when API returns no text', async () => {
    createDOM(prefix);
    api.mockResolvedValueOnce({ text: '' });

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_ocr_no_text', 'error');
    }, { timeout: 2000 });
  });

  it('shows error toast when API throws', async () => {
    createDOM(prefix);
    api.mockRejectedValueOnce(new Error('network error'));

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_ocr_generic_error', 'error', { title: 'toast_ocr_title_failed', duration: 5000 });
    }, { timeout: 2000 });
  });

  it('shows error toast for token limit exceeded', async () => {
    createDOM(prefix);
    const tokenErr = new Error('token limit');
    tokenErr.data = { error_type: 'token_limit' };
    api.mockRejectedValueOnce(tokenErr);

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_ocr_token_limit', 'error', { title: 'toast_ocr_title_failed', duration: 5000 });
    }, { timeout: 2000 });
  });

  it('shows warning toast for fallback provider', async () => {
    createDOM(prefix);
    api.mockResolvedValueOnce({ text: 'sukker, mel', fallback: true, provider: 'Tesseract', error_detail: 'invalid API key' });

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_ocr_fallback', 'warning', { title: 'toast_ocr_title_fallback', duration: 5000 });
    }, { timeout: 2000 });
  });

  it('appends to existing textarea content', async () => {
    const { textarea } = createDOM(prefix);
    textarea.value = 'existing ingredients';
    api.mockResolvedValueOnce({ text: 'new text' });

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(textarea.value).toBe('existing ingredients\nnew text');
    }, { timeout: 2000 });
  });

  it('disables button and shows spinner during OCR', async () => {
    const { btn, spin } = createDOM(prefix);
    let resolveApi;
    api.mockImplementationOnce(() => new Promise(r => { resolveApi = r; }));

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalled();
    }, { timeout: 2000 });

    // Button should be disabled while API is pending
    expect(btn.disabled).toBe(true);
    expect(spin.style.display).toBe('inline-block');

    // Resolve the API call
    resolveApi({ text: 'done' });

    await vi.waitFor(() => {
      expect(btn.disabled).toBe(false);
      expect(spin.style.display).toBe('none');
    }, { timeout: 2000 });
  });

  it('works without button element', async () => {
    // Only create textarea, no button
    const textarea = document.createElement('textarea');
    textarea.id = prefix + '-ingredients';
    document.body.appendChild(textarea);
    api.mockResolvedValueOnce({ text: 'result' });

    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });

    scanIngredients(prefix);
    clickSpy.mockRestore();

    Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
    fileInput.onchange();

    await vi.waitFor(() => {
      expect(textarea.value).toBe('result');
    }, { timeout: 2000 });
  });
});
