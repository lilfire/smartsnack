import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: null,
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
    advancedFilters: null,
  };
  return {
    state: _state,
    NUTRI_IDS: ['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'],
    catEmoji: vi.fn(() => '\u{1F4E6}'),
    catLabel: vi.fn((t) => t),
    esc: (s) => String(s ?? ''),
    safeDataUri: vi.fn((uri) => uri || ''),
    fmtNum: vi.fn((v) => v == null ? '-' : String(v)),
    showToast: vi.fn(),
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    rerender: vi.fn(),
  };
});

import { loadProductImage, resizeImage, removeProductImage, triggerImageUpload, viewProductImage } from '../images.js';
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

describe('triggerImageUpload', () => {
  it('shows error for files larger than 10MB', async () => {
    const clickSpy = vi.fn();
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'input') {
        const inp = { type: '', accept: '', click: clickSpy, files: [], onchange: null };
        // Simulate change after click
        clickSpy.mockImplementation(() => {
          inp.files = [{ size: 11 * 1024 * 1024, name: 'huge.jpg' }];
          inp.onchange();
        });
        return inp;
      }
      return document.createElement.wrappedMethod
        ? document.createElement.wrappedMethod.call(document, tag)
        : Object.getPrototypeOf(document).createElement.call(document, tag);
    });

    triggerImageUpload(1);
    expect(clickSpy).toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith('toast_image_too_large', 'error');
    document.createElement.mockRestore?.();
  });

  it('uploads and saves resized image', async () => {
    api.mockResolvedValueOnce({});
    state.cachedResults = [{ id: 1, has_image: 0 }];

    let capturedOnchange;
    const origFileReader = global.FileReader;
    const origImage = global.Image;

    // Mock Image so resizeImage resolves immediately (small image path)
    global.Image = class {
      set src(val) {
        this.width = 100;
        this.height = 100;
        Promise.resolve().then(() => this.onload && this.onload());
      }
    };

    global.FileReader = class {
      readAsDataURL() {
        this.onload({ target: { result: 'data:image/png;base64,original' } });
      }
    };

    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'input') {
        const inp = {
          type: '', accept: '',
          click: vi.fn(),
          files: [{ size: 1024, name: 'photo.jpg' }],
          set onchange(fn) { capturedOnchange = fn; },
          get onchange() { return capturedOnchange; },
        };
        return inp;
      }
      return origCreate(tag);
    });

    triggerImageUpload(1);
    await capturedOnchange();
    // Let Image.onload microtask + resizeImage promise settle
    await new Promise((r) => setTimeout(r, 50));

    expect(api).toHaveBeenCalledWith('/api/products/1/image', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith('toast_image_saved', 'success');
    expect(state.cachedResults[0].has_image).toBe(1);

    document.createElement.mockRestore?.();
    global.FileReader = origFileReader;
    global.Image = origImage;
  });

  it('does nothing when no file selected', async () => {
    let capturedOnchange;
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'input') {
        const inp = {
          type: '', accept: '',
          click: vi.fn(),
          files: [],
          set onchange(fn) { capturedOnchange = fn; },
          get onchange() { return capturedOnchange; },
        };
        return inp;
      }
      return origCreate(tag);
    });

    triggerImageUpload(1);
    await capturedOnchange();
    expect(api).not.toHaveBeenCalled();
    document.createElement.mockRestore?.();
  });

  it('shows error on upload failure', async () => {
    api.mockRejectedValueOnce(new Error('fail'));

    let capturedOnchange;
    const origFileReader = global.FileReader;
    const origImage = global.Image;

    global.Image = class {
      set src(val) {
        this.width = 100;
        this.height = 100;
        Promise.resolve().then(() => this.onload && this.onload());
      }
    };

    global.FileReader = class {
      readAsDataURL() {
        this.onload({ target: { result: 'data:image/png;base64,original' } });
      }
    };

    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'input') {
        const inp = {
          type: '', accept: '',
          click: vi.fn(),
          files: [{ size: 1024, name: 'photo.jpg' }],
          set onchange(fn) { capturedOnchange = fn; },
          get onchange() { return capturedOnchange; },
        };
        return inp;
      }
      return origCreate(tag);
    });

    triggerImageUpload(1);
    await capturedOnchange();
    await new Promise((r) => setTimeout(r, 50));

    expect(showToast).toHaveBeenCalledWith('toast_image_upload_error', 'error');
    document.createElement.mockRestore?.();
    global.FileReader = origFileReader;
    global.Image = origImage;
  });
});

describe('viewProductImage', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(() => {
    // Close any open modal to remove stale keydown listeners
    const bg = document.querySelector('.img-viewer-bg');
    if (bg) bg.click();
  });

  it('opens modal with cached image', async () => {
    state.imageCache[1] = 'data:image/png;base64,cached';
    await viewProductImage(1);
    const bg = document.querySelector('.img-viewer-bg');
    expect(bg).toBeTruthy();
    expect(bg.querySelector('img').src).toContain('cached');
  });

  it('loads image via API on cache miss', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ image: 'data:image/png;base64,loaded' }),
    });
    await viewProductImage(2);
    const bg = document.querySelector('.img-viewer-bg');
    expect(bg).toBeTruthy();
    expect(bg.querySelector('img').src).toContain('loaded');
  });

  it('does nothing when no image available', async () => {
    state.imageCache[3] = null;
    await viewProductImage(3);
    expect(document.querySelector('.img-viewer-bg')).toBeNull();
  });

  it('closes modal on Escape key', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    await viewProductImage(1);
    expect(document.querySelector('.img-viewer-bg')).toBeTruthy();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(document.querySelector('.img-viewer-bg')).toBeNull();
  });

  it('closes modal on backdrop click', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    await viewProductImage(1);
    const bg = document.querySelector('.img-viewer-bg');
    expect(bg).toBeTruthy();
    bg.click();
    expect(document.querySelector('.img-viewer-bg')).toBeNull();
  });

  it('does not close modal when clicking image', async () => {
    state.imageCache[1] = 'data:image/png;base64,abc';
    await viewProductImage(1);
    const img = document.querySelector('.img-viewer-bg img');
    expect(img).toBeTruthy();
    img.click();
    expect(document.querySelector('.img-viewer-bg')).toBeTruthy();
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
