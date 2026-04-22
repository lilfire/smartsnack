import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
    cachedStats: { total: 5, types: 2, categories: [] },
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
  };
  return {
    state: _state,
    api: vi.fn().mockResolvedValue({}),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockResolvedValue({ total: 5, types: 2 }),
    NUTRI_IDS: ['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'],
    showConfirmModal: vi.fn().mockResolvedValue(true),
    showToast: vi.fn(),
    upgradeSelect: vi.fn(),
    announceStatus: vi.fn(),
    trapFocus: vi.fn(() => vi.fn()),
    esc: (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
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
    buildTypeSelect: vi.fn(),
  };
});

vi.mock('../render.js', () => ({
  renderResults: vi.fn(),
  getFlagConfig: vi.fn(() => ({})),
}));

vi.mock('../settings-weights.js', () => ({
  loadSettings: vi.fn(),
}));

vi.mock('../off-utils.js', () => ({
  isValidEan: vi.fn((v) => /^\d{8,13}$/.test(v || '')),
  validateOffBtn: vi.fn(),
}));
vi.mock('../off-conflicts.js', () => ({
  showMergeConflictModal: vi.fn(),
  showEditDuplicateModal: vi.fn(),
}));
vi.mock('../off-duplicates.js', () => ({
  showDuplicateMergeModal: vi.fn(),
}));
vi.mock('../off-review.js', () => ({
  showOffAddReview: vi.fn(),
  closeOffAddReview: vi.fn(),
  submitToOff: vi.fn(),
}));
vi.mock('../off-api.js', () => ({
  lookupOFF: vi.fn().mockResolvedValue({}),
}));

import { loadEanManager, addEan, deleteEan, setEanPrimary } from '../ean-manager.js';
import { api, showToast } from '../state.js';
import { lookupOFF } from '../off-api.js';

const PRODUCT_ID = 42;
// Default fixtures: no EAN is synced with OFF
const MOCK_EANS_TWO = [
  { id: 1, ean: '7038010069307', is_primary: true, synced_with_off: false },
  { id: 2, ean: '5000000000001', is_primary: false, synced_with_off: false },
];
const MOCK_EANS_THREE = [
  { id: 1, ean: '7038010069307', is_primary: true, synced_with_off: false },
  { id: 2, ean: '5000000000001', is_primary: false, synced_with_off: false },
  { id: 3, ean: '8901234567890', is_primary: false, synced_with_off: false },
];
// Primary EAN is OFF-synced; secondary is not
const MOCK_EANS_PRIMARY_SYNCED = [
  { id: 1, ean: '7038010069307', is_primary: true, synced_with_off: true },
  { id: 2, ean: '5000000000001', is_primary: false, synced_with_off: false },
];
// Secondary EAN is OFF-synced; primary is not
const MOCK_EANS_SECONDARY_SYNCED = [
  { id: 1, ean: '7038010069307', is_primary: true, synced_with_off: false },
  { id: 2, ean: '5000000000001', is_primary: false, synced_with_off: true },
];
// Both EANs synced
const MOCK_EANS_BOTH_SYNCED = [
  { id: 1, ean: '7038010069307', is_primary: true, synced_with_off: true },
  { id: 2, ean: '5000000000001', is_primary: false, synced_with_off: true },
];

function setupDom() {
  document.body.innerHTML = '';
  const container = document.createElement('div');
  container.id = 'ean-manager-' + PRODUCT_ID;
  document.body.appendChild(container);
  const hiddenEan = document.createElement('input');
  hiddenEan.id = 'ed-ean';
  document.body.appendChild(hiddenEan);
}

beforeEach(() => {
  vi.clearAllMocks();
  setupDom();
});

afterEach(() => {
  document.body.innerHTML = '';
});

// ── OFF Badge Rendering ─────────────────────────────

describe('OFF badge rendering', () => {
  it('renders .ean-badge-off only on rows with synced_with_off=true', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const badges = document.querySelectorAll('.ean-badge-off');
    expect(badges.length).toBe(1);
    expect(badges[0].textContent).toBe('OFF');
    const items = document.querySelectorAll('.ean-item');
    expect(items[0].querySelector('.ean-badge-off')).not.toBeNull();
    expect(items[1].querySelector('.ean-badge-off')).toBeNull();
  });

  it('does not render .ean-badge-off when no EAN is synced', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_THREE);
    await loadEanManager(PRODUCT_ID);

    expect(document.querySelectorAll('.ean-badge-off').length).toBe(0);
  });

  it('renders badge on secondary EAN when only secondary is synced', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_SECONDARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    expect(items[0].querySelector('.ean-badge-off')).toBeNull();
    expect(items[1].querySelector('.ean-badge-off')).not.toBeNull();
  });
});

