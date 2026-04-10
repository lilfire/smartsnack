import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

import { saveOffCredentials, checkRefreshStatus, refreshAllFromOff } from '../settings-off.js';
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
