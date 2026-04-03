import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  esc: (s) => String(s),
  showToast: vi.fn(),
  trapFocus: vi.fn(() => vi.fn()),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../off-utils.js', () => ({
  offState: { ctx: { prefix: 'p', productId: null }, reviewResolve: null },
}));

vi.mock('../off-picker.js', () => ({
  closeOffPicker: vi.fn(),
}));

import { showOffAddReview, closeOffAddReview, submitToOff } from '../off-review.js';
import { offState } from '../off-utils.js';
import { closeOffPicker } from '../off-picker.js';
import { api, showToast } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
  offState.ctx = { prefix: 'p', productId: null };
  offState.reviewResolve = null;
});

// ── closeOffAddReview ────────────────────────────────
describe('closeOffAddReview', () => {
  it('removes the review modal if present', () => {
    const bg = document.createElement('div');
    bg.id = 'off-add-review-bg';
    document.body.appendChild(bg);
    closeOffAddReview();
    expect(document.getElementById('off-add-review-bg')).toBeNull();
  });

  it('does nothing if modal not present', () => {
    expect(() => closeOffAddReview()).not.toThrow();
  });

  it('calls reviewResolve if set', () => {
    const resolve = vi.fn();
    offState.reviewResolve = resolve;
    closeOffAddReview();
    expect(resolve).toHaveBeenCalled();
    expect(offState.reviewResolve).toBeNull();
  });
});

// ── showOffAddReview ─────────────────────────────────
describe('showOffAddReview', () => {
  function setupDOM() {
    const fields = ['name', 'brand', 'stores', 'ingredients', 'kcal', 'energy_kj',
      'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'];
    document.body.innerHTML = fields.map((f) => `<input id="p-${f}" value="">`).join('');
  }

  it('renders the review modal', () => {
    setupDOM();
    document.getElementById('p-name').value = 'Test Product';
    showOffAddReview('12345678');
    const bg = document.getElementById('off-add-review-bg');
    expect(bg).not.toBeNull();
    expect(bg.getAttribute('role')).toBe('dialog');
  });

  it('returns a promise', () => {
    setupDOM();
    const result = showOffAddReview('12345678');
    expect(result).toBeInstanceOf(Promise);
  });

  it('shows filled fields section when name is filled', () => {
    setupDOM();
    document.getElementById('p-name').value = 'My Product';
    showOffAddReview('12345678');
    const bg = document.getElementById('off-add-review-bg');
    const body = bg.querySelector('.off-modal-body');
    expect(body.innerHTML).toContain('off_review_filled');
  });

  it('shows empty fields section when some are empty', () => {
    setupDOM();
    document.getElementById('p-name').value = 'Test';
    showOffAddReview('12345678');
    const bg = document.getElementById('off-add-review-bg');
    expect(bg.querySelector('.off-modal-body').innerHTML).toContain('off_review_empty');
  });

  it('disables submit when name is missing', () => {
    setupDOM();
    showOffAddReview('12345678');
    const submitBtn = document.getElementById('off-submit-btn');
    expect(submitBtn.style.pointerEvents).toBe('none');
  });

  it('closes on background click when clicking bg directly', () => {
    setupDOM();
    showOffAddReview('12345678');
    const bg = document.getElementById('off-add-review-bg');
    bg.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    // If target === bg, it closes
    expect(document.getElementById('off-add-review-bg')).toBeNull();
  });

  it('calls previous reviewResolve if already set', () => {
    setupDOM();
    const resolve = vi.fn();
    offState.reviewResolve = resolve;
    showOffAddReview('12345678');
    expect(resolve).toHaveBeenCalled();
  });

  it('uses prefixOverride when provided', () => {
    const altFields = ['name', 'brand', 'stores', 'ingredients', 'kcal', 'energy_kj',
      'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'];
    document.body.innerHTML = altFields.map((f) => `<input id="alt-${f}" value="">`).join('');
    document.getElementById('alt-name').value = 'Alt Product';
    showOffAddReview('12345678', 'alt');
    const bg = document.getElementById('off-add-review-bg');
    expect(bg).not.toBeNull();
  });
});

// ── submitToOff ──────────────────────────────────────
describe('submitToOff', () => {
  function setupDOM(name = 'Chicken Breast', weight = '200', portion = '100') {
    document.body.innerHTML = `
      <input id="p-name" value="${name}">
      <input id="p-brand" value="FoodCo">
      <input id="p-stores" value="">
      <input id="p-ingredients" value="">
      <input id="p-kcal" value="120">
      <input id="p-energy_kj" value="">
      <input id="p-fat" value="">
      <input id="p-saturated_fat" value="">
      <input id="p-carbs" value="">
      <input id="p-sugar" value="">
      <input id="p-protein" value="25">
      <input id="p-fiber" value="">
      <input id="p-salt" value="">
      <input id="p-weight" value="${weight}">
      <input id="p-portion" value="${portion}">
      <button id="off-submit-btn"></button>
      <div id="off-add-review-bg"></div>`;
  }

  it('calls api and shows success toast on success', async () => {
    setupDOM();
    api.mockResolvedValue({});
    await submitToOff('12345678');
    expect(api).toHaveBeenCalledWith('/api/off/add-product', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
    expect(closeOffPicker).toHaveBeenCalled();
  });

  it('appends unit to weight/portion in submitted body', async () => {
    setupDOM('Product', '250', '50');
    api.mockResolvedValue({});
    await submitToOff('12345678');
    const body = JSON.parse(api.mock.calls[0][1].body);
    expect(body.quantity).toBe('250 g');
    expect(body.serving_size).toBe('50 g');
  });

  it('shows error toast on API failure', async () => {
    setupDOM();
    api.mockRejectedValue(new Error('toast_network_error'));
    await submitToOff('12345678');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('uses prefix override', async () => {
    const altFields = ['name', 'brand', 'stores', 'ingredients', 'kcal', 'energy_kj',
      'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion'];
    document.body.innerHTML = altFields.map((f) => `<input id="q-${f}" value="">`).join('')
      + '<button id="off-submit-btn"></button>';
    document.getElementById('q-name').value = 'Alt';
    api.mockResolvedValue({});
    await submitToOff('12345678', 'q');
    expect(api).toHaveBeenCalled();
  });
});
