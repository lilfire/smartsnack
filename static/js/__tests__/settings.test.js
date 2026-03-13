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

import {
  SCORE_COLORS, SCORE_CFG_MAP, weightData,
  toggleWeightConfig, removeWeight, addWeightFromDropdown,
  toggleSettingsSection, downloadBackup, saveOffCredentials,
  loadCategories, updateCategoryLabel, updateCategoryEmoji, addCategory, deleteCategory,
  loadPq, addPq, deletePq, saveWeights, renderWeightItems,
  loadFlags, addFlag, deleteFlag, updateFlagLabel,
  savePqField, handleRestore, handleImport, estimateAllPq,
  onWeightDirection, onWeightFormula, onWeightMin, onWeightMax, onWeightSlider,
  autosavePq, renderPqTable, checkRefreshStatus, loadSettings,
  refreshAllFromOff,
} from '../settings.js';
import { state, api, showToast, fetchStats, showConfirmModal } from '../state.js';

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  document.body.innerHTML = '';
  weightData.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('SCORE_COLORS', () => {
  it('has expected keys', () => {
    expect(SCORE_COLORS).toHaveProperty('kcal');
    expect(SCORE_COLORS).toHaveProperty('protein');
    expect(SCORE_COLORS).toHaveProperty('fat');
    expect(SCORE_COLORS).toHaveProperty('sugar');
    expect(SCORE_COLORS).toHaveProperty('salt');
    expect(SCORE_COLORS).toHaveProperty('taste_score');
  });

  it('values are hex colors', () => {
    Object.values(SCORE_COLORS).forEach((c) => {
      expect(c).toMatch(/^#[0-9a-fA-F]{6}$/);
    });
  });
});

describe('toggleWeightConfig', () => {
  it('toggles display from none to visible', () => {
    const el = document.createElement('div');
    el.id = 'wcfg-kcal';
    el.style.display = 'none';
    document.body.appendChild(el);
    toggleWeightConfig('kcal');
    expect(el.style.display).toBe('');
  });

  it('toggles display from visible to none', () => {
    const el = document.createElement('div');
    el.id = 'wcfg-kcal';
    el.style.display = '';
    document.body.appendChild(el);
    toggleWeightConfig('kcal');
    expect(el.style.display).toBe('none');
  });

  it('does nothing for nonexistent element', () => {
    expect(() => toggleWeightConfig('missing')).not.toThrow();
  });
});

describe('removeWeight', () => {
  it('disables weight and sets weight to 0', () => {
    weightData.push({ field: 'kcal', enabled: true, weight: 50 });
    // Create required DOM elements
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    removeWeight('kcal');
    expect(weightData[0].enabled).toBe(false);
    expect(weightData[0].weight).toBe(0);
  });
});

describe('addWeightFromDropdown', () => {
  it('enables weight from dropdown selection', () => {
    weightData.push({ field: 'kcal', label: 'Kcal', enabled: false, weight: 0 });
    const sel = document.createElement('select');
    sel.id = 'weight-add-select';
    const opt = document.createElement('option');
    opt.value = 'kcal';
    sel.appendChild(opt);
    sel.value = 'kcal';
    document.body.appendChild(sel);
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    addWeightFromDropdown();
    expect(weightData[0].enabled).toBe(true);
    expect(weightData[0].weight).toBe(10);
  });

  it('does nothing when no selection', () => {
    const sel = document.createElement('select');
    sel.id = 'weight-add-select';
    sel.value = '';
    document.body.appendChild(sel);
    expect(() => addWeightFromDropdown()).not.toThrow();
  });
});

describe('toggleSettingsSection', () => {
  it('collapses open section', () => {
    const header = document.createElement('div');
    const body = document.createElement('div');
    body.style.display = '';
    document.body.appendChild(header);
    document.body.appendChild(body);
    // Make body the next sibling
    header.after(body);
    toggleSettingsSection(header);
    expect(body.style.display).toBe('none');
    expect(header.classList.contains('open')).toBe(false);
  });

  it('expands collapsed section', () => {
    const header = document.createElement('div');
    const body = document.createElement('div');
    body.style.display = 'none';
    document.body.appendChild(header);
    document.body.appendChild(body);
    header.after(body);
    toggleSettingsSection(header);
    expect(body.style.display).toBe('');
    expect(header.classList.contains('open')).toBe(true);
  });

  it('does nothing when no sibling', () => {
    const header = document.createElement('div');
    document.body.appendChild(header);
    // Remove all next siblings
    while (header.nextElementSibling) header.nextElementSibling.remove();
    expect(() => toggleSettingsSection(header)).not.toThrow();
  });
});

describe('downloadBackup', () => {
  it('sets window.location.href', () => {
    const origLocation = window.location;
    delete window.location;
    window.location = { href: '' };
    downloadBackup();
    expect(window.location.href).toBe('/api/backup');
    expect(showToast).toHaveBeenCalledWith('toast_backup_downloaded', 'success');
    window.location = origLocation;
  });
});

describe('loadCategories', () => {
  it('renders categories in cat-list', async () => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '🧀', label: 'Dairy', count: 5 },
      { name: 'meat', emoji: '🥩', label: 'Meat', count: 3 },
    ]);
    await loadCategories();
    expect(list.innerHTML).toContain('Dairy');
    expect(list.innerHTML).toContain('Meat');
    expect(list.querySelectorAll('.cat-item').length).toBe(2);
  });

  it('shows empty message when no categories', async () => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([]);
    await loadCategories();
    expect(list.innerHTML).toContain('No categories');
  });

  it('shows error on API failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockRejectedValueOnce(new Error('fail'));
    await loadCategories();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    console.error.mockRestore();
  });
});

describe('updateCategoryLabel', () => {
  it('updates category label via API', async () => {
    api.mockResolvedValueOnce({});
    await updateCategoryLabel('dairy', 'Meieri');
    expect(api).toHaveBeenCalledWith('/api/categories/dairy', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_category_updated', 'success');
  });

  it('shows error for empty label', async () => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([]);
    await updateCategoryLabel('dairy', '   ');
    expect(showToast).toHaveBeenCalledWith('toast_display_name_empty', 'error');
  });
});

describe('updateCategoryEmoji', () => {
  it('updates emoji via API', async () => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce({}) // PUT
       .mockResolvedValueOnce([]); // loadCategories
    await updateCategoryEmoji('dairy', '🥛');
    expect(api).toHaveBeenCalledWith('/api/categories/dairy', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ emoji: '🥛' }),
    }));
  });
});

describe('addCategory', () => {
  beforeEach(() => {
    ['cat-name', 'cat-emoji', 'cat-label'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const trigger = document.createElement('button');
    trigger.id = 'cat-emoji-trigger';
    document.body.appendChild(trigger);
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
  });

  it('shows error when name or label empty', async () => {
    document.getElementById('cat-name').value = '';
    document.getElementById('cat-label').value = '';
    await addCategory();
    expect(showToast).toHaveBeenCalledWith('toast_name_display_required', 'error');
  });

  it('creates category and resets form', async () => {
    document.getElementById('cat-name').value = 'snack';
    document.getElementById('cat-label').value = 'Snacks';
    document.getElementById('cat-emoji').value = '🍿';
    api.mockResolvedValueOnce({}) // POST
       .mockResolvedValueOnce([]); // loadCategories
    await addCategory();
    expect(api).toHaveBeenCalledWith('/api/categories', expect.objectContaining({ method: 'POST' }));
    expect(document.getElementById('cat-name').value).toBe('');
  });
});

describe('deleteCategory', () => {
  it('deletes category with no products after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce({}) // DELETE
       .mockResolvedValueOnce([]); // loadCategories
    await deleteCategory('snack', 'Snacks', 0);
    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith('/api/categories/snack', { method: 'DELETE' });
  });

  it('does not delete when confirmation cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deleteCategory('snack', 'Snacks', 0);
    expect(api).not.toHaveBeenCalled();
  });

  it('shows reassignment modal when category has products', async () => {
    api.mockResolvedValueOnce([
      { name: 'snack', emoji: '🍿', label: 'Snacks' },
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
    ]);
    await deleteCategory('snack', 'Snacks', 5);
    expect(document.querySelector('.cat-move-modal')).not.toBeNull();
    // Clean up modal
    const bg = document.querySelector('.cat-move-modal-bg');
    if (bg) bg.remove();
  });
});

describe('loadPq', () => {
  it('renders protein quality sources', async () => {
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([
      { id: 1, label: 'Whey', keywords: ['whey'], pdcaas: 1.0, diaas: 1.1 },
    ]);
    await loadPq();
    expect(list.innerHTML).toContain('Whey');
    expect(list.querySelector('.pq-card')).not.toBeNull();
  });

  it('shows empty message when no sources', async () => {
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([]);
    await loadPq();
    expect(list.innerHTML).toContain('No protein sources');
  });
});

