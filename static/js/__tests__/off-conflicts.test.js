import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  trapFocus: vi.fn(() => vi.fn()),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../off-utils.js', () => ({
  _fieldLabel: vi.fn((f) => f),
  _esc: (s) => String(s),
}));

import {
  MERGE_CONFLICT_FIELDS,
  OFF_PROVIDED_FIELDS,
  USER_ONLY_MERGE_FIELDS,
  showEditDuplicateModal,
  showMergeConflictModal,
  showScanDuplicateModal,
} from '../off-conflicts.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
});

// ── Constants ────────────────────────────────────────
describe('MERGE_CONFLICT_FIELDS', () => {
  it('is an array with expected fields', () => {
    expect(Array.isArray(MERGE_CONFLICT_FIELDS)).toBe(true);
    expect(MERGE_CONFLICT_FIELDS).toContain('brand');
    expect(MERGE_CONFLICT_FIELDS).toContain('kcal');
    expect(MERGE_CONFLICT_FIELDS).toContain('protein');
    expect(MERGE_CONFLICT_FIELDS).toContain('taste_score');
  });
});

describe('OFF_PROVIDED_FIELDS', () => {
  it('is a Set containing OFF fields', () => {
    expect(OFF_PROVIDED_FIELDS instanceof Set).toBe(true);
    expect(OFF_PROVIDED_FIELDS.has('name')).toBe(true);
    expect(OFF_PROVIDED_FIELDS.has('ean')).toBe(true);
    expect(OFF_PROVIDED_FIELDS.has('kcal')).toBe(true);
    expect(OFF_PROVIDED_FIELDS.has('taste_score')).toBe(false);
  });
});

describe('USER_ONLY_MERGE_FIELDS', () => {
  it('excludes OFF provided fields', () => {
    for (const f of USER_ONLY_MERGE_FIELDS) {
      expect(OFF_PROVIDED_FIELDS.has(f)).toBe(false);
    }
  });

  it('contains user-only fields like taste_score', () => {
    expect(USER_ONLY_MERGE_FIELDS).toContain('taste_score');
  });
});

// ── showEditDuplicateModal ───────────────────────────
describe('showEditDuplicateModal', () => {
  it('renders a dialog and resolves "delete" for synced duplicate', async () => {
    const dup = { is_synced_with_off: true, match_type: 'ean', name: 'Dup Product' };
    const p = showEditDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    expect(bg.getAttribute('role')).toBe('dialog');
    // Click the delete/register button
    const yesBtn = bg.querySelector('.confirm-yes');
    expect(yesBtn).not.toBeNull();
    yesBtn.click();
    const result = await p;
    expect(result).toBe('delete');
    expect(document.body.contains(bg)).toBe(false);
  });

  it('shows merge button for non-synced duplicate', async () => {
    const dup = { is_synced_with_off: false, match_type: 'name', name: 'Another' };
    const p = showEditDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    const mergeBtn = bg.querySelector('.confirm-yes');
    expect(mergeBtn.textContent).toContain('duplicate_action_merge_into');
    mergeBtn.click();
    const result = await p;
    expect(result).toBe('merge');
  });

  it('resolves "cancel" when cancel is clicked', async () => {
    const dup = { is_synced_with_off: false, match_type: 'name', name: 'Test' };
    const p = showEditDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    const cancelBtn = bg.querySelector('.confirm-no');
    cancelBtn.click();
    expect(await p).toBe('cancel');
  });
});

