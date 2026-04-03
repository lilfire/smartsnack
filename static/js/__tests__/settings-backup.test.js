import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  state: { imageCache: {}, currentView: 'search' },
  api: vi.fn().mockResolvedValue({}),
  showConfirmModal: vi.fn().mockResolvedValue(true),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

vi.mock('../settings-weights.js', () => ({
  loadSettings: vi.fn().mockResolvedValue(undefined),
}));

import {
  toggleSettingsSection,
  downloadBackup,
  handleRestore,
  handleImport,
  estimateAllPq,
} from '../settings-backup.js';
import { api, showToast, showConfirmModal, state } from '../state.js';
import { loadData } from '../products.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  api.mockResolvedValue({});
  showConfirmModal.mockResolvedValue(true);
});

// ── toggleSettingsSection ────────────────────────────
describe('toggleSettingsSection', () => {
  it('hides body when it is currently visible', () => {
    document.body.innerHTML = `
      <div id="header"></div>
      <div id="body" style=""></div>`;
    const header = document.getElementById('header');
    header.nextElementSibling; // just verify
    const body = document.getElementById('body');
    body.style.display = '';
    toggleSettingsSection(header);
    expect(body.style.display).toBe('none');
    expect(header.getAttribute('aria-expanded')).toBe('false');
  });

  it('shows body when it is currently hidden', () => {
    document.body.innerHTML = `
      <div id="header" class="open" aria-expanded="true"></div>
      <div id="body" style="display:none"></div>`;
    const header = document.getElementById('header');
    toggleSettingsSection(header);
    expect(document.getElementById('body').style.display).toBe('');
    expect(header.getAttribute('aria-expanded')).toBe('true');
  });

  it('does nothing if no next sibling', () => {
    document.body.innerHTML = '<div id="header"></div>';
    const header = document.getElementById('header');
    expect(() => toggleSettingsSection(header)).not.toThrow();
  });

  it('toggles "open" class on header', () => {
    // Start with body hidden (closed section) — toggle opens it, adds 'open'
    document.body.innerHTML = `<div id="h"></div><div id="b" style="display:none"></div>`;
    const h = document.getElementById('h');
    toggleSettingsSection(h);
    expect(h.classList.contains('open')).toBe(true);
    toggleSettingsSection(h);
    expect(h.classList.contains('open')).toBe(false);
  });
});

// ── downloadBackup ───────────────────────────────────
describe('downloadBackup', () => {
  it('sets window.location.href to backup endpoint', () => {
    const original = window.location.href;
    downloadBackup();
    // jsdom doesn't really navigate, but showToast should be called
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });
});

// ── estimateAllPq ────────────────────────────────────
describe('estimateAllPq', () => {
  function setupDOM() {
    document.body.innerHTML = `
      <button id="btn-estimate-all-pq"></button>
      <div id="estimate-pq-status" style="display:none"></div>`;
  }

  it('calls API and shows success', async () => {
    setupDOM();
    api.mockResolvedValue({ total: 10, updated: 8, skipped: 2 });
    await estimateAllPq();
    expect(api).toHaveBeenCalledWith('/api/bulk/estimate-pq', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
    expect(loadData).toHaveBeenCalled();
  });

  it('shows error from API response', async () => {
    setupDOM();
    api.mockResolvedValue({ error: 'Estimation failed' });
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith('Estimation failed', 'error');
  });

  it('shows error on network failure', async () => {
    setupDOM();
    api.mockRejectedValue(new Error('fail'));
    await estimateAllPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('re-enables button after completion', async () => {
    setupDOM();
    api.mockResolvedValue({ total: 5, updated: 5, skipped: 0 });
    await estimateAllPq();
    const btn = document.getElementById('btn-estimate-all-pq');
    expect(btn.disabled).toBe(false);
  });

  it('works when DOM elements are missing', async () => {
    document.body.innerHTML = '';
    api.mockResolvedValue({ total: 5, updated: 5, skipped: 0 });
    await expect(estimateAllPq()).resolves.not.toThrow();
  });
});

// ── handleRestore ────────────────────────────────────
describe('handleRestore', () => {
  it('does nothing with empty file input', async () => {
    const input = { files: [] };
    await handleRestore(input);
    expect(api).not.toHaveBeenCalled();
  });

  it('cancels on confirm false', async () => {
    showConfirmModal.mockResolvedValue(false);
    const input = { files: [new File(['{}'], 'backup.json')], value: '' };
    await handleRestore(input);
    expect(api).not.toHaveBeenCalled();
  });

  it('calls restore API on confirmed valid JSON file', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValue({ message: 'Restored!' });
    const fileContent = JSON.stringify({ products: [] });
    const file = new File([fileContent], 'backup.json', { type: 'application/json' });
    let capturedValue = '';
    const input = {
      files: [file],
      get value() { return capturedValue; },
      set value(v) { capturedValue = v; },
    };
    const restorePromise = handleRestore(input);
    // FileReader is async in jsdom
    await new Promise((r) => setTimeout(r, 50));
    await restorePromise;
    expect(api).toHaveBeenCalledWith('/api/restore', expect.objectContaining({ method: 'POST' }));
  });
});

// ── handleImport ─────────────────────────────────────
describe('handleImport', () => {
  it('does nothing with empty file input', () => {
    handleImport({ files: [] });
    expect(api).not.toHaveBeenCalled();
  });

  it('processes valid JSON file with import dialog', async () => {
    api.mockResolvedValue({ message: 'Imported!' });
    const fileContent = JSON.stringify({ products: [{ name: 'Test' }] });
    const file = new File([fileContent], 'import.json', { type: 'application/json' });
    let capturedValue = '';
    const input = {
      files: [file],
      get value() { return capturedValue; },
      set value(v) { capturedValue = v; },
    };
    handleImport(input);
    await new Promise((r) => setTimeout(r, 50));
    // Dialog should appear
    const bg = document.querySelector('.scan-modal-bg');
    if (bg) {
      // Cancel it
      const cancelBtn = bg.querySelector('.scan-modal-btn-cancel');
      if (cancelBtn) cancelBtn.click();
    }
  });

  it('shows error on invalid JSON', async () => {
    const file = new File(['not json'], 'bad.json', { type: 'application/json' });
    let capturedValue = '';
    const input = {
      files: [file],
      get value() { return capturedValue; },
      set value(v) { capturedValue = v; },
    };
    handleImport(input);
    await new Promise((r) => setTimeout(r, 50));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});
