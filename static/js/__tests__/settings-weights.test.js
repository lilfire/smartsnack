import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue([]),
  esc: (s) => String(s),
  upgradeSelect: vi.fn(),
  showToast: vi.fn(),
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
vi.mock('../settings-off.js', () => ({ loadOffCredentials: vi.fn(), checkRefreshStatus: vi.fn() }));
vi.mock('../render.js', () => ({ loadFlagConfig: vi.fn(), getFlagConfig: vi.fn(() => ({})) }));

import {
  SCORE_COLORS,
  SCORE_CFG_MAP,
  weightData,
  toggleWeightConfig,
  removeWeight,
  addWeightFromDropdown,
  onWeightDirection,
  onWeightFormula,
  onWeightMin,
  onWeightMax,
  onWeightSlider,
  saveWeights,
  renderWeightItems,
} from '../settings-weights.js';
import { api, showToast, upgradeSelect } from '../state.js';
import { loadData } from '../products.js';

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  document.body.innerHTML = '';
  weightData.length = 0;
  api.mockResolvedValue([]);
});

afterEach(() => {
  vi.useRealTimers();
});

function addWeightItem(field, enabled = true, weight = 50, direction = 'lower', formula = 'minmax') {
  weightData.push({ field, enabled, weight, direction, formula, formula_min: 0, formula_max: 100, label: field });
}

// ── SCORE_COLORS ─────────────────────────────────────
describe('SCORE_COLORS', () => {
  it('contains expected color keys', () => {
    expect(SCORE_COLORS.kcal).toBeTruthy();
    expect(SCORE_COLORS.protein).toBeTruthy();
    expect(SCORE_COLORS.salt).toBeTruthy();
  });
});

// ── toggleWeightConfig ───────────────────────────────
describe('toggleWeightConfig', () => {
  it('toggles config visibility', () => {
    document.body.innerHTML = '<div id="wcfg-kcal" style="display:none"></div>';
    toggleWeightConfig('kcal');
    expect(document.getElementById('wcfg-kcal').style.display).toBe('');
    toggleWeightConfig('kcal');
    expect(document.getElementById('wcfg-kcal').style.display).toBe('none');
  });

  it('does nothing if element missing', () => {
    expect(() => toggleWeightConfig('nonexistent')).not.toThrow();
  });
});

// ── removeWeight ─────────────────────────────────────
describe('removeWeight', () => {
  it('disables weight and sets to 0', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    addWeightItem('kcal', true, 50);
    removeWeight('kcal');
    const item = weightData.find((w) => w.field === 'kcal');
    expect(item.enabled).toBe(false);
    expect(item.weight).toBe(0);
  });

  it('does nothing for unknown field', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    expect(() => removeWeight('unknownfield')).not.toThrow();
  });
});

// ── addWeightFromDropdown ────────────────────────────
describe('addWeightFromDropdown', () => {
  it('returns early when no select or empty value', () => {
    document.body.innerHTML = '';
    expect(() => addWeightFromDropdown()).not.toThrow();
  });

  it('enables a disabled weight', () => {
    document.body.innerHTML = `
      <select id="weight-add-select"><option value="protein">Protein</option></select>
      <div id="weight-items"></div>`;
    document.getElementById('weight-add-select').value = 'protein';
    addWeightItem('protein', false, 0);
    addWeightFromDropdown();
    const item = weightData.find((w) => w.field === 'protein');
    expect(item.enabled).toBe(true);
    expect(item.weight).toBe(10);
  });

  it('does not change weight if already > 0', () => {
    document.body.innerHTML = `
      <select id="weight-add-select"><option value="fat">Fat</option></select>
      <div id="weight-items"></div>`;
    document.getElementById('weight-add-select').value = 'fat';
    addWeightItem('fat', false, 30);
    addWeightFromDropdown();
    expect(weightData.find((w) => w.field === 'fat').weight).toBe(30);
  });
});

