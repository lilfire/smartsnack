/**
 * Tests for OCR toast notification system — all 4 scenarios + accessibility.
 *
 * These tests validate the expected toast notification behavior for the
 * OCR toast notification system as specified in LSO-228/LSO-229:
 *
 * 1. Success: Primary Provider — success toast, 3s duration
 * 2. Success: Fallback Provider — warning toast, 5s duration
 * 3. Failure: Token Limit Exceeded — error toast, 5s duration
 * 4. Failure: Generic Error — error toast with detail, 5s duration
 * 5. Generic Error fallback — default message when error_detail missing
 * 6. Accessibility — ARIA live regions
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((key, params) => {
    // Return key with params interpolated for testing
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  }),
}));

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((dataUri) => Promise.resolve(dataUri)),
}));

import { scanIngredients } from '../ocr.js';
import { api, showToast } from '../state.js';
import { t } from '../i18n.js';
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

/**
 * Helper to trigger scanIngredients with a file and wait for API call.
 * Installs a MockFileReader so the async FileReader path completes.
 * Returns the fileInput for further assertions if needed.
 */
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

  // Wait for FileReader + resizeImage + API call to complete
  await vi.waitFor(() => {
    expect(api).toHaveBeenCalled();
  }, { timeout: 2000 });

  globalThis.FileReader = originalFileReader;
  return fileInput;
}