// ── Per-EAN OFF Fetch Button ────────────────────────

describe('Per-EAN OFF fetch button', () => {
  it('every non-synced EAN row renders .btn-ean-off (primary + secondaries)', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_THREE);
    await loadEanManager(PRODUCT_ID);

    const offBtns = document.querySelectorAll('.btn-ean-off');
    expect(offBtns.length).toBe(3);
    offBtns.forEach((btn) => {
      expect(btn.dataset.eanAction).toBe('fetch-ean-off');
    });
  });

  it('primary EAN row renders .btn-ean-off when not synced', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    expect(items[0].querySelector('.btn-ean-off')).not.toBeNull();
    expect(items[1].querySelector('.btn-ean-off')).not.toBeNull();
  });

  it('synced primary EAN does NOT render .btn-ean-off (shows unlock instead)', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    expect(items[0].querySelector('.btn-ean-off')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="unsync-ean"]')).not.toBeNull();
  });

  it('synced secondary EAN does NOT render .btn-ean-off', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_SECONDARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    expect(items[1].querySelector('.btn-ean-off')).toBeNull();
  });
});

// ── Per-EAN sync state ──────────────────────────────

describe('Per-EAN sync state', () => {
  it('all EANs unsynced: every row has delete button (>1 EAN)', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const deleteBtns = document.querySelectorAll('[data-ean-action="delete-ean"]');
    expect(deleteBtns.length).toBe(2);
  });

  it('all EANs unsynced: only secondaries get set-primary; every row gets fetch-OFF', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const setPrimaryBtns = document.querySelectorAll('[data-ean-action="set-primary"]');
    expect(setPrimaryBtns.length).toBe(1);
    expect(setPrimaryBtns[0].dataset.eanId).toBe('2');
    const offBtns = document.querySelectorAll('.btn-ean-off');
    expect(offBtns.length).toBe(2);
    expect(Array.from(offBtns).map((b) => b.dataset.eanId).sort()).toEqual(['1', '2']);
  });

  it('all EANs unsynced: no per-row unlock buttons rendered', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    expect(document.querySelectorAll('[data-ean-action="unsync-ean"]').length).toBe(0);
  });

  it('synced row hides delete / set-primary / fetch-OFF and shows unlock', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    // Synced primary row: only the unlock button + OFF badge
    expect(items[0].querySelector('[data-ean-action="delete-ean"]')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="set-primary"]')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="fetch-ean-off"]')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="unsync-ean"]')).not.toBeNull();
    expect(items[0].querySelector('.ean-badge-off')).not.toBeNull();
  });

  it('non-synced secondary in a mixed product still has its normal buttons', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    // Secondary (non-synced) row: delete + set-primary + fetch-OFF
    expect(items[1].querySelector('[data-ean-action="delete-ean"]')).not.toBeNull();
    expect(items[1].querySelector('[data-ean-action="set-primary"]')).not.toBeNull();
    expect(items[1].querySelector('[data-ean-action="fetch-ean-off"]')).not.toBeNull();
    expect(items[1].querySelector('[data-ean-action="unsync-ean"]')).toBeNull();
  });

  it('non-synced primary in a mixed product has fetch-OFF (but no set-primary on itself)', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_SECONDARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const items = document.querySelectorAll('.ean-item');
    // Primary (non-synced) row: fetch-OFF + delete (len>1), but no set-primary on itself
    expect(items[0].querySelector('[data-ean-action="fetch-ean-off"]')).not.toBeNull();
    expect(items[0].querySelector('[data-ean-action="set-primary"]')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="delete-ean"]')).not.toBeNull();
  });

  it('all EANs synced: every row has only the unlock button', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_BOTH_SYNCED);
    await loadEanManager(PRODUCT_ID);

    expect(document.querySelectorAll('[data-ean-action="delete-ean"]').length).toBe(0);
    expect(document.querySelectorAll('[data-ean-action="set-primary"]').length).toBe(0);
    expect(document.querySelectorAll('[data-ean-action="fetch-ean-off"]').length).toBe(0);
    expect(document.querySelectorAll('[data-ean-action="unsync-ean"]').length).toBe(2);
  });

  it('does not render .ean-lock-notice in any state', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_BOTH_SYNCED);
    await loadEanManager(PRODUCT_ID);

    expect(document.querySelector('.ean-lock-notice')).toBeNull();
  });

  it('add-EAN input is always rendered, even when all EANs are synced', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_BOTH_SYNCED);
    await loadEanManager(PRODUCT_ID);

    expect(document.getElementById('ean-add-input-' + PRODUCT_ID)).not.toBeNull();
  });

  it('clicking add-EAN with a synced product still POSTs the new EAN', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '99887766554';

    api.mockResolvedValueOnce({ id: 3, ean: '99887766554', is_primary: false });
    api.mockResolvedValueOnce([
      ...MOCK_EANS_PRIMARY_SYNCED,
      { id: 3, ean: '99887766554', is_primary: false, synced_with_off: false },
    ]);

    document.querySelector('[data-ean-action="add-ean"]').click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        '/api/products/' + PRODUCT_ID + '/eans',
        { method: 'POST', body: JSON.stringify({ ean: '99887766554' }) }
      );
    });
  });

  it('after add-EAN, the existing synced row stays locked (the original bug)', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    const input = document.getElementById('ean-add-input-' + PRODUCT_ID);
    input.value = '99887766554';

    api.mockResolvedValueOnce({ id: 3, ean: '99887766554', is_primary: false });
    api.mockResolvedValueOnce([
      ...MOCK_EANS_PRIMARY_SYNCED,
      { id: 3, ean: '99887766554', is_primary: false, synced_with_off: false },
    ]);

    document.querySelector('[data-ean-action="add-ean"]').click();

    await vi.waitFor(() => {
      const items = document.querySelectorAll('.ean-item');
      expect(items.length).toBe(3);
    });

    const items = document.querySelectorAll('.ean-item');
    // Synced primary stays locked: no delete button on its row
    expect(items[0].querySelector('[data-ean-action="delete-ean"]')).toBeNull();
    expect(items[0].querySelector('[data-ean-action="unsync-ean"]')).not.toBeNull();
    // The newly added third row is freely editable
    expect(items[2].querySelector('[data-ean-action="delete-ean"]')).not.toBeNull();
  });
});

