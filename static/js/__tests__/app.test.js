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
    initAllFieldSelects: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  initLanguage: vi.fn().mockResolvedValue(),
  changeLanguage: vi.fn(),
  t: vi.fn((k) => k),
}));

vi.mock('../filters.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    toggleFilters: vi.fn(),
    setSort: vi.fn(),
    rerender: vi.fn(),
  };
});

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
  unlockEan: vi.fn(),
  loadData: vi.fn(),
  switchView: vi.fn(),
  setFilter: vi.fn(),
  toggleExpand: vi.fn(),
  onSearchInput: vi.fn(),
  clearSearch: vi.fn(),
  registerProduct: vi.fn(),
  loadEanManager: vi.fn(),
  addEan: vi.fn(),
  deleteEan: vi.fn(),
  setEanPrimary: vi.fn(),
}));

vi.mock('../settings-weights.js', () => ({
  SCORE_CFG_MAP: {},
  weightData: [],
  loadSettings: vi.fn(),
  toggleWeightConfig: vi.fn(),
  removeWeight: vi.fn(),
  addWeightFromDropdown: vi.fn(),
  onWeightDirection: vi.fn(),
  onWeightFormula: vi.fn(),
  onWeightMin: vi.fn(),
  onWeightMax: vi.fn(),
  onWeightSlider: vi.fn(),
  saveWeights: vi.fn(),
}));
vi.mock('../settings-categories.js', () => ({
  updateCategoryLabel: vi.fn(),
  addCategory: vi.fn(),
  deleteCategory: vi.fn(),
}));
vi.mock('../settings-flags.js', () => ({
  addFlag: vi.fn(),
  deleteFlag: vi.fn(),
  updateFlagLabel: vi.fn(),
}));
vi.mock('../settings-pq.js', () => ({
  autosavePq: vi.fn(),
  deletePq: vi.fn(),
  addPq: vi.fn(),
}));
vi.mock('../settings-backup.js', () => ({
  downloadBackup: vi.fn(),
  handleRestore: vi.fn(),
  handleImport: vi.fn(),
  initRestoreDragDrop: vi.fn(),
  toggleSettingsSection: vi.fn(),
  estimateAllPq: vi.fn(),
}));
vi.mock('../settings-ocr.js', () => ({
  loadOcrSettings: vi.fn(),
  saveOcrSettings: vi.fn(),
}));
vi.mock('../settings-off.js', () => ({
  saveOffCredentials: vi.fn(),
  refreshAllFromOff: vi.fn(),
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

vi.mock('../advanced-filters.js', () => ({
  toggleAdvancedFilters: vi.fn(),
}));

vi.mock('../ocr.js', () => ({
  scanIngredients: vi.fn(),
}));

vi.mock('../off-utils.js', () => ({
  validateOffBtn: vi.fn(),
  estimateProteinQuality: vi.fn(),
  updateEstimateBtn: vi.fn(),
}));
vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn(),
}));
vi.mock('../off-picker.js', () => ({
  closeOffPicker: vi.fn(),
  offModalSearch: vi.fn(),
  selectOffResult: vi.fn(),
}));
vi.mock('../off-review.js', () => ({
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

    // Verify ALL functions exposed via Object.assign(window, {...})
    const expectedFunctions = [
      // i18n
      'changeLanguage',
      // filters
      'toggleFilters', 'setSort', 'toggleAdvancedFilters',
      // images
      'triggerImageUpload', 'removeProductImage',
      // products
      'showToast', 'startEdit', 'saveProduct', 'deleteProduct',
      'switchView', 'setFilter', 'toggleExpand',
      'onSearchInput', 'clearSearch', 'registerProduct',
      'loadEanManager', 'addEan', 'deleteEan', 'setEanPrimary',
      'rerender',
      // settings — sections
      'toggleSettingsSection',
      // settings — weights
      'toggleWeightConfig', 'removeWeight', 'addWeightFromDropdown',
      'onWeightDirection', 'onWeightFormula', 'onWeightMin', 'onWeightMax', 'onWeightSlider',
      // settings — categories
      'updateCategoryLabel', 'addCategory', 'deleteCategory',
      // settings — flags
      'addFlag', 'deleteFlag', 'updateFlagLabel',
      // settings — protein quality
      'autosavePq', 'deletePq', 'addPq',
      // settings — backup
      'downloadBackup', 'handleRestore', 'handleImport',
      // settings — OFF credentials
      'saveOffCredentials',
      // settings — OCR
      'saveOcrSettings',
      // settings — bulk operations
      'refreshAllFromOff', 'estimateAllPq',
      // scanner
      'openScanner', 'closeScanner', 'openSearchScanner',
      'closeScanModal', 'scanRegisterNew', 'scanUpdateExisting',
      'closeScanPicker', 'scanPickerSearch', 'scanPickerSelect',
      'scanOffFetch', 'closeScanOffConfirm',
      // openfoodfacts
      'validateOffBtn', 'lookupOFF', 'closeOffPicker', 'offModalSearch',
      'selectOffResult', 'estimateProteinQuality', 'updateEstimateBtn',
      'showOffAddReview', 'closeOffAddReview', 'submitToOff',
      // state access
      'loadData',
    ];
    for (const fn of expectedFunctions) {
      expect(typeof window[fn]).toBe('function');
    }
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

    const { weightData, SCORE_CFG_MAP } = await import('../settings-weights.js');

    expect(weightData).toHaveLength(2);
    expect(weightData[0]).toEqual({ field: 'fat', label: 'Fat', desc: 'Fat desc', direction: 'lower' });
    expect(weightData[1]).toEqual({ field: 'sugar', label: 'Sugar', desc: 'Sugar desc', direction: 'lower' });

    expect(SCORE_CFG_MAP.fat).toEqual({ label: 'Fat', desc: 'Fat desc', direction: 'lower' });
    expect(SCORE_CFG_MAP.sugar).toEqual({ label: 'Sugar', desc: 'Sugar desc', direction: 'lower' });
  });
});

