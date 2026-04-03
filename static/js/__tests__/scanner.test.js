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
    catEmoji: vi.fn(() => '📦'),
    catLabel: vi.fn((t) => t),
    esc: (s) => String(s),
    safeDataUri: vi.fn((u) => u || ''),
    fmtNum: vi.fn((v) => v == null ? '-' : String(v)),
    showToast: vi.fn(),
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    upgradeSelect: vi.fn(),
    trapFocus: vi.fn(() => vi.fn()),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    buildFilters: vi.fn(),
    rerender: vi.fn(),
  };
});

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../products.js', () => ({
  showToast: vi.fn(),
  switchView: vi.fn(),
  loadData: vi.fn().mockResolvedValue(),
}));

vi.mock('../off-utils.js', () => ({
  validateOffBtn: vi.fn(),
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
}));
vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn(),
}));

vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
}));

import {
  openScanner, closeScanner, openSearchScanner,
  closeScanModal, scanRegisterNew, scanUpdateExisting,
  showScanNotFoundModal, closeScanPicker, showScanOffConfirm, closeScanOffConfirm,
  scanPickerSearch, scanPickerSelect, scanOffFetch,
} from '../scanner.js';
import { state, api, fetchProducts } from '../state.js';
import { showToast, switchView, loadData } from '../products.js';
import { rerender, buildFilters } from '../filters.js';
import { loadProductImage } from '../images.js';
import { renderResults } from '../render.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  document.body.style.overflow = '';
  // Clean up any scanner UI
  const scanBg = document.getElementById('scanner-bg');
  if (scanBg) scanBg.remove();
});

describe('openScanner', () => {
  it('shows toast error when Html5Qrcode not loaded', () => {
    delete global.Html5Qrcode;
    openScanner('ed', 1);
    expect(showToast).toHaveBeenCalledWith('toast_scanner_load_error', 'error');
  });

  it('creates scanner UI when Html5Qrcode available', () => {
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(),
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    openScanner('ed', 1);
    expect(document.getElementById('scanner-bg')).not.toBeNull();
    expect(document.body.style.overflow).toBe('hidden');
    closeScanner();
  });
});

