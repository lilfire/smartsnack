// ── SmartSnack Entry Point ───────────────────────────
// ES Module entry point — imports all modules and exposes functions to window

import { state, api } from './state.js';
import { initLanguage, changeLanguage } from './i18n.js';
import { toggleFilters, setSort, rerender } from './filters.js';
import { triggerImageUpload, removeProductImage } from './images.js';
import { renderResults } from './render.js';
import {
  showToast, startEdit, saveProduct, deleteProduct,
  loadData, switchView, setFilter, toggleExpand,
  onSearchInput, clearSearch, registerProduct
} from './products.js';
import {
  SCORE_CFG_MAP, weightData,
  loadSettings, toggleSettingsSection, toggleWeightConfig, removeWeight, addWeightFromDropdown,
  onWeightDirection, onWeightFormula, onWeightMin, onWeightMax, onWeightSlider,
  saveWeights,
  updateCategoryLabel, addCategory, deleteCategory,
  autosavePq, deletePq, addPq,
  downloadBackup, handleRestore, handleImport,
  initRestoreDragDrop,
  saveOffCredentials
} from './settings.js';
import {
  openScanner, closeScanner, openSearchScanner,
  closeScanModal, scanRegisterNew, scanUpdateExisting,
  closeScanPicker, scanPickerSearch, scanPickerSelect,
  showScanOffConfirm, closeScanOffConfirm, scanOffFetch
} from './scanner.js';
import {
  validateOffBtn, lookupOFF, closeOffPicker, offModalSearch,
  selectOffResult, estimateProteinQuality, updateEstimateBtn,
  showOffAddReview, closeOffAddReview, submitToOff
} from './openfoodfacts.js';

// ── Expose functions to window for HTML onclick handlers ──
Object.assign(window, {
  // i18n
  changeLanguage,
  // filters
  toggleFilters, setSort,
  // images
  triggerImageUpload, removeProductImage,
  // products
  showToast, startEdit, saveProduct, deleteProduct,
  switchView, setFilter, toggleExpand,
  onSearchInput, clearSearch, registerProduct,
  rerender,
  // settings — sections
  toggleSettingsSection,
  // settings — weights
  toggleWeightConfig, removeWeight, addWeightFromDropdown,
  onWeightDirection, onWeightFormula, onWeightMin, onWeightMax, onWeightSlider,
  // settings — categories
  updateCategoryLabel, addCategory, deleteCategory,
  // settings — protein quality
  autosavePq, deletePq, addPq,
  // settings — backup
  downloadBackup, handleRestore, handleImport,
  // settings — OFF credentials
  saveOffCredentials,
  // scanner
  openScanner, closeScanner, openSearchScanner,
  closeScanModal, scanRegisterNew, scanUpdateExisting,
  closeScanPicker, scanPickerSearch, scanPickerSelect,
  scanOffFetch, closeScanOffConfirm,
  // openfoodfacts
  validateOffBtn, lookupOFF, closeOffPicker, offModalSearch,
  selectOffResult, estimateProteinQuality, updateEstimateBtn,
  showOffAddReview, closeOffAddReview, submitToOff,
  // state access for inline handlers
  get editingId() { return state.editingId; },
  set editingId(v) { state.editingId = v; },
  loadData,
});

// ── Init ─────────────────────────────────────────────
(async function() {
  await initLanguage();
  try {
    var wc = await api('/api/weights');
    weightData.length = 0;
    wc.forEach(function(w) { weightData.push(w); });
    wc.forEach(function(w) { SCORE_CFG_MAP[w.field] = { label: w.label, desc: w.desc, direction: w.direction }; });
  } catch(e) {}
  initRestoreDragDrop();
  loadData();
  document.getElementById('search-input').focus();
})();
