// ── DOM event bindings for server-rendered templates ─────────────
// Replaces the inline on*="" attributes that used to live in
// templates/partials/*.html so the CSP can drop 'unsafe-inline'
// from script-src. Dynamically rendered markup (product list, edit
// form) binds its own handlers in render.js via data-action delegation.

import { t } from './i18n.js';
import { switchView, onSearchInput, clearSearch, registerProduct } from './products.js';
import { toggleFilters } from './filters.js';
import { toggleAdvancedFilters } from './advanced-filters.js';
import { openScanner, openSearchScanner } from './scanner.js';
import { validateOffBtn, estimateProteinQuality, updateEstimateBtn } from './off-utils.js';
import { lookupOFF } from './off-api.js';
import { scanIngredients, scanNutrition } from './ocr.js';
import { captureProductImage, clearPendingImage } from './images.js';
import { addCategory } from './settings-categories.js';
import { addFlag } from './settings-flags.js';
import { addPq } from './settings-pq.js';
import {
  downloadBackup, handleRestore, handleImport,
  toggleSettingsSection, estimateAllPq,
} from './settings-backup.js';
import { saveOcrSettings } from './settings-ocr.js';
import { saveOffCredentials, refreshAllFromOff } from './settings-off.js';

function on(id, event, handler) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, handler);
}

export function initDomBindings() {
  // ── Header nav tabs ──
  document.querySelectorAll('.nav-tab[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // ── Search view ──
  on('search-input', 'input', () => onSearchInput());
  on('search-clear', 'click', () => clearSearch());
  on('btn-scan-search', 'click', () => openSearchScanner());
  on('adv-filter-toggle', 'click', () => toggleAdvancedFilters());
  on('filter-toggle', 'click', () => toggleFilters());

  // ── Register view ──
  on('f-ean', 'input', () => validateOffBtn('f'));
  on('f-scan-btn', 'click', () => openScanner('f'));
  on('f-off-btn', 'click', () => lookupOFF('f'));
  on('f-name', 'input', (e) => {
    validateOffBtn('f');
    e.target.setAttribute('aria-invalid', 'false');
    const err = document.getElementById('f-name-error');
    if (err) err.style.display = 'none';
  });
  on('f-ocr-btn', 'click', () => scanIngredients('f'));
  on('f-ingredients', 'input', () => updateEstimateBtn('f'));
  on('f-ocr-nutri-btn', 'click', () => scanNutrition('f'));
  on('f-smak', 'input', (e) => {
    const slider = e.target;
    slider.setAttribute('aria-valuenow', slider.value);
    const out = document.getElementById('smak-val');
    if (out) out.textContent = slider.value;
    const v = slider.value;
    requestAnimationFrame(() => {
      const lbl = document.getElementById('smak-label-text');
      if (!lbl) return;
      lbl.setAttribute('data-i18n-param-val', v);
      lbl.textContent = t('label_taste', { val: v });
    });
  });
  on('f-estimate-btn', 'click', () => estimateProteinQuality('f'));
  on('f-image-btn', 'click', () => captureProductImage('f'));
  on('f-image-remove', 'click', () => clearPendingImage('f'));
  on('btn-submit', 'click', () => registerProduct());

  // ── Settings view: collapsible section headers ──
  document.querySelectorAll('.settings-toggle').forEach((header) => {
    header.addEventListener('click', () => toggleSettingsSection(header));
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleSettingsSection(header);
      }
    });
  });

  // ── Settings view: buttons and inputs ──
  // (language-select change is bound in app.js after initLanguage())
  on('btn-add-category', 'click', () => addCategory());
  on('btn-add-flag', 'click', () => addFlag());
  on('btn-add-pq', 'click', () => addPq());
  on('btn-estimate-all-pq', 'click', () => estimateAllPq());
  on('btn-save-off-credentials', 'click', () => saveOffCredentials());
  on('btn-refresh-all-off', 'click', () => refreshAllFromOff());
  on('btn-save-ocr-settings', 'click', () => saveOcrSettings());
  on('btn-download-backup', 'click', () => downloadBackup());
  on('btn-import-trigger', 'click', () => {
    const input = document.getElementById('import-file');
    if (input) input.click();
  });
  const restoreDrop = document.getElementById('restore-drop');
  if (restoreDrop) {
    const openRestorePicker = () => {
      const input = document.getElementById('restore-file');
      if (input) input.click();
    };
    restoreDrop.addEventListener('click', openRestorePicker);
    restoreDrop.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') openRestorePicker();
    });
  }
  on('restore-file', 'change', (e) => handleRestore(e.target));
  on('import-file', 'change', (e) => handleImport(e.target));
}