// ── Unsync EAN ──────────────────────────────────────

describe('Unsync EAN', () => {
  it('clicking unlock button calls POST .../eans/<id>/unsync', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);
    api.mockClear();

    api.mockResolvedValueOnce({ ok: true });
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    document.querySelector('[data-ean-action="unsync-ean"]').click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        '/api/products/' + PRODUCT_ID + '/eans/1/unsync',
        { method: 'POST' }
      );
    });
  });

  it('after unsync, the row becomes editable in the rerender', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_PRIMARY_SYNCED);
    await loadEanManager(PRODUCT_ID);

    api.mockResolvedValueOnce({ ok: true });
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    document.querySelector('[data-ean-action="unsync-ean"]').click();

    await vi.waitFor(() => {
      const items = document.querySelectorAll('.ean-item');
      expect(items[0].querySelector('[data-ean-action="unsync-ean"]')).toBeNull();
      expect(items[0].querySelector('.ean-badge-off')).toBeNull();
    });
  });
});

// ── Error Handling ──────────────────────────────────

describe('Error handling', () => {
  it('loadEanManager shows error when API fails', async () => {
    api.mockRejectedValueOnce(new Error('Network error'));
    await loadEanManager(PRODUCT_ID);

    const container = document.getElementById('ean-manager-' + PRODUCT_ID);
    expect(container.querySelector('.field-error')).not.toBeNull();
  });

  it('loadEanManager exits early when container is missing', async () => {
    document.body.innerHTML = '';
    await loadEanManager(PRODUCT_ID);
    expect(api).not.toHaveBeenCalled();
  });
});

// ── _fetchEanOff click behaviour ─────────────────────

