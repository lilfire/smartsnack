import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

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
  onScopeChange,
  refreshScopeSelect,
  openAddOverridePicker,
  deleteActiveCategoryOverride,
} from '../settings-weights.js';
import { api, showToast, upgradeSelect, showConfirmModal } from '../state.js';
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

// ── Per-category override scope ──────────────────────────
function setupScopeDom() {
  document.body.innerHTML = `
    <div class="settings-section-body">
      <div class="weights-scope-row">
        <select id="weight-scope-select"></select>
        <button id="weight-scope-add"></button>
        <button id="weight-scope-delete" style="display:none"></button>
      </div>
      <p id="weight-scope-hint"></p>
      <div id="weight-items"></div>
    </div>`;
}

async function bootGlobalScope(cats = []) {
  setupScopeDom();
  api.mockImplementation((url) => {
    if (url === '/api/weights') return Promise.resolve([
      { field: 'kcal', enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
    ]);
    if (url === '/api/categories') return Promise.resolve(cats);
    return Promise.resolve({});
  });
  // Trigger the global-load branch via onScopeChange('')
  await onScopeChange('');
  // populate scope dropdown by invoking refreshScopeSelect
  await refreshScopeSelect();
}

describe('refreshScopeSelect', () => {
  it('populates scope dropdown with Global plus only categories that have overrides', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
      { name: 'Drinks', emoji: '🧃', label: 'Drinks', count: 0, has_weight_overrides: false },
    ]);
    const sel = document.getElementById('weight-scope-select');
    const opts = Array.from(sel.options).map((o) => o.value);
    expect(opts).toEqual(['', 'Snacks']);
  });

  it('hides the add-override button when every category already has overrides', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    const addBtn = document.getElementById('weight-scope-add');
    expect(addBtn.style.display).toBe('none');
  });

  it('shows the add-override button when at least one category lacks overrides', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: false },
    ]);
    const addBtn = document.getElementById('weight-scope-add');
    expect(addBtn.style.display).toBe('');
  });
});

describe('onScopeChange to category', () => {
  beforeEach(async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
        { field: 'sugar', is_overridden: false, enabled: true, weight: 30, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Sugar' },
      ]);
      return Promise.resolve({});
    });
  });

  it('GETs the category weights and renders only overridden rows', async () => {
    await onScopeChange('Snacks');
    expect(api).toHaveBeenCalledWith('/api/categories/Snacks/weights');
    expect(document.getElementById('wi-kcal')).not.toBeNull();
    expect(document.getElementById('wi-sugar')).toBeNull();
  });

  it('lists non-overridden fields in the add dropdown', async () => {
    await onScopeChange('Snacks');
    const sel = document.getElementById('weight-add-select');
    expect(sel).not.toBeNull();
    const opts = Array.from(sel.options).map((o) => o.value);
    expect(opts).toContain('sugar');
    expect(opts).not.toContain('kcal');
  });

  it('shows the delete-override button when scoped to a category', async () => {
    await onScopeChange('Snacks');
    expect(document.getElementById('weight-scope-delete').style.display).toBe('');
  });

  it('shows a trash button on every overridden row', async () => {
    await onScopeChange('Snacks');
    const trashBtns = document.querySelectorAll('#weight-items .weight-item .btn-red');
    expect(trashBtns.length).toBe(1);
  });
});

describe('addWeightFromDropdown in category scope', () => {
  it('sets is_overridden=true and triggers a category PUT', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'sugar', is_overridden: false, enabled: true, weight: 30, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Sugar' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    const sel = document.getElementById('weight-add-select');
    sel.value = 'sugar';
    api.mockClear();
    api.mockResolvedValue({});
    const { addWeightFromDropdown } = await import('../settings-weights.js');
    addWeightFromDropdown();
    vi.advanceTimersByTime(400);
    await Promise.resolve();
    await Promise.resolve();
    expect(document.getElementById('wi-sugar')).not.toBeNull();
    const putCall = api.mock.calls.find((c) => c[0] === '/api/categories/Snacks/weights' && c[1]?.method === 'PUT');
    expect(putCall).toBeTruthy();
    const body = JSON.parse(putCall[1].body);
    const sugar = body.find((p) => p.field === 'sugar');
    expect(sugar.is_overridden).toBe(true);
  });
});

