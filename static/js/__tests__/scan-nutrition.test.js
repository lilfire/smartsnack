import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((key, params) => {
    if (!params) return key;
    return key + ':' + JSON.stringify(params);
  }),
}));

vi.mock('../images.js', () => ({
  resizeImage: vi.fn((dataUri) => Promise.resolve(dataUri)),
}));

import { scanNutrition } from '../ocr.js';
import { api, showToast } from '../state.js';
import { resizeImage } from '../images.js';

const NUTRI_FIELDS = [
  'kcal', 'energy_kj', 'fat', 'saturated_fat',
  'carbs', 'sugar', 'fiber', 'protein', 'salt',
];

function createNutritionDOM(prefix) {
  const btn = document.createElement('button');
  btn.id = prefix + '-ocr-nutri-btn';
  const spin = document.createElement('span');
  spin.className = 'ocr-spin';
  spin.style.display = 'none';
  btn.appendChild(spin);
  document.body.appendChild(btn);

  const inputs = {};
  for (const field of NUTRI_FIELDS) {
    const input = document.createElement('input');
    input.type = 'number';
    input.id = prefix + '-' + field;
    document.body.appendChild(input);
    inputs[field] = input;
  }
  return { btn, inputs };
}

async function runScanWithResponse(prefix, response) {
  const fakeDataUrl = 'data:image/jpeg;base64,xyz';
  resizeImage.mockResolvedValueOnce(fakeDataUrl);
  if (response instanceof Error) {
    api.mockRejectedValueOnce(response);
  } else {
    api.mockResolvedValueOnce(response);
  }

  let fileInput;
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
    fileInput = this;
  });

  scanNutrition(prefix);
  clickSpy.mockRestore();

  const file = new File([new Uint8Array(100)], 'label.jpg', { type: 'image/jpeg' });
  Object.defineProperty(fileInput, 'files', { value: [file], writable: false });

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

  fileInput.onchange();

  await vi.waitFor(() => {
    expect(api).toHaveBeenCalled();
  }, { timeout: 2000 });
  // Allow the async onSuccess to complete.
  await new Promise((r) => setTimeout(r, 5));

  globalThis.FileReader = originalFileReader;
}

