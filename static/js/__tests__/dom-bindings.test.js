// ── Tests for dom-bindings.js (LSO-1783) ─────────────────────────
// The inline on*="" attributes in templates/partials/*.html were replaced
// by addEventListener bindings so the CSP can drop 'unsafe-inline' from
// script-src. These tests verify every binding dispatches to the right
// module function.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../i18n.js', () => ({
  t: vi.fn((key, params) => (params && params.val != null ? `${key}:${params.val}` : key)),
}));
vi.mock('../products.js', () => ({
  switchView: vi.fn(),
  onSearchInput: vi.fn(),
  clearSearch: vi.fn(),
  registerProduct: vi.fn(),
}));
vi.mock('../filters.js', () => ({ toggleFilters: vi.fn() }));
vi.mock('../advanced-filters.js', () => ({ toggleAdvancedFilters: vi.fn() }));
vi.mock('../scanner.js', () => ({ openScanner: vi.fn(), openSearchScanner: vi.fn() }));
vi.mock('../off-utils.js', () => ({
  validateOffBtn: vi.fn(),
  estimateProteinQuality: vi.fn(),
  updateEstimateBtn: vi.fn(),
}));
vi.mock('../off-api.js', () => ({ lookupOFF: vi.fn() }));
vi.mock('../ocr.js', () => ({ scanIngredients: vi.fn(), scanNutrition: vi.fn() }));
vi.mock('../images.js', () => ({ captureProductImage: vi.fn(), clearPendingImage: vi.fn() }));
vi.mock('../settings-categories.js', () => ({ addCategory: vi.fn() }));
vi.mock('../settings-flags.js', () => ({ addFlag: vi.fn() }));
vi.mock('../settings-pq.js', () => ({ addPq: vi.fn() }));
vi.mock('../settings-backup.js', () => ({
  downloadBackup: vi.fn(),
  handleRestore: vi.fn(),
  handleImport: vi.fn(),
  toggleSettingsSection: vi.fn(),
  estimateAllPq: vi.fn(),
}));
vi.mock('../settings-ocr.js', () => ({ saveOcrSettings: vi.fn() }));
vi.mock('../settings-off.js', () => ({ saveOffCredentials: vi.fn(), refreshAllFromOff: vi.fn() }));

import { initDomBindings } from '../dom-bindings.js';
import { t } from '../i18n.js';
import { switchView, onSearchInput, clearSearch, registerProduct } from '../products.js';
import { toggleFilters } from '../filters.js';
import { toggleAdvancedFilters } from '../advanced-filters.js';
import { openScanner, openSearchScanner } from '../scanner.js';
import { validateOffBtn, estimateProteinQuality, updateEstimateBtn } from '../off-utils.js';
import { lookupOFF } from '../off-api.js';
import { scanIngredients, scanNutrition } from '../ocr.js';
import { captureProductImage, clearPendingImage } from '../images.js';
import { addCategory } from '../settings-categories.js';
import { addFlag } from '../settings-flags.js';
import { addPq } from '../settings-pq.js';
import {
  downloadBackup, handleRestore, handleImport,
  toggleSettingsSection, estimateAllPq,
} from '../settings-backup.js';
import { saveOcrSettings } from '../settings-ocr.js';
import { saveOffCredentials, refreshAllFromOff } from '../settings-off.js';

function click(id) {
  document.getElementById(id).dispatchEvent(new MouseEvent('click', { bubbles: true }));
}

function input(id) {
  document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true }));
}

function change(id) {
  document.getElementById(id).dispatchEvent(new Event('change', { bubbles: true }));
}

function keydown(el, key) {
  const e = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  el.dispatchEvent(e);
  return e;
}

afterEach(() => {
  document.body.innerHTML = '';
  vi.clearAllMocks();
});

describe('initDomBindings — resilience', () => {
  it('does not throw when no bound elements exist in the DOM', () => {
    document.body.innerHTML = '<div></div>';
    expect(() => initDomBindings()).not.toThrow();
  });
});