describe('addPq', () => {
  beforeEach(() => {
    ['pq-add-label', 'pq-add-kw', 'pq-add-pdcaas', 'pq-add-diaas'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
  });

  it('shows error when keywords missing', async () => {
    document.getElementById('pq-add-kw').value = '';
    document.getElementById('pq-add-pdcaas').value = '0.8';
    document.getElementById('pq-add-diaas').value = '0.9';
    await addPq();
    expect(showToast).toHaveBeenCalledWith('toast_pq_keywords_required', 'error');
  });

  it('adds PQ source and resets form', async () => {
    document.getElementById('pq-add-label').value = 'Casein';
    document.getElementById('pq-add-kw').value = 'casein, milk protein';
    document.getElementById('pq-add-pdcaas').value = '1.0';
    document.getElementById('pq-add-diaas').value = '1.18';
    api.mockResolvedValueOnce({}) // POST
       .mockResolvedValueOnce([]); // loadPq
    await addPq();
    expect(api).toHaveBeenCalledWith('/api/protein-quality', expect.objectContaining({ method: 'POST' }));
    expect(document.getElementById('pq-add-kw').value).toBe('');
  });
});

describe('renderPqTable', () => {
  it('renders PQ cards with change handlers when data is loaded', async () => {
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce([
      { id: 1, label: 'Whey', keywords: ['whey', 'whey protein'], pdcaas: 1.0, diaas: 1.09 },
      { id: 2, label: 'Casein', keywords: ['casein'], pdcaas: 1.0, diaas: 0.98 },
    ]);
    await loadPq();
    expect(list.querySelectorAll('.pq-card').length).toBe(2);
    expect(list.innerHTML).toContain('Whey');
    expect(list.innerHTML).toContain('Casein');
    expect(document.getElementById('pqe-label-1')).not.toBeNull();
    expect(document.getElementById('pqe-kw-1')).not.toBeNull();
  });

  it('shows error when PQ loading fails', async () => {
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockRejectedValueOnce(new Error('fail'));
    await loadPq();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    expect(list.innerHTML).toContain('No protein sources');
  });
});

describe('renderWeightItems with mixed enabled/disabled', () => {
  it('renders add-weight dropdown for disabled weights', () => {
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    weightData.push(
      { field: 'kcal', label: 'Kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 500 },
      { field: 'protein', label: 'Protein', enabled: false, weight: 0, direction: 'higher', formula: 'minmax', formula_min: 0, formula_max: 100 },
    );
    renderWeightItems();
    // Enabled weight should render as weight-item
    expect(container.querySelector('.weight-item.enabled')).not.toBeNull();
    // Disabled weight should appear in add dropdown
    const addSelect = document.getElementById('weight-add-select');
    expect(addSelect).not.toBeNull();
    expect(addSelect.innerHTML).toContain('Protein');
  });
});

describe('initRestoreDragDrop', () => {
  it('creates drag-and-drop zone', () => {
    const { initRestoreDragDrop } = require('../settings.js');
    const drop = document.createElement('div');
    drop.id = 'restore-drop';
    document.body.appendChild(drop);
    initRestoreDragDrop();
    // Fire dragover event
    const dragover = new Event('dragover');
    dragover.preventDefault = vi.fn();
    drop.dispatchEvent(dragover);
    expect(drop.classList.contains('dragover')).toBe(true);
  });
});

describe('deletePq', () => {
  it('deletes PQ source after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce({}) // DELETE
       .mockResolvedValueOnce([]); // loadPq
    await deletePq(1, 'Whey');
    expect(api).toHaveBeenCalledWith('/api/protein-quality/1', { method: 'DELETE' });
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('does nothing when confirmation cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deletePq(1, 'Whey');
    expect(api).not.toHaveBeenCalled();
  });
});

describe('saveWeights', () => {
  it('saves weights via API', async () => {
    weightData.push({ field: 'kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 0 });
    // Create DOM elements for enabled weights
    const slider = document.createElement('input');
    slider.id = 'w-kcal';
    slider.value = '50';
    document.body.appendChild(slider);
    const minEl = document.createElement('input');
    minEl.id = 'wn-kcal';
    minEl.value = '0';
    document.body.appendChild(minEl);
    const maxEl = document.createElement('input');
    maxEl.id = 'wm-kcal';
    maxEl.value = '500';
    document.body.appendChild(maxEl);
    // Also create stats-line for loadData
    const statsLine = document.createElement('div');
    statsLine.id = 'stats-line';
    document.body.appendChild(statsLine);

    api.mockResolvedValueOnce({}); // PUT weights
    await saveWeights();
    expect(api).toHaveBeenCalledWith('/api/weights', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_weights_saved', 'success');
  });
});

describe('saveOffCredentials', () => {
  it('saves credentials via API', async () => {
    const userId = document.createElement('input');
    userId.id = 'off-user-id';
    userId.value = 'myuser';
    document.body.appendChild(userId);
    const pw = document.createElement('input');
    pw.id = 'off-password';
    pw.value = 'secret';
    document.body.appendChild(pw);
    api.mockResolvedValueOnce({});
    await saveOffCredentials();
    expect(api).toHaveBeenCalledWith('/api/settings/off-credentials', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_off_credentials_saved', 'success');
  });

  it('does not send password when it is placeholder bullets', async () => {
    const userId = document.createElement('input');
    userId.id = 'off-user-id';
    userId.value = 'myuser';
    document.body.appendChild(userId);
    const pw = document.createElement('input');
    pw.id = 'off-password';
    pw.value = '••••••••';
    document.body.appendChild(pw);
    api.mockResolvedValueOnce({});
    await saveOffCredentials();
    const callBody = JSON.parse(api.mock.calls[0][1].body);
    expect(callBody.off_password).toBeUndefined();
  });
});

describe('loadFlags', () => {
  beforeEach(() => {
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
  });

  it('renders user and system flags', async () => {
    api.mockResolvedValueOnce([
      { name: 'vegan', label: 'Vegan', type: 'user', count: 3 },
      { name: 'lactose_free', label: 'Lactose Free', type: 'system', count: 5 },
    ]);
    await loadFlags();
    const list = document.getElementById('flag-list');
    expect(list.innerHTML).toContain('Vegan');
    expect(list.innerHTML).toContain('Lactose Free');
    expect(list.querySelector('.flag-type-user')).not.toBeNull();
    expect(list.querySelector('.flag-type-system')).not.toBeNull();
  });

  it('shows empty message when no flags', async () => {
    api.mockResolvedValueOnce([]);
    await loadFlags();
    expect(document.getElementById('flag-list').innerHTML).toContain('No flags');
  });

  it('shows error on API failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await loadFlags();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    console.error.mockRestore();
  });
});

describe('addFlag', () => {
  beforeEach(() => {
    ['flag-add-name', 'flag-add-label'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
  });

  it('shows error when name or label empty', async () => {
    document.getElementById('flag-add-name').value = '';
    document.getElementById('flag-add-label').value = '';
    await addFlag();
    expect(showToast).toHaveBeenCalledWith('toast_name_display_required', 'error');
  });

  it('creates flag and resets form', async () => {
    document.getElementById('flag-add-name').value = 'organic';
    document.getElementById('flag-add-label').value = 'Organic';
    api.mockResolvedValueOnce({}) // POST
       .mockResolvedValueOnce([]); // loadFlags
    await addFlag();
    expect(api).toHaveBeenCalledWith('/api/flags', expect.objectContaining({ method: 'POST' }));
    expect(document.getElementById('flag-add-name').value).toBe('');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });
});

describe('deleteFlag', () => {
  beforeEach(() => {
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
  });

  it('deletes flag after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({}) // DELETE
       .mockResolvedValueOnce([]); // loadFlags
    await deleteFlag('vegan', 'Vegan', 0);
    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith('/api/flags/vegan', { method: 'DELETE' });
  });

  it('does not delete when cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deleteFlag('vegan', 'Vegan', 0);
    expect(api).not.toHaveBeenCalled();
  });
});

describe('updateFlagLabel', () => {
  beforeEach(() => {
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
  });

  it('updates flag label via API', async () => {
    api.mockResolvedValueOnce({});
    await updateFlagLabel('vegan', 'Vegansk');
    expect(api).toHaveBeenCalledWith('/api/flags/vegan', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_flag_updated', 'success');
  });

  it('shows error for empty label', async () => {
    api.mockResolvedValueOnce([]);
    await updateFlagLabel('vegan', '   ');
    expect(showToast).toHaveBeenCalledWith('toast_display_name_empty', 'error');
  });
});

describe('savePqField', () => {
  it('saves PQ field via API', async () => {
    const ids = [
      { tag: 'input', id: 'pqe-label-1', value: 'Whey' },
      { tag: 'input', id: 'pqe-kw-1', value: 'whey, whey protein' },
      { tag: 'input', id: 'pqe-pdcaas-1', value: '1.0' },
      { tag: 'input', id: 'pqe-diaas-1', value: '1.1' },
    ];
    ids.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    api.mockResolvedValueOnce({});
    await savePqField(1);
    expect(api).toHaveBeenCalledWith('/api/protein-quality/1', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_updated', 'success');
  });

  it('does nothing when keywords empty', async () => {
    const ids = [
      { tag: 'input', id: 'pqe-label-1', value: 'Whey' },
      { tag: 'input', id: 'pqe-kw-1', value: '' },
      { tag: 'input', id: 'pqe-pdcaas-1', value: '1.0' },
      { tag: 'input', id: 'pqe-diaas-1', value: '1.1' },
    ];
    ids.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    await savePqField(1);
    expect(api).not.toHaveBeenCalled();
  });
});

describe('handleRestore', () => {
  it('restores database from file after confirmation', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({ message: 'Restored!' });

    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };

    const input = { files: [new Blob(['{}'])], value: 'file.json' };
    await handleRestore(input);
    await vi.advanceTimersByTimeAsync(50);

    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith('/api/restore', expect.objectContaining({ method: 'POST' }));

    global.FileReader = origFileReader;
  });

  it('does nothing when cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    const input = { files: [new Blob(['{}'])], value: 'file.json' };
    await handleRestore(input);
    expect(api).not.toHaveBeenCalled();
    expect(input.value).toBe('');
  });

  it('does nothing when no files', async () => {
    const input = { files: [], value: '' };
    await handleRestore(input);
    expect(showConfirmModal).not.toHaveBeenCalled();
  });
});

describe('handleImport', () => {
  it('imports data from file', async () => {
    api.mockResolvedValueOnce({ message: 'Imported 5 products' });

    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };

    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    // Advance timer to trigger FileReader onload
    await vi.advanceTimersByTimeAsync(0);
    // Click the start button in the import duplicate dialog
    const startBtn = document.querySelector('.scan-modal-btn-register');
    if (startBtn) startBtn.click();
    await vi.advanceTimersByTimeAsync(50);

    expect(api).toHaveBeenCalledWith('/api/import', expect.objectContaining({ method: 'POST' }));

    global.FileReader = origFileReader;
  });

  it('does nothing when no files', () => {
    const input = { files: [], value: '' };
    handleImport(input);
    expect(api).not.toHaveBeenCalled();
  });
});

describe('estimateAllPq', () => {
  it('estimates PQ for all products', async () => {
    const btn = document.createElement('button');
    btn.id = 'btn-estimate-all-pq';
    document.body.appendChild(btn);
    const status = document.createElement('div');
    status.id = 'estimate-pq-status';
    status.style.display = 'none';
    document.body.appendChild(status);

    api.mockResolvedValueOnce({ total: 10, updated: 8, skipped: 2 });
    await estimateAllPq();
    expect(api).toHaveBeenCalledWith('/api/bulk/estimate-pq', { method: 'POST' });
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
    expect(btn.disabled).toBe(false);
  });

  it('shows error on failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const btn = document.createElement('button');
    btn.id = 'btn-estimate-all-pq';
    document.body.appendChild(btn);
    const status = document.createElement('div');
    status.id = 'estimate-pq-status';
    document.body.appendChild(status);

    api.mockRejectedValueOnce(new Error('fail'));
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    expect(btn.disabled).toBe(false);
    console.error.mockRestore();
  });

  it('shows error when API returns error field', async () => {
    const btn = document.createElement('button');
    btn.id = 'btn-estimate-all-pq';
    document.body.appendChild(btn);
    const status = document.createElement('div');
    status.id = 'estimate-pq-status';
    document.body.appendChild(status);

    api.mockResolvedValueOnce({ error: 'Something went wrong' });
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith('Something went wrong', 'error');
  });
});

describe('saveWeights error path', () => {
  it('shows error on save failure', async () => {
    weightData.push({ field: 'kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 0 });
    const slider = document.createElement('input');
    slider.id = 'w-kcal';
    slider.value = '50';
    document.body.appendChild(slider);

    api.mockRejectedValueOnce(new Error('fail'));
    await saveWeights();
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
  });
});

describe('saveOffCredentials error paths', () => {
  it('shows encryption error when error message matches', async () => {
    const userId = document.createElement('input');
    userId.id = 'off-user-id';
    userId.value = 'user';
    document.body.appendChild(userId);
    const pw = document.createElement('input');
    pw.id = 'off-password';
    pw.value = 'secret';
    document.body.appendChild(pw);

    api.mockRejectedValueOnce(new Error('encryption_not_configured'));
    await saveOffCredentials();
    expect(showToast).toHaveBeenCalledWith('toast_encryption_not_configured', 'error');
  });

  it('shows generic save error for other errors', async () => {
    const userId = document.createElement('input');
    userId.id = 'off-user-id';
    userId.value = 'user';
    document.body.appendChild(userId);
    const pw = document.createElement('input');
    pw.id = 'off-password';
    pw.value = 'secret';
    document.body.appendChild(pw);

    api.mockRejectedValueOnce(new Error('other_error'));
    await saveOffCredentials();
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
  });
});

describe('addCategory error paths', () => {
  beforeEach(() => {
    ['cat-name', 'cat-emoji', 'cat-label'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const trigger = document.createElement('button');
    trigger.id = 'cat-emoji-trigger';
    document.body.appendChild(trigger);
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
  });

  it('shows error when API returns error field', async () => {
    document.getElementById('cat-name').value = 'snack';
    document.getElementById('cat-label').value = 'Snacks';
    api.mockResolvedValueOnce({ error: 'Category exists' });
    await addCategory();
    expect(showToast).toHaveBeenCalledWith('Category exists', 'error');
  });

  it('shows network error on exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    document.getElementById('cat-name').value = 'snack';
    document.getElementById('cat-label').value = 'Snacks';
    api.mockRejectedValueOnce(new Error('fail'));
    await addCategory();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('uses default emoji when emoji field is empty', async () => {
    document.getElementById('cat-name').value = 'snack';
    document.getElementById('cat-label').value = 'Snacks';
    document.getElementById('cat-emoji').value = '';
    api.mockResolvedValueOnce({})
       .mockResolvedValueOnce([]);
    await addCategory();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.emoji).toBe('\u{1F4E6}');
  });
});

describe('addFlag error path', () => {
  beforeEach(() => {
    ['flag-add-name', 'flag-add-label'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
  });

  it('shows error when API returns error field', async () => {
    document.getElementById('flag-add-name').value = 'organic';
    document.getElementById('flag-add-label').value = 'Organic';
    api.mockResolvedValueOnce({ error: 'Flag exists' });
    await addFlag();
    expect(showToast).toHaveBeenCalledWith('Flag exists', 'error');
  });

  it('shows network error on exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    document.getElementById('flag-add-name').value = 'organic';
    document.getElementById('flag-add-label').value = 'Organic';
    api.mockRejectedValueOnce(new Error('fail'));
    await addFlag();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });
});

describe('deleteCategory with only category', () => {
  it('shows error when no other categories to move to', async () => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    // Has products but only one category
    api.mockResolvedValueOnce([{ name: 'snack', emoji: '', label: 'Snacks' }]);
    await deleteCategory('snack', 'Snacks', 5);
    expect(showToast).toHaveBeenCalledWith('toast_cannot_delete_only_category', 'error');
  });
});

describe('deleteCategory delete response error', () => {
  it('shows error when delete returns error field', async () => {
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce({ error: 'Cannot delete' });
    await deleteCategory('snack', 'Snacks', 0);
    expect(showToast).toHaveBeenCalledWith('Cannot delete', 'error');
  });
});

describe('deleteFlag error path', () => {
  it('shows network error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
    showConfirmModal.mockResolvedValue(true);
    api.mockRejectedValueOnce(new Error('fail'));
    await deleteFlag('vegan', 'Vegan', 0);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('uses count > 0 message variant', async () => {
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'flag-list';
    document.body.appendChild(list);
    api.mockResolvedValueOnce({})
       .mockResolvedValueOnce([]);
    await deleteFlag('vegan', 'Vegan', 5);
    expect(showConfirmModal).toHaveBeenCalledWith(
      expect.any(String), 'Vegan',
      'confirm_delete_flag_body',
      expect.any(String), expect.any(String)
    );
  });
});

describe('onWeightDirection', () => {
  it('updates direction on weight item', () => {
    weightData.push({ field: 'kcal', direction: 'lower' });
    const sel = document.createElement('select');
    sel.id = 'wd-kcal';
    const opt = document.createElement('option');
    opt.value = 'higher';
    sel.appendChild(opt);
    sel.value = 'higher';
    document.body.appendChild(sel);
    onWeightDirection('kcal');
    expect(weightData[0].direction).toBe('higher');
  });
});

describe('onWeightFormula', () => {
  it('shows min/max inputs for direct formula', () => {
    weightData.push({ field: 'kcal', formula: 'minmax' });
    const sel = document.createElement('select');
    sel.id = 'wf-kcal';
    const opt = document.createElement('option');
    opt.value = 'direct';
    sel.appendChild(opt);
    sel.value = 'direct';
    document.body.appendChild(sel);
    const minEl = document.createElement('input');
    minEl.id = 'wn-kcal';
    minEl.style.display = 'none';
    document.body.appendChild(minEl);
    const maxEl = document.createElement('input');
    maxEl.id = 'wm-kcal';
    maxEl.style.display = 'none';
    document.body.appendChild(maxEl);
    onWeightFormula('kcal');
    expect(weightData[0].formula).toBe('direct');
    expect(minEl.style.display).toBe('');
    expect(maxEl.style.display).toBe('');
  });

  it('hides min/max inputs for minmax formula', () => {
    weightData.push({ field: 'kcal', formula: 'direct' });
    const sel = document.createElement('select');
    sel.id = 'wf-kcal';
    const opt = document.createElement('option');
    opt.value = 'minmax';
    sel.appendChild(opt);
    sel.value = 'minmax';
    document.body.appendChild(sel);
    const minEl = document.createElement('input');
    minEl.id = 'wn-kcal';
    minEl.style.display = '';
    document.body.appendChild(minEl);
    const maxEl = document.createElement('input');
    maxEl.id = 'wm-kcal';
    maxEl.style.display = '';
    document.body.appendChild(maxEl);
    onWeightFormula('kcal');
    expect(minEl.style.display).toBe('none');
    expect(maxEl.style.display).toBe('none');
  });
});

describe('onWeightMin', () => {
  it('updates formula_min on weight item', () => {
    weightData.push({ field: 'kcal', formula_min: 0 });
    const el = document.createElement('input');
    el.id = 'wn-kcal';
    el.value = '10';
    document.body.appendChild(el);
    onWeightMin('kcal');
    expect(weightData[0].formula_min).toBe(10);
  });
});

describe('onWeightMax', () => {
  it('updates formula_max on weight item', () => {
    weightData.push({ field: 'kcal', formula_max: 0 });
    const el = document.createElement('input');
    el.id = 'wm-kcal';
    el.value = '500';
    document.body.appendChild(el);
    onWeightMax('kcal');
    expect(weightData[0].formula_max).toBe(500);
  });
});

describe('onWeightSlider', () => {
  it('updates weight value and display', () => {
    weightData.push({ field: 'kcal', weight: 50 });
    const slider = document.createElement('input');
    slider.id = 'w-kcal';
    slider.value = '75';
    document.body.appendChild(slider);
    const valEl = document.createElement('span');
    valEl.id = 'wv-kcal';
    document.body.appendChild(valEl);
    onWeightSlider('kcal');
    expect(weightData[0].weight).toBe(75);
    expect(valEl.textContent).toBe('75.0');
  });
});

describe('savePqField error path', () => {
  it('shows error when API returns error field', async () => {
    const ids = [
      { tag: 'input', id: 'pqe-label-1', value: 'Whey' },
      { tag: 'input', id: 'pqe-kw-1', value: 'whey' },
      { tag: 'input', id: 'pqe-pdcaas-1', value: '1.0' },
      { tag: 'input', id: 'pqe-diaas-1', value: '1.1' },
    ];
    ids.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    api.mockResolvedValueOnce({ error: 'Invalid data' });
    await savePqField(1);
    expect(showToast).toHaveBeenCalledWith('Invalid data', 'error');
  });

  it('shows save error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const ids = [
      { tag: 'input', id: 'pqe-label-1', value: 'Whey' },
      { tag: 'input', id: 'pqe-kw-1', value: 'whey' },
      { tag: 'input', id: 'pqe-pdcaas-1', value: '1.0' },
      { tag: 'input', id: 'pqe-diaas-1', value: '1.1' },
    ];
    ids.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    api.mockRejectedValueOnce(new Error('fail'));
    await savePqField(1);
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
    console.error.mockRestore();
  });

  it('returns early when pdcaas or diaas is NaN', async () => {
    const ids = [
      { tag: 'input', id: 'pqe-label-1', value: 'Whey' },
      { tag: 'input', id: 'pqe-kw-1', value: 'whey' },
      { tag: 'input', id: 'pqe-pdcaas-1', value: 'abc' },
      { tag: 'input', id: 'pqe-diaas-1', value: '1.1' },
    ];
    ids.forEach(({ tag, id, value }) => {
      const el = document.createElement(tag);
      el.id = id;
      el.value = value;
      document.body.appendChild(el);
    });
    await savePqField(1);
    expect(api).not.toHaveBeenCalled();
  });
});

describe('addPq error paths', () => {
  beforeEach(() => {
    ['pq-add-label', 'pq-add-kw', 'pq-add-pdcaas', 'pq-add-diaas'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
  });

  it('shows error when API returns error field', async () => {
    document.getElementById('pq-add-kw').value = 'whey';
    document.getElementById('pq-add-pdcaas').value = '1.0';
    document.getElementById('pq-add-diaas').value = '1.1';
    api.mockResolvedValueOnce({ error: 'Duplicate keywords' });
    await addPq();
    expect(showToast).toHaveBeenCalledWith('Duplicate keywords', 'error');
  });

  it('shows network error on exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    document.getElementById('pq-add-kw').value = 'whey';
    document.getElementById('pq-add-pdcaas').value = '1.0';
    document.getElementById('pq-add-diaas').value = '1.1';
    api.mockRejectedValueOnce(new Error('fail'));
    await addPq();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });
});

describe('updateCategoryLabel error path', () => {
  it('shows save error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await updateCategoryLabel('dairy', 'Dairy');
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
    console.error.mockRestore();
  });
});

describe('updateCategoryEmoji error path', () => {
  it('shows save error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockRejectedValueOnce(new Error('fail'));
    await updateCategoryEmoji('dairy', '🥛');
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
    console.error.mockRestore();
  });
});

