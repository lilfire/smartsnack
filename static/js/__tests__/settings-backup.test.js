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
  initRestoreDragDrop,
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
  let assignedHrefs;
  let origLocationDescriptor;

  beforeEach(() => {
    assignedHrefs = [];
    origLocationDescriptor = Object.getOwnPropertyDescriptor(window, 'location');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        set href(v) { assignedHrefs.push(v); },
        get href() { return assignedHrefs[assignedHrefs.length - 1] || ''; },
      },
    });
  });

  afterEach(() => {
    delete window.SMARTSNACK_API_KEY;
    if (origLocationDescriptor) {
      Object.defineProperty(window, 'location', origLocationDescriptor);
    }
  });

  it('sets window.location.href to /api/backup when no API key configured', () => {
    downloadBackup();
    expect(assignedHrefs[0]).toBe('/api/backup');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('includes api_key query param when SMARTSNACK_API_KEY is set', () => {
    window.SMARTSNACK_API_KEY = 'my-secret';
    downloadBackup();
    expect(assignedHrefs[0]).toBe('/api/backup?api_key=my-secret');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('URL-encodes special characters in api_key', () => {
    window.SMARTSNACK_API_KEY = 'key with spaces&special=chars';
    downloadBackup();
    expect(assignedHrefs[0]).toContain('api_key=key%20with%20spaces%26special%3Dchars');
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

  it('shows real API error message when api throws (not SyntaxError)', async () => {
    api.mockRejectedValue(new Error('Restore failed: database locked'));
    const fileContent = JSON.stringify({ products: [] });
    const file = new File([fileContent], 'backup.json', { type: 'application/json' });
    let capturedValue = '';
    const input = {
      files: [file],
      get value() { return capturedValue; },
      set value(v) { capturedValue = v; },
    };
    handleRestore(input);
    await new Promise((r) => setTimeout(r, 50));
    expect(showToast).toHaveBeenCalledWith('Restore failed: database locked', 'error');
  });

  it('shows toast_invalid_file for SyntaxError (malformed JSON)', async () => {
    const file = new File(['not valid json {{{'], 'backup.json', { type: 'application/json' });
    let capturedValue = '';
    const input = {
      files: [file],
      get value() { return capturedValue; },
      set value(v) { capturedValue = v; },
    };
    handleRestore(input);
    await new Promise((r) => setTimeout(r, 50));
    expect(showToast).toHaveBeenCalledWith('toast_invalid_file', 'error');
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

// ── initRestoreDragDrop ───────────────────────────────
describe('initRestoreDragDrop', () => {
  it('does nothing when restore-drop element is absent', () => {
    document.body.innerHTML = '';
    expect(() => initRestoreDragDrop()).not.toThrow();
  });

  it('adds dragover class on dragover event', () => {
    document.body.innerHTML = '<div id="restore-drop"></div>';
    initRestoreDragDrop();
    const drop = document.getElementById('restore-drop');
    const ev = new Event('dragover');
    ev.preventDefault = vi.fn();
    drop.dispatchEvent(ev);
    expect(drop.classList.contains('dragover')).toBe(true);
    expect(ev.preventDefault).toHaveBeenCalled();
  });

  it('removes dragover class on dragleave', () => {
    document.body.innerHTML = '<div id="restore-drop"></div>';
    initRestoreDragDrop();
    const drop = document.getElementById('restore-drop');
    drop.classList.add('dragover');
    drop.dispatchEvent(new Event('dragleave'));
    expect(drop.classList.contains('dragover')).toBe(false);
  });

  it('calls handleRestore with the dropped file on drop', async () => {
    document.body.innerHTML = '<div id="restore-drop"></div>';
    initRestoreDragDrop();
    const drop = document.getElementById('restore-drop');
    const mockFile = new Blob(['{}'], { type: 'application/json' });
    const dropEvent = new Event('drop');
    dropEvent.preventDefault = vi.fn();
    dropEvent.dataTransfer = { files: [mockFile] };
    drop.classList.add('dragover');
    drop.dispatchEvent(dropEvent);
    expect(drop.classList.contains('dragover')).toBe(false);
    expect(dropEvent.preventDefault).toHaveBeenCalled();
    // handleRestore is triggered with the file; api would be called
    await new Promise((r) => setTimeout(r, 50));
    // Confirm dialog shown (from handleRestore)
    expect(showConfirmModal).toHaveBeenCalled();
  });

  it('does not call handleRestore when no files dropped', () => {
    document.body.innerHTML = '<div id="restore-drop"></div>';
    initRestoreDragDrop();
    const drop = document.getElementById('restore-drop');
    const dropEvent = new Event('drop');
    dropEvent.preventDefault = vi.fn();
    dropEvent.dataTransfer = { files: [] };
    drop.dispatchEvent(dropEvent);
    // showConfirmModal not called since no file
    expect(showConfirmModal).not.toHaveBeenCalled();
  });
});