describe('closeScanner', () => {
  it('removes scanner bg from DOM', () => {
    const bg = document.createElement('div');
    bg.id = 'scanner-bg';
    document.body.appendChild(bg);
    document.body.style.overflow = 'hidden';
    closeScanner();
    expect(document.getElementById('scanner-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });

  it('handles case when no scanner bg exists', () => {
    expect(() => closeScanner()).not.toThrow();
  });
});

describe('openSearchScanner', () => {
  it('shows error when Html5Qrcode not loaded', () => {
    delete global.Html5Qrcode;
    openSearchScanner();
    expect(showToast).toHaveBeenCalledWith('toast_scanner_not_loaded', 'error');
  });
});

describe('showScanNotFoundModal', () => {
  it('creates modal with correct EAN', () => {
    showScanNotFoundModal('1234567890123');
    const modal = document.getElementById('scan-modal-bg');
    expect(modal).not.toBeNull();
    expect(modal.innerHTML).toContain('1234567890123');
    expect(modal.innerHTML).toContain('scan_product_not_found');
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('has register, update, and cancel buttons', () => {
    showScanNotFoundModal('1234567890123');
    expect(document.querySelector('.scan-modal-btn-register')).not.toBeNull();
    expect(document.querySelector('.scan-modal-btn-update')).not.toBeNull();
    expect(document.querySelector('.scan-modal-btn-cancel')).not.toBeNull();
  });
});

describe('closeScanModal', () => {
  it('removes scan modal', () => {
    const bg = document.createElement('div');
    bg.id = 'scan-modal-bg';
    document.body.appendChild(bg);
    document.body.style.overflow = 'hidden';
    closeScanModal();
    expect(document.getElementById('scan-modal-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });

  it('handles missing modal', () => {
    expect(() => closeScanModal()).not.toThrow();
  });
});

describe('scanRegisterNew', () => {
  it('closes modal, switches to register view, and sets EAN', () => {
    const bg = document.createElement('div');
    bg.id = 'scan-modal-bg';
    document.body.appendChild(bg);
    const eanEl = document.createElement('input');
    eanEl.id = 'f-ean';
    document.body.appendChild(eanEl);
    scanRegisterNew('1234567890123');
    expect(document.getElementById('scan-modal-bg')).toBeNull();
    expect(switchView).toHaveBeenCalledWith('register');
    expect(eanEl.value).toBe('1234567890123');
  });
});

describe('scanUpdateExisting', () => {
  it('closes scan modal and opens product picker', () => {
    const bg = document.createElement('div');
    bg.id = 'scan-modal-bg';
    document.body.appendChild(bg);
    scanUpdateExisting('1234567890123');
    expect(document.getElementById('scan-modal-bg')).toBeNull();
    expect(document.getElementById('scan-picker-bg')).not.toBeNull();
  });
});

describe('closeScanPicker', () => {
  it('removes picker modal', () => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    document.body.appendChild(bg);
    closeScanPicker();
    expect(document.getElementById('scan-picker-bg')).toBeNull();
  });
});

describe('showScanOffConfirm', () => {
  it('creates OFF confirm modal', () => {
    showScanOffConfirm('1234567890123', 1);
    const modal = document.getElementById('scan-off-confirm-bg');
    expect(modal).not.toBeNull();
    expect(modal.innerHTML).toContain('1234567890123');
    expect(modal.innerHTML).toContain('scan_fetch_off_title');
  });
});

describe('closeScanOffConfirm', () => {
  it('removes OFF confirm modal', () => {
    const bg = document.createElement('div');
    bg.id = 'scan-off-confirm-bg';
    document.body.appendChild(bg);
    closeScanOffConfirm();
    expect(document.getElementById('scan-off-confirm-bg')).toBeNull();
  });
});

describe('scanPickerSearch', () => {
  beforeEach(() => {
    // Set up picker modal DOM
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('shows error when query empty', async () => {
    document.getElementById('scan-picker-input').value = '';
    await scanPickerSearch();
    expect(showToast).toHaveBeenCalledWith('toast_enter_product_name', 'error');
  });

  it('shows empty message when no results', async () => {
    document.getElementById('scan-picker-input').value = 'nonexistent';
    fetchProducts.mockResolvedValueOnce([]);
    await scanPickerSearch();
    const body = document.getElementById('scan-picker-body');
    expect(body.innerHTML).toContain('off-modal-empty');
  });

  it('renders search results', async () => {
    document.getElementById('scan-picker-input').value = 'Milk';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'Milk', type: 'dairy', has_image: 0 },
      { id: 2, name: 'Milk 2', type: 'dairy', has_image: 0 },
    ]);
    await scanPickerSearch();
    const cnt = document.getElementById('scan-picker-count');
    expect(cnt.textContent).toBe('scan_result_count_other');
  });

  it('shows error on network failure', async () => {
    document.getElementById('scan-picker-input').value = 'test';
    fetchProducts.mockRejectedValueOnce(new Error('fail'));
    await scanPickerSearch();
    const body = document.getElementById('scan-picker-body');
    expect(body.innerHTML).toContain('toast_network_error');
  });
});

describe('scanPickerSelect', () => {
  it('saves EAN to product', async () => {
    // Trigger scanUpdateExisting to set _scanPickerEan
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    const prod = { id: 5, name: 'Test', ean: '' };
    api.mockResolvedValueOnce(prod) // GET product
       .mockResolvedValueOnce({}); // PUT product
    await scanPickerSelect(5);
    expect(api).toHaveBeenCalledWith('/api/products/5');
    expect(api).toHaveBeenCalledWith('/api/products/5', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
    // Should show OFF confirm modal
    expect(document.getElementById('scan-off-confirm-bg')).not.toBeNull();
  });

  it('shows error when save fails', async () => {
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    api.mockResolvedValueOnce({ id: 5, name: 'Test' })
       .mockRejectedValueOnce(new Error('fail'));
    await scanPickerSelect(5);
    expect(showToast).toHaveBeenCalledWith('toast_ean_save_error', 'error');
  });
});

describe('scanOffFetch', () => {
  it('sets up edit state and triggers OFF lookup', async () => {
    state.currentView = 'search';
    loadData.mockResolvedValueOnce();
    await scanOffFetch('1234567890123', 42);
    expect(state.expandedId).toBe(42);
    expect(state.editingId).toBe(42);
    expect(rerender).toHaveBeenCalled();
  });

  it('switches view if not on search', async () => {
    state.currentView = 'settings';
    loadData.mockResolvedValueOnce();
    await scanOffFetch('1234567890123', 42);
    expect(switchView).toHaveBeenCalledWith('search');
  });
});

describe('startScannerHardware error handling', () => {
  it('shows error UI when scanner.start() rejects', async () => {
    const mockStart = vi.fn().mockRejectedValue(new Error('Camera denied'));
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    openScanner('ed', 1);
    // Wait for the rejected promise in the catch block
    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_scanner_load_error', 'error');
    });
    const errDiv = document.querySelector('.scanner-error');
    expect(errDiv).not.toBeNull();
    expect(errDiv.querySelector('.scanner-error-icon')).not.toBeNull();
    expect(errDiv.querySelector('p')).not.toBeNull();
    const cancelBtn = errDiv.querySelector('.btn-sm.btn-outline');
    expect(cancelBtn).not.toBeNull();
    // Click the cancel button to close the scanner
    cancelBtn.click();
    expect(document.getElementById('scanner-bg')).toBeNull();
  });
});

describe('onBarcodeDetected via openScanner', () => {
  it('vibrates, sets EAN, shows toast, and closes scanner', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    // Set up EAN input element
    const eanInput = document.createElement('input');
    eanInput.id = 'ed-ean';
    document.body.appendChild(eanInput);

    openScanner('ed', 1);
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // Simulate barcode detection
    capturedOnSuccess('7038010055720');

    expect(navigator.vibrate).toHaveBeenCalledWith(100);
    expect(eanInput.value).toBe('7038010055720');
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_barcode_scanned'), 'success');
    expect(document.getElementById('scanner-bg')).toBeNull();
  });
});

describe('showScanNotFoundModal button interactions', () => {
  it('cancel button closes the modal', () => {
    showScanNotFoundModal('1234567890123');
    const cancelBtn = document.querySelector('.scan-modal-btn-cancel');
    cancelBtn.click();
    expect(document.getElementById('scan-modal-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });

  it('background click closes the modal', () => {
    showScanNotFoundModal('1234567890123');
    const bg = document.getElementById('scan-modal-bg');
    // Simulate clicking the background itself (not a child)
    bg.onclick({ target: bg });
    expect(document.getElementById('scan-modal-bg')).toBeNull();
  });

  it('register button calls scanRegisterNew flow', () => {
    showScanNotFoundModal('1234567890123');
    const regBtn = document.querySelector('.scan-modal-btn-register');
    regBtn.click();
    expect(switchView).toHaveBeenCalledWith('register');
  });
});

// ── Additional branch coverage tests ────────────────────

describe('startScannerHardware when .scanner-video-wrap is missing', () => {
  it('does not crash when videoWrap element is absent', async () => {
    const mockStart = vi.fn().mockRejectedValue(new Error('Camera denied'));
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    openScanner('ed', 1);
    // Remove .scanner-video-wrap before the rejected promise handler runs
    const videoWrap = document.querySelector('.scanner-video-wrap');
    if (videoWrap) videoWrap.remove();

    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_scanner_load_error', 'error');
    });
    // The error div should NOT have been created since videoWrap was removed
    expect(document.querySelector('.scanner-error')).toBeNull();
    closeScanner();
  });
});

describe('onBarcodeDetected when navigator.vibrate is undefined', () => {
  it('works without crashing when vibrate is not available', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };

    // Ensure vibrate is undefined
    const origVibrate = navigator.vibrate;
    delete navigator.vibrate;
    Object.defineProperty(navigator, 'vibrate', { value: undefined, configurable: true, writable: true });

    const eanInput = document.createElement('input');
    eanInput.id = 'ed-ean';
    document.body.appendChild(eanInput);

    openScanner('ed', 1);
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // Should not throw even without vibrate
    expect(() => capturedOnSuccess('7038010055720')).not.toThrow();
    expect(eanInput.value).toBe('7038010055720');
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_barcode_scanned'), 'success');

    // Restore vibrate
    navigator.vibrate = origVibrate;
  });
});

describe('onBarcodeDetected when EAN element does not exist', () => {
  it('does not crash when the target EAN input is missing from DOM', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    // Deliberately do NOT create an 'ed-ean' element
    openScanner('ed', 1);
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    expect(() => capturedOnSuccess('7038010055720')).not.toThrow();
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('toast_barcode_scanned'), 'success');
    // No EAN element to set, so no element should exist
    expect(document.getElementById('ed-ean')).toBeNull();
  });
});

describe('onSearchScanDetected when currentView is already search', () => {
  it('does not call switchView when already on search view', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    // Set up required DOM elements for onSearchScanDetected
    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    searchClear.classList.add('visible');
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    state.currentView = 'search';
    const matchingProduct = { id: 10, name: 'TestProduct', type: 'dairy', ean: '7038010055720' };
    fetchProducts.mockResolvedValue([matchingProduct]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('7038010055720');
    await vi.waitFor(() => {
      expect(buildFilters).toHaveBeenCalled();
    });

    expect(switchView).not.toHaveBeenCalled();
    // Reset
    fetchProducts.mockResolvedValue([]);
  });
});

describe('onSearchScanDetected when filter row is already open', () => {
  it('does not add open class again when filter row already has it', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    searchClear.classList.add('visible');
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    filterRow.classList.add('open'); // Already open
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    state.currentView = 'search';
    const matchingProduct = { id: 11, name: 'OpenFilterProduct', type: 'snack', ean: '1234567890128' };
    fetchProducts.mockResolvedValue([matchingProduct]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('1234567890128');
    await vi.waitFor(() => {
      expect(renderResults).toHaveBeenCalled();
    });

    // Filter row should still have 'open' but the add branch was skipped
    expect(filterRow.classList.contains('open')).toBe(true);
    // filterToggle should NOT have gotten 'open' added since the condition was false
    expect(filterToggle.classList.contains('open')).toBe(false);
    fetchProducts.mockResolvedValue([]);
  });
});

describe('onSearchScanDetected when product row element is null', () => {
  it('does not crash when the product row is not in DOM', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    state.currentView = 'search';
    const matchingProduct = { id: 99, name: 'NoRowProduct', type: 'bread', ean: '9999999999999' };
    fetchProducts.mockResolvedValue([matchingProduct]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('9999999999999');
    await vi.waitFor(() => {
      expect(renderResults).toHaveBeenCalled();
    });

    // Deliberately no .table-row[data-product-id="99"] in DOM
    // Wait for the setTimeout(150) to fire
    await vi.waitFor(() => {
      // The setTimeout should have fired and not crashed
      expect(document.querySelector('.scan-highlight')).toBeNull();
    });
    fetchProducts.mockResolvedValue([]);
  });
});

describe('scanPickerSearch singular result count', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('shows singular translation key when exactly 1 result', async () => {
    document.getElementById('scan-picker-input').value = 'Cheese';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'Cheese', type: 'dairy', has_image: 0 },
    ]);
    await scanPickerSearch();
    const cnt = document.getElementById('scan-picker-count');
    expect(cnt.textContent).toBe('scan_result_count_one');
  });
});