describe('language-select callback', () => {
  it('calls upgradeSelect for #language-select with a changeLanguage callback', async () => {
    vi.resetModules();
    document.body.innerHTML = '';

    const langSelect = document.createElement('select');
    langSelect.id = 'language-select';
    langSelect.className = 'field-select';
    langSelect.innerHTML = '<option value="no">Norsk</option><option value="en">English</option>';
    document.body.appendChild(langSelect);

    await import('../app.js');
    await flushPromises();

    const { upgradeSelect } = await import('../state.js');
    const { changeLanguage } = await import('../i18n.js');

    const langCall = upgradeSelect.mock.calls.find((c) => c[0] === langSelect);
    expect(langCall).toBeDefined();
    expect(typeof langCall[1]).toBe('function');

    // Invoking the callback must call changeLanguage with the chosen value
    langCall[1]('en');
    expect(changeLanguage).toHaveBeenCalledWith('en');
  });

  it('does not throw when #language-select is absent', async () => {
    vi.resetModules();
    document.body.innerHTML = '';

    // No language-select in DOM — should not throw
    await expect(import('../app.js')).resolves.toBeDefined();
    await flushPromises();
  });
});

describe('touchstart range input handler', () => {
  let scrollSpy;

  beforeEach(async () => {
    vi.useFakeTimers();
    vi.resetModules();
    document.body.innerHTML = '';
    const searchInput = document.createElement('input');
    searchInput.id = 'search-input';
    document.body.appendChild(searchInput);
    scrollSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    await import('../app.js');
    await vi.advanceTimersByTimeAsync(0);
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    scrollSpy.mockRestore();
  });

  it('blurs active number input when range is touched', async () => {
    const numberInput = document.createElement('input');
    numberInput.type = 'number';
    document.body.appendChild(numberInput);
    numberInput.focus();

    const range = document.createElement('input');
    range.type = 'range';
    document.body.appendChild(range);

    const blurSpy = vi.spyOn(numberInput, 'blur');

    range.dispatchEvent(new TouchEvent('touchstart', { bubbles: true }));

    expect(blurSpy).toHaveBeenCalled();

    // Advance past all scheduled restores (50, 150, 300ms)
    await vi.advanceTimersByTimeAsync(300);
    expect(scrollSpy).toHaveBeenCalled();
  });

  it('blurs active text input when range is touched', async () => {
    const textInput = document.createElement('input');
    textInput.type = 'text';
    document.body.appendChild(textInput);
    textInput.focus();

    const range = document.createElement('input');
    range.type = 'range';
    document.body.appendChild(range);

    const blurSpy = vi.spyOn(textInput, 'blur');

    range.dispatchEvent(new TouchEvent('touchstart', { bubbles: true }));

    expect(blurSpy).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300);
  });

  it('does nothing when non-range element is touched', () => {
    const numberInput = document.createElement('input');
    numberInput.type = 'number';
    document.body.appendChild(numberInput);
    numberInput.focus();

    const button = document.createElement('button');
    document.body.appendChild(button);

    const blurSpy = vi.spyOn(numberInput, 'blur');

    button.dispatchEvent(new TouchEvent('touchstart', { bubbles: true }));

    expect(blurSpy).not.toHaveBeenCalled();
  });

  it('does nothing when no relevant input is focused', () => {
    const range = document.createElement('input');
    range.type = 'range';
    document.body.appendChild(range);

    scrollSpy.mockClear();
    range.dispatchEvent(new TouchEvent('touchstart', { bubbles: true }));

    // scrollTo should not be called since no relevant input was active
    expect(scrollSpy).not.toHaveBeenCalled();
  });
});