// ── onWeightDirection ────────────────────────────────
describe('onWeightDirection', () => {
  it('updates direction from select element', () => {
    document.body.innerHTML = '<select id="wd-kcal"><option value="higher">Higher</option></select>';
    document.getElementById('wd-kcal').value = 'higher';
    addWeightItem('kcal');
    onWeightDirection('kcal');
    vi.advanceTimersByTime(400);
    expect(weightData.find((w) => w.field === 'kcal').direction).toBe('higher');
  });
});

// ── onWeightFormula ──────────────────────────────────
describe('onWeightFormula', () => {
  it('updates formula and shows/hides min/max inputs', () => {
    document.body.innerHTML = `
      <select id="wf-kcal"><option value="direct">Direct</option></select>
      <input id="wn-kcal" style="display:none">
      <input id="wm-kcal" style="display:none">`;
    document.getElementById('wf-kcal').value = 'direct';
    addWeightItem('kcal');
    onWeightFormula('kcal');
    expect(document.getElementById('wn-kcal').style.display).toBe('');
    expect(document.getElementById('wm-kcal').style.display).toBe('');
  });

  it('hides min/max for minmax formula', () => {
    document.body.innerHTML = `
      <select id="wf-kcal"><option value="minmax">Minmax</option></select>
      <input id="wn-kcal" style="">
      <input id="wm-kcal" style="">`;
    document.getElementById('wf-kcal').value = 'minmax';
    addWeightItem('kcal', true, 50, 'lower', 'direct');
    onWeightFormula('kcal');
    expect(document.getElementById('wn-kcal').style.display).toBe('none');
    expect(document.getElementById('wm-kcal').style.display).toBe('none');
  });
});

// ── onWeightMin / onWeightMax ────────────────────────
describe('onWeightMin', () => {
  it('updates formula_min on weight item', () => {
    document.body.innerHTML = '<input id="wn-kcal" value="5">';
    addWeightItem('kcal');
    onWeightMin('kcal');
    vi.advanceTimersByTime(400);
    expect(weightData.find((w) => w.field === 'kcal').formula_min).toBe(5);
  });
});

describe('onWeightMax', () => {
  it('updates formula_max on weight item', () => {
    document.body.innerHTML = '<input id="wm-kcal" value="200">';
    addWeightItem('kcal');
    onWeightMax('kcal');
    vi.advanceTimersByTime(400);
    expect(weightData.find((w) => w.field === 'kcal').formula_max).toBe(200);
  });
});

// ── onWeightSlider ───────────────────────────────────
describe('onWeightSlider', () => {
  it('updates weight from slider and shows value', () => {
    document.body.innerHTML = `
      <input id="w-kcal" value="75">
      <span id="wv-kcal"></span>`;
    addWeightItem('kcal');
    onWeightSlider('kcal');
    expect(document.getElementById('wv-kcal').textContent).toBe('75.0');
    expect(weightData.find((w) => w.field === 'kcal').weight).toBe(75);
  });
});