describe('scanPickerSearch loadProductImage with dataUri', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('renders image when has_image is true and loadProductImage returns a data URI', async () => {
    const fakeDataUri = 'data:image/png;base64,AAAA';
    loadProductImage.mockResolvedValueOnce(fakeDataUri);

    document.getElementById('scan-picker-input').value = 'ImgProduct';
    fetchProducts.mockResolvedValueOnce([
      { id: 50, name: 'ImgProduct', type: 'dairy', has_image: 1 },
    ]);
    await scanPickerSearch();

    // Wait for the loadProductImage promise to resolve and update the DOM
    await vi.waitFor(() => {
      const imgEl = document.getElementById('scan-pick-img-50');
      expect(imgEl).not.toBeNull();
      expect(imgEl.innerHTML).toContain('<img');
      expect(imgEl.innerHTML).toContain(fakeDataUri);
    });
  });
});

describe('scanPickerSearch EAN vs no EAN products', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('shows EAN for products with ean and scan_no_ean for those without', async () => {
    document.getElementById('scan-picker-input').value = 'Test';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'WithEAN', type: 'dairy', has_image: 0, ean: '7038010055720' },
      { id: 2, name: 'NoEAN', type: 'dairy', has_image: 0, ean: '' },
    ]);
    await scanPickerSearch();

    const body = document.getElementById('scan-picker-body');
    expect(body.innerHTML).toContain('EAN: 7038010055720');
    expect(body.innerHTML).toContain('scan_no_ean');
  });
});

