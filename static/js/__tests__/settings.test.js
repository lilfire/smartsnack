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

import {
  SCORE_COLORS, SCORE_CFG_MAP, weightData,
  toggleWeightConfig, removeWeight, addWeightFromDropdown,
  toggleSettingsSection, downloadBackup, saveOffCredentials,
  loadCategories, updateCategoryLabel, updateCategoryEmoji, addCategory, deleteCategory,
  loadPq, addPq, deletePq, saveWeights,
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