describe('scanNutrition', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('posts to /api/ocr/nutrition', async () => {
    createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: { kcal: 250 },
      count: 1,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(api).toHaveBeenCalledWith(
      '/api/ocr/nutrition',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('populates empty inputs with returned values', async () => {
    const { inputs } = createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: {
        kcal: 250,
        fat: 12.5,
        protein: 8,
        salt: 0.8,
      },
      count: 4,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(inputs.kcal.value).toBe('250');
    expect(inputs.fat.value).toBe('12.5');
    expect(inputs.protein.value).toBe('8');
    expect(inputs.salt.value).toBe('0.8');
    expect(inputs.carbs.value).toBe('');
  });

  it('skips non-empty inputs (overwrite protection)', async () => {
    const { inputs } = createNutritionDOM('f');
    inputs.fat.value = '99';
    await runScanWithResponse('f', {
      values: { kcal: 250, fat: 12.5 },
      count: 2,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(inputs.kcal.value).toBe('250');
    expect(inputs.fat.value).toBe('99'); // unchanged
  });

  it('adds ocr-flash class to filled inputs', async () => {
    const { inputs } = createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: { kcal: 250 },
      count: 1,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(inputs.kcal.classList.contains('ocr-flash')).toBe(true);
  });

  it('shows success toast with filled/skipped counts', async () => {
    const { inputs } = createNutritionDOM('f');
    inputs.fat.value = '99';
    await runScanWithResponse('f', {
      values: { kcal: 250, fat: 12.5, protein: 8 },
      count: 3,
      provider: 'Claude Vision',
      fallback: false,
    });
    const successCalls = showToast.mock.calls.filter(
      (c) => c[0].startsWith('toast_ocr_nutrition_success_provider')
    );
    expect(successCalls.length).toBe(1);
    expect(successCalls[0][0]).toContain('"filled":2');
    expect(successCalls[0][0]).toContain('"skipped":1');
    expect(successCalls[0][0]).toContain('"provider":"Claude Vision"');
  });

  it('shows no_values toast when values dict is empty', async () => {
    createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: {},
      count: 0,
      error_type: 'no_values',
      provider: 'Tesseract (Local)',
      fallback: false,
    });
    const noValuesCalls = showToast.mock.calls.filter(
      (c) => c[0] === 'toast_ocr_nutrition_no_values'
    );
    expect(noValuesCalls.length).toBe(1);
  });

  it('shows all_skipped toast when every returned field was pre-filled', async () => {
    const { inputs } = createNutritionDOM('f');
    inputs.kcal.value = '100';
    inputs.fat.value = '5';
    await runScanWithResponse('f', {
      values: { kcal: 250, fat: 12.5 },
      count: 2,
      provider: 'Claude Vision',
      fallback: false,
    });
    const skippedCalls = showToast.mock.calls.filter(
      (c) => c[0].startsWith('toast_ocr_nutrition_all_skipped')
    );
    expect(skippedCalls.length).toBe(1);
    expect(skippedCalls[0][0]).toContain('"skipped":2');
    // Values must remain unchanged.
    expect(inputs.kcal.value).toBe('100');
    expect(inputs.fat.value).toBe('5');
  });

  it('shows fallback toast when provider fell back to tesseract', async () => {
    createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: { kcal: 250 },
      count: 1,
      provider: 'Tesseract (Local)',
      fallback: true,
    });
    const fallbackCalls = showToast.mock.calls.filter(
      (c) => c[0].startsWith('toast_ocr_fallback')
    );
    expect(fallbackCalls.length).toBe(1);
  });

  it('dispatches quota toast on 429 error', async () => {
    createNutritionDOM('f');
    const err = new Error('quota');
    err.data = { error_type: 'provider_quota' };
    await runScanWithResponse('f', err);
    const quotaCalls = showToast.mock.calls.filter(
      (c) => c[0] === 'toast_ocr_provider_quota'
    );
    expect(quotaCalls.length).toBe(1);
  });

  it('dispatches invalid_image toast on 400 error', async () => {
    createNutritionDOM('f');
    const err = new Error('bad image');
    err.data = { error_type: 'invalid_image' };
    await runScanWithResponse('f', err);
    const invalidCalls = showToast.mock.calls.filter(
      (c) => c[0] === 'toast_ocr_invalid_image'
    );
    expect(invalidCalls.length).toBe(1);
  });

  it('filters unknown keys from values dict', async () => {
    const { inputs } = createNutritionDOM('f');
    await runScanWithResponse('f', {
      values: { kcal: 250, not_a_field: 999, fat: 10 },
      count: 3,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(inputs.kcal.value).toBe('250');
    expect(inputs.fat.value).toBe('10');
    // A rogue input must not be created by the scanner.
    expect(document.getElementById('f-not_a_field')).toBeNull();
  });

  it('also works with edit-modal prefix "ed"', async () => {
    const { inputs } = createNutritionDOM('ed');
    await runScanWithResponse('ed', {
      values: { kcal: 300, protein: 10 },
      count: 2,
      provider: 'Claude Vision',
      fallback: false,
    });
    expect(inputs.kcal.value).toBe('300');
    expect(inputs.protein.value).toBe('10');
  });

  it('rejects files over 10 MB', async () => {
    createNutritionDOM('f');
    let fileInput;
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function () {
      fileInput = this;
    });
    scanNutrition('f');
    clickSpy.mockRestore();

    const bigFile = new File([new Uint8Array(11 * 1024 * 1024)], 'big.jpg', { type: 'image/jpeg' });
    Object.defineProperty(fileInput, 'files', { value: [bigFile], writable: false });
    fileInput.onchange();

    expect(showToast).toHaveBeenCalledWith('toast_image_too_large', 'error');
    expect(api).not.toHaveBeenCalled();
  });
});