describe('onSearchScanDetected when product is not found', () => {
  it('shows scan not found modal when EAN does not match any product', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    state.currentView = 'search';
    // First call (all products): none match the scanned EAN by primary EAN
    // Second call (secondary EAN search): no results either
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'Other', type: 'dairy', ean: '0000000000000' },
    ]).mockResolvedValueOnce([]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('9876543210987');
    await vi.waitFor(() => {
      // Should show the not-found modal since no product matched
      expect(document.getElementById('scan-modal-bg')).not.toBeNull();
    });
    fetchProducts.mockResolvedValue([]);
  });
});

describe('onSearchScanDetected when product row EXISTS in DOM', () => {
  it('highlights and scrolls to the product row', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    // Create the product row element in the DOM
    const tableRow = document.createElement('div');
    tableRow.className = 'table-row';
    tableRow.setAttribute('data-product-id', '77');
    tableRow.scrollIntoView = vi.fn();
    document.body.appendChild(tableRow);

    state.currentView = 'search';
    const matchingProduct = { id: 77, name: 'RowProduct', type: 'dairy', ean: '5555555555555' };
    fetchProducts.mockResolvedValue([matchingProduct]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('5555555555555');
    await vi.waitFor(() => {
      expect(renderResults).toHaveBeenCalled();
    });

    // Wait for the setTimeout(150) to fire and highlight the row
    await vi.waitFor(() => {
      expect(tableRow.classList.contains('scan-highlight')).toBe(true);
    });
    expect(tableRow.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });
    fetchProducts.mockResolvedValue([]);
  });
});