describe('updateFlagLabel error path', () => {
  it('shows save error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await updateFlagLabel('vegan', 'Vegan');
    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
    console.error.mockRestore();
  });
});

describe('checkRefreshStatus', () => {
  it('does nothing when status is not running', async () => {
    api.mockResolvedValueOnce({ running: false });
    await checkRefreshStatus();
    // No EventSource should be created
    expect(api).toHaveBeenCalledWith('/api/bulk/refresh-off/status');
  });

  it('handles API error silently', async () => {
    api.mockRejectedValueOnce(new Error('fail'));
    await checkRefreshStatus();
    // Should not throw
  });
});

describe('deletePq error path', () => {
  it('shows network error on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'pq-list';
    document.body.appendChild(list);
    api.mockRejectedValueOnce(new Error('fail'));
    await deletePq(1, 'Whey');
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });
});

describe('loadSettings', () => {
  beforeEach(() => {
    // Create DOM elements needed by loadSettings
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji', 'stats-line',
     'refresh-off-progress', 'refresh-off-bar'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    const langSelect = document.createElement('select');
    langSelect.id = 'language-select';
    document.body.appendChild(langSelect);
  });

  it('loads weights, languages, categories, flags, and PQ', async () => {
    api
      .mockResolvedValueOnce([{ field: 'kcal', label: 'Kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 500 }]) // /api/weights
      .mockResolvedValueOnce([{ code: 'no', label: 'Norsk', flag: '🇳🇴' }, { code: 'en', label: 'English', flag: '🇬🇧' }]) // /api/languages
      .mockResolvedValueOnce([{ name: 'dairy', emoji: '🧀', label: 'Dairy', count: 5 }]) // /api/categories
      .mockResolvedValueOnce([{ name: 'organic', label: 'Organic', type: 'user', count: 0 }]) // /api/flags
      .mockResolvedValueOnce([]) // /api/protein-quality
      .mockResolvedValueOnce({ off_user_id: '', has_password: false }) // /api/settings/off-credentials
      .mockResolvedValueOnce({ running: false }); // /api/bulk/refresh-off/status
    await loadSettings();
    expect(weightData.length).toBe(1);
    expect(weightData[0].field).toBe('kcal');
    const langSelect = document.getElementById('language-select');
    expect(langSelect.children.length).toBe(2);
    // Settings content should be shown, loading hidden
    expect(document.getElementById('settings-loading').style.display).toBe('none');
    expect(document.getElementById('settings-content').style.display).toBe('');
  });

  it('handles weight loading error gracefully', async () => {
    api
      .mockRejectedValueOnce(new Error('weight fail')) // /api/weights fails
      .mockResolvedValueOnce([{ code: 'no', label: 'Norsk' }]) // /api/languages
      .mockResolvedValueOnce([]) // /api/categories
      .mockResolvedValueOnce([]) // /api/flags
      .mockResolvedValueOnce([]) // /api/protein-quality
      .mockResolvedValueOnce({ off_user_id: '', has_password: false }) // /api/settings/off-credentials
      .mockResolvedValueOnce({ running: false }); // /api/bulk/refresh-off/status
    await loadSettings();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
  });

  it('prevents concurrent loads', async () => {
    // Use mockImplementation to always return [] but restore default after
    api.mockImplementation(() => Promise.resolve([]));
    const p1 = loadSettings();
    const p2 = loadSettings();
    await Promise.all([p1, p2]);
    // Only one set of API calls should happen (first call wins)
    const weightCalls = api.mock.calls.filter(c => c[0] === '/api/weights');
    expect(weightCalls.length).toBe(1);
    // Restore default mock
    api.mockReset().mockResolvedValue({});
  });
});

describe('deleteCategory with reassignment', () => {
  beforeEach(() => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    const statsLine = document.createElement('div');
    statsLine.id = 'stats-line';
    document.body.appendChild(statsLine);
  });

  it('shows reassignment modal and completes move+delete', async () => {
    // First API call: fetch categories
    api
      .mockResolvedValueOnce([
        { name: 'dairy', emoji: '🧀', label: 'Dairy' },
        { name: 'meat', emoji: '🥩', label: 'Meat' },
      ])
      // Second: DELETE with move_to
      .mockResolvedValueOnce({})
      // Third: fetchStats
      .mockResolvedValueOnce({ total: 5, types: 2 })
      // Fourth: loadCategories
      .mockResolvedValueOnce([{ name: 'meat', emoji: '🥩', label: 'Meat', count: 8 }]);

    // Start the delete - this will create a modal
    const p = deleteCategory('dairy', 'Dairy', 3);
    // Let microtasks settle so the modal gets created
    await vi.advanceTimersByTimeAsync(0);

    // Find and click the confirm button in the reassignment modal
    const confirmBtn = document.querySelector('.cat-move-confirm');
    expect(confirmBtn).not.toBeNull();
    confirmBtn.click();
    await p;

    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_category_moved_deleted'), 'success');
  });

  it('closes reassignment modal on cancel', async () => {
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
    ]);

    const p = deleteCategory('dairy', 'Dairy', 3);
    await vi.advanceTimersByTimeAsync(0);

    const cancelBtn = document.querySelector('.cat-move-cancel');
    expect(cancelBtn).not.toBeNull();
    cancelBtn.click();
    await p;

    // Modal should be removed
    expect(document.querySelector('.cat-move-modal-bg')).toBeNull();
  });

  it('renders reassignment modal with other categories', async () => {
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
    ]);

    const p = deleteCategory('dairy', 'Dairy', 3);
    await vi.advanceTimersByTimeAsync(0);

    const modal = document.querySelector('.cat-move-modal');
    expect(modal).not.toBeNull();
    const sel = document.querySelector('.cat-move-select');
    expect(sel).not.toBeNull();
    // Only 'meat' should be available (dairy filtered out)
    expect(sel.options.length).toBe(1);
    expect(sel.options[0].value).toBe('meat');

    // Close via cancel
    document.querySelector('.cat-move-cancel').click();
    await p;
  });

  it('closes modal when background is clicked', async () => {
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '🧀', label: 'Dairy' },
      { name: 'meat', emoji: '🥩', label: 'Meat' },
    ]);

    const p = deleteCategory('dairy', 'Dairy', 3);
    await vi.advanceTimersByTimeAsync(0);

    const bg = document.querySelector('.cat-move-modal-bg');
    expect(bg).not.toBeNull();
    // Simulate background click
    bg.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await p;

    expect(document.querySelector('.cat-move-modal-bg')).toBeNull();
  });
});

