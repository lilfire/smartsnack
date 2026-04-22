import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

import { saveOffCredentials, checkRefreshStatus, refreshAllFromOff, loadOffLanguagePriority } from '../settings-off.js';
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

// ── loadOffLanguagePriority ──────────────────────────
describe('loadOffLanguagePriority', () => {
  function setupLangDOM() {
    document.body.innerHTML = `
      <div id="off-lang-priority-list"></div>
      <select id="off-lang-add-select"></select>
      <button id="off-lang-add-btn"></button>`;
  }

  it('does nothing when list element is absent', async () => {
    document.body.innerHTML = '';
    await loadOffLanguagePriority();
    expect(api).not.toHaveBeenCalled();
  });

  it('loads language priority and renders items', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }, { code: 'se', name: 'Swedish' }] });

    await loadOffLanguagePriority();

    const list = document.getElementById('off-lang-priority-list');
    expect(list.querySelectorAll('.off-lang-item').length).toBe(2);
  });

  it('shows error toast on API failure', async () => {
    setupLangDOM();
    api.mockRejectedValue(new Error('fail'));
    await loadOffLanguagePriority();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('binds the add button to push a new language', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });

    await loadOffLanguagePriority();

    const addSelect = document.getElementById('off-lang-add-select');
    const addBtn = document.getElementById('off-lang-add-btn');

    // Simulate selecting 'en' and clicking add
    const opt = document.createElement('option');
    opt.value = 'en';
    addSelect.appendChild(opt);
    addSelect.value = 'en';

    // Mock the save API call
    api.mockResolvedValueOnce({});

    addBtn.click();
    await new Promise((r) => setTimeout(r, 0));

    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    expect(items.length).toBe(2);
  });

  it('does not bind add button twice on re-call', async () => {
    setupLangDOM();
    api.mockResolvedValueOnce({ languages: ['no'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }] });
    await loadOffLanguagePriority();

    // Second call - button already bound
    api.mockResolvedValueOnce({ languages: ['no'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }] });
    await loadOffLanguagePriority();

    const addBtn = document.getElementById('off-lang-add-btn');
    expect(addBtn.dataset.bound).toBe('1');
  });
});

// ── _renderOffLangPriority interactions ───────────────
describe('_renderOffLangPriority interactions (via loadOffLanguagePriority)', () => {
  async function setupWithLangs(priority = ['no', 'en', 'se']) {
    document.body.innerHTML = `
      <div id="off-lang-priority-list"></div>
      <select id="off-lang-add-select"></select>
      <button id="off-lang-add-btn"></button>`;
    api.mockResolvedValueOnce({ languages: priority });
    api.mockResolvedValueOnce({ languages: [
      { code: 'no', name: 'Norwegian' },
      { code: 'en', name: 'English' },
      { code: 'se', name: 'Swedish' },
      { code: 'fi', name: 'Finnish' },
    ]});
    await loadOffLanguagePriority();
  }

  it('moves item up when up button clicked', async () => {
    await setupWithLangs(['no', 'en', 'se']);
    api.mockResolvedValue({});

    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    // Click "up" on second item (en)
    const upBtn = items[1].querySelector('button[aria-label="off_lang_move_up"]');
    upBtn.click();
    await new Promise((r) => setTimeout(r, 0));

    // After moving up, 'en' should be first
    const updatedItems = list.querySelectorAll('.off-lang-item');
    expect(updatedItems[0].querySelector('.off-lang-code').textContent).toBe('en');
  });

  it('moves item down when down button clicked', async () => {
    await setupWithLangs(['no', 'en', 'se']);
    api.mockResolvedValue({});

    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    // Click "down" on first item (no)
    const downBtn = items[0].querySelector('button[aria-label="off_lang_move_down"]');
    downBtn.click();
    await new Promise((r) => setTimeout(r, 0));

    // After moving down, 'en' should be first
    const updatedItems = list.querySelectorAll('.off-lang-item');
    expect(updatedItems[0].querySelector('.off-lang-code').textContent).toBe('en');
  });

  it('removes item when remove button clicked', async () => {
    await setupWithLangs(['no', 'en', 'se']);
    api.mockResolvedValue({});

    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    // Click remove on second item (en)
    const removeBtn = items[1].querySelector('button.btn-red');
    removeBtn.click();
    await new Promise((r) => setTimeout(r, 0));

    const updatedItems = list.querySelectorAll('.off-lang-item');
    expect(updatedItems.length).toBe(2);
  });

  it('disables up button on first item', async () => {
    await setupWithLangs(['no', 'en']);
    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    const upBtn = items[0].querySelector('button[aria-label="off_lang_move_up"]');
    expect(upBtn.disabled).toBe(true);
  });

  it('disables down button on last item', async () => {
    await setupWithLangs(['no', 'en']);
    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    const downBtn = items[1].querySelector('button[aria-label="off_lang_move_down"]');
    expect(downBtn.disabled).toBe(true);
  });

  it('disables remove button when only one item remains', async () => {
    await setupWithLangs(['no']);
    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    const removeBtn = items[0].querySelector('button.btn-red');
    expect(removeBtn.disabled).toBe(true);
  });

  it('shows error toast when _saveOffLangPriority fails', async () => {
    await setupWithLangs(['no', 'en']);
    api.mockRejectedValue(new Error('save fail'));

    const list = document.getElementById('off-lang-priority-list');
    const items = list.querySelectorAll('.off-lang-item');
    const downBtn = items[0].querySelector('button[aria-label="off_lang_move_down"]');
    downBtn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('disables add button when all languages are already selected', async () => {
    // Only 2 languages available, both already selected
    document.body.innerHTML = `
      <div id="off-lang-priority-list"></div>
      <select id="off-lang-add-select"></select>
      <button id="off-lang-add-btn"></button>`;
    api.mockResolvedValueOnce({ languages: ['no', 'en'] });
    api.mockResolvedValueOnce({ languages: [{ code: 'no', name: 'Norwegian' }, { code: 'en', name: 'English' }] });
    await loadOffLanguagePriority();

    const addBtn = document.getElementById('off-lang-add-btn');
    expect(addBtn.disabled).toBe(true);
  });
});