describe('onSearchScanDetected switchView when not on search', () => {
  it('calls switchView when currentView is not search', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);

    state.currentView = 'register'; // NOT search
    fetchProducts.mockResolvedValue([
      { id: 1, name: 'Prod', type: 'dairy', ean: '1111111111111' },
    ]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('1111111111111');
    await vi.waitFor(() => {
      expect(switchView).toHaveBeenCalledWith('search');
    });
    fetchProducts.mockResolvedValue([]);
  });
});

describe('scanPickerSearch click delegation on result rows', () => {
  it('calls scanPickerSelect when clicking a result row', async () => {
    // Set _scanPickerEan via scanUpdateExisting
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    // scanUpdateExisting already creates picker DOM, just set the input value
    const inp = document.getElementById('scan-picker-input');
    inp.value = 'Clickable';

    fetchProducts.mockResolvedValueOnce([
      { id: 42, name: 'Clickable', type: 'dairy', has_image: 0 },
    ]);
    api.mockResolvedValueOnce({ id: 42, name: 'Clickable', ean: '' })
       .mockResolvedValueOnce({});

    await scanPickerSearch();

    // Click a result row - the body was replaced by scanPickerSearch via cloneNode
    const resultRow = document.querySelector('[data-action="pick"]');
    expect(resultRow).not.toBeNull();
    resultRow.click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith('/api/products/42');
    });
  });
});

describe('scanPickerSelect when _scanPickerEan is null', () => {
  it('returns early when no EAN is set', async () => {
    // Don't call scanUpdateExisting, so _scanPickerEan stays null
    // We need to ensure _scanPickerEan is null by calling closeScanPicker
    closeScanPicker();
    await scanPickerSelect(1);
    // Should not call api at all
    expect(api).not.toHaveBeenCalled();
  });
});

describe('showScanOffConfirm background click', () => {
  it('closes modal when background is clicked', () => {
    showScanOffConfirm('1234567890123', 1);
    const bg = document.getElementById('scan-off-confirm-bg');
    expect(bg).not.toBeNull();
    bg.onclick({ target: bg });
    expect(document.getElementById('scan-off-confirm-bg')).toBeNull();
  });
});

describe('showScanProductPicker background click', () => {
  it('closes picker when background is clicked', () => {
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');
    const bg = document.getElementById('scan-picker-bg');
    expect(bg).not.toBeNull();
    bg.onclick({ target: bg });
    expect(document.getElementById('scan-picker-bg')).toBeNull();
  });
});

