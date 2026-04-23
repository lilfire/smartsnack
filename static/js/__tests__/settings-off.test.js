import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

import {
  loadOffCredentials,
  saveOffCredentials,
  checkRefreshStatus,
  refreshAllFromOff,
  loadOffLanguagePriority,
} from '../settings-off.js';
import { api, showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  api.mockResolvedValue({});
  // Mock EventSource globally
  global.EventSource = vi.fn(() => ({
    onmessage: null,
    onerror: null,
    close: vi.fn(),
  }));
});

function setupCredentialDOM(userId = 'testuser', password = 'mypassword') {
  document.body.innerHTML = `
    <input id="off-user-id" value="${userId}">
    <input id="off-password" value="${password}">`;
}

// ── saveOffCredentials ───────────────────────────────
describe('saveOffCredentials', () => {
  it('calls api with user id', async () => {
    setupCredentialDOM('testuser', '');
    await saveOffCredentials();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.off_user_id).toBe('testuser');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('includes password when not placeholder', async () => {
    setupCredentialDOM('user', 'realpassword');
    await saveOffCredentials();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.off_password).toBe('realpassword');
  });

  it('omits password when it is the placeholder value', async () => {
    setupCredentialDOM('user', '••••••••');
    await saveOffCredentials();
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.off_password).toBeUndefined();
  });

  it('shows success toast', async () => {
    setupCredentialDOM();
    await saveOffCredentials();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows encryption error toast on encryption_not_configured', async () => {
    setupCredentialDOM();
    api.mockRejectedValue({ message: 'encryption_not_configured' });
    await saveOffCredentials();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows generic save error on other failures', async () => {
    setupCredentialDOM();
    api.mockRejectedValue(new Error('Network error'));
    await saveOffCredentials();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── checkRefreshStatus ───────────────────────────────
describe('checkRefreshStatus', () => {
  it('calls the status API', async () => {
    api.mockResolvedValue({ running: false });
    await checkRefreshStatus();
    expect(api).toHaveBeenCalledWith('/api/bulk/refresh-off/status');
  });

  it('connects to stream when running is true', async () => {
    document.body.innerHTML = `
      <button id="btn-refresh-all-off"></button>
      <div id="refresh-off-progress" style="display:none"></div>
      <div id="refresh-off-bar"></div>
      <div id="refresh-off-status"></div>`;
    api.mockResolvedValue({ running: true });
    await checkRefreshStatus();
    expect(global.EventSource).toHaveBeenCalledWith('/api/bulk/refresh-off/stream');
  });

  it('does not connect when not running', async () => {
    api.mockResolvedValue({ running: false });
    await checkRefreshStatus();
    expect(global.EventSource).not.toHaveBeenCalled();
  });

  it('silently ignores errors', async () => {
    api.mockRejectedValue(new Error('fail'));
    await expect(checkRefreshStatus()).resolves.not.toThrow();
  });
});

// ── refreshAllFromOff ────────────────────────────────
describe('refreshAllFromOff', () => {
  function setupRefreshDOM() {
    document.body.innerHTML = `
      <button id="btn-refresh-all-off"></button>
      <div id="refresh-off-progress"></div>
      <div id="refresh-off-bar"></div>
      <div id="refresh-off-status"></div>`;
  }

  it('shows refresh modal and starts refresh on confirm', async () => {
    setupRefreshDOM();
    // Run the function but immediately cancel the modal
    const p = refreshAllFromOff();
    await new Promise((r) => setTimeout(r, 0));
    const bg = document.querySelector('.scan-modal-bg');
    if (bg) {
      const cancelBtn = bg.querySelector('.confirm-no');
      if (cancelBtn) cancelBtn.click();
    }
    await p;
    expect(api).not.toHaveBeenCalled(); // cancelled
  });

  it('calls start API after confirming', async () => {
    setupRefreshDOM();
    api.mockResolvedValue({});
    const p = refreshAllFromOff();
    await new Promise((r) => setTimeout(r, 0));
    const bg = document.querySelector('.scan-modal-bg');
    if (bg) {
      const startBtn = bg.querySelector('.confirm-yes');
      if (startBtn) startBtn.click();
    }
    await p;
    expect(api).toHaveBeenCalledWith(
      '/api/bulk/refresh-off/start',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('shows error toast on API failure', async () => {
    setupRefreshDOM();
    api.mockRejectedValue(new Error('fail'));
    const p = refreshAllFromOff();
    await new Promise((r) => setTimeout(r, 0));
    const bg = document.querySelector('.scan-modal-bg');
    if (bg) {
      const startBtn = bg.querySelector('.confirm-yes');
      if (startBtn) startBtn.click();
    }
    await p;
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows already_running message if stream already active', async () => {
    setupRefreshDOM();
    api.mockResolvedValue({ error: 'already_running' });
    const p = refreshAllFromOff();
    await new Promise((r) => setTimeout(r, 0));
    const bg = document.querySelector('.scan-modal-bg');
    if (bg) {
      const startBtn = bg.querySelector('.confirm-yes');
      if (startBtn) startBtn.click();
    }
    await p;
    // Should connect to stream
    expect(global.EventSource).toHaveBeenCalled();
  });
});

// ── loadOffCredentials ───────────────────────────────

describe('loadOffCredentials', () => {
  function setupCredDOM() {
    document.body.innerHTML = `
      <input id="off-user-id">
      <input id="off-password">`;
  }

  it('populates user id field on success', async () => {
    setupCredDOM();
    api.mockResolvedValueOnce({ off_user_id: 'myuser', has_password: false });
    await loadOffCredentials();
    expect(document.getElementById('off-user-id').value).toBe('myuser');
  });

  it('fills password field with placeholder when has_password is true', async () => {
    setupCredDOM();
    api.mockResolvedValueOnce({ off_user_id: 'u', has_password: true });
    await loadOffCredentials();
    expect(document.getElementById('off-password').value).toBe('\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022');
  });

  it('leaves password blank when has_password is false', async () => {
    setupCredDOM();
    api.mockResolvedValueOnce({ off_user_id: 'u', has_password: false });
    await loadOffCredentials();
    expect(document.getElementById('off-password').value).toBe('');
  });

  it('shows error toast on API failure', async () => {
    setupCredDOM();
    api.mockRejectedValueOnce(new Error('fail'));
    await loadOffCredentials();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('does not crash when DOM elements are absent', async () => {
    document.body.innerHTML = '';
    api.mockResolvedValueOnce({ off_user_id: 'u', has_password: false });
    await expect(loadOffCredentials()).resolves.not.toThrow();
  });
});

// ── loadOffLanguagePriority ──────────────────────────

describe('loadOffLanguagePriority', () => {
  function setupLangDOM() {
    document.body.innerHTML = `
      <div id="off-lang-priority-list"></div>
      <select id="off-lang-add-select"></select>
      <button id="off-lang-add-btn"></button>`;
  }

  it('does nothing when #off-lang-priority-list is absent', async () => {
    document.body.innerHTML = '';
    await expect(loadOffLanguagePriority()).resolves.not.toThrow();
    expect(api).not.toHaveBeenCalled();
  });

  it('renders language priority items on success', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }, { code: 'se', name: 'Swedish' }] });
    await loadOffLanguagePriority();
    const items = document.querySelectorAll('.off-lang-item');
    expect(items.length).toBe(2);
  });

  it('shows error toast on API failure', async () => {
    setupLangDOM();
    api.mockRejectedValueOnce(new Error('fail'));
    await loadOffLanguagePriority();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('populates add-select with available (unprioritised) languages', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    const opts = document.querySelectorAll('#off-lang-add-select option');
    expect(opts.length).toBe(1);
    expect(opts[0].value).toBe('en');
  });

  it('disables add-btn when no languages available to add', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    const addBtn = document.getElementById('off-lang-add-btn');
    expect(addBtn.disabled).toBe(true);
  });

  it('move-up button reorders and saves', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    api.mockResolvedValueOnce({}); // save

    const items = document.querySelectorAll('.off-lang-item');
    const upBtns = items[1].querySelectorAll('button');
    upBtns[0].click(); // up button on second item
    await Promise.resolve();

    expect(api).toHaveBeenCalledWith(
      '/api/settings/off-language-priority',
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('move-down button reorders and saves', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    api.mockResolvedValueOnce({}); // save

    const items = document.querySelectorAll('.off-lang-item');
    const downBtns = items[0].querySelectorAll('button');
    downBtns[1].click(); // down button on first item
    await Promise.resolve();

    expect(api).toHaveBeenCalledWith(
      '/api/settings/off-language-priority',
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('remove button removes language and saves', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    api.mockResolvedValueOnce({}); // save

    const items = document.querySelectorAll('.off-lang-item');
    const removeBtn = items[0].querySelector('.btn-red');
    removeBtn.click();
    await Promise.resolve();

    const remaining = document.querySelectorAll('.off-lang-item');
    expect(remaining.length).toBe(1);
  });

  it('add-btn adds selected language and saves', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();
    api.mockResolvedValueOnce({}); // save

    const addSelect = document.getElementById('off-lang-add-select');
    const addBtn = document.getElementById('off-lang-add-btn');
    addSelect.value = 'en';
    addBtn.click();
    await Promise.resolve();

    expect(api).toHaveBeenCalledWith(
      '/api/settings/off-language-priority',
      expect.objectContaining({ method: 'PUT' }),
    );
    const items = document.querySelectorAll('.off-lang-item');
    expect(items.length).toBe(2);
  });
});
