import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedResults: [],
    categories: [],
    imageCache: {},
    sortCol: 'total_score',
    sortDir: 'desc',
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    esc: (s) => String(s),
    catEmoji: vi.fn(() => '📦'),
    catLabel: vi.fn((t) => t),
    safeDataUri: vi.fn((u) => u || ''),
    fetchProducts: vi.fn().mockResolvedValue([]),
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
} from '../scanner.js';
import { state } from '../state.js';
import { showToast, switchView } from '../products.js';

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