describe('refreshAllFromOff', () => {
  let mockES;
  beforeEach(() => {
    // Create DOM elements used by refreshAllFromOff and _connectRefreshStream
    ['btn-refresh-all-off', 'refresh-off-progress', 'refresh-off-bar', 'refresh-off-status'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    // Stub EventSource globally for all tests in this block
    mockES = { onmessage: null, onerror: null, close: vi.fn() };
    vi.stubGlobal('EventSource', vi.fn(() => mockES));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    api.mockReset().mockResolvedValue({});
  });

  it('does nothing when modal is cancelled via cancel button', async () => {
    const p = refreshAllFromOff();
    await vi.advanceTimersByTimeAsync(0);

    // The modal should be in the DOM
    const noBtn = document.querySelector('.confirm-no');
    expect(noBtn).not.toBeNull();
    noBtn.click();
    await p;

    // No API call for starting refresh should have been made
    expect(api).not.toHaveBeenCalledWith('/api/bulk/refresh-off/start', expect.anything());
  });

  it('does nothing when modal is dismissed via Escape key', async () => {
    const p = refreshAllFromOff();
    await vi.advanceTimersByTimeAsync(0);

    const modal = document.querySelector('.scan-modal-bg');
    expect(modal).not.toBeNull();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await p;

    expect(api).not.toHaveBeenCalledWith('/api/bulk/refresh-off/start', expect.anything());
    // Modal should be removed
    expect(document.querySelector('.scan-modal-bg')).toBeNull();
  });

  it('does nothing when modal is dismissed via background click', async () => {
    const p = refreshAllFromOff();
    await vi.advanceTimersByTimeAsync(0);

    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    // Click on background itself (not child)
    bg.dispatchEvent(new MouseEvent('click', { bubbles: false }));
    await p;

    expect(api).not.toHaveBeenCalledWith('/api/bulk/refresh-off/start', expect.anything());
  });

  it('starts refresh when modal is confirmed with defaults', async () => {
    api.mockResolvedValueOnce({}); // POST /api/bulk/refresh-off/start

    const p = refreshAllFromOff();

    const yesBtn = document.querySelector('.confirm-yes');
    expect(yesBtn).not.toBeNull();
    yesBtn.click();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    expect(api).toHaveBeenCalledWith('/api/bulk/refresh-off/start', expect.objectContaining({
      method: 'POST',
    }));
    // Body should not include search_missing since checkbox was not checked
    const callBody = JSON.parse(api.mock.calls[0][1].body);
    expect(callBody.search_missing).toBeUndefined();
  });

  it('starts refresh with searchMissing options when checkbox is checked', async () => {
    api.mockResolvedValueOnce({}); // POST /api/bulk/refresh-off/start

    const p = refreshAllFromOff();

    // Check the searchMissing checkbox
    const cb = document.querySelector('.refresh-off-cb-label input[type="checkbox"]');
    expect(cb).not.toBeNull();
    cb.checked = true;
    cb.dispatchEvent(new Event('change'));

    // Sliders should now be visible
    const sliders = document.querySelector('.refresh-off-sliders');
    expect(sliders.style.display).toBe('');

    const yesBtn = document.querySelector('.confirm-yes');
    yesBtn.click();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    const callBody = JSON.parse(api.mock.calls[0][1].body);
    expect(callBody.search_missing).toBe(true);
    expect(callBody.min_certainty).toBe(100);
    expect(callBody.min_completeness).toBe(75);
  });

  it('shows error toast on non-already_running API error', async () => {
    api.mockResolvedValueOnce({ error: 'some_error' });

    const p = refreshAllFromOff();
    document.querySelector('.confirm-yes').click();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);

    expect(showToast).toHaveBeenCalledWith('some_error', 'error');
  });

  it('shows network error toast on API exception', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('network fail'));

    const p = refreshAllFromOff();
    document.querySelector('.confirm-yes').click();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('handles already_running error from API', async () => {
    api.mockResolvedValueOnce({ error: 'already_running' });

    const p = refreshAllFromOff();
    document.querySelector('.confirm-yes').click();
    await vi.advanceTimersByTimeAsync(0);
    await p;

    // Should still connect to stream (not show error toast)
    expect(EventSource).toHaveBeenCalled();
  });

  it('slider input updates displayed value', async () => {
    const p = refreshAllFromOff();
    await vi.advanceTimersByTimeAsync(0);

    // Check checkbox to show sliders
    const cb = document.querySelector('.refresh-off-cb-label input[type="checkbox"]');
    cb.checked = true;
    cb.dispatchEvent(new Event('change'));

    // Find range inputs and change value
    const ranges = document.querySelectorAll('.refresh-off-range-row input[type="range"]');
    expect(ranges.length).toBe(2);
    ranges[0].value = '80';
    ranges[0].dispatchEvent(new Event('input'));
    const valSpan = ranges[0].parentElement.querySelector('.refresh-off-range-val');
    expect(valSpan.textContent).toBe('80');

    // Cancel to clean up
    document.querySelector('.confirm-no').click();
    await p;
  });
});

