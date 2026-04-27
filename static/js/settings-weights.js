// ── Settings: Nutrition Weights ──────────────────────
import { api, esc, upgradeSelect, showToast, showConfirmModal } from './state.js';
import { t, getCurrentLang, changeLanguage } from './i18n.js';
import { loadData } from './products.js';
import { initEmojiPicker } from './emoji-picker.js';
import { loadCategories } from './settings-categories.js';
import { loadFlags } from './settings-flags.js';
import { loadPq } from './settings-pq.js';
import { loadOcrSettings, loadOcrProviders } from './settings-ocr.js';
import { loadOffCredentials, checkRefreshStatus, loadOffLanguagePriority } from './settings-off.js';

// Re-export showToast so existing importers continue to work
export { showToast };

// ── Score config (shared with render.js) ────────────
export const SCORE_COLORS = {
  kcal: '#aa66ff', energy_kj: '#9955ee', carbs: '#ff44aa', sugar: '#ff66cc',
  fat: '#ff8844', saturated_fat: '#ffaa66', protein: '#00d4ff', fiber: '#44ff88',
  salt: '#ff4444', taste_score: '#E8B84B', volume: '#ff8800', price: '#ff6600',
  est_pdcaas: '#00e5cc', est_diaas: '#00bfff',
  pct_protein_cal: '#00d4ff', pct_fat_cal: '#ff8844', pct_carb_cal: '#ff44aa'
};
export const SCORE_CFG_MAP = {};
export const weightData = [];

// ── Per-category override scope state ────────────────
let _activeScope = '';
const categoryScopeData = [];
let _allCategories = [];

let _settingsLoading = false;

async function reloadGlobalWeights() {
  weightData.length = 0;
  const wd = await api('/api/weights');
  wd.forEach((w) => { weightData.push(w); });
  Object.keys(SCORE_CFG_MAP).forEach((k) => { delete SCORE_CFG_MAP[k]; });
  weightData.forEach((w) => {
    SCORE_CFG_MAP[w.field] = { label: w.label, direction: w.direction, formula: w.formula, formula_min: w.formula_min, formula_max: w.formula_max };
  });
}

export async function loadSettings() {
  if (_settingsLoading) return;
  _settingsLoading = true;
  try {
    const settingsLoading = document.getElementById('settings-loading');
    const settingsContent = document.getElementById('settings-content');
    if (settingsLoading) settingsLoading.style.display = '';
    if (settingsContent) settingsContent.style.display = 'none';
    try {
      await reloadGlobalWeights();
      _allCategories = await api('/api/categories');
      _activeScope = '';
      populateScopeSelect();
      renderWeightItems();
      updateScopeHint();
      updateScopeButtons();
    } catch(e) { showToast(t('toast_load_error'), 'error'); }
    if (settingsLoading) settingsLoading.style.display = 'none';
    if (settingsContent) settingsContent.style.display = '';
    // Populate language dropdown dynamically
    const langSelect = document.getElementById('language-select');
    if (langSelect) {
      try {
        const langs = await api('/api/languages');
        langSelect.innerHTML = '';
        langs.sort((a, b) => a.label.localeCompare(b.label));
        langs.forEach((l) => {
          const opt = document.createElement('option');
          opt.value = l.code;
          opt.textContent = (l.flag ? l.flag + ' ' : '') + l.label;
          langSelect.appendChild(opt);
        });
      } catch(e) { showToast(t('toast_load_error'), 'error'); }
      langSelect.value = getCurrentLang();
      upgradeSelect(langSelect, (val) => { changeLanguage(val); });
    }
    loadCategories();
    initEmojiPicker(document.getElementById('cat-emoji-trigger'), document.getElementById('cat-emoji'));
    loadFlags();
    loadPq();
    loadOffCredentials();
    loadOffLanguagePriority();
    checkRefreshStatus();
    await loadOcrProviders();
    await loadOcrSettings();
  } finally {
    _settingsLoading = false;
  }
}