// ── saveWeights ──────────────────────────────────────
describe('saveWeights', () => {
  it('calls api with weight payload', async () => {
    document.body.innerHTML = '<div id="weights-saved-indicator"></div>';
    addWeightItem('kcal', true, 50);
    document.body.innerHTML += '<input id="w-kcal" value="50"><input id="wn-kcal" value=""><input id="wm-kcal" value="">';
    api.mockResolvedValue({});
    await saveWeights();
    expect(api).toHaveBeenCalledWith('/api/weights', expect.objectContaining({ method: 'PUT' }));
    expect(loadData).toHaveBeenCalled();
  });

  it('shows error toast on API failure', async () => {
    addWeightItem('kcal', true, 50);
    document.body.innerHTML = '<input id="w-kcal" value="50"><input id="wn-kcal" value=""><input id="wm-kcal" value="">';
    api.mockRejectedValue(new Error('fail'));
    await saveWeights();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── renderWeightItems ────────────────────────────────
describe('renderWeightItems', () => {
  it('renders enabled weight items', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    addWeightItem('kcal', true, 60);
    renderWeightItems();
    const container = document.getElementById('weight-items');
    expect(container.querySelector('#wi-kcal')).not.toBeNull();
  });

  it('renders dropdown for disabled weights', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    addWeightItem('kcal', true, 60);
    addWeightItem('protein', false, 0);
    renderWeightItems();
    const select = document.getElementById('weight-add-select');
    expect(select).not.toBeNull();
  });

  it('renders no dropdown when all weights are enabled', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    addWeightItem('kcal', true, 60);
    renderWeightItems();
    expect(document.getElementById('weight-add-select')).toBeNull();
  });
});

// ── renderWeightItems upgradeSelect callbacks ──────────
// Invoke anonymous callbacks passed to upgradeSelect to cover lines 228, 232, 235

describe('renderWeightItems - weight-add-select callback (line 228)', () => {
  it('calling the upgradeSelect callback for weight-add-select triggers addWeightFromDropdown', () => {
    document.body.innerHTML = '<div id="weight-items"></div>';
    addWeightItem('kcal', true, 60);
    addWeightItem('fat', false, 0);
    vi.clearAllMocks();
    renderWeightItems();

    // upgradeSelect mock.calls:
    // [0] = weight-add-select (disabled weights present)
    // [1] = wd-kcal, [2] = wf-kcal
    const addCallback = upgradeSelect.mock.calls[0]?.[1];
    expect(typeof addCallback).toBe('function');

    // Set the dropdown value so addWeightFromDropdown does something
    const sel = document.getElementById('weight-add-select');
    if (sel) sel.value = 'fat';
    addCallback();

    const fatItem = weightData.find((w) => w.field === 'fat');
    expect(fatItem.enabled).toBe(true);
  });
});

describe('renderWeightItems - direction/formula callbacks (lines 232, 235)', () => {
  it('direction callback calls onWeightDirection for the field', () => {
    document.body.innerHTML = `
      <div id="weight-items"></div>
      <select id="wd-kcal"><option value="higher">Higher</option></select>
      <select id="wf-kcal"><option value="minmax">Minmax</option></select>
      <input id="wn-kcal" style="display:none">
      <input id="wm-kcal" style="display:none">`;
    addWeightItem('kcal', true, 60, 'lower', 'minmax');
    vi.clearAllMocks();
    renderWeightItems();

    // upgradeSelect call order: [0]=weight-add-select, [1]=wd-kcal, [2]=wf-kcal
    const dirCallback = upgradeSelect.mock.calls[1]?.[1];
    expect(typeof dirCallback).toBe('function');
    document.getElementById('wd-kcal').value = 'higher';
    dirCallback();
    expect(weightData.find((w) => w.field === 'kcal').direction).toBe('higher');
  });

  it('formula callback calls onWeightFormula for the field', () => {
    document.body.innerHTML = `
      <div id="weight-items"></div>
      <select id="wd-kcal"><option value="lower">Lower</option></select>
      <select id="wf-kcal"><option value="direct">Direct</option></select>
      <input id="wn-kcal" style="display:none">
      <input id="wm-kcal" style="display:none">`;
    addWeightItem('kcal', true, 60, 'lower', 'minmax');
    vi.clearAllMocks();
    renderWeightItems();

    // upgradeSelect call order: [0]=weight-add-select, [1]=wd-kcal, [2]=wf-kcal
    const fmlaCallback = upgradeSelect.mock.calls[2]?.[1];
    expect(typeof fmlaCallback).toBe('function');
    document.getElementById('wf-kcal').value = 'direct';
    fmlaCallback();
    expect(weightData.find((w) => w.field === 'kcal').formula).toBe('direct');
  });
});
