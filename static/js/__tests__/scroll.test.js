import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { _state } = vi.hoisted(() => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    pagination: { offset: 0, total: null, inFlight: false, pageSize: 50 },
    cachedResults: [],
  };
  return { _state };
});

vi.mock('../state.js', () => ({
  state: _state,
  fetchProducts: vi.fn(),
}));

vi.mock('../render.js', () => ({
  appendResults: vi.fn(),
}));

import { initInfiniteScroll, teardownInfiniteScroll, showScrollLoader, hideScrollLoader, loadNextPage } from '../scroll.js';
import { state, fetchProducts } from '../state.js';
import { appendResults } from '../render.js';

beforeEach(() => {
  vi.clearAllMocks();
  state.pagination = { offset: 0, total: null, inFlight: false, pageSize: 50 };
  state.cachedResults = [];
  state.currentFilter = [];
  // Set up minimal DOM
  document.body.innerHTML = `
    <div id="scroll-loader" style="display:none"></div>
    <div id="results-container"></div>
    <input id="search-input" value="" />
  `;
});

afterEach(() => {
  teardownInfiniteScroll();
  document.body.innerHTML = '';
});

describe('showScrollLoader / hideScrollLoader', () => {
  it('shows the scroll loader element', () => {
    showScrollLoader();
    expect(document.getElementById('scroll-loader').style.display).toBe('');
  });

  it('hides the scroll loader element', () => {
    showScrollLoader();
    hideScrollLoader();
    expect(document.getElementById('scroll-loader').style.display).toBe('none');
  });

  it('does not throw if scroll-loader element is absent', () => {
    document.getElementById('scroll-loader').remove();
    expect(() => showScrollLoader()).not.toThrow();
    expect(() => hideScrollLoader()).not.toThrow();
  });
});

describe('loadNextPage', () => {
  it('does nothing if inFlight is true', async () => {
    state.pagination.inFlight = true;
    await loadNextPage();
    expect(fetchProducts).not.toHaveBeenCalled();
  });

  it('does nothing if all results loaded', async () => {
    state.pagination.offset = 50;
    state.pagination.total = 50;
    state.pagination.pageSize = 50;
    await loadNextPage();
    expect(fetchProducts).not.toHaveBeenCalled();
  });

  it('fetches next page with correct offset', async () => {
    state.pagination.offset = 50;
    state.pagination.total = 150;
    fetchProducts.mockResolvedValue({ products: [{ id: 3, name: 'C' }], total: 150 });
    await loadNextPage();
    expect(fetchProducts).toHaveBeenCalledWith(
      expect.any(String),
      state.currentFilter,
      { limit: 50, offset: 100 }
    );
  });

  it('appends products to cachedResults and calls appendResults', async () => {
    state.pagination.offset = 0;
    state.pagination.total = 100;
    const newProducts = [{ id: 3, name: 'C' }];
    fetchProducts.mockResolvedValue({ products: newProducts, total: 100 });
    await loadNextPage();
    expect(state.cachedResults).toEqual(newProducts);
    expect(appendResults).toHaveBeenCalledWith(newProducts);
  });

  it('handles plain array response (backward compat)', async () => {
    state.pagination.offset = 0;
    state.pagination.total = 100;
    const newProducts = [{ id: 4, name: 'D' }];
    fetchProducts.mockResolvedValue(newProducts);
    await loadNextPage();
    expect(state.cachedResults).toEqual(newProducts);
    expect(appendResults).toHaveBeenCalledWith(newProducts);
  });

  it('updates pagination offset after successful fetch', async () => {
    state.pagination.offset = 50;
    state.pagination.total = 200;
    fetchProducts.mockResolvedValue({ products: [{ id: 5 }], total: 200 });
    await loadNextPage();
    expect(state.pagination.offset).toBe(100);
  });

  it('updates pagination total from response', async () => {
    state.pagination.offset = 0;
    state.pagination.total = null;
    fetchProducts.mockResolvedValue({ products: [{ id: 6 }], total: 75 });
    await loadNextPage();
    expect(state.pagination.total).toBe(75);
  });

  it('does not throw on fetch error', async () => {
    state.pagination.offset = 0;
    state.pagination.total = 100;
    fetchProducts.mockRejectedValue(new Error('network'));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(loadNextPage()).resolves.not.toThrow();
    console.error.mockRestore();
  });

  it('resets inFlight to false after fetch', async () => {
    state.pagination.offset = 0;
    state.pagination.total = 100;
    fetchProducts.mockResolvedValue({ products: [], total: 100 });
    await loadNextPage();
    expect(state.pagination.inFlight).toBe(false);
  });
});

describe('initInfiniteScroll / teardownInfiniteScroll', () => {
  it('attaches a scroll listener to window', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    state.pagination.total = 200;
    initInfiniteScroll();
    expect(addSpy).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true });
  });

  it('removes scroll listener on teardown', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    state.pagination.total = 200;
    initInfiniteScroll();
    teardownInfiniteScroll();
    expect(removeSpy).toHaveBeenCalledWith('scroll', expect.any(Function));
  });

  it('does not attach listener if all results are loaded', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    state.pagination.offset = 50;
    state.pagination.total = 50;
    initInfiniteScroll();
    expect(addSpy).not.toHaveBeenCalledWith('scroll', expect.any(Function), expect.any(Object));
  });

  it('calls teardown before re-initializing', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    state.pagination.total = 200;
    initInfiniteScroll();
    initInfiniteScroll(); // second call should teardown first
    expect(removeSpy).toHaveBeenCalled();
  });
});
