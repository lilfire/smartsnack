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
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  buildFilters: vi.fn(),
  rerender: vi.fn(),
}));

vi.mock('../images.js', () => ({
  loadProductImage: vi.fn().mockResolvedValue(null),
}));

vi.mock('../products.js', () => ({
  showToast: vi.fn(),
  switchView: vi.fn(),
  loadData: vi.fn().mockResolvedValue(),
}));

vi.mock('../openfoodfacts.js', () => ({
  validateOffBtn: vi.fn(),
  lookupOFF: vi.fn(),
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
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
import { rerender } from '../filters.js';

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
    expect(cnt.textContent).toContain('2');
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