describe('scanOffFetch sets eanEl value', () => {
  it('sets the ed-ean input value after loadData', async () => {
    state.currentView = 'search';
    loadData.mockResolvedValueOnce();
    const eanEl = document.createElement('input');
    eanEl.id = 'ed-ean';
    document.body.appendChild(eanEl);

    await scanOffFetch('7777777777777', 42);

    // Wait for the setTimeout(300) to fire and set eanEl value
    await vi.waitFor(() => {
      expect(eanEl.value).toBe('7777777777777');
    });
  });
});

describe('onSearchScanDetected error handling', () => {
  it('logs error and shows toast when fetchProducts throws', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    state.currentView = 'search';
    // Make fetchProducts reject to trigger the catch branch
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    fetchProducts.mockRejectedValue(new Error('network failure'));

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    capturedOnSuccess('1234567890123');
    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_network_error', 'error');
    });
    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
    fetchProducts.mockResolvedValue([]);
  });
});

// ── Targeted branch coverage tests for lines 88, 320, 354, 391, 138-140, 155, 165 ──

describe('openScanner with truthy productId (line 88 branch)', () => {
  it('stores truthy productId in scanner context', () => {
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(),
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    // Call with a truthy productId (42) to cover the productId || null truthy branch
    openScanner('ed', 42);
    expect(document.getElementById('scanner-bg')).not.toBeNull();
    closeScanner();
  });

  it('stores null when productId is 0 (falsy)', () => {
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(),
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    // Call with falsy productId (0) to cover the productId || null falsy branch
    openScanner('ed', 0);
    expect(document.getElementById('scanner-bg')).not.toBeNull();
    closeScanner();
  });

  it('stores null when productId is undefined', () => {
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(),
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    openScanner('ed', undefined);
    expect(document.getElementById('scanner-bg')).not.toBeNull();
    closeScanner();
  });
});

describe('scanPickerSearch Enter key handler (line 320 branch)', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('triggers search when Enter is pressed in scan picker input', async () => {
    // Use showScanProductPicker to build the DOM with event listeners attached
    // We need to rebuild it via the real function
    document.body.innerHTML = '';
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    const inp = document.getElementById('scan-picker-input');
    inp.value = 'TestEnter';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'TestEnter', type: 'dairy', has_image: 0 },
    ]);

    // Dispatch Enter keydown event
    const enterEvent = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
    inp.dispatchEvent(enterEvent);

    await vi.waitFor(() => {
      expect(fetchProducts).toHaveBeenCalledWith('TestEnter', []);
    });
  });

  it('does not trigger search when non-Enter key is pressed', async () => {
    document.body.innerHTML = '';
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    const inp = document.getElementById('scan-picker-input');
    inp.value = 'NoSearch';

    // Dispatch a non-Enter keydown event
    const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true });
    inp.dispatchEvent(tabEvent);

    // fetchProducts should NOT have been called for 'NoSearch'
    expect(fetchProducts).not.toHaveBeenCalledWith('NoSearch', []);
  });
});

describe('scanPickerSearch when input element is missing (line 354 branch)', () => {
  it('shows error toast when scan-picker-input does not exist', async () => {
    // Set up DOM with body and count but NO input element
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    // Deliberately NO scan-picker-input
    document.body.appendChild(bg);

    await scanPickerSearch();
    // query will be '' since inp is null, so it should show the empty query toast
    expect(showToast).toHaveBeenCalledWith('toast_enter_product_name', 'error');
  });
});

describe('scanPickerSearch loadProductImage returns falsy (line 391 branch)', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('does not render image when loadProductImage returns null for a product with has_image', async () => {
    // loadProductImage returns null (falsy) - covers the `if (!dataUri) return` branch
    loadProductImage.mockResolvedValueOnce(null);

    document.getElementById('scan-picker-input').value = 'NullImg';
    fetchProducts.mockResolvedValueOnce([
      { id: 60, name: 'NullImg', type: 'dairy', has_image: 1 },
    ]);
    await scanPickerSearch();

    // Wait for loadProductImage promise to resolve
    await vi.waitFor(() => {
      expect(loadProductImage).toHaveBeenCalledWith(60);
    });

    // The image element should exist but should NOT contain an <img> tag
    const imgEl = document.getElementById('scan-pick-img-60');
    expect(imgEl).not.toBeNull();
    expect(imgEl.innerHTML).not.toContain('<img');
  });
});

