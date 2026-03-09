import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedResults: [],
    categories: [],
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

import { loadProductImage, resizeImage, removeProductImage } from '../images.js';
import { state, api, showConfirmModal, showToast } from '../state.js';
import { rerender } from '../filters.js';

beforeEach(() => {
  vi.clearAllMocks();
  state.imageCache = {};
  state.cachedResults = [];
});

describe('loadProductImage', () => {
  it('returns cached image when available', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    const result = await loadProductImage(1);
    expect(result).toBe('data:image/png;base64,abc');
  });

  it('returns cached null (no image)', async () => {
    state.imageCache[1] = null;
    const result = await loadProductImage(1);
    expect(result).toBeNull();
  });

  it('fetches image from API and caches it', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ image: 'data:image/png;base64,xyz' }),
    });
    const result = await loadProductImage(1);
    expect(result).toBe('data:image/png;base64,xyz');
    expect(state.imageCache[1]).toBe('data:image/png;base64,xyz');
  });

  it('caches null for 404 response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    const result = await loadProductImage(1);
    expect(result).toBeNull();
    expect(state.imageCache[1]).toBeNull();
  });

  it('does not cache on transient error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const result = await loadProductImage(1);
    expect(result).toBeNull();
    expect(state.imageCache[1]).toBeUndefined();
  });

  it('returns null on fetch exception', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    const result = await loadProductImage(1);
    expect(result).toBeNull();
  });
});

describe('resizeImage', () => {
  it('returns original dataUri when image is small enough', async () => {
    const smallUri = 'data:image/png;base64,iVBORw0KGgo=';
    // Mock Image to simulate small image that fits within maxSize
    const origImage = global.Image;
    global.Image = class {
      set src(val) {
        // Simulate a small image (200x100)
        this.width = 200;
        this.height = 100;
        setTimeout(() => this.onload && this.onload(), 0);
      }
    };
    const result = await resizeImage(smallUri, 400);
    expect(result).toBe(smallUri);
    global.Image = origImage;
  });

  it('resizes image when larger than maxSize', async () => {
    const largeUri = 'data:image/png;base64,iVBORw0KGgo=';
    const origImage = global.Image;
    const origCreateElement = document.createElement.bind(document);
    global.Image = class {
      set src(val) {
        this.width = 800;
        this.height = 600;
        setTimeout(() => this.onload && this.onload(), 0);
      }
    };
    // Mock canvas since jsdom doesn't support getContext('2d')
    const mockCtx = { drawImage: vi.fn() };
    const mockCanvas = {
      width: 0, height: 0,
      getContext: vi.fn(() => mockCtx),
      toDataURL: vi.fn(() => 'data:image/jpeg;base64,resized'),
    };
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'canvas') return mockCanvas;
      return origCreateElement(tag);
    });
    const result = await resizeImage(largeUri, 400);
    expect(result).toBe('data:image/jpeg;base64,resized');
    expect(mockCanvas.width).toBe(400);
    expect(mockCanvas.height).toBe(300);
    expect(mockCtx.drawImage).toHaveBeenCalled();
    global.Image = origImage;
    document.createElement.mockRestore?.();
  });

  it('returns original on image load error', async () => {
    const uri = 'data:image/png;base64,invalid';
    const origImage = global.Image;
    global.Image = class {
      set src(val) {
        setTimeout(() => this.onerror && this.onerror(), 0);
      }
    };
    const result = await resizeImage(uri, 400);
    expect(result).toBe(uri);
    global.Image = origImage;
  });
});

describe('removeProductImage', () => {
  it('confirms and removes image', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockResolvedValueOnce({});
    state.cachedResults = [{ id: 1, has_image: 1 }];
    await removeProductImage(1);
    expect(showConfirmModal).toHaveBeenCalled();
    expect(api).toHaveBeenCalledWith('/api/products/1/image', { method: 'DELETE' });
    expect(state.imageCache[1]).toBeNull();
    expect(state.cachedResults[0].has_image).toBe(0);
    expect(showToast).toHaveBeenCalledWith('toast_image_removed', 'success');
    expect(rerender).toHaveBeenCalled();
  });

  it('does nothing when confirmation cancelled', async () => {
    showConfirmModal.mockResolvedValue(false);
    await removeProductImage(1);
    expect(api).not.toHaveBeenCalled();
  });

  it('shows error on API failure', async () => {
    showConfirmModal.mockResolvedValue(true);
    api.mockRejectedValueOnce(new Error('fail'));
    await removeProductImage(1);
    expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
  });
});
