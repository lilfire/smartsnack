// Regression tests for LSO-1700 Bug 1: a saveWeights() call arriving while a
// save is already in-flight must be queued and re-run, not silently dropped.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue([]),
  esc: (s) => String(s),
  upgradeSelect: vi.fn(),
  showToast: vi.fn(),
  showConfirmModal: vi.fn().mockResolvedValue(true),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((k) => k),
  getCurrentLang: vi.fn(() => 'no'),
  changeLanguage: vi.fn(),
}));

vi.mock('../products.js', () => ({ loadData: vi.fn() }));
vi.mock('../emoji-picker.js', () => ({ initEmojiPicker: vi.fn() }));
vi.mock('../settings-categories.js', () => ({ loadCategories: vi.fn() }));
vi.mock('../settings-flags.js', () => ({ loadFlags: vi.fn() }));
vi.mock('../settings-pq.js', () => ({ loadPq: vi.fn() }));
vi.mock('../settings-ocr.js', () => ({ loadOcrSettings: vi.fn(), loadOcrProviders: vi.fn() }));
vi.mock('../settings-off.js', () => ({ loadOffCredentials: vi.fn(), checkRefreshStatus: vi.fn(), loadOffLanguagePriority: vi.fn() }));

import { saveWeights, weightData } from '../settings-weights.js';
import { api } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  weightData.length = 0;
  weightData.push({ field: 'kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'kcal' });
  api.mockResolvedValue([]);
});

function flush() {
  return new Promise((r) => setTimeout(r, 0));
}

describe('saveWeights pending-save coalescing', () => {
  it('re-runs the save when called while a save is in-flight (API called exactly twice)', async () => {
    let resolveFirst;
    api.mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }));

    const p1 = saveWeights();
    // Second call arrives while the first PUT is still in-flight
    const p2 = saveWeights();
    await p2;
    expect(api).toHaveBeenCalledTimes(1);

    resolveFirst([]);
    await p1;
    await flush();

    // The in-flight change must trigger exactly one follow-up save
    expect(api).toHaveBeenCalledTimes(2);
    expect(api).toHaveBeenLastCalledWith('/api/weights', expect.objectContaining({ method: 'PUT' }));
  });

  it('coalesces multiple calls during one in-flight save into a single follow-up', async () => {
    let resolveFirst;
    api.mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }));

    const p1 = saveWeights();
    await saveWeights();
    await saveWeights();
    await saveWeights();
    expect(api).toHaveBeenCalledTimes(1);

    resolveFirst([]);
    await p1;
    await flush();
    expect(api).toHaveBeenCalledTimes(2);
  });

  it('does not schedule a follow-up save when no call arrived during the save', async () => {
    await saveWeights();
    await flush();
    expect(api).toHaveBeenCalledTimes(1);
  });
});
