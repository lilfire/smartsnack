// Tests for ean-manager.js error branches: cannot_delete_synced_ean, unsyncEan error
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  esc: (s) => String(s),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
}));

vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn().mockResolvedValue(undefined),
}));

import { deleteEan, unsyncEan, loadEanManager } from '../ean-manager.js';
import { api, showToast } from '../state.js';

const PRODUCT_ID = 42;

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = `<div id="ean-manager-${PRODUCT_ID}"></div>`;
  // loadEanManager calls api for the eans list; default to empty array
  api.mockResolvedValue([]);
});

// ── deleteEan error branches ──────────────────────────

describe('deleteEan - error_cannot_remove_only_ean', () => {
  it('shows error_cannot_remove_only_ean toast for that error code', async () => {
    const error = new Error('cannot remove only ean');
    error.data = { error: 'error_cannot_remove_only_ean' };
    api.mockRejectedValueOnce(error);
    await deleteEan(PRODUCT_ID, 1);
    expect(showToast).toHaveBeenCalledWith('error_cannot_remove_only_ean', 'error');
  });
});

describe('deleteEan - cannot_delete_synced_ean', () => {
  it('shows error_cannot_delete_synced_ean toast for that error code', async () => {
    const error = new Error('cannot delete synced ean');
    error.data = { error: 'cannot_delete_synced_ean' };
    api.mockRejectedValueOnce(error);
    await deleteEan(PRODUCT_ID, 5);
    expect(showToast).toHaveBeenCalledWith('error_cannot_delete_synced_ean', 'error');
  });
});

describe('deleteEan - generic error', () => {
  it('shows e.message for unknown error codes', async () => {
    const error = new Error('Unexpected failure');
    error.data = { error: 'some_other_code' };
    api.mockRejectedValueOnce(error);
    await deleteEan(PRODUCT_ID, 3);
    expect(showToast).toHaveBeenCalledWith('Unexpected failure', 'error');
  });

  it('falls back to toast_network_error when no message', async () => {
    const error = new Error('');
    error.data = null;
    error.message = '';
    api.mockRejectedValueOnce(error);
    await deleteEan(PRODUCT_ID, 4);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });

  it('falls back when error has no data property', async () => {
    const error = new Error('Network error');
    api.mockRejectedValueOnce(error);
    await deleteEan(PRODUCT_ID, 6);
    expect(showToast).toHaveBeenCalledWith('Network error', 'error');
  });
});

// ── unsyncEan error branch (line 167) ────────────────

describe('unsyncEan - success', () => {
  it('calls api and shows success toast', async () => {
    api.mockResolvedValueOnce({}) // unsync
      .mockResolvedValueOnce([]); // loadEanManager
    await unsyncEan(PRODUCT_ID, 10);
    expect(api).toHaveBeenCalledWith(
      `/api/products/${PRODUCT_ID}/eans/10/unsync`,
      expect.objectContaining({ method: 'POST' }),
    );
    expect(showToast).toHaveBeenCalledWith('toast_ean_unlocked', 'success');
  });
});

describe('unsyncEan - error path', () => {
  it('shows error toast with e.message on API failure', async () => {
    const error = new Error('Server down');
    api.mockRejectedValueOnce(error);
    await unsyncEan(PRODUCT_ID, 11);
    expect(showToast).toHaveBeenCalledWith('Server down', 'error');
  });

  it('falls back to toast_network_error when no message', async () => {
    const error = new Error('');
    error.message = '';
    api.mockRejectedValueOnce(error);
    await unsyncEan(PRODUCT_ID, 12);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });
});