// ── Scope dropdown / add / delete ──────────────────────
function populateScopeSelect() {
  const sel = document.getElementById('weight-scope-select');
  if (!sel) return;
  sel.innerHTML = '';
  const globalOpt = document.createElement('option');
  globalOpt.value = '';
  globalOpt.textContent = t('weights_scope_global');
  sel.appendChild(globalOpt);
  _allCategories
    .filter((c) => c.has_weight_overrides)
    .forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = (c.emoji ? c.emoji + ' ' : '') + c.label;
      sel.appendChild(opt);
    });
  sel.value = _activeScope;
  upgradeSelect(sel, (val) => onScopeChange(val));
  const addBtn = document.getElementById('weight-scope-add');
  if (addBtn && !addBtn._wired) {
    addBtn.addEventListener('click', openAddOverridePicker);
    addBtn._wired = true;
  }
  const delBtn = document.getElementById('weight-scope-delete');
  if (delBtn && !delBtn._wired) {
    delBtn.addEventListener('click', deleteActiveCategoryOverride);
    delBtn._wired = true;
  }
}

function updateScopeButtons() {
  const addBtn = document.getElementById('weight-scope-add');
  const delBtn = document.getElementById('weight-scope-delete');
  const anyWithoutOverride = _allCategories.some((c) => !c.has_weight_overrides);
  if (addBtn) addBtn.style.display = anyWithoutOverride ? '' : 'none';
  if (delBtn) delBtn.style.display = _activeScope ? '' : 'none';
}

function updateScopeHint() {
  const el = document.getElementById('weight-scope-hint');
  if (!el) return;
  el.textContent = _activeScope
    ? t('weights_scope_hint_category')
    : t('weights_scope_hint_global');
}

export async function onScopeChange(scope) {
  _activeScope = scope || '';
  try {
    if (_activeScope === '') {
      await reloadGlobalWeights();
    } else {
      const data = await api('/api/categories/' + encodeURIComponent(_activeScope) + '/weights');
      categoryScopeData.length = 0;
      data.forEach((d) => categoryScopeData.push(d));
    }
    renderWeightItems();
    updateScopeHint();
    updateScopeButtons();
  } catch(e) {
    showToast(t('toast_load_error'), 'error');
  }
}

export async function refreshScopeSelect() {
  try {
    _allCategories = await api('/api/categories');
    if (_activeScope && !_allCategories.some((c) => c.name === _activeScope && c.has_weight_overrides)) {
      _activeScope = '';
      await reloadGlobalWeights();
      renderWeightItems();
      updateScopeHint();
    }
    populateScopeSelect();
    updateScopeButtons();
  } catch(e) { /* best-effort */ }
}

export function openAddOverridePicker() {
  const candidates = _allCategories.filter((c) => !c.has_weight_overrides);
  if (!candidates.length) {
    showToast(t('toast_no_categories_without_overrides'), 'info');
    return;
  }
  const bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  const modal = document.createElement('div');
  modal.className = 'scan-modal';
  const iconDiv = document.createElement('div');
  iconDiv.className = 'scan-modal-icon';
  iconDiv.textContent = '⚙';
  modal.appendChild(iconDiv);
  const h3 = document.createElement('h3');
  h3.textContent = t('add_category_override_title');
  modal.appendChild(h3);
  const p = document.createElement('p');
  p.textContent = t('add_category_override_hint');
  modal.appendChild(p);

  const sel = document.createElement('select');
  sel.className = 'field-select cat-move-select';
  candidates.forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c.name;
    opt.textContent = (c.emoji ? c.emoji + ' ' : '') + c.label;
    sel.appendChild(opt);
  });
  modal.appendChild(sel);

  const actions = document.createElement('div');
  actions.className = 'scan-modal-actions';
  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'scan-modal-btn-register';
  confirmBtn.textContent = t('btn_save');
  actions.appendChild(confirmBtn);
  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'scan-modal-btn-cancel';
  cancelBtn.textContent = t('btn_cancel');
  actions.appendChild(cancelBtn);
  modal.appendChild(actions);

  bg.appendChild(modal);
  document.body.appendChild(bg);
  upgradeSelect(sel);

  function close() { bg.remove(); }
  cancelBtn.onclick = close;
  bg.addEventListener('click', (e) => { if (e.target === bg) close(); });
  confirmBtn.onclick = async () => {
    const chosen = sel.value;
    const cat = _allCategories.find((c) => c.name === chosen);
    if (cat) cat.has_weight_overrides = true;
    populateScopeSelect();
    const scopeSel = document.getElementById('weight-scope-select');
    if (scopeSel) scopeSel.value = chosen;
    close();
    await onScopeChange(chosen);
  };
}