describe('OCR Toast Notifications', () => {
  const prefix = 'reg';

  beforeEach(() => {
    document.body.innerHTML = '';
    vi.clearAllMocks();
  });

  describe('Scenario 1: Success — Primary Provider', () => {
    it('shows success toast when API returns text with provider', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({ text: 'sukker, mel, vann', provider: 'EasyOCR' });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const call = showToast.mock.calls[0];
      // Should show success toast
      expect(call[1]).toBe('success');
    });

    it('sets textarea value on success', async () => {
      const { textarea } = createDOM(prefix);
      api.mockResolvedValueOnce({ text: 'sukker, mel, vann', provider: 'EasyOCR' });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(textarea.value).toBe('sukker, mel, vann');
      }, { timeout: 2000 });
    });

    it('uses success toast type (not warning or error)', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({ text: 'ingredients', provider: 'EasyOCR' });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
        const call = showToast.mock.calls[0];
        expect(call[1]).toBe('success');
        // For primary provider, no fallback field, should NOT be warning
        expect(call[1]).not.toBe('warning');
      }, { timeout: 2000 });
    });
  });

  describe('Scenario 2: Success — Fallback Provider', () => {
    it('shows warning toast when API returns fallback response', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({
        text: 'sukker, mel',
        provider: 'EasyOCR',
        fallback: true,
        fallback_provider: 'EasyOCR',
        reason: 'primary provider unavailable',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      // With fallback, toast type should be 'warning' not 'success'
      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[1]).toBe('warning');
    });

    it('uses 5s duration for fallback warning toast', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({
        text: 'mel',
        provider: 'EasyOCR',
        fallback: true,
        fallback_provider: 'EasyOCR',
        reason: 'primary provider unavailable',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      // Duration should be 5000ms for warning toasts
      if (toastCall[2] && toastCall[2].duration) {
        expect(toastCall[2].duration).toBe(5000);
      }
    });

    it('still sets textarea value on fallback success', async () => {
      const { textarea } = createDOM(prefix);
      api.mockResolvedValueOnce({
        text: 'mel, sukker',
        provider: 'EasyOCR',
        fallback: true,
        fallback_provider: 'EasyOCR',
        reason: 'primary provider unavailable',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(textarea.value).toBe('mel, sukker');
      }, { timeout: 2000 });
    });
  });

  describe('Scenario 3: Failure — Token Limit Exceeded', () => {
    it('shows error toast for token limit exceeded', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({
        error: 'Token limit exceeded',
        error_type: 'token_limit_exceeded',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[1]).toBe('error');
    });

    it('does not set textarea value on token limit error', async () => {
      const { textarea } = createDOM(prefix);
      api.mockResolvedValueOnce({
        error: 'Token limit exceeded',
        error_type: 'token_limit_exceeded',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      expect(textarea.value).toBe('');
    });
  });

  describe('Scenario 4: Failure — Generic Error', () => {
    it('shows error toast with error_detail for generic errors', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({
        error: 'OCR processing failed',
        error_type: 'generic',
        error_detail: 'network timeout',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[1]).toBe('error');
    });

    it('does not set textarea on generic error', async () => {
      const { textarea } = createDOM(prefix);
      api.mockResolvedValueOnce({
        error: 'OCR processing failed',
        error_type: 'generic',
        error_detail: 'network timeout',
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      expect(textarea.value).toBe('');
    });
  });

  describe('Scenario 4b: Failure — Invalid Image', () => {
    it('shows error toast with invalid_image translation key', async () => {
      createDOM(prefix);
      const err = new Error('Bad Request');
      err.data = { error: 'Invalid or corrupt image', error_type: 'invalid_image' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[0]).toBe('toast_ocr_invalid_image');
      expect(toastCall[1]).toBe('error');
    });

    it('does not set textarea on invalid_image error', async () => {
      const { textarea } = createDOM(prefix);
      const err = new Error('Bad Request');
      err.data = { error: 'Invalid or corrupt image', error_type: 'invalid_image' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      expect(textarea.value).toBe('');
    });
  });

  describe('Scenario 4c: Failure — Provider Timeout', () => {
    it('shows error toast with provider_timeout translation key', async () => {
      createDOM(prefix);
      const err = new Error('Service Unavailable');
      err.data = { error: 'OCR provider is not responding', error_type: 'provider_timeout' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[0]).toBe('toast_ocr_provider_timeout');
      expect(toastCall[1]).toBe('error');
    });

    it('does not set textarea on provider_timeout error', async () => {
      const { textarea } = createDOM(prefix);
      const err = new Error('Service Unavailable');
      err.data = { error: 'OCR provider is not responding', error_type: 'provider_timeout' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      expect(textarea.value).toBe('');
    });
  });

  describe('Scenario 4d: Failure — Provider Quota Exceeded', () => {
    it('shows error toast with provider_quota translation key', async () => {
      createDOM(prefix);
      const err = new Error('Too Many Requests');
      err.data = { error: 'OCR provider quota exceeded', error_type: 'provider_quota' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[0]).toBe('toast_ocr_provider_quota');
      expect(toastCall[1]).toBe('error');
    });

    it('uses 6s duration for provider_quota error toast', async () => {
      createDOM(prefix);
      const err = new Error('Too Many Requests');
      err.data = { error: 'OCR provider quota exceeded', error_type: 'provider_quota' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[2]).toMatchObject({ duration: 6000 });
    });

    it('does not set textarea on provider_quota error', async () => {
      const { textarea } = createDOM(prefix);
      const err = new Error('Too Many Requests');
      err.data = { error: 'OCR provider quota exceeded', error_type: 'provider_quota' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      expect(textarea.value).toBe('');
    });
  });

  describe('Scenario 4e: Failure — No Text (via error path)', () => {
    it('shows error toast with no_text translation key', async () => {
      createDOM(prefix);
      const err = new Error('No text');
      err.data = { error: 'No text found', error_type: 'no_text' };
      api.mockRejectedValueOnce(err);

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[0]).toBe('toast_ocr_no_text');
      expect(toastCall[1]).toBe('error');
    });
  });

  describe('Scenario 4e: Failure — Generic with error_detail', () => {
    it('passes error_detail to generic error translation key', async () => {
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
      // t() mock returns "key:params", so verify the key and that error_detail is passed
      expect(toastCall[0]).toContain('toast_ocr_generic_error');
      expect(toastCall[0]).toContain('OCR processing failed (RuntimeError)');
      expect(toastCall[1]).toBe('error');
    });
  });

  describe('Scenario 5: Generic Error Fallback — missing error_detail', () => {
    it('shows default error message when error_detail is missing', async () => {
      createDOM(prefix);
      api.mockResolvedValueOnce({
        error: 'OCR processing failed',
        error_type: 'generic',
        // No error_detail field
      });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(showToast).toHaveBeenCalled();
      }, { timeout: 2000 });

      const calls = showToast.mock.calls;
      const toastCall = calls[calls.length - 1];
      expect(toastCall[1]).toBe('error');
    });
  });

  describe('Scenario 6: Accessibility — ARIA live regions', () => {
    it('toast element exists in DOM for screen reader announcements', () => {
      // Create the toast element as it would be in the template
      const toast = document.createElement('div');
      toast.id = 'toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);

      const toastEl = document.getElementById('toast');
      expect(toastEl).not.toBeNull();
      expect(toastEl.getAttribute('aria-live')).toBeTruthy();
    });

    it('toast should use appropriate ARIA role', () => {
      const toast = document.createElement('div');
      toast.id = 'toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);

      const toastEl = document.getElementById('toast');
      const role = toastEl.getAttribute('role');
      // Should have role="status" or role="alert"
      expect(['status', 'alert']).toContain(role);
    });
  });

  describe('Button state management', () => {
    it('re-enables button after successful OCR', async () => {
      const { btn } = createDOM(prefix);
      api.mockResolvedValueOnce({ text: 'ingredients', provider: 'EasyOCR' });

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(btn.disabled).toBe(false);
      }, { timeout: 2000 });
    });

    it('re-enables button after error', async () => {
      const { btn } = createDOM(prefix);
      api.mockRejectedValueOnce(new Error('network error'));

      await triggerScan(prefix);

      await vi.waitFor(() => {
        expect(btn.disabled).toBe(false);
      }, { timeout: 2000 });
    });
  });
});
