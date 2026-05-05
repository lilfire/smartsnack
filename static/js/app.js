// ── SmartSnack Entry Point ───────────────────────────
// ES Module entry point — imports all modules and exposes functions to window

import { state, api, upgradeSelect, initAllFieldSelects } from './state.js';
import { initLanguage, changeLanguage, t } from './i18n.js';
import { toggleFilters, setSort, rerender } from './filters.js';
import { triggerImageUpload, removeProductImage, captureProductImage, clearPendingImage } from './images.js';
import { renderResults, loadFlagConfig } from './render.js';
import {
  showToast, startEdit, saveProduct, deleteProduct, unlockEan,
  loadData, switchView, setFilter, toggleExpand,
  onSearchInput, clearSearch, registerProduct,
  loadEanManager, addEan, deleteEan, setEanPrimary
} from './products.js';
import {
  SCORE_CFG_MAP, weightData,
  loadSettings, toggleWeightConfig, removeWeight, addWeightFromDropdown,
  onWeightDirection, onWeightFormula, onWeightMin, onWeightMax, onWeightSlider,
  saveWeights,
} from './settings-weights.js';
import { updateCategoryLabel, addCategory, deleteCategory } from './settings-categories.js';
import { addFlag, deleteFlag, updateFlagLabel } from './settings-flags.js';
import { autosavePq, deletePq, addPq } from './settings-pq.js';
import {
  downloadBackup, handleRestore, handleImport,
  initRestoreDragDrop, toggleSettingsSection, estimateAllPq,
} from './settings-backup.js';
import { loadOcrSettings, saveOcrSettings } from './settings-ocr.js';
import { saveOffCredentials, refreshAllFromOff } from './settings-off.js';
import {
  openScanner, closeScanner, openSearchScanner,
  closeScanModal, scanRegisterNew, scanUpdateExisting,
  closeScanPicker, scanPickerSearch, scanPickerSelect,
  showScanOffConfirm, closeScanOffConfirm, scanOffFetch
} from './scanner.js';
import { validateOffBtn, estimateProteinQuality, updateEstimateBtn } from './off-utils.js';
import { lookupOFF } from './off-api.js';
import { closeOffPicker, offModalSearch, selectOffResult } from './off-picker.js';
import { showOffAddReview, closeOffAddReview, submitToOff } from './off-review.js';
import { toggleAdvancedFilters } from './advanced-filters.js';
import { scanIngredients } from './ocr.js';

// ── Expose functions to window for HTML onclick handlers ──
Object.assign(window, {
  // i18n
  changeLanguage,
  // filters
  toggleFilters, setSort, toggleAdvancedFilters,
  // images
  triggerImageUpload, removeProductImage, captureProductImage, clearPendingImage,
  // products
  showToast, startEdit, saveProduct, deleteProduct, unlockEan,
  switchView, setFilter, toggleExpand,
  onSearchInput, clearSearch, registerProduct,
  loadEanManager, addEan, deleteEan, setEanPrimary,
  rerender,
  // settings — sections
  toggleSettingsSection,
  // settings — weights
  toggleWeightConfig, removeWeight, addWeightFromDropdown,
  onWeightDirection, onWeightFormula, onWeightMin, onWeightMax, onWeightSlider,
  // settings — categories
  updateCategoryLabel, addCategory, deleteCategory,
  // settings — flags
  addFlag, deleteFlag, updateFlagLabel,
  // settings — protein quality
  autosavePq, deletePq, addPq,
  // settings — backup
  downloadBackup, handleRestore, handleImport,
  // settings — OFF credentials
  saveOffCredentials,
  // settings — OCR
  saveOcrSettings,
  // settings — bulk operations
  refreshAllFromOff, estimateAllPq,
  // scanner
  openScanner, closeScanner, openSearchScanner,
  closeScanModal, scanRegisterNew, scanUpdateExisting,
  closeScanPicker, scanPickerSearch, scanPickerSelect,
  scanOffFetch, closeScanOffConfirm,
  // ocr
  scanIngredients,
  // openfoodfacts
  validateOffBtn, lookupOFF, closeOffPicker, offModalSearch,
  selectOffResult, estimateProteinQuality, updateEstimateBtn,
  showOffAddReview, closeOffAddReview, submitToOff,
  // state access for inline handlers
  loadData,
});

// Object.assign does not copy getters/setters — use defineProperty instead
Object.defineProperty(window, 'editingId', {
  get() { return state.editingId; },
  set(v) { state.editingId = v; },
  configurable: true,
});

// ── Fix Android keyboard-dismiss scroll jump on range inputs ─────
// When a number/text input has focus and the user taps a range slider,
// the virtual keyboard closes and the viewport resizes, causing the
// browser to scroll back to a previous position. We prevent this by
// saving scroll position on touchstart, blurring the active input,
// and restoring scroll position after the keyboard has fully dismissed.
document.addEventListener('touchstart', function(e) {
  if (e.target.type !== 'range') return;
  var active = document.activeElement;
  if (!active || (active.type !== 'number' && active.type !== 'text' && active.tagName !== 'TEXTAREA')) return;
  var scrollY = window.scrollY;
  active.blur();
  // Restore scroll after keyboard dismiss (may take up to ~300ms on Android)
  var restore = function() { window.scrollTo(0, scrollY); };
  requestAnimationFrame(restore);
  setTimeout(restore, 50);
  setTimeout(restore, 150);
  setTimeout(restore, 300);
}, { passive: true });

// ── Init ─────────────────────────────────────────────
(async function() {
  await initLanguage();
  initAllFieldSelects();
  const langSel = document.getElementById('language-select');
  if (langSel) langSel.onchange = () => changeLanguage(langSel.value);
  try {
    const wc = await api('/api/weights');
    weightData.length = 0;
    Object.keys(SCORE_CFG_MAP).forEach(function(k) { delete SCORE_CFG_MAP[k]; });
    wc.forEach(function(w) {
      weightData.push(w);
      SCORE_CFG_MAP[w.field] = { label: w.label, desc: w.desc, direction: w.direction };
    });
  } catch(e) { showToast(t('toast_load_error'), 'error'); }
  await loadFlagConfig();
  initRestoreDragDrop();
  loadData();
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.focus();
})();