describe('loadSettings - loadOffCredentials paths', () => {
  beforeEach(() => {
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji', 'stats-line',
     'refresh-off-progress', 'refresh-off-bar'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    // OFF credentials fields need to be input elements
    ['off-user-id', 'off-password'].forEach((id) => {
      const el = document.createElement('input');
      el.id = id;
      document.body.appendChild(el);
    });
    const langSelect = document.createElement('select');
    langSelect.id = 'language-select';
    document.body.appendChild(langSelect);
  });

  it('shows error toast when loadOffCredentials fails', async () => {
    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([{ field: 'kcal', label: 'Kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 500 }]);
      if (url === '/api/languages') return Promise.resolve([{ code: 'no', label: 'Norsk', flag: '\uD83C\uDDF3\uD83C\uDDF4' }]);
      if (url === '/api/settings/off-credentials') return Promise.reject(new Error('cred fail'));
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    await vi.advanceTimersByTimeAsync(0);
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    api.mockReset().mockResolvedValue({});
  });

  it('populates OFF credentials fields on success with password', async () => {
    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([{ field: 'kcal', label: 'Kcal', enabled: true, weight: 50, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 500 }]);
      if (url === '/api/languages') return Promise.resolve([{ code: 'no', label: 'Norsk', flag: '\uD83C\uDDF3\uD83C\uDDF4' }]);
      if (url === '/api/settings/off-credentials') return Promise.resolve({ off_user_id: 'myuser', has_password: true });
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    await vi.advanceTimersByTimeAsync(0);
    expect(document.getElementById('off-user-id').value).toBe('myuser');
    expect(document.getElementById('off-password').value).toBe('\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022');
    api.mockReset().mockResolvedValue({});
  });
});

// ══════════════════════════════════════════════════════
// NEW TESTS: Cover falsy branches of null-check guards
// ══════════════════════════════════════════════════════

describe('_connectRefreshStream with NO DOM elements', () => {
  let mockES;
  beforeEach(() => {
    // Intentionally NO DOM elements — covers all if(btn), if(bar), if(status), if(progressWrap) falsy branches
    mockES = { onmessage: null, onerror: null, close: vi.fn() };
    vi.stubGlobal('EventSource', vi.fn(() => mockES));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    api.mockReset().mockResolvedValue({});
  });

  it('handles onmessage with running data and no DOM elements', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // Fire onmessage with running data — bar/status are null, falsy branches hit
    mockES.onmessage({ data: JSON.stringify({ running: true, total: 10, current: 3, name: 'TestProduct' }) });
    expect(mockES.close).not.toHaveBeenCalled();
  });

  it('handles onmessage with running data using ean instead of name', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // data.name is falsy, falls back to data.ean
    mockES.onmessage({ data: JSON.stringify({ running: true, total: 5, current: 2, ean: '12345' }) });
    expect(mockES.close).not.toHaveBeenCalled();
  });

  it('handles onmessage with done data, no report, no DOM', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // done without report — covers data.report falsy branch + all DOM falsy branches
    mockES.onmessage({ data: JSON.stringify({ done: true, total: 10, updated: 5, skipped: 3, errors: 2 }) });
    expect(mockES.close).toHaveBeenCalled();
    expect(showToast).toHaveBeenCalled();
  });

  it('handles onmessage with done data and report but no container', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // done with report — _renderRefreshReport called but container missing -> early return
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 5, updated: 3, skipped: 1, errors: 1,
      report: [{ name: 'P1', status: 'updated', fields: ['kcal'] }]
    }) });
    expect(mockES.close).toHaveBeenCalled();
  });

  it('handles onmessage with invalid JSON data', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // Invalid JSON triggers the catch and returns early
    mockES.onmessage({ data: 'not json' });
    expect(mockES.close).not.toHaveBeenCalled();
  });

  it('handles onmessage with running=true but total=0', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // data.running && data.total > 0 is false when total is 0
    mockES.onmessage({ data: JSON.stringify({ running: true, total: 0, current: 0 }) });
    expect(mockES.close).not.toHaveBeenCalled();
  });

  it('handles onerror with no DOM elements', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // onerror — btn and progressWrap are null, falsy branches hit
    mockES.onerror();
    expect(mockES.close).toHaveBeenCalled();
  });

  it('closes previous EventSource when reconnecting', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    const firstES = mockES;
    // Create a new mock for the second connection
    const mockES2 = { onmessage: null, onerror: null, close: vi.fn() };
    EventSource.mockImplementation(() => mockES2);
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    expect(firstES.close).toHaveBeenCalled();
  });
});

