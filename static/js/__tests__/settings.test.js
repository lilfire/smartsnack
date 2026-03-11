import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedStats: { total: 5, types: 2, categories: [] },
    cachedResults: [],
    categories: [],
    imageCache: {},
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    esc: (s) => String(s),
    fetchStats: vi.fn().mockResolvedValue({}),
    upgradeSelect: vi.fn(),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
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
} from '../settings.js';
import { state, api, showToast, fetchStats, showConfirmModal } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  weightData.length = 0;
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
    await new Promise((r) => setTimeout(r, 50));

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
    await new Promise((r) => setTimeout(r, 50));

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