// ── showMergeConflictModal ───────────────────────────
describe('showMergeConflictModal', () => {
  it('resolves immediately with empty object when no conflicts', async () => {
    const formData = { brand: 'Acme' };
    const dup = { brand: 'Acme' };
    const result = await showMergeConflictModal(formData, dup, null);
    expect(result).toEqual({});
  });

  it('auto-resolves fields provided by OFF', async () => {
    const formData = { kcal: 100 };
    const dup = { kcal: 200 };
    const offAppliedFields = new Set(['kcal']);
    const result = await showMergeConflictModal(formData, dup, offAppliedFields);
    expect(result.kcal).toBe(100);
  });

  it('returns null on cancel', async () => {
    const formData = { brand: 'A' };
    const dup = { name: 'Dup', brand: 'B' };
    const p = showMergeConflictModal(formData, dup, null);
    const bg = document.querySelector('.scan-modal-bg');
    const cancelBtn = bg.querySelector('.confirm-no');
    cancelBtn.click();
    expect(await p).toBeNull();
  });

  it('renders conflict rows for conflicting fields', async () => {
    const formData = { brand: 'FormBrand' };
    const dup = { name: 'Dup', brand: 'DupBrand' };
    const p = showMergeConflictModal(formData, dup, null);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg.querySelectorAll('.conflict-option').length).toBeGreaterThan(0);
    // Apply the modal
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    // Default is formVal
    expect(result.brand).toBe('FormBrand');
  });

  it('keep-all-other button switches choices to dup values', async () => {
    const formData = { brand: 'A' };
    const dup = { name: 'Dup', brand: 'B' };
    const p = showMergeConflictModal(formData, dup, null);
    const bg = document.querySelector('.scan-modal-bg');
    const keepAllOther = bg.querySelector('.conflict-bulk button:last-child');
    keepAllOther.click();
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.brand).toBe('B');
  });

  it('keep-all-current button keeps form values', async () => {
    const formData = { brand: 'A' };
    const dup = { name: 'Dup', brand: 'B' };
    const p = showMergeConflictModal(formData, dup, null);
    const bg = document.querySelector('.scan-modal-bg');
    const keepAllCurrent = bg.querySelector('.conflict-bulk button:first-child');
    keepAllCurrent.click();
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.brand).toBe('A');
  });

  it('clicking dup option changes choice for that field', async () => {
    const formData = { brand: 'A' };
    const dup = { name: 'Dup', brand: 'B' };
    const p = showMergeConflictModal(formData, dup, null);
    const bg = document.querySelector('.scan-modal-bg');
    // Second option is the dup value
    const opts = bg.querySelectorAll('.conflict-option');
    opts[1].click();
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.brand).toBe('B');
  });
});

// ── showScanDuplicateModal ────────────────────────────
describe('showScanDuplicateModal', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('renders a dialog with aria-modal for synced duplicate', async () => {
    const dup = { is_synced_with_off: true, match_type: 'ean', name: 'SyncedProd' };
    const p = showScanDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    expect(bg.getAttribute('role')).toBe('dialog');
    expect(bg.getAttribute('aria-modal')).toBe('true');
    // Synced duplicate: only an OK button (confirm-yes class)
    const okBtn = bg.querySelector('.confirm-yes');
    expect(okBtn).not.toBeNull();
    okBtn.click();
    expect(await p).toBe('cancel');
  });

  it('uses synced message key for synced duplicate', async () => {
    const { t } = await import('../i18n.js');
    const dup = { is_synced_with_off: true, match_type: 'ean', name: 'A' };
    showScanDuplicateModal(dup);
    // The modal text used duplicate_found_synced key
    expect(t).toHaveBeenCalledWith('duplicate_found_synced', expect.objectContaining({ name: 'A' }));
    document.querySelector('.scan-modal-bg').querySelector('.confirm-yes').click();
  });

  it('resolves "overwrite" when merge button clicked for unsynced duplicate', async () => {
    const dup = { is_synced_with_off: false, match_type: 'name', name: 'UnsyncedProd' };
    const p = showScanDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    const mergeBtn = bg.querySelector('.confirm-yes');
    expect(mergeBtn).not.toBeNull();
    mergeBtn.click();
    expect(await p).toBe('overwrite');
    expect(document.body.contains(bg)).toBe(false);
  });

  it('resolves "create_new" when create_new button clicked for unsynced duplicate', async () => {
    const dup = { is_synced_with_off: false, match_type: 'barcode', name: 'Dup2' };
    const p = showScanDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    const btns = bg.querySelectorAll('.scan-modal-btn-register');
    // First btn = merge (confirm-yes), second = create_new
    const createNewBtn = Array.from(btns).find((b) => !b.classList.contains('confirm-yes'));
    expect(createNewBtn).not.toBeNull();
    createNewBtn.click();
    expect(await p).toBe('create_new');
  });

  it('resolves "cancel" when cancel button clicked for unsynced duplicate', async () => {
    const dup = { is_synced_with_off: false, match_type: 'ean', name: 'Dup3' };
    const p = showScanDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    const cancelBtn = bg.querySelector('.confirm-no');
    expect(cancelBtn).not.toBeNull();
    cancelBtn.click();
    expect(await p).toBe('cancel');
  });

  it('uses unsynced message key for unsynced duplicate', async () => {
    const { t } = await import('../i18n.js');
    t.mockClear();
    const dup = { is_synced_with_off: false, match_type: 'name', name: 'B' };
    showScanDuplicateModal(dup);
    expect(t).toHaveBeenCalledWith('duplicate_found_unsynced', expect.objectContaining({ name: 'B' }));
    document.querySelector('.confirm-no').click();
  });

  it('removes modal from DOM after resolution', async () => {
    const dup = { is_synced_with_off: false, match_type: 'ean', name: 'Dup4' };
    const p = showScanDuplicateModal(dup);
    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.confirm-no').click();
    await p;
    expect(document.querySelector('.scan-modal-bg')).toBeNull();
  });
});