describe('closeSearchScanner via close button (lines 138-140, 155)', () => {
  it('resets search scan mode and closes scanner when close button is clicked', async () => {
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(),
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };

    openSearchScanner();
    expect(document.getElementById('scanner-bg')).not.toBeNull();

    // Click the close button which triggers the closeSearchScanner callback
    const closeBtn = document.querySelector('.scanner-close');
    expect(closeBtn).not.toBeNull();
    closeBtn.click();

    expect(document.getElementById('scanner-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });
});

describe('closeSearchScanner via error cancel button (line 165)', () => {
  it('calls closeSearchScanner when error cancel button is clicked in search scanner', async () => {
    const mockStart = vi.fn().mockRejectedValue(new Error('Camera denied'));
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };

    openSearchScanner();
    await vi.waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('toast_scanner_load_error', 'error');
    });

    // The error UI should have a cancel button that calls closeSearchScanner
    const cancelBtn = document.querySelector('.btn-sm.btn-outline');
    expect(cancelBtn).not.toBeNull();
    cancelBtn.click();

    expect(document.getElementById('scanner-bg')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });
});

describe('showScanNotFoundModal update button triggers scanUpdateExisting', () => {
  it('update button closes modal and opens picker', () => {
    showScanNotFoundModal('1234567890123');
    const updBtn = document.querySelector('.scan-modal-btn-update');
    expect(updBtn).not.toBeNull();
    updBtn.click();
    // scanUpdateExisting closes scan modal and opens scan picker
    expect(document.getElementById('scan-modal-bg')).toBeNull();
    expect(document.getElementById('scan-picker-bg')).not.toBeNull();
  });
});

describe('showScanOffConfirm fetch and skip button interactions', () => {
  it('fetch button triggers scanOffFetch', async () => {
    loadData.mockResolvedValueOnce();
    showScanOffConfirm('1234567890123', 1);
    const fetchBtn = document.querySelector('.scan-modal-btn-register');
    expect(fetchBtn).not.toBeNull();
    fetchBtn.click();
    // Should close the confirm modal
    expect(document.getElementById('scan-off-confirm-bg')).toBeNull();
  });

  it('skip button closes modal and calls loadData', async () => {
    showScanOffConfirm('1234567890123', 1);
    const skipBtn = document.querySelector('.scan-modal-btn-cancel');
    expect(skipBtn).not.toBeNull();
    skipBtn.click();
    expect(document.getElementById('scan-off-confirm-bg')).toBeNull();
    expect(loadData).toHaveBeenCalled();
  });
});

describe('showScanProductPicker close button and search button click (line 311, 324)', () => {
  it('close button closes the picker', () => {
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    const closeBtn = document.querySelector('.off-modal-close');
    expect(closeBtn).not.toBeNull();
    closeBtn.click();
    expect(document.getElementById('scan-picker-bg')).toBeNull();
  });

  it('search button triggers scanPickerSearch', async () => {
    const modalBg = document.createElement('div');
    modalBg.id = 'scan-modal-bg';
    document.body.appendChild(modalBg);
    scanUpdateExisting('1234567890123');

    const inp = document.getElementById('scan-picker-input');
    inp.value = 'BtnSearch';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'BtnSearch', type: 'dairy', has_image: 0 },
    ]);

    // Click the search button (second button in the search div)
    const searchBtn = document.querySelector('.off-modal-search button');
    expect(searchBtn).not.toBeNull();
    searchBtn.click();

    await vi.waitFor(() => {
      expect(fetchProducts).toHaveBeenCalledWith('BtnSearch', []);
    });
  });
});

describe('openSearchScanner search scan success callback (line 159-163)', () => {
  it('triggers onSearchScanDetected and sets _searchScanMode to false', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    state.currentView = 'search';
    fetchProducts.mockResolvedValue([]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // First call should trigger onSearchScanDetected
    capturedOnSuccess('1111111111111');

    // Second call should be ignored because _searchScanMode was set to false
    capturedOnSuccess('2222222222222');

    await vi.waitFor(() => {
      // Only the not-found modal for the first scan should appear
      expect(document.getElementById('scan-modal-bg')).not.toBeNull();
    });

    fetchProducts.mockResolvedValue([]);
  });
});