describe('_renderRefreshReport with container present', () => {
  let mockES;
  beforeEach(() => {
    const container = document.createElement('div');
    container.id = 'refresh-off-progress';
    document.body.appendChild(container);
    mockES = { onmessage: null, onerror: null, close: vi.fn() };
    vi.stubGlobal('EventSource', vi.fn(() => mockES));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    api.mockReset().mockResolvedValue({});
  });

  it('renders report with updated status and fields', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 3, updated: 2, skipped: 1, errors: 0,
      report: [
        { name: 'Product A', status: 'updated', fields: ['kcal', 'protein'] },
      ]
    }) });
    const report = document.querySelector('.refresh-report');
    expect(report).not.toBeNull();
    const toggle = report.querySelector('.refresh-report-toggle');
    expect(toggle).not.toBeNull();
  });

  it('renders report with various statuses and report items visible in modal', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 4, updated: 1, skipped: 2, errors: 1,
      report: [
        { name: 'P1', status: 'updated', fields: ['kcal'] },
        { name: 'P2', status: 'skipped', reason: 'not_found' },
        { ean: '999', status: 'error', reason: 'some_unknown_reason', detail: 'extra info' },
        { status: 'skipped', reason: 'no_results' },
      ]
    }) });
    const report = document.querySelector('.refresh-report');
    expect(report).not.toBeNull();
    // The toggle button should exist
    const toggle = report.querySelector('.refresh-report-toggle');
    expect(toggle).not.toBeNull();
  });

  it('opens report modal when toggle button is clicked', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 1, updated: 1, skipped: 0, errors: 0,
      report: [{ name: 'P1', status: 'updated', fields: ['fat'] }]
    }) });
    const toggle = document.querySelector('.refresh-report-toggle');
    toggle.click();
    const modalBg = document.getElementById('refresh-report-modal-bg');
    expect(modalBg).not.toBeNull();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('closes report modal via close button', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 1, updated: 1, skipped: 0, errors: 0,
      report: [{ name: 'P1', status: 'updated', fields: ['fat'] }]
    }) });
    document.querySelector('.refresh-report-toggle').click();
    const closeBtn = document.querySelector('.off-modal-close');
    closeBtn.click();
    expect(document.getElementById('refresh-report-modal-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });

  it('closes report modal via Escape key', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 1, updated: 1, skipped: 0, errors: 0,
      report: [{ name: 'P1', status: 'updated', fields: ['fat'] }]
    }) });
    document.querySelector('.refresh-report-toggle').click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(document.getElementById('refresh-report-modal-bg')).toBeNull();
  });

  it('closes report modal via background click', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 1, updated: 1, skipped: 0, errors: 0,
      report: [{ name: 'P1', status: 'updated', fields: ['fat'] }]
    }) });
    document.querySelector('.refresh-report-toggle').click();
    const bg = document.getElementById('refresh-report-modal-bg');
    bg.dispatchEvent(new MouseEvent('click', { bubbles: false }));
    expect(document.getElementById('refresh-report-modal-bg')).toBeNull();
  });

  it('removes previous report when new one arrives', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    // First report
    mockES.onmessage({ data: JSON.stringify({
      done: true, total: 1, updated: 1, skipped: 0, errors: 0,
      report: [{ name: 'P1', status: 'updated', fields: ['fat'] }]
    }) });
    expect(document.querySelectorAll('.refresh-report').length).toBe(1);
    // Reconnect and send second report
    const mockES2 = { onmessage: null, onerror: null, close: vi.fn() };
    EventSource.mockImplementation(() => mockES2);
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES2.onmessage({ data: JSON.stringify({
      done: true, total: 2, updated: 2, skipped: 0, errors: 0,
      report: [{ name: 'P2', status: 'updated', fields: ['salt'] }]
    }) });
    // Old report replaced by new
    expect(document.querySelectorAll('.refresh-report').length).toBe(1);
  });
});

describe('handleImport error and cancel paths', () => {
  it('shows error toast for invalid JSON in file', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: 'not valid json' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['x'])], value: 'bad.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(10);
    expect(showToast).toHaveBeenCalledWith('toast_invalid_file', 'error');
    global.FileReader = origFileReader;
  });

  it('cancels import when duplicate dialog is cancelled', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    // Click cancel button on the duplicate dialog
    const cancelBtn = document.querySelector('.scan-modal-btn-cancel');
    expect(cancelBtn).not.toBeNull();
    cancelBtn.click();
    await vi.advanceTimersByTimeAsync(10);
    expect(api).not.toHaveBeenCalledWith('/api/import', expect.anything());
    expect(input.value).toBe('');
    global.FileReader = origFileReader;
  });

  it('shows error when import API returns error', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    api.mockResolvedValueOnce({ error: 'Import failed' });
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    const startBtn = document.querySelector('.scan-modal-btn-register');
    startBtn.click();
    await vi.advanceTimersByTimeAsync(50);
    expect(showToast).toHaveBeenCalledWith('Import failed', 'error');
    global.FileReader = origFileReader;
  });

  it('loads settings when import succeeds and currentView is settings', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    // Set up DOM for loadSettings to work
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    state.currentView = 'settings';
    api.mockResolvedValueOnce({ message: 'Imported 5 products' }); // /api/import
    // loadSettings will call many apis
    api.mockImplementation(() => Promise.resolve([]));
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    const startBtn = document.querySelector('.scan-modal-btn-register');
    startBtn.click();
    await vi.advanceTimersByTimeAsync(50);
    expect(showToast).toHaveBeenCalledWith('Imported 5 products', 'success');
    state.currentView = 'search';
    api.mockReset().mockResolvedValue({});
    global.FileReader = origFileReader;
  });
});

describe('showImportDuplicateDialog edge cases', () => {
  it('closes dialog via Escape key', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await vi.advanceTimersByTimeAsync(10);
    expect(document.querySelector('.scan-modal-bg')).toBeNull();
    expect(api).not.toHaveBeenCalledWith('/api/import', expect.anything());
    global.FileReader = origFileReader;
  });

  it('closes dialog via background click', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    const bg = document.querySelector('.scan-modal-bg');
    bg.dispatchEvent(new MouseEvent('click', { bubbles: false }));
    await vi.advanceTimersByTimeAsync(10);
    expect(document.querySelector('.scan-modal-bg')).toBeNull();
    global.FileReader = origFileReader;
  });

  it('shows merge section when merge action is selected', async () => {
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['{}'])], value: 'import.json' };
    handleImport(input);
    await vi.advanceTimersByTimeAsync(0);
    // Select merge radio
    const mergeRadio = document.querySelector('input[name="on_duplicate"][value="merge"]');
    expect(mergeRadio).not.toBeNull();
    mergeRadio.checked = true;
    // Trigger change on the action section
    const actionSection = mergeRadio.closest('.import-dup-section');
    actionSection.dispatchEvent(new Event('change', { bubbles: true }));
    // Merge rules should now be visible
    const mergeRules = document.querySelector('.import-dup-merge-rules');
    expect(mergeRules.style.display).toBe('');
    // Clean up
    document.querySelector('.scan-modal-btn-cancel').click();
    await vi.advanceTimersByTimeAsync(10);
    global.FileReader = origFileReader;
  });
});

