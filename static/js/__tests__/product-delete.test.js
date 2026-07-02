import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedResults: [],
    imageCache: {},
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  rerender: vi.fn(),
}));

vi.mock('../products.js', () => ({
  loadData: vi.fn().mockResolvedValue(),
}));

import { deleteProduct } from '../product-delete.js';
import { state, api, showConfirmModal, showToast } from '../state.js';

function findUndo(productToastIndex = 0) {
  const calls = showToast.mock.calls.filter((c) => c[1] === 'success' && c[2] && c[2].onUndo);
  return calls[productToastIndex] ? calls[productToastIndex][2].onUndo : null;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  showConfirmModal.mockResolvedValue(true);
  api.mockResolvedValue({});
  state.cachedResults = [
    { id: 1, name: 'Milk' },
    { id: 2, name: 'Bread' },
  ];
  state.imageCache = {};
  state.expandedId = null;
  state.editingId = null;
});

afterEach(async () => {
  // Drain any pending 5s undo timers so state does not leak between tests
  await vi.runAllTimersAsync();
  vi.clearAllTimers();
  vi.useRealTimers();
});

// H7 regression (LSO-1684): a second delete inside the 5s undo window used to
// clearTimeout the first product's pending DELETE without ever firing it, so
// the first product silently reappeared after reload.
describe('deleteProduct rapid double delete (H7)', () => {
  it('does not fire DELETE before the 5s undo window elapses', async () => {
    await deleteProduct(1, 'Milk');
    expect(api).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(5000);
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
  });

  it('flushes the first pending DELETE immediately when a second delete starts', async () => {
    await deleteProduct(1, 'Milk');
    expect(api).not.toHaveBeenCalled();

    await deleteProduct(2, 'Bread');
    // First product's DELETE must have fired during the second call, before
    // any timer advanced.
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
    expect(api).toHaveBeenCalledTimes(1);

    // Second product still has its own undo window.
    await vi.advanceTimersByTimeAsync(5000);
    expect(api).toHaveBeenCalledWith('/api/products/2', { method: 'DELETE' });
    expect(api).toHaveBeenCalledTimes(2);
  });

  it('keeps the second product undoable after flushing the first', async () => {
    await deleteProduct(1, 'Milk');
    await deleteProduct(2, 'Bread');

    const undoBread = findUndo(1);
    expect(undoBread).toBeTypeOf('function');
    undoBread();

    await vi.advanceTimersByTimeAsync(6000);
    // Only the flushed first product was deleted server-side.
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
    expect(state.cachedResults.find((p) => p.id === 2)).toBeTruthy();
  });

  it('undo prevents the DELETE from ever firing', async () => {
    await deleteProduct(1, 'Milk');
    const undoMilk = findUndo(0);
    expect(undoMilk).toBeTypeOf('function');
    undoMilk();

    await vi.advanceTimersByTimeAsync(6000);
    expect(api).not.toHaveBeenCalled();
    expect(state.cachedResults.find((p) => p.id === 1)).toBeTruthy();
    expect(showToast).toHaveBeenCalledWith('toast_delete_undone', 'info');
  });

  it('shows a network error toast when the flushed DELETE fails and still schedules the second', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.mockRejectedValueOnce(new Error('network fail'));

    await deleteProduct(1, 'Milk');
    await deleteProduct(2, 'Bread');

    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');

    await vi.advanceTimersByTimeAsync(5000);
    expect(api).toHaveBeenCalledWith('/api/products/2', { method: 'DELETE' });
    console.error.mockRestore();
  });

  it('restores the cached image when undo is clicked', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    await deleteProduct(1, 'Milk');
    expect(state.imageCache[1]).toBeUndefined();

    const undoMilk = findUndo(0);
    undoMilk();
    expect(state.imageCache[1]).toBe('data:image/png;base64,abc');
  });

  it('restores product and image when the deferred DELETE fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    state.imageCache[1] = 'data:image/png;base64,abc';
    api.mockRejectedValueOnce(new Error('network fail'));

    await deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(5000);

    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    expect(state.cachedResults.find((p) => p.id === 1)).toBeTruthy();
    expect(state.imageCache[1]).toBe('data:image/png;base64,abc');
    console.error.mockRestore();
  });

  it('falls back to an empty name when the product is not cached', async () => {
    await deleteProduct(99);
    expect(showConfirmModal).toHaveBeenCalledWith(
      expect.any(String), '', expect.any(String), expect.any(String), expect.any(String), true
    );
  });

  it('does nothing when the confirmation modal is cancelled', async () => {
    showConfirmModal.mockResolvedValueOnce(false);
    await deleteProduct(1, 'Milk');
    await vi.advanceTimersByTimeAsync(6000);
    expect(api).not.toHaveBeenCalled();
    expect(state.cachedResults.find((p) => p.id === 1)).toBeTruthy();
  });

  it('handles a missing cachedResults list without crashing', async () => {
    state.cachedResults = null;
    await deleteProduct(1, 'Milk');
    expect(Array.isArray(state.cachedResults)).toBe(true);
    await vi.advanceTimersByTimeAsync(5000);
    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
  });

  it('three rapid deletes flush the first two and keep the third pending', async () => {
    state.cachedResults.push({ id: 3, name: 'Cheese' });
    await deleteProduct(1, 'Milk');
    await deleteProduct(2, 'Bread');
    await deleteProduct(3, 'Cheese');

    expect(api).toHaveBeenCalledWith('/api/products/1', { method: 'DELETE' });
    expect(api).toHaveBeenCalledWith('/api/products/2', { method: 'DELETE' });
    expect(api).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(5000);
    expect(api).toHaveBeenCalledWith('/api/products/3', { method: 'DELETE' });
    expect(api).toHaveBeenCalledTimes(3);
  });
});