export async function deleteActiveCategoryOverride() {
  if (!_activeScope) return;
  const cat = _allCategories.find((c) => c.name === _activeScope);
  const label = cat ? cat.label : _activeScope;
  const ok = await showConfirmModal(
    '\u{1F5D1}',
    label,
    t('confirm_delete_category_override', { name: label }),
    t('btn_delete'),
    t('btn_cancel')
  );
  if (!ok) return;
  const targetName = _activeScope;
  const payload = categoryScopeData.map((w) => ({
    field: w.field,
    is_overridden: false,
    enabled: !!w.enabled,
    weight: w.weight,
    direction: w.direction,
    formula: w.formula,
    formula_min: w.formula_min != null ? w.formula_min : 0,
    formula_max: w.formula_max != null ? w.formula_max : 0,
  }));
  try {
    await api('/api/categories/' + encodeURIComponent(targetName) + '/weights', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (cat) cat.has_weight_overrides = false;
    showToast(t('toast_category_override_deleted'), 'success');
    _activeScope = '';
    await reloadGlobalWeights();
    populateScopeSelect();
    renderWeightItems();
    updateScopeHint();
    updateScopeButtons();
    loadData();
  } catch(e) {
    showToast(t('toast_save_error'), 'error');
  }
}

// ── Renderer (identical UI for global and category scope) ──
// In category scope, "active" = is_overridden, "inactive" = inherited.
// In global scope,   "active" = enabled,       "inactive" = disabled.
export function renderWeightItems() {
  const container = document.getElementById('weight-items');
  if (!container) return;
  const isCategory = !!_activeScope;
  const source = isCategory ? categoryScopeData : weightData;
  const isActive = (w) => isCategory ? !!w.is_overridden : !!w.enabled;
  const active = source.filter(isActive);
  const inactive = source.filter((w) => !isActive(w));
  container.innerHTML = '';

  active.forEach((w) => {
    const col = SCORE_COLORS[w.field] || '#888';
    const dirLower = w.direction === 'lower';
    const isDirect = w.formula === 'direct';
    const sf = w.field;

    const item = document.createElement('div');
    item.className = 'weight-item enabled';
    item.id = 'wi-' + sf;
    item.style.cssText = 'margin-bottom:10px;border-left:3px solid ' + col;

    const header = document.createElement('div');
    header.className = 'weight-header';

    const topDiv = document.createElement('div');
    topDiv.className = 'weight-top';
    const label = document.createElement('label');
    label.className = 'field-label';
    label.style.margin = '0';
    label.textContent = w.label;
    topDiv.appendChild(label);
    header.appendChild(topDiv);

    const valSpan = document.createElement('span');
    valSpan.className = 'weight-val mono accent';
    valSpan.id = 'wv-' + sf;
    valSpan.textContent = (w.weight != null ? w.weight : 0).toFixed(1);
    header.appendChild(valSpan);

    const cfgBtn = document.createElement('button');
    cfgBtn.className = 'weight-cfg-btn';
    cfgBtn.title = 'Advanced';
    cfgBtn.innerHTML = '&#9881;';
    cfgBtn.addEventListener('click', () => toggleWeightConfig(sf));
    header.appendChild(cfgBtn);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-sm btn-red';
    removeBtn.title = isCategory ? t('btn_remove_override') : 'Remove';
    removeBtn.innerHTML = '&#128465;';
    removeBtn.addEventListener('click', () => removeWeight(sf));
    header.appendChild(removeBtn);

    item.appendChild(header);

    const cfgDiv = document.createElement('div');
    cfgDiv.className = 'weight-config';
    cfgDiv.id = 'wcfg-' + sf;
    cfgDiv.style.display = 'none';

    const cfgRow = document.createElement('div');
    cfgRow.className = 'wc-row';

    const dirSelect = document.createElement('select');
    dirSelect.className = 'wc-select';
    dirSelect.id = 'wd-' + sf;
    dirSelect.innerHTML = '<option value="lower" ' + (dirLower ? 'selected' : '') + '>' + esc(t('direction_lower')) + '</option>'
      + '<option value="higher" ' + (!dirLower ? 'selected' : '') + '>' + esc(t('direction_higher')) + '</option>';
    dirSelect.addEventListener('change', () => onWeightDirection(sf));
    cfgRow.appendChild(dirSelect);

    const fmlaSelect = document.createElement('select');
    fmlaSelect.className = 'wc-select';
    fmlaSelect.id = 'wf-' + sf;
    fmlaSelect.innerHTML = '<option value="minmax" ' + (!isDirect ? 'selected' : '') + '>' + esc(t('formula_minmax')) + '</option>'
      + '<option value="direct" ' + (isDirect ? 'selected' : '') + '>' + esc(t('formula_direct')) + '</option>';
    fmlaSelect.addEventListener('change', () => onWeightFormula(sf));
    cfgRow.appendChild(fmlaSelect);

    const minInput = document.createElement('input');
    minInput.type = 'number';
    minInput.className = 'wc-max';
    minInput.id = 'wn-' + sf;
    minInput.value = w.formula_min != null ? w.formula_min : '';
    minInput.placeholder = 'Min';
    minInput.step = '0.01';
    minInput.style.display = isDirect ? '' : 'none';
    minInput.addEventListener('input', () => onWeightMin(sf));
    cfgRow.appendChild(minInput);

    const maxInput = document.createElement('input');
    maxInput.type = 'number';
    maxInput.className = 'wc-max';
    maxInput.id = 'wm-' + sf;
    maxInput.value = w.formula_max != null ? w.formula_max : '';
    maxInput.placeholder = 'Max';
    maxInput.step = '0.01';
    maxInput.style.display = isDirect ? '' : 'none';
    maxInput.addEventListener('input', () => onWeightMax(sf));
    cfgRow.appendChild(maxInput);

    cfgDiv.appendChild(cfgRow);
    item.appendChild(cfgDiv);

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '0';
    slider.max = '100';
    slider.step = '1';
    slider.value = w.weight != null ? w.weight : 0;
    slider.id = 'w-' + sf;
    slider.className = 'weight-slider';
    slider.addEventListener('input', () => onWeightSlider(sf));
    item.appendChild(slider);

    container.appendChild(item);
  });

  // Bottom "+ add weight / + add override" dropdown — same UI for both scopes.
  if (inactive.length) {
    const placeholder = '— ' + t(isCategory ? 'btn_add_override' : 'btn_add_weight') + ' —';
    const addRow = document.createElement('div');
    addRow.className = 'weight-add-row';

    const addSelect = document.createElement('select');
    addSelect.className = 'field-select';
    addSelect.id = 'weight-add-select';
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = placeholder;
    addSelect.appendChild(placeholderOpt);
    inactive.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach((w) => {
      const opt = document.createElement('option');
      opt.value = w.field;
      opt.textContent = w.label;
      addSelect.appendChild(opt);
    });
    addRow.appendChild(addSelect);

    const addBtn = document.createElement('button');
    addBtn.className = 'btn-register weight-add-btn';
    addBtn.textContent = '+';
    addBtn.addEventListener('click', addWeightFromDropdown);
    addRow.appendChild(addBtn);

    container.appendChild(addRow);
  }

  upgradeSelect(document.getElementById('weight-add-select'), () => {
    addWeightFromDropdown();
  });
  active.forEach((w) => {
    upgradeSelect(document.getElementById('wd-' + w.field), () => {
      onWeightDirection(w.field);
    });
    upgradeSelect(document.getElementById('wf-' + w.field), () => {
      onWeightFormula(w.field);
    });
  });
}

export function toggleWeightConfig(field) {
  const el = document.getElementById('wcfg-' + field);
  if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
}

let _weightSaveTimer = null;
let _weightSavedTimer = null;
function debouncedSaveWeights() { clearTimeout(_weightSaveTimer); _weightSaveTimer = setTimeout(saveWeights, 400); }

function getActiveItem(field) {
  const source = _activeScope ? categoryScopeData : weightData;
  return source.find((w) => w.field === field);
}

export function removeWeight(field) {
  const item = getActiveItem(field);
  if (item) {
    if (_activeScope) {
      item.is_overridden = false;
    } else {
      item.enabled = false;
      item.weight = 0;
    }
  }
  renderWeightItems();
  debouncedSaveWeights();
}

export function addWeightFromDropdown() {
  const sel = document.getElementById('weight-add-select');
  if (!sel || !sel.value) return;
  const item = getActiveItem(sel.value);
  if (item) {
    if (_activeScope) {
      item.is_overridden = true;
      if (!item.enabled) item.enabled = true;
      if (item.weight == null || item.weight === 0) item.weight = 10;
    } else {
      item.enabled = true;
      if (item.weight === 0) item.weight = 10;
    }
  }
  renderWeightItems();
  debouncedSaveWeights();
}

export function onWeightDirection(field) {
  const item = getActiveItem(field);
  if (item) item.direction = document.getElementById('wd-' + field).value;
  debouncedSaveWeights();
}

export function onWeightFormula(field) {
  const item = getActiveItem(field);
  const val = document.getElementById('wf-' + field).value;
  if (item) item.formula = val;
  const minEl = document.getElementById('wn-' + field);
  const maxEl = document.getElementById('wm-' + field);
  if (minEl) minEl.style.display = val === 'direct' ? '' : 'none';
  if (maxEl) maxEl.style.display = val === 'direct' ? '' : 'none';
  debouncedSaveWeights();
}

export function onWeightMin(field) {
  const item = getActiveItem(field);
  if (item) item.formula_min = parseFloat(document.getElementById('wn-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightMax(field) {
  const item = getActiveItem(field);
  if (item) item.formula_max = parseFloat(document.getElementById('wm-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightSlider(field) {
  const val = parseFloat(document.getElementById('w-' + field).value);
  document.getElementById('wv-' + field).textContent = val.toFixed(1);
  const item = getActiveItem(field);
  if (item) item.weight = val;
  debouncedSaveWeights();
}

let _weightSaving = false;
export async function saveWeights() {
  if (_weightSaving) return;
  _weightSaving = true;
  try {
    const isCategory = !!_activeScope;
    const source = isCategory ? categoryScopeData : weightData;
    const payload = source.map((w) => {
      const fMin = w.formula_min != null ? w.formula_min : 0;
      const fMax = w.formula_max != null ? w.formula_max : 0;
      // Pull the live values from the DOM only for rows currently rendered as editable.
      const editableInDom = isCategory ? !!w.is_overridden : !!w.enabled;
      const minEl = editableInDom ? document.getElementById('wn-' + w.field) : null;
      const maxEl = editableInDom ? document.getElementById('wm-' + w.field) : null;
      const sliderEl = editableInDom ? document.getElementById('w-' + w.field) : null;
      const minVal = (minEl && minEl.value !== '') ? parseFloat(minEl.value) : NaN;
      const maxVal = (maxEl && maxEl.value !== '') ? parseFloat(maxEl.value) : NaN;
      const base = {
        field: w.field,
        enabled: !!w.enabled,
        weight: parseFloat(sliderEl ? sliderEl.value : w.weight),
        direction: w.direction,
        formula: w.formula,
        formula_min: isFinite(minVal) ? minVal : fMin,
        formula_max: isFinite(maxVal) ? maxVal : fMax,
      };
      if (isCategory) base.is_overridden = !!w.is_overridden;
      return base;
    });
    if (isCategory) {
      const targetName = _activeScope;
      await api('/api/categories/' + encodeURIComponent(targetName) + '/weights', {
        method: 'PUT', body: JSON.stringify(payload),
      });
      // Update has_weight_overrides flag in the cached list and refresh dropdown if it changed
      const cat = _allCategories.find((c) => c.name === targetName);
      const anyOverride = payload.some((p) => p.is_overridden);
      if (cat && cat.has_weight_overrides !== anyOverride) {
        cat.has_weight_overrides = anyOverride;
        if (!anyOverride) {
          // category no longer has overrides — keep current scope but refresh dropdown
          populateScopeSelect();
          updateScopeButtons();
        } else {
          populateScopeSelect();
          updateScopeButtons();
        }
      }
    } else {
      await api('/api/weights', { method: 'PUT', body: JSON.stringify(payload) });
    }
    const indicator = document.getElementById('weights-saved-indicator');
    if (indicator) { indicator.style.opacity = '1'; clearTimeout(_weightSavedTimer); _weightSavedTimer = setTimeout(() => { indicator.style.opacity = '0'; }, 1500); }
    loadData();
  } catch(e) { showToast(t('toast_save_error'), 'error'); }
  finally { _weightSaving = false; }
}
