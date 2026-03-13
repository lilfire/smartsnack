import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all module dependencies to prevent side effects
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
    api: vi.fn().mockResolvedValue([]),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({}),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  initLanguage: vi.fn().mockResolvedValue(),
  changeLanguage: vi.fn(),
  t: vi.fn((k) => k),
}));

vi.mock('../filters.js', () => ({
  toggleFilters: vi.fn(),
  setSort: vi.fn(),
  rerender: vi.fn(),
}));

vi.mock('../images.js', () => ({
  triggerImageUpload: vi.fn(),
  removeProductImage: vi.fn(),
}));

vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
  loadFlagConfig: vi.fn().mockResolvedValue(),
}));

vi.mock('../products.js', () => ({
  showToast: vi.fn(),
  startEdit: vi.fn(),
  saveProduct: vi.fn(),
  deleteProduct: vi.fn(),
  loadData: vi.fn(),
  switchView: vi.fn(),
  setFilter: vi.fn(),
  toggleExpand: vi.fn(),
  onSearchInput: vi.fn(),
  clearSearch: vi.fn(),
  registerProduct: vi.fn(),
}));

vi.mock('../settings.js', () => ({
  SCORE_CFG_MAP: {},
  weightData: [],
  loadSettings: vi.fn(),
  toggleSettingsSection: vi.fn(),
  toggleWeightConfig: vi.fn(),
  removeWeight: vi.fn(),
  addWeightFromDropdown: vi.fn(),
  onWeightDirection: vi.fn(),
  onWeightFormula: vi.fn(),
  onWeightMin: vi.fn(),
  onWeightMax: vi.fn(),
  onWeightSlider: vi.fn(),
  saveWeights: vi.fn(),
  updateCategoryLabel: vi.fn(),
  addCategory: vi.fn(),
  deleteCategory: vi.fn(),
  addFlag: vi.fn(),
  deleteFlag: vi.fn(),
  updateFlagLabel: vi.fn(),
  autosavePq: vi.fn(),
  deletePq: vi.fn(),
  addPq: vi.fn(),
  downloadBackup: vi.fn(),
  handleRestore: vi.fn(),
  handleImport: vi.fn(),
  initRestoreDragDrop: vi.fn(),
  saveOffCredentials: vi.fn(),
  refreshAllFromOff: vi.fn(),
  estimateAllPq: vi.fn(),
}));

vi.mock('../scanner.js', () => ({
  openScanner: vi.fn(),
  closeScanner: vi.fn(),
  openSearchScanner: vi.fn(),
  closeScanModal: vi.fn(),
  scanRegisterNew: vi.fn(),
  scanUpdateExisting: vi.fn(),
  closeScanPicker: vi.fn(),
  scanPickerSearch: vi.fn(),
  scanPickerSelect: vi.fn(),
  showScanOffConfirm: vi.fn(),
  closeScanOffConfirm: vi.fn(),
  scanOffFetch: vi.fn(),
}));

vi.mock('../openfoodfacts.js', () => ({
  validateOffBtn: vi.fn(),
  lookupOFF: vi.fn(),
  closeOffPicker: vi.fn(),
  offModalSearch: vi.fn(),
  selectOffResult: vi.fn(),
  estimateProteinQuality: vi.fn(),
  updateEstimateBtn: vi.fn(),
  showOffAddReview: vi.fn(),
  closeOffAddReview: vi.fn(),
  submitToOff: vi.fn(),
}));

beforeEach(() => {
  document.body.innerHTML = '';
  const searchInput = document.createElement('input');
  searchInput.id = 'search-input';
  document.body.appendChild(searchInput);
  // Reset window to avoid leaks between tests
  vi.clearAllMocks();
});

describe('app.js', () => {
  it('exposes public functions to window after import', async () => {
    // Import app.js which assigns functions to window
    await import('../app.js');

    // Verify key functions are exposed
    expect(typeof window.switchView).toBe('function');
    expect(typeof window.setFilter).toBe('function');
    expect(typeof window.toggleExpand).toBe('function');
    expect(typeof window.startEdit).toBe('function');
    expect(typeof window.saveProduct).toBe('function');
    expect(typeof window.deleteProduct).toBe('function');
    expect(typeof window.loadData).toBe('function');
    expect(typeof window.registerProduct).toBe('function');
    expect(typeof window.openScanner).toBe('function');
    expect(typeof window.closeScanner).toBe('function');
    expect(typeof window.toggleFilters).toBe('function');
    expect(typeof window.setSort).toBe('function');
    expect(typeof window.changeLanguage).toBe('function');
    expect(typeof window.downloadBackup).toBe('function');
    expect(typeof window.lookupOFF).toBe('function');
    expect(typeof window.submitToOff).toBe('function');
  });

  it('exposes editingId as getter/setter on window', async () => {
    const { state } = await import('../state.js');
    await import('../app.js');

    window.editingId = 42;
    expect(state.editingId).toBe(42);

    state.editingId = 99;
    expect(window.editingId).toBe(99);
  });
});

const flushPromises = () => new Promise((r) => setTimeout(r, 0));

describe('app.js initialization', () => {
  it('skips focus when search-input element is absent', async () => {
    vi.resetModules();
    document.body.innerHTML = '';

    await import('../app.js');
    await flushPromises();

    // No error thrown means the if (searchInput) false branch executed safely
  });

  it('calls showToast when api /api/weights rejects', async () => {
    vi.resetModules();
    document.body.innerHTML = '';

    const { api } = await import('../state.js');
    api.mockRejectedValueOnce(new Error('network fail'));

    await import('../app.js');
    await flushPromises();

    const { showToast } = await import('../products.js');
    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
  });

  it('populates weightData and SCORE_CFG_MAP from api response', async () => {
    vi.resetModules();
    document.body.innerHTML = '';

    const { api } = await import('../state.js');
    api.mockResolvedValueOnce([
      { field: 'fat', label: 'Fat', desc: 'Fat desc', direction: 'lower' },
      { field: 'sugar', label: 'Sugar', desc: 'Sugar desc', direction: 'lower' },
    ]);

    await import('../app.js');
    await flushPromises();

    const { weightData, SCORE_CFG_MAP } = await import('../settings.js');

    expect(weightData).toHaveLength(2);
    expect(weightData[0]).toEqual({ field: 'fat', label: 'Fat', desc: 'Fat desc', direction: 'lower' });
    expect(weightData[1]).toEqual({ field: 'sugar', label: 'Sugar', desc: 'Sugar desc', direction: 'lower' });

    expect(SCORE_CFG_MAP.fat).toEqual({ label: 'Fat', desc: 'Fat desc', direction: 'lower' });
    expect(SCORE_CFG_MAP.sugar).toEqual({ label: 'Sugar', desc: 'Sugar desc', direction: 'lower' });
  });
});
