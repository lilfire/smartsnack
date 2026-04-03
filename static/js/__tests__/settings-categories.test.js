import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  state: { cachedStats: { total: 5, types: 2 } },
  api: vi.fn().mockResolvedValue([]),
  esc: (s) => String(s),
  fetchStats: vi.fn().mockResolvedValue({}),
  upgradeSelect: vi.fn(),
  showConfirmModal: vi.fn().mockResolvedValue(true),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../emoji-picker.js', () => ({
  initEmojiPicker: vi.fn(),
  resetEmojiPicker: vi.fn(),
}));

import {
  loadCategories,
  updateCategoryLabel,
  updateCategoryEmoji,
  addCategory,
  deleteCategory,
} from '../settings-categories.js';
import { api, showToast, fetchStats, showConfirmModal } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  api.mockResolvedValue([]);
  showConfirmModal.mockResolvedValue(true);
});

// ── loadCategories ───────────────────────────────────
describe('loadCategories', () => {
  it('shows empty message when no categories', async () => {
    api.mockResolvedValue([]);
    document.body.innerHTML = '<div id="cat-list"></div><div id="stats-line"></div>';
    await loadCategories();
    expect(document.getElementById('cat-list').innerHTML).toContain('No categories');
  });

  it('renders categories list', async () => {
    const cats = [{ name: 'dairy', label: 'Dairy', emoji: '🥛', count: 3 }];
    api.mockResolvedValue(cats);
    document.body.innerHTML = '<div id="cat-list"></div>';
    await loadCategories();
    const list = document.getElementById('cat-list');
    expect(list.innerHTML).toContain('dairy');
  });

  it('shows error toast on API failure', async () => {
    api.mockRejectedValue(new Error('API error'));
    document.body.innerHTML = '<div id="cat-list"></div>';
    await loadCategories();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── updateCategoryLabel ──────────────────────────────
describe('updateCategoryLabel', () => {
  it('shows error for empty label', async () => {
    document.body.innerHTML = '<div id="cat-list"></div>';
    api.mockResolvedValue([]);
    await updateCategoryLabel('dairy', '   ');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls api with updated label', async () => {
    document.body.innerHTML = '<div id="cat-list"></div><div id="stats-line"></div>';
    api.mockResolvedValue([]);
    await updateCategoryLabel('dairy', 'Dairy Products');
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining('/api/categories/dairy'),
      expect.objectContaining({ method: 'PUT' }),
    );
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error toast on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await updateCategoryLabel('dairy', 'Dairy');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── updateCategoryEmoji ──────────────────────────────
describe('updateCategoryEmoji', () => {
  it('calls api with new emoji', async () => {
    document.body.innerHTML = '<div id="cat-list"></div><div id="stats-line"></div>';
    api.mockResolvedValue([]);
    await updateCategoryEmoji('dairy', '🐄');
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining('/api/categories/dairy'),
      expect.objectContaining({ method: 'PUT', body: expect.stringContaining('🐄') }),
    );
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error on failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await updateCategoryEmoji('dairy', '🐄');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── addCategory ──────────────────────────────────────
describe('addCategory', () => {
  function setupDOM(name = 'snacks', label = 'Snacks', emoji = '🍕') {
    document.body.innerHTML = `
      <input id="cat-name" value="${name}">
      <input id="cat-label" value="${label}">
      <input id="cat-emoji" value="${emoji}">
      <button id="cat-emoji-trigger"></button>
      <div id="cat-list"></div>
      <div id="stats-line"></div>`;
  }

  it('shows error when name or label is empty', async () => {
    setupDOM('', 'Snacks');
    await addCategory();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls api to create category', async () => {
    setupDOM('snacks', 'Snacks');
    api.mockResolvedValue({});
    await addCategory();
    expect(api).toHaveBeenCalledWith('/api/categories', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error from API response', async () => {
    setupDOM('snacks', 'Snacks');
    api.mockResolvedValue({ error: 'Category exists' });
    await addCategory();
    expect(showToast).toHaveBeenCalledWith('Category exists', 'error');
  });

  it('shows error on network failure', async () => {
    setupDOM('snacks', 'Snacks');
    api.mockRejectedValue(new Error('fail'));
    await addCategory();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('defaults emoji to 📦 when empty', async () => {
    setupDOM('snacks', 'Snacks', '');
    api.mockResolvedValue({});
    await addCategory();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.emoji).toBe('📦');
  });
});

// ── deleteCategory ───────────────────────────────────
describe('deleteCategory', () => {
  it('shows confirm modal for zero-count category', async () => {
    document.body.innerHTML = '<div id="cat-list"></div><div id="stats-line"></div>';
    api.mockResolvedValue({});
    await deleteCategory('snacks', 'Snacks', 0);
    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith(expect.stringContaining('/api/categories/snacks'), expect.objectContaining({ method: 'DELETE' }));
  });

  it('cancels delete when confirm modal returns false', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deleteCategory('snacks', 'Snacks', 0);
    expect(api).not.toHaveBeenCalled();
  });

  it('shows error from delete API response', async () => {
    document.body.innerHTML = '<div id="cat-list"></div><div id="stats-line"></div>';
    api.mockResolvedValue({ error: 'Cannot delete' });
    await deleteCategory('snacks', 'Snacks', 0);
    expect(showToast).toHaveBeenCalledWith('Cannot delete', 'error');
  });

  it('shows error when only category (no others)', async () => {
    // category has products, api returns only itself
    api.mockResolvedValue([{ name: 'snacks', label: 'Snacks', emoji: '🍕' }]);
    await deleteCategory('snacks', 'Snacks', 3);
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows move modal when category has products and others exist', async () => {
    api.mockResolvedValue([
      { name: 'snacks', label: 'Snacks', emoji: '🍕' },
      { name: 'dairy', label: 'Dairy', emoji: '🥛' },
    ]);
    deleteCategory('snacks', 'Snacks', 3);
    await new Promise((r) => setTimeout(r, 0));
    const modal = document.querySelector('.cat-move-modal-bg');
    expect(modal).not.toBeNull();
    // Cancel modal
    const cancelBtn = modal.querySelector('.cat-move-cancel');
    cancelBtn.click();
  });

  it('shows network error on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await deleteCategory('snacks', 'Snacks', 0);
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});
