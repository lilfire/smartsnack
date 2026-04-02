/**
 * Regression tests for OCR error_type alignment (LSO-354).
 *
 * Bug: Frontend checked error_type === 'token_limit' but the backend
 * returns 'token_limit_exceeded'. These tests verify the frontend
 * correctly handles the backend value.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((key, params) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  }),
}));

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((dataUri) => Promise.resolve(dataUri)),
}));

import { scanIngredients } from '../ocr.js';
import { api, showToast } from '../state.js';
import { resizeImage } from '../images.js';

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

async function triggerScan(prefix) {
  const fakeDataUrl = 'data:image/jpeg;base64,dGVzdA==';
  resizeImage.mockResolvedValueOnce(fakeDataUrl);

  let fileInput;
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
    fileInput = this;
  });

  scanIngredients(prefix);
  clickSpy.mockRestore();

  const originalFileReader = globalThis.FileReader;
  class MockFileReader {
    constructor() { this.onload = null; this.onerror = null; }
    readAsDataURL() {
      setTimeout(() => {
        if (this.onload) this.onload({ target: { result: fakeDataUrl } });
      }, 0);
    }
  }
  globalThis.FileReader = MockFileReader;

  Object.defineProperty(fileInput, 'files', { value: [createFile()], writable: false });
  fileInput.onchange();

  await vi.waitFor(() => {
    expect(api).toHaveBeenCalled();
  }, { timeout: 2000 });

  globalThis.FileReader = originalFileReader;
  return fileInput;
}

describe('OCR error_type regression — token_limit_exceeded (LSO-354)', () => {
  const prefix = 'reg354';

  beforeEach(() => {
    document.body.innerHTML = '';
    vi.clearAllMocks();
  });

  it('shows token_limit toast for error_type "token_limit_exceeded" (not "token_limit")', async () => {
    createDOM(prefix);
    const err = new Error('Token limit');
    err.data = { error: 'Token limit exceeded', error_type: 'token_limit_exceeded' };
    api.mockRejectedValueOnce(err);

    await triggerScan(prefix);

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 2000 });

    const calls = showToast.mock.calls;
    const toastCall = calls[calls.length - 1];
    expect(toastCall[0]).toBe('toast_ocr_token_limit');
    expect(toastCall[1]).toBe('error');
    expect(toastCall[2]).toEqual(
      expect.objectContaining({ duration: 5000 })
    );
  });

  it('does NOT match old "token_limit" value — generic handler used instead', async () => {
    createDOM(prefix);
    const err = new Error('Old token limit');
    // Simulate the OLD (incorrect) backend value that no longer exists
    err.data = { error: 'Token limit', error_type: 'token_limit', error_detail: 'old value' };
    api.mockRejectedValueOnce(err);

    await triggerScan(prefix);

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 2000 });

    const calls = showToast.mock.calls;
    const toastCall = calls[calls.length - 1];
    // The old "token_limit" value should fall through to the generic handler
    expect(toastCall[0]).toContain('toast_ocr_generic_error');
    expect(toastCall[1]).toBe('error');
  });

  it('handles generic errors without confusion with token_limit', async () => {
    createDOM(prefix);
    const err = new Error('Internal Server Error');
    err.data = {
      error: 'OCR processing failed',
      error_type: 'generic',
      error_detail: 'OCR processing failed (RuntimeError)',
    };
    api.mockRejectedValueOnce(err);

    await triggerScan(prefix);

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 2000 });

    const calls = showToast.mock.calls;
    const toastCall = calls[calls.length - 1];
    expect(toastCall[0]).toContain('toast_ocr_generic_error');
    expect(toastCall[1]).toBe('error');
  });
});