describe('initDomBindings — header nav tabs', () => {
  it('routes tab clicks to switchView with the tab data-view value', () => {
    document.body.innerHTML = `
      <button class="nav-tab" id="tab-search" data-view="search"></button>
      <button class="nav-tab" id="tab-register" data-view="register"></button>
      <button class="nav-tab" id="tab-settings" data-view="settings"></button>`;
    initDomBindings();
    click('tab-register');
    expect(switchView).toHaveBeenCalledTimes(1);
    expect(switchView).toHaveBeenCalledWith('register');
    click('tab-settings');
    expect(switchView).toHaveBeenCalledWith('settings');
    click('tab-search');
    expect(switchView).toHaveBeenCalledWith('search');
  });
});

describe('initDomBindings — search view', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <input id="search-input">
      <button id="search-clear"></button>
      <button id="btn-scan-search"></button>
      <button id="adv-filter-toggle"></button>
      <button id="filter-toggle"></button>`;
    initDomBindings();
  });

  it('search input dispatches onSearchInput', () => {
    input('search-input');
    expect(onSearchInput).toHaveBeenCalledTimes(1);
  });

  it('clear button dispatches clearSearch', () => {
    click('search-clear');
    expect(clearSearch).toHaveBeenCalledTimes(1);
  });

  it('scan button opens the search scanner', () => {
    click('btn-scan-search');
    expect(openSearchScanner).toHaveBeenCalledTimes(1);
  });

  it('filter toggles dispatch to their modules', () => {
    click('adv-filter-toggle');
    expect(toggleAdvancedFilters).toHaveBeenCalledTimes(1);
    click('filter-toggle');
    expect(toggleFilters).toHaveBeenCalledTimes(1);
  });
});

describe('initDomBindings — register view', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <input id="f-ean">
      <button id="f-scan-btn"></button>
      <button id="f-off-btn"></button>
      <input id="f-name">
      <span id="f-name-error" style="display:block"></span>
      <button id="f-ocr-btn"></button>
      <textarea id="f-ingredients"></textarea>
      <button id="f-ocr-nutri-btn"></button>
      <span id="smak-label-text"></span>
      <input type="range" id="f-smak" min="0" max="6" step="0.5" value="3" aria-valuenow="3">
      <span id="smak-val">3</span>
      <button id="f-estimate-btn"></button>
      <button id="f-image-btn"></button>
      <button id="f-image-remove"></button>
      <button id="btn-submit"></button>`;
    initDomBindings();
  });

  it('EAN input validates the OFF fetch button', () => {
    input('f-ean');
    expect(validateOffBtn).toHaveBeenCalledWith('f');
  });

  it('scan button opens the scanner for the register form', () => {
    click('f-scan-btn');
    expect(openScanner).toHaveBeenCalledWith('f');
  });

  it('fetch button looks up OFF', () => {
    click('f-off-btn');
    expect(lookupOFF).toHaveBeenCalledWith('f');
  });

  it('name input validates, clears aria-invalid, and hides the field error', () => {
    const name = document.getElementById('f-name');
    name.setAttribute('aria-invalid', 'true');
    input('f-name');
    expect(validateOffBtn).toHaveBeenCalledWith('f');
    expect(name.getAttribute('aria-invalid')).toBe('false');
    expect(document.getElementById('f-name-error').style.display).toBe('none');
  });

  it('OCR buttons scan ingredients and nutrition for the register form', () => {
    click('f-ocr-btn');
    expect(scanIngredients).toHaveBeenCalledWith('f');
    click('f-ocr-nutri-btn');
    expect(scanNutrition).toHaveBeenCalledWith('f');
  });

  it('ingredients input updates the estimate button', () => {
    input('f-ingredients');
    expect(updateEstimateBtn).toHaveBeenCalledWith('f');
  });

  it('taste slider updates aria-valuenow, the value display, and the i18n label', () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => { cb(); return 0; });
    const slider = document.getElementById('f-smak');
    slider.value = '4.5';
    input('f-smak');
    expect(slider.getAttribute('aria-valuenow')).toBe('4.5');
    expect(document.getElementById('smak-val').textContent).toBe('4.5');
    const label = document.getElementById('smak-label-text');
    expect(label.getAttribute('data-i18n-param-val')).toBe('4.5');
    expect(t).toHaveBeenCalledWith('label_taste', { val: '4.5' });
    expect(label.textContent).toBe('label_taste:4.5');
    rafSpy.mockRestore();
  });

  it('estimate, image, and submit buttons dispatch to their modules', () => {
    click('f-estimate-btn');
    expect(estimateProteinQuality).toHaveBeenCalledWith('f');
    click('f-image-btn');
    expect(captureProductImage).toHaveBeenCalledWith('f');
    click('f-image-remove');
    expect(clearPendingImage).toHaveBeenCalledWith('f');
    click('btn-submit');
    expect(registerProduct).toHaveBeenCalledTimes(1);
  });
});

