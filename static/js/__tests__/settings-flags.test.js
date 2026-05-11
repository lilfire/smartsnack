import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue([]),
  esc: (s) => String(s),
  showConfirmModal: vi.fn().mockResolvedValue(true),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

// Mock render.js dynamic import used in _refreshFlagConfig
vi.mock('../render.js', () => ({
  loadFlagConfig: vi.fn().mockResolvedValue(undefined),
  getFlagConfig: vi.fn(() => ({})),
}));

import { loadFlags, updateFlagLabel, addFlag, deleteFlag } from '../settings-flags.js';
import { api, showToast, showConfirmModal } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  api.mockResolvedValue([]);
  showConfirmModal.mockResolvedValue(true);
});

// ── loadFlags ────────────────────────────────────────
describe('loadFlags', () => {
  it('shows empty message when no flags', async () => {
    api.mockResolvedValue([]);
    document.body.innerHTML = '<div id="flag-list"></div>';
    await loadFlags();
    expect(document.getElementById('flag-list').innerHTML).toContain('No flags');
  });

  it('renders user flags with editable input', async () => {
    const flags = [{ name: 'eco', label: 'Eco', type: 'user', count: 2 }];
    api.mockResolvedValue(flags);
    document.body.innerHTML = '<div id="flag-list"></div>';
    await loadFlags();
    const list = document.getElementById('flag-list');
    expect(list.querySelector('input[data-flag-name="eco"]')).not.toBeNull();
  });

  it('renders system flags as read-only', async () => {
    const flags = [{ name: 'organic', label: 'Organic', type: 'system', count: 5 }];
    api.mockResolvedValue(flags);
    document.body.innerHTML = '<div id="flag-list"></div>';
    await loadFlags();
    const list = document.getElementById('flag-list');
    expect(list.querySelector('.flag-item-system')).not.toBeNull();
    expect(list.querySelector('input[data-flag-name="organic"]')).toBeNull();
  });

  it('shows error toast on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    document.body.innerHTML = '<div id="flag-list"></div>';
    await loadFlags();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── updateFlagLabel ──────────────────────────────────
describe('updateFlagLabel', () => {
  it('shows error for empty label', async () => {
    document.body.innerHTML = '<div id="flag-list"></div>';
    api.mockResolvedValue([]);
    await updateFlagLabel('eco', '  ');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
    expect(api).not.toHaveBeenCalledWith(expect.stringContaining('/api/flags/'), expect.anything());
  });

  it('calls api with new label', async () => {
    await updateFlagLabel('eco', 'Eco Friendly');
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining('/api/flags/eco'),
      expect.objectContaining({ method: 'PUT' }),
    );
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await updateFlagLabel('eco', 'Eco');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── addFlag ──────────────────────────────────────────
describe('addFlag', () => {
  function setupDOM(name = 'eco', label = 'Eco') {
    document.body.innerHTML = `
      <input id="flag-add-name" value="${name}">
      <input id="flag-add-label" value="${label}">
      <div id="flag-list"></div>`;
  }

  it('shows error when name or label is empty', async () => {
    setupDOM('', 'Eco');
    await addFlag();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls api to create flag', async () => {
    setupDOM('eco', 'Eco');
    api.mockResolvedValue({});
    await addFlag();
    expect(api).toHaveBeenCalledWith('/api/flags', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows API error message', async () => {
    setupDOM('eco', 'Eco');
    api.mockResolvedValue({ error: 'Flag exists' });
    await addFlag();
    expect(showToast).toHaveBeenCalledWith('Flag exists', 'error');
  });

  it('clears inputs on success', async () => {
    setupDOM('eco', 'Eco');
    api.mockResolvedValue({});
    await addFlag();
    expect(document.getElementById('flag-add-name').value).toBe('');
    expect(document.getElementById('flag-add-label').value).toBe('');
  });

  it('shows network error on exception', async () => {
    setupDOM('eco', 'Eco');
    api.mockRejectedValue(new Error('fail'));
    await addFlag();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── deleteFlag ───────────────────────────────────────
describe('deleteFlag', () => {
  it('shows confirm modal', async () => {
    api.mockResolvedValue({});
    await deleteFlag('eco', 'Eco', 0);
    expect(showConfirmModal).toHaveBeenCalled();
  });

  it('cancels when confirm modal returns false', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deleteFlag('eco', 'Eco', 2);
    expect(api).not.toHaveBeenCalled();
  });

  it('calls api to delete flag', async () => {
    api.mockResolvedValue({});
    document.body.innerHTML = '<div id="flag-list"></div>';
    await deleteFlag('eco', 'Eco', 0);
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining('/api/flags/eco'),
      expect.objectContaining({ method: 'DELETE' }),
    );
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await deleteFlag('eco', 'Eco', 0);
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('includes count info in confirm message for non-empty flag', async () => {
    api.mockResolvedValue({});
    document.body.innerHTML = '<div id="flag-list"></div>';
    await deleteFlag('eco', 'Eco', 5);
    expect(showConfirmModal).toHaveBeenCalledWith(
      expect.any(String),
      'Eco',
      expect.stringContaining('confirm_delete_flag_body'),
      expect.any(String),
      expect.any(String),
    );
  });
});
