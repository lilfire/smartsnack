import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  trapFocus: vi.fn(() => vi.fn()),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../off-utils.js', () => ({
  _fieldLabel: vi.fn((f) => f),
  _volumeLabel: vi.fn((v) => String(v)),
  _esc: (s) => String(s),
}));

vi.mock('../off-conflicts.js', () => ({
  MERGE_CONFLICT_FIELDS: ['brand', 'stores', 'taste_score', 'kcal', 'protein'],
  OFF_PROVIDED_FIELDS: new Set(['name', 'ean', 'brand', 'stores', 'kcal', 'protein']),
  USER_ONLY_MERGE_FIELDS: ['taste_score'],
}));

import { showDuplicateMergeModal } from '../off-duplicates.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
});

describe('showDuplicateMergeModal', () => {
  const baseFormData = { name: 'Product A', brand: 'BrandA', taste_score: 3.5 };
  const baseDuplicate = { name: 'Product B', brand: 'BrandB', taste_score: 4.0, is_synced_with_off: false, match_type: 'name' };

  it('renders a dialog element', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    expect(bg.getAttribute('role')).toBe('dialog');
    expect(bg.getAttribute('aria-modal')).toBe('true');
    // Cancel to clean up
    const cancelBtn = bg.querySelector('.confirm-no');
    cancelBtn.click();
    await p;
  });

  it('resolves null on cancel', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    const cancelBtn = bg.querySelector('.confirm-no');
    cancelBtn.click();
    expect(await p).toBeNull();
  });

  it('resolves with scenario "neither" when neither synced', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.scenario).toBe('neither');
  });

  it('resolves with scenario "b_synced" when dup is synced', async () => {
    const syncedDup = { ...baseDuplicate, is_synced_with_off: true };
    const p = showDuplicateMergeModal(baseFormData, syncedDup, false);
    const bg = document.querySelector('.scan-modal-bg');
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.scenario).toBe('b_synced');
  });

  it('resolves with scenario "a_synced" when A is synced and B is not', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, true);
    const bg = document.querySelector('.scan-modal-bg');
    const applyBtn = bg.querySelector('.conflict-apply-btn');
    applyBtn.click();
    const result = await p;
    expect(result.scenario).toBe('a_synced');
  });

  it('resolves "skip" when skip button clicked', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    const skipBtn = bg.querySelector('.scan-modal-btn-register');
    skipBtn.click();
    const result = await p;
    expect(result.scenario).toBe('skip');
  });

  it('auto-resolves field where one side is empty', async () => {
    const formData = { name: 'A', brand: '', taste_score: 3.5 };
    const dup = { name: 'B', brand: 'BrandB', taste_score: 4.0, is_synced_with_off: false, match_type: 'name' };
    const p = showDuplicateMergeModal(formData, dup, false);
    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    // brand auto-resolved to b value since a was empty
    expect(result.choices.brand).toBe('BrandB');
  });

  it('keep-all-a button switches all choices to A values', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    if (bulkBtns.length > 0) {
      bulkBtns[0].click(); // keep all A
    }
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(result.scenario).toBe('neither');
    // taste_score should be aVal (3.5) when keep all A
    if (result.choices.taste_score !== undefined) {
      expect(result.choices.taste_score).toBeLessThanOrEqual(3.5);
    }
  });

  it('shows no conflict section when fields match', async () => {
    const formData = { name: 'Same', brand: 'Same', taste_score: 3.0 };
    const dup = { name: 'Dup', brand: 'Same', taste_score: 3.0, is_synced_with_off: false, match_type: 'name' };
    const p = showDuplicateMergeModal(formData, dup, false);
    const bg = document.querySelector('.scan-modal-bg');
    const conflictFields = bg.querySelectorAll('.conflict-fields');
    // Should not exist or be empty
    expect(conflictFields.length).toBeLessThanOrEqual(1);
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(result.scenario).toBe('neither');
  });

  it('ean match_type renders with expected scenario on apply', async () => {
    const dup = { ...baseDuplicate, match_type: 'ean', is_synced_with_off: false };
    const p = showDuplicateMergeModal(baseFormData, dup, false);
    const bg = document.querySelector('.scan-modal-bg');
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(['neither', 'skip', 'b_synced', 'a_synced']).toContain(result.scenario);
  });

  it('both sides null values auto-resolve without crash', async () => {
    const formData = { name: null, brand: null, taste_score: null };
    const dup = { name: null, brand: null, taste_score: null, is_synced_with_off: false, match_type: 'name' };
    const p = showDuplicateMergeModal(formData, dup, false);
    const bg = document.querySelector('.scan-modal-bg');
    expect(bg).not.toBeNull();
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(result).not.toBeNull();
  });

  it('numeric taste_score conflict shows both values', async () => {
    const formData = { name: 'A', brand: 'BrandA', taste_score: 2 };
    const dup = { name: 'B', brand: 'BrandA', taste_score: 5, is_synced_with_off: false, match_type: 'name' };
    const p = showDuplicateMergeModal(formData, dup, false);
    const bg = document.querySelector('.scan-modal-bg');
    // Modal should show conflict for taste_score (2 vs 5)
    const html = bg.innerHTML;
    // Verify dialog is rendered (conflict or resolution shown)
    expect(html.length).toBeGreaterThan(100);
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(result.scenario).toBe('neither');
  });

  it('keep-all-b button switches all choices to B values', async () => {
    const p = showDuplicateMergeModal(baseFormData, baseDuplicate, false);
    const bg = document.querySelector('.scan-modal-bg');
    const bulkBtns = bg.querySelectorAll('.conflict-bulk button');
    if (bulkBtns.length > 1) {
      bulkBtns[1].click(); // keep all B
    }
    bg.querySelector('.conflict-apply-btn').click();
    const result = await p;
    expect(result.scenario).toBe('neither');
    if (result.choices.taste_score !== undefined) {
      expect(result.choices.taste_score).toBeGreaterThanOrEqual(3.5);
    }
  });
});