describe('initDomBindings — settings section toggles', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <h3 class="settings-toggle" id="sec-a" role="button" tabindex="0"></h3>
      <h3 class="settings-toggle" id="sec-b" role="button" tabindex="0"></h3>`;
    initDomBindings();
  });

  it('click toggles the clicked header only', () => {
    const a = document.getElementById('sec-a');
    a.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(toggleSettingsSection).toHaveBeenCalledTimes(1);
    expect(toggleSettingsSection).toHaveBeenCalledWith(a);
  });

  it('Enter and Space toggle and prevent default scrolling/activation', () => {
    const b = document.getElementById('sec-b');
    const enter = keydown(b, 'Enter');
    expect(toggleSettingsSection).toHaveBeenCalledWith(b);
    expect(enter.defaultPrevented).toBe(true);
    const space = keydown(b, ' ');
    expect(toggleSettingsSection).toHaveBeenCalledTimes(2);
    expect(space.defaultPrevented).toBe(true);
  });

  it('other keys do not toggle', () => {
    keydown(document.getElementById('sec-a'), 'Tab');
    expect(toggleSettingsSection).not.toHaveBeenCalled();
  });
});

describe('initDomBindings — settings buttons and backup inputs', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <button id="btn-add-category"></button>
      <button id="btn-add-flag"></button>
      <button id="btn-add-pq"></button>
      <button id="btn-estimate-all-pq"></button>
      <button id="btn-save-off-credentials"></button>
      <button id="btn-refresh-all-off"></button>
      <button id="btn-save-ocr-settings"></button>
      <button id="btn-download-backup"></button>
      <button id="btn-import-trigger"></button>
      <div id="restore-drop" role="button" tabindex="0"></div>
      <input type="file" id="restore-file">
      <input type="file" id="import-file">`;
    initDomBindings();
  });

  it.each([
    ['btn-add-category', () => addCategory],
    ['btn-add-flag', () => addFlag],
    ['btn-add-pq', () => addPq],
    ['btn-estimate-all-pq', () => estimateAllPq],
    ['btn-save-off-credentials', () => saveOffCredentials],
    ['btn-refresh-all-off', () => refreshAllFromOff],
    ['btn-save-ocr-settings', () => saveOcrSettings],
    ['btn-download-backup', () => downloadBackup],
  ])('%s click dispatches to its module function', (id, getFn) => {
    click(id);
    expect(getFn()).toHaveBeenCalledTimes(1);
  });

  it('import trigger opens the hidden import file picker', () => {
    const picker = vi.spyOn(document.getElementById('import-file'), 'click');
    click('btn-import-trigger');
    expect(picker).toHaveBeenCalledTimes(1);
  });

  it('restore drop zone opens the hidden restore file picker on click, Enter, and Space', () => {
    const picker = vi.spyOn(document.getElementById('restore-file'), 'click');
    const drop = document.getElementById('restore-drop');
    drop.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(picker).toHaveBeenCalledTimes(1);
    keydown(drop, 'Enter');
    expect(picker).toHaveBeenCalledTimes(2);
    keydown(drop, ' ');
    expect(picker).toHaveBeenCalledTimes(3);
    keydown(drop, 'Escape');
    expect(picker).toHaveBeenCalledTimes(3);
  });

  it('file input change events pass the input element to the handlers', () => {
    change('restore-file');
    expect(handleRestore).toHaveBeenCalledWith(document.getElementById('restore-file'));
    change('import-file');
    expect(handleImport).toHaveBeenCalledWith(document.getElementById('import-file'));
  });
});