describe('removeWeight in category scope', () => {
  it('flips is_overridden=false and triggers a category PUT', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    api.mockClear();
    api.mockResolvedValue({});
    removeWeight('kcal');
    vi.advanceTimersByTime(400);
    await Promise.resolve();
    await Promise.resolve();
    expect(document.getElementById('wi-kcal')).toBeNull();
    const putCall = api.mock.calls.find((c) => c[0] === '/api/categories/Snacks/weights' && c[1]?.method === 'PUT');
    expect(putCall).toBeTruthy();
    const body = JSON.parse(putCall[1].body);
    const kcal = body.find((p) => p.field === 'kcal');
    expect(kcal.is_overridden).toBe(false);
  });
});

describe('onScopeChange back to global', () => {
  it('reloads /api/weights and hides the delete button', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([
        { field: 'kcal', enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    expect(document.getElementById('wi-kcal')).not.toBeNull();
    await onScopeChange('');
    // global view also has wi-kcal but rebuilt; delete button hidden
    expect(document.getElementById('weight-scope-delete').style.display).toBe('none');
  });
});

describe('saveWeights branches on scope', () => {
  it('PUTs /api/categories/<name>/weights when in category scope', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    api.mockClear();
    api.mockResolvedValue({});
    await saveWeights();
    expect(api).toHaveBeenCalledWith('/api/categories/Snacks/weights', expect.objectContaining({ method: 'PUT' }));
    expect(loadData).toHaveBeenCalled();
  });
});

describe('openAddOverridePicker', () => {
  it('lists only categories without overrides and switches scope on confirm', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: false },
      { name: 'Drinks', emoji: '🧃', label: 'Drinks', count: 0, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: false, enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    openAddOverridePicker();
    const modal = document.querySelector('.scan-modal');
    expect(modal).not.toBeNull();
    const sel = modal.querySelector('select');
    const opts = Array.from(sel.options).map((o) => o.value);
    expect(opts).toEqual(['Snacks']);
    sel.value = 'Snacks';
    const confirmBtn = modal.querySelector('.scan-modal-btn-register');
    await confirmBtn.onclick();
    expect(api).toHaveBeenCalledWith('/api/categories/Snacks/weights');
    const scopeSel = document.getElementById('weight-scope-select');
    expect(scopeSel.value).toBe('Snacks');
  });

  it('shows a toast when every category already has overrides', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    showToast.mockClear();
    openAddOverridePicker();
    expect(document.querySelector('.scan-modal')).toBeNull();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'info');
  });
});

describe('deleteActiveCategoryOverride', () => {
  it('PUTs full payload with all is_overridden=false, snaps to global, refreshes', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      if (url === '/api/weights') return Promise.resolve([
        { field: 'kcal', enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    showConfirmModal.mockResolvedValue(true);
    api.mockClear();
    loadData.mockClear();
    await deleteActiveCategoryOverride();
    const putCall = api.mock.calls.find(
      (c) => c[0] === '/api/categories/Snacks/weights' && c[1] && c[1].method === 'PUT'
    );
    expect(putCall).toBeTruthy();
    const body = JSON.parse(putCall[1].body);
    expect(body.every((p) => p.is_overridden === false)).toBe(true);
    const scopeSel = document.getElementById('weight-scope-select');
    expect(scopeSel.value).toBe('');
    expect(loadData).toHaveBeenCalled();
  });

  it('does nothing when user cancels the confirm modal', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    showConfirmModal.mockResolvedValue(false);
    api.mockClear();
    await deleteActiveCategoryOverride();
    const putCalls = api.mock.calls.filter((c) => c[1] && c[1].method === 'PUT');
    expect(putCalls.length).toBe(0);
  });
});

describe('refreshScopeSelect handles deleted active category', () => {
  it('snaps scope back to global if the active category lost its override', async () => {
    await bootGlobalScope([
      { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: true },
    ]);
    api.mockImplementation((url) => {
      if (url === '/api/categories/Snacks/weights') return Promise.resolve([
        { field: 'kcal', is_overridden: true, enabled: true, weight: 80, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      if (url === '/api/weights') return Promise.resolve([
        { field: 'kcal', enabled: true, weight: 60, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 100, label: 'Kcal' },
      ]);
      if (url === '/api/categories') return Promise.resolve([
        { name: 'Snacks', emoji: '🍿', label: 'Snacks', count: 1, has_weight_overrides: false },
      ]);
      return Promise.resolve({});
    });
    await onScopeChange('Snacks');
    expect(document.getElementById('weight-scope-delete').style.display).toBe('');
    await refreshScopeSelect();
    // Active scope should reset and global render should be back, delete hidden
    expect(document.getElementById('weight-scope-delete').style.display).toBe('none');
    const scopeSel = document.getElementById('weight-scope-select');
    expect(scopeSel.value).toBe('');
  });
});