describe('_fetchEanOff click behaviour', () => {
  beforeEach(() => {
    window._pendingOFFEan = null;
    document.getElementById('ed-ean').value = '7038010069307'; // primary
  });

  it('does NOT promote secondary EAN to primary on fetch click', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);
    api.mockClear();

    const offBtn = document.querySelector(
      '[data-ean-action="fetch-ean-off"][data-ean-id="2"]'
    );
    offBtn.click();
    await Promise.resolve(); await Promise.resolve();

    const setPrimaryCall = api.mock.calls.find(c => c[0].includes('set-primary'));
    expect(setPrimaryCall).toBeUndefined();
  });

  it('does NOT mutate #ed-ean when fetching OFF for a secondary', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const offBtn = document.querySelector(
      '[data-ean-action="fetch-ean-off"][data-ean-id="2"]'
    );
    offBtn.click();
    await Promise.resolve(); await Promise.resolve();

    // #ed-ean must still point at the primary so saveProduct does not swap it
    expect(document.getElementById('ed-ean').value).toBe('7038010069307');
  });

  it('stashes the targeted EAN on window._pendingOFFEan for saveProduct', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);

    const offBtn = document.querySelector(
      '[data-ean-action="fetch-ean-off"][data-ean-id="2"]'
    );
    offBtn.click();
    await Promise.resolve(); await Promise.resolve();

    expect(window._pendingOFFEan).toBe('5000000000001');
  });

  it('calls lookupOFF with the secondary EAN in opts.ean', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);
    lookupOFF.mockClear();

    const offBtn = document.querySelector(
      '[data-ean-action="fetch-ean-off"][data-ean-id="2"]'
    );
    offBtn.click();
    await Promise.resolve(); await Promise.resolve();

    expect(lookupOFF).toHaveBeenCalledTimes(1);
    expect(lookupOFF).toHaveBeenCalledWith(
      'ed',
      PRODUCT_ID,
      { ean: '5000000000001' }
    );
  });

  it('calls lookupOFF with the primary EAN when fetching from the primary row', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID);
    lookupOFF.mockClear();

    const offBtn = document.querySelector(
      '[data-ean-action="fetch-ean-off"][data-ean-id="1"]'
    );
    offBtn.click();
    await Promise.resolve(); await Promise.resolve();

    expect(lookupOFF).toHaveBeenCalledWith(
      'ed',
      PRODUCT_ID,
      { ean: '7038010069307' }
    );
    expect(window._pendingOFFEan).toBe('7038010069307');
  });
});

// ── Event delegation in rendered EAN list ────────────

describe('EAN manager event delegation', () => {
  it('clicking set-primary button calls setEanPrimary', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    const btn = document.querySelector('[data-ean-action="set-primary"]');
    expect(btn).not.toBeNull();
    btn.click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        '/api/products/' + PRODUCT_ID + '/eans/2/set-primary',
        { method: 'PATCH' }
      );
    });
  });

  it('clicking delete button calls deleteEan', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    api.mockResolvedValueOnce({});
    api.mockResolvedValueOnce([{ id: 1, ean: '7038010069307', is_primary: true }]);

    // First delete button is for the primary EAN (id=1)
    const btn = document.querySelector('[data-ean-action="delete-ean"]');
    expect(btn).not.toBeNull();
    btn.click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        '/api/products/' + PRODUCT_ID + '/eans/1',
        { method: 'DELETE' }
      );
    });
  });

  it('clicking fetch-ean-off button triggers lookupOFF with the EAN value', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    const offBtn = document.querySelector('[data-ean-action="fetch-ean-off"]');
    expect(offBtn).not.toBeNull();
    offBtn.click();

    await vi.waitFor(() => {
      expect(lookupOFF).toHaveBeenCalledWith('ed', PRODUCT_ID, { ean: offBtn.dataset.eanValue });
    });
  });

  it('clicking area without data-ean-action does nothing', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    const container = document.getElementById('ean-manager-' + PRODUCT_ID);
    container.click();

    expect(api).not.toHaveBeenCalled();
  });

  it('pressing Enter in add input triggers addEan', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    const addInput = document.getElementById('ean-add-input-' + PRODUCT_ID);
    expect(addInput).not.toBeNull();
    addInput.value = '5000000000001';

    api.mockResolvedValueOnce({ id: 3, ean: '5000000000001', is_primary: false });
    api.mockResolvedValueOnce(MOCK_EANS_TWO);

    const enterEvent = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
    addInput.dispatchEvent(enterEvent);

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        '/api/products/' + PRODUCT_ID + '/eans',
        { method: 'POST', body: JSON.stringify({ ean: '5000000000001' }) }
      );
    });
    // Wait for addEan's full async chain (loadEanManager reload + showToast)
    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledTimes(2);
    });
  });

  it('pressing non-Enter key in add input does not trigger addEan', async () => {
    api.mockResolvedValueOnce(MOCK_EANS_TWO);
    await loadEanManager(PRODUCT_ID, false);
    api.mockClear();

    const addInput = document.getElementById('ean-add-input-' + PRODUCT_ID);
    expect(addInput).not.toBeNull();
    addInput.value = '5000000000001';

    const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true });
    addInput.dispatchEvent(tabEvent);

    expect(api).not.toHaveBeenCalled();
  });
});