describe('initRestoreDragDrop missing element', () => {
  it('returns early when restore-drop element is missing', () => {
    const { initRestoreDragDrop } = require('../settings.js');
    // No DOM element created — should return early without error
    expect(() => initRestoreDragDrop()).not.toThrow();
  });

  it('handles drop event with no files', () => {
    const { initRestoreDragDrop } = require('../settings.js');
    const drop = document.createElement('div');
    drop.id = 'restore-drop';
    document.body.appendChild(drop);
    initRestoreDragDrop();
    // Simulate drop with no files
    const dropEvent = new Event('drop');
    dropEvent.preventDefault = vi.fn();
    dropEvent.dataTransfer = { files: [] };
    drop.dispatchEvent(dropEvent);
    expect(drop.classList.contains('dragover')).toBe(false);
  });

  it('handles dragleave event', () => {
    const { initRestoreDragDrop } = require('../settings.js');
    const drop = document.createElement('div');
    drop.id = 'restore-drop';
    document.body.appendChild(drop);
    initRestoreDragDrop();
    drop.classList.add('dragover');
    drop.dispatchEvent(new Event('dragleave'));
    expect(drop.classList.contains('dragover')).toBe(false);
  });
});

describe('loadSettings with missing DOM elements', () => {
  it('works without settings-loading, settings-content, or language-select', async () => {
    // Only create weight-items and cat-list (minimum for renderWeightItems/loadCategories)
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    const catList = document.createElement('div');
    catList.id = 'cat-list';
    document.body.appendChild(catList);
    const flagList = document.createElement('div');
    flagList.id = 'flag-list';
    document.body.appendChild(flagList);
    const pqList = document.createElement('div');
    pqList.id = 'pq-list';
    document.body.appendChild(pqList);

    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([]);
      if (url === '/api/categories') return Promise.resolve([]);
      if (url === '/api/flags') return Promise.resolve([]);
      if (url === '/api/protein-quality') return Promise.resolve([]);
      if (url === '/api/settings/off-credentials') return Promise.resolve({ off_user_id: '', has_password: false });
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    // settingsLoading and settingsContent are null — falsy branches hit
    // langSelect is null — entire block skipped
    expect(weightData.length).toBe(0);
    api.mockReset().mockResolvedValue({});
  });

  it('handles language API failure', async () => {
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    const langSelect = document.createElement('select');
    langSelect.id = 'language-select';
    document.body.appendChild(langSelect);

    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([]);
      if (url === '/api/languages') return Promise.reject(new Error('lang fail'));
      if (url === '/api/categories') return Promise.resolve([]);
      if (url === '/api/flags') return Promise.resolve([]);
      if (url === '/api/protein-quality') return Promise.resolve([]);
      if (url === '/api/settings/off-credentials') return Promise.resolve({ off_user_id: '', has_password: false });
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
    api.mockReset().mockResolvedValue({});
  });

  it('renders language option without flag property', async () => {
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    const langSelect = document.createElement('select');
    langSelect.id = 'language-select';
    document.body.appendChild(langSelect);

    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([]);
      // Language without flag — covers l.flag falsy branch (line 61)
      if (url === '/api/languages') return Promise.resolve([{ code: 'en', label: 'English' }]);
      if (url === '/api/categories') return Promise.resolve([]);
      if (url === '/api/flags') return Promise.resolve([]);
      if (url === '/api/protein-quality') return Promise.resolve([]);
      if (url === '/api/settings/off-credentials') return Promise.resolve({ off_user_id: '', has_password: false });
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    const opt = langSelect.querySelector('option');
    expect(opt.textContent).toBe('English'); // No flag prefix
    api.mockReset().mockResolvedValue({});
  });
});

describe('estimateAllPq with no DOM elements', () => {
  it('succeeds with no btn or status element', async () => {
    // No DOM elements — all if(btn)/if(status) falsy branches hit
    api.mockResolvedValueOnce({ total: 10, updated: 8, skipped: 2 });
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('handles error with no btn or status element', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('handles API error field with no btn or status', async () => {
    api.mockResolvedValueOnce({ error: 'pq error' });
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith('pq error', 'error');
  });
});

describe('refreshAllFromOff with missing bar and prevReport', () => {
  let mockES;
  beforeEach(() => {
    // Only create the button, NOT the bar or progress elements
    const btn = document.createElement('button');
    btn.id = 'btn-refresh-all-off';
    document.body.appendChild(btn);
    mockES = { onmessage: null, onerror: null, close: vi.fn() };
    vi.stubGlobal('EventSource', vi.fn(() => mockES));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    api.mockReset().mockResolvedValue({});
  });

  it('starts refresh without bar or prevReport elements', async () => {
    api.mockResolvedValueOnce({});
    const p = refreshAllFromOff();
    document.querySelector('.confirm-yes').click();
    await vi.advanceTimersByTimeAsync(0);
    await p;
    expect(api).toHaveBeenCalledWith('/api/bulk/refresh-off/start', expect.anything());
  });
});

describe('saveWeights with disabled weights and missing slider elements', () => {
  it('preserves disabled weight values without DOM elements', async () => {
    weightData.push(
      { field: 'kcal', enabled: false, weight: 0, direction: 'lower', formula: 'minmax', formula_min: 5, formula_max: 100 },
    );
    api.mockResolvedValueOnce({});
    await saveWeights();
    const payload = JSON.parse(api.mock.calls[0][1].body);
    expect(payload[0].enabled).toBe(false);
    expect(payload[0].formula_min).toBe(5);
  });

  it('handles enabled weight without slider/min/max elements (ternary fallbacks)', async () => {
    weightData.push(
      { field: 'protein', enabled: true, weight: 30, direction: 'higher', formula: 'direct', formula_min: 0, formula_max: 50 },
    );
    // No DOM elements for protein — sliderEl/minEl/maxEl are null, ternary fallback used
    api.mockResolvedValueOnce({});
    await saveWeights();
    const payload = JSON.parse(api.mock.calls[0][1].body);
    expect(payload[0].weight).toBe(30); // Falls back to w.weight
    expect(payload[0].formula_min).toBe(0); // Falls back to 0
    expect(payload[0].formula_max).toBe(0);
  });
});

describe('onWeightFormula with missing min/max elements', () => {
  it('does not throw when min/max elements are missing', () => {
    weightData.push({ field: 'salt', formula: 'minmax' });
    const sel = document.createElement('select');
    sel.id = 'wf-salt';
    const opt = document.createElement('option');
    opt.value = 'direct';
    sel.appendChild(opt);
    sel.value = 'direct';
    document.body.appendChild(sel);
    // No wn-salt or wm-salt elements — falsy branches for minEl/maxEl
    expect(() => onWeightFormula('salt')).not.toThrow();
    expect(weightData[0].formula).toBe('direct');
  });
});

describe('savePqField with missing DOM elements', () => {
  it('returns early when label element is missing', async () => {
    // Only create some elements, not all — early return on line 631
    const kw = document.createElement('input');
    kw.id = 'pqe-kw-99';
    kw.value = 'test';
    document.body.appendChild(kw);
    await savePqField(99);
    expect(api).not.toHaveBeenCalled();
  });
});

describe('handleRestore error and settings paths', () => {
  it('shows error when restore API returns error field', async () => {
    showConfirmModal.mockResolvedValue(true);
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    api.mockResolvedValueOnce({ error: 'Restore failed' });
    const input = { files: [new Blob(['{}'])], value: 'file.json' };
    await handleRestore(input);
    await vi.advanceTimersByTimeAsync(50);
    expect(showToast).toHaveBeenCalledWith('Restore failed', 'error');
    global.FileReader = origFileReader;
  });

  it('shows invalid file toast for corrupt JSON on restore', async () => {
    showConfirmModal.mockResolvedValue(true);
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: 'corrupt data' } });
        }, 0);
      }
    };
    const input = { files: [new Blob(['x'])], value: 'file.json' };
    await handleRestore(input);
    await vi.advanceTimersByTimeAsync(50);
    expect(showToast).toHaveBeenCalledWith('toast_invalid_file', 'error');
    global.FileReader = origFileReader;
  });

  it('reloads settings when restore succeeds and currentView is settings', async () => {
    showConfirmModal.mockResolvedValue(true);
    state.currentView = 'settings';
    // Create minimum DOM for loadSettings
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    const origFileReader = global.FileReader;
    global.FileReader = class {
      readAsText() {
        setTimeout(() => {
          this.onload({ target: { result: '{"products":[]}' } });
        }, 0);
      }
    };
    api.mockResolvedValueOnce({ message: 'Restored!' });
    api.mockImplementation(() => Promise.resolve([]));
    const input = { files: [new Blob(['{}'])], value: 'file.json' };
    await handleRestore(input);
    await vi.advanceTimersByTimeAsync(50);
    expect(showToast).toHaveBeenCalledWith('Restored!', 'success');
    state.currentView = 'search';
    api.mockReset().mockResolvedValue({});
    global.FileReader = origFileReader;
  });
});