describe('scanPickerSearch brand vs no brand products', () => {
  beforeEach(() => {
    const bg = document.createElement('div');
    bg.id = 'scan-picker-bg';
    const body = document.createElement('div');
    body.id = 'scan-picker-body';
    body.className = 'off-modal-body';
    bg.appendChild(body);
    const cnt = document.createElement('div');
    cnt.id = 'scan-picker-count';
    bg.appendChild(cnt);
    const inp = document.createElement('input');
    inp.id = 'scan-picker-input';
    bg.appendChild(inp);
    document.body.appendChild(bg);
  });

  it('shows brand for products with brand and omits it for those without', async () => {
    document.getElementById('scan-picker-input').value = 'Brand';
    fetchProducts.mockResolvedValueOnce([
      { id: 1, name: 'WithBrand', type: 'dairy', has_image: 0, brand: 'Tine' },
      { id: 2, name: 'NoBrand', type: 'snack', has_image: 0, brand: '' },
    ]);
    await scanPickerSearch();

    const body = document.getElementById('scan-picker-body');
    expect(body.innerHTML).toContain('Tine');
    // The product without brand should not have the separator
    const results = body.querySelectorAll('.off-result');
    const noBrandResult = results[1];
    const brandDiv = noBrandResult.querySelector('.off-result-brand');
    expect(brandDiv.textContent).not.toContain('\u00B7');
  });
});

describe('onSearchScanDetected secondary EAN match', () => {
  it('identifies product when scanned barcode matches a secondary EAN in eans array', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    searchClear.classList.add('visible');
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    state.currentView = 'search';
    // Product has primary EAN '7038010069307' but also a secondary EAN '5000000000001'
    const product = {
      id: 10, name: 'TestProduct', type: 'dairy',
      ean: '7038010069307',
      eans: ['7038010069307', '5000000000001'],
    };
    // First fetchProducts call returns all products (includes the one with eans array)
    fetchProducts.mockResolvedValueOnce([product]);
    // Second call for filtered results
    fetchProducts.mockResolvedValueOnce([product]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // Scan a SECONDARY EAN — not the primary one
    capturedOnSuccess('5000000000001');
    await vi.waitFor(() => {
      expect(buildFilters).toHaveBeenCalled();
    });

    // The product should be found via the eans array match
    expect(state.currentFilter).toEqual(['dairy']);
    expect(renderResults).toHaveBeenCalled();

    fetchProducts.mockResolvedValue([]);
  });

  it('falls back to backend search when secondary EAN is not in local eans array', async () => {
    let capturedOnSuccess;
    const mockStart = vi.fn().mockImplementation((facingMode, config, onSuccess) => {
      capturedOnSuccess = onSuccess;
      return Promise.resolve();
    });
    global.Html5Qrcode = vi.fn().mockImplementation(() => ({
      start: mockStart,
      stop: vi.fn().mockResolvedValue(),
      clear: vi.fn(),
    }));
    global.Html5QrcodeSupportedFormats = {
      EAN_13: 0, EAN_8: 1, UPC_A: 2, UPC_E: 3,
    };
    navigator.vibrate = vi.fn();

    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    const searchClear = document.createElement('div');
    searchClear.id = 'search-clear';
    searchClear.classList.add('visible');
    document.body.appendChild(searchClear);
    const filterRow = document.createElement('div');
    filterRow.id = 'filter-row';
    document.body.appendChild(filterRow);
    const filterToggle = document.createElement('div');
    filterToggle.id = 'filter-toggle';
    document.body.appendChild(filterToggle);

    state.currentView = 'search';
    // Product has no eans array — only primary EAN
    const product = {
      id: 10, name: 'TestProduct', type: 'dairy',
      ean: '7038010069307',
    };
    // First call: all products (no local match for the scanned code)
    fetchProducts.mockResolvedValueOnce([product]);
    // Second call: backend search finds the product via secondary EAN
    fetchProducts.mockResolvedValueOnce([product]);
    // Third call: filtered results for rendering
    fetchProducts.mockResolvedValueOnce([product]);

    openSearchScanner();
    await vi.waitFor(() => {
      expect(capturedOnSuccess).toBeDefined();
    });

    // Scan a secondary EAN that is not in the local eans array
    capturedOnSuccess('5000000000001');
    await vi.waitFor(() => {
      expect(buildFilters).toHaveBeenCalled();
    });

    // fetchProducts should be called with the scanned code for backend search
    expect(fetchProducts).toHaveBeenCalledWith('5000000000001', []);

    fetchProducts.mockResolvedValue([]);
  });
});