describe('deleteCategory reassignment error paths', () => {
  beforeEach(() => {
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
  });

  it('shows error when reassignment delete returns error field', async () => {
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '', label: 'Dairy' },
      { name: 'meat', emoji: '', label: 'Meat' },
    ]);
    api.mockResolvedValueOnce({ error: 'Move failed' });
    const p = deleteCategory('dairy', 'Dairy', 3);
    await vi.advanceTimersByTimeAsync(0);
    const confirmBtn = document.querySelector('.cat-move-confirm');
    confirmBtn.click();
    await p;
    expect(showToast).toHaveBeenCalledWith('Move failed', 'error');
  });

  it('shows network error when reassignment delete throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockResolvedValueOnce([
      { name: 'dairy', emoji: '', label: 'Dairy' },
      { name: 'meat', emoji: '', label: 'Meat' },
    ]);
    api.mockRejectedValueOnce(new Error('network'));
    const p = deleteCategory('dairy', 'Dairy', 3);
    await vi.advanceTimersByTimeAsync(0);
    document.querySelector('.cat-move-confirm').click();
    await p;
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });

  it('handles categories API failure in deleteCategory', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('fail'));
    await deleteCategory('dairy', 'Dairy', 3);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });
});

describe('renderWeightItems with direct formula and formula_min/max null', () => {
  it('renders with formula_min and formula_max as null', () => {
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    weightData.push({
      field: 'kcal', label: 'Kcal', enabled: true, weight: 50,
      direction: 'higher', formula: 'direct', formula_min: null, formula_max: null
    });
    renderWeightItems();
    const minInput = document.getElementById('wn-kcal');
    const maxInput = document.getElementById('wm-kcal');
    expect(minInput.value).toBe('');
    expect(maxInput.value).toBe('');
    // Also verify direct formula shows the inputs
    expect(minInput.style.display).toBe('');
    expect(maxInput.style.display).toBe('');
  });

  it('renders all disabled weights (no enabled)', () => {
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    weightData.push(
      { field: 'kcal', label: 'Kcal', enabled: false, weight: 0, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 0 },
    );
    renderWeightItems();
    expect(container.querySelectorAll('.weight-item').length).toBe(0);
    expect(document.getElementById('weight-add-select')).not.toBeNull();
  });
});

describe('addWeightFromDropdown with missing select', () => {
  it('returns early when weight-add-select element is missing', () => {
    const container = document.createElement('div');
    container.id = 'weight-items';
    document.body.appendChild(container);
    // No weight-add-select element
    expect(() => addWeightFromDropdown()).not.toThrow();
  });
});

describe('updateStatsLine falsy paths', () => {
  it('handles updateStatsLine when stats-line element is missing', async () => {
    // updateStatsLine is called by updateCategoryLabel after success
    // No stats-line element — falsy branch for el
    api.mockResolvedValueOnce({});
    await updateCategoryLabel('dairy', 'Meieri');
    expect(showToast).toHaveBeenCalledWith('toast_category_updated', 'success');
  });

  it('handles updateStatsLine when cachedStats is null', async () => {
    const el = document.createElement('div');
    el.id = 'stats-line';
    document.body.appendChild(el);
    const origStats = state.cachedStats;
    state.cachedStats = null;
    api.mockResolvedValueOnce({});
    await updateCategoryLabel('dairy', 'Meieri');
    state.cachedStats = origStats;
  });
});

describe('deleteCategory with count=0 and delete error from API exception', () => {
  it('shows network error when delete API throws for zero-product category', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    showConfirmModal.mockResolvedValue(true);
    const list = document.createElement('div');
    list.id = 'cat-list';
    document.body.appendChild(list);
    api.mockRejectedValueOnce(new Error('network fail'));
    await deleteCategory('snack', 'Snacks', 0);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    console.error.mockRestore();
  });
});

describe('_connectRefreshStream with some DOM elements', () => {
  let mockES;
  beforeEach(() => {
    // Create bar and status but NOT btn or progressWrap
    const bar = document.createElement('div');
    bar.id = 'refresh-off-bar';
    document.body.appendChild(bar);
    const status = document.createElement('div');
    status.id = 'refresh-off-status';
    document.body.appendChild(status);
    mockES = { onmessage: null, onerror: null, close: vi.fn() };
    vi.stubGlobal('EventSource', vi.fn(() => mockES));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    api.mockReset().mockResolvedValue({});
  });

  it('updates bar and status on running message', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({ running: true, total: 10, current: 5, name: 'Test' }) });
    expect(document.getElementById('refresh-off-bar').style.width).toBe('50%');
  });

  it('sets bar to 100% on done', async () => {
    api.mockResolvedValueOnce({ running: true });
    await checkRefreshStatus();
    mockES.onmessage({ data: JSON.stringify({ done: true, total: 10, updated: 5, skipped: 3, errors: 2 }) });
    expect(document.getElementById('refresh-off-bar').style.width).toBe('100%');
  });
});

describe('saveWeights with mixed enabled/disabled and formula_max 0', () => {
  it('handles disabled weight with formula_min/max as 0 (falsy)', async () => {
    weightData.push(
      { field: 'sugar', enabled: false, weight: 0, direction: 'lower', formula: 'minmax', formula_min: 0, formula_max: 0 },
    );
    api.mockResolvedValueOnce({});
    await saveWeights();
    const payload = JSON.parse(api.mock.calls[0][1].body);
    expect(payload[0].formula_min).toBe(0);
    expect(payload[0].formula_max).toBe(0);
  });
});

describe('autosavePq', () => {
  it('calls savePqField after 400ms debounce', () => {
    // Set up DOM elements that savePqField needs
    ['label', 'kw', 'pdcaas', 'diaas'].forEach((suffix) => {
      const el = document.createElement('input');
      el.id = 'pqe-' + suffix + '-1';
      el.value = suffix === 'kw' ? 'milk' : suffix === 'label' ? 'Milk' : '0.8';
      document.body.appendChild(el);
    });
    api.mockResolvedValue({ id: 1 });

    autosavePq(1);
    // Should not have called API yet
    expect(api).not.toHaveBeenCalled();

    // Advance past the 400ms debounce
    vi.advanceTimersByTime(400);
    expect(api).toHaveBeenCalledWith('/api/protein-quality/1', expect.objectContaining({ method: 'PUT' }));
  });

  it('debounces multiple rapid calls for the same id', () => {
    ['label', 'kw', 'pdcaas', 'diaas'].forEach((suffix) => {
      const el = document.createElement('input');
      el.id = 'pqe-' + suffix + '-2';
      el.value = suffix === 'kw' ? 'whey' : suffix === 'label' ? 'Whey' : '1.0';
      document.body.appendChild(el);
    });
    api.mockResolvedValue({ id: 2 });

    autosavePq(2);
    vi.advanceTimersByTime(200);
    autosavePq(2); // reset the timer
    vi.advanceTimersByTime(200);
    // Only 200ms since last call — should not have fired yet
    expect(api).not.toHaveBeenCalled();

    vi.advanceTimersByTime(200);
    // Now 400ms since last call — should fire exactly once
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('handles different ids independently', () => {
    [3, 4].forEach((id) => {
      ['label', 'kw', 'pdcaas', 'diaas'].forEach((suffix) => {
        const el = document.createElement('input');
        el.id = 'pqe-' + suffix + '-' + id;
        el.value = suffix === 'kw' ? 'soy' : suffix === 'label' ? 'Soy' : '0.9';
        document.body.appendChild(el);
      });
    });
    api.mockResolvedValue({});

    autosavePq(3);
    vi.advanceTimersByTime(200);
    autosavePq(4);
    vi.advanceTimersByTime(200);
    // id 3 should have fired (400ms elapsed), id 4 should not (only 200ms)
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).toHaveBeenCalledWith('/api/protein-quality/3', expect.anything());

    vi.advanceTimersByTime(200);
    // Now id 4 should also have fired
    expect(api).toHaveBeenCalledTimes(2);
    expect(api).toHaveBeenCalledWith('/api/protein-quality/4', expect.anything());
  });
});

describe('loadSettings - loadOffCredentials with missing off-user-id/off-password', () => {
  it('handles missing OFF credential DOM elements gracefully', async () => {
    ['settings-loading', 'settings-content', 'weight-items', 'cat-list',
     'flag-list', 'pq-list', 'cat-emoji-trigger', 'cat-emoji'].forEach((id) => {
      const el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    });
    // Intentionally NOT creating off-user-id or off-password elements
    api.mockImplementation((url) => {
      if (url === '/api/weights') return Promise.resolve([]);
      if (url === '/api/categories') return Promise.resolve([]);
      if (url === '/api/flags') return Promise.resolve([]);
      if (url === '/api/protein-quality') return Promise.resolve([]);
      if (url === '/api/settings/off-credentials') return Promise.resolve({ off_user_id: 'test', has_password: false });
      if (url === '/api/bulk/refresh-off/status') return Promise.resolve({ running: false });
      return Promise.resolve([]);
    });
    await loadSettings();
    // Should not throw — if(el) and if(pw) falsy branches hit in loadOffCredentials
    api.mockReset().mockResolvedValue({});
  });
});
