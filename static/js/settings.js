// ── Weights, Categories, Protein Quality, Backup ────
import { state, api, esc, fetchStats, upgradeSelect, showConfirmModal, showToast } from './state.js';
import { t, getCurrentLang, changeLanguage } from './i18n.js';
import { loadData } from './products.js';
import { initEmojiPicker, resetEmojiPicker } from './emoji-picker.js';

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

let _settingsLoading = false;

function updateStatsLine() {
  const el = document.getElementById('stats-line');
  if (el && state.cachedStats) {
    el.textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  }
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
      weightData.length = 0;
      const wd = await api('/api/weights');
      wd.forEach((w) => { weightData.push(w); });
      // Reset and rebuild SCORE_CFG_MAP
      Object.keys(SCORE_CFG_MAP).forEach((k) => { delete SCORE_CFG_MAP[k]; });
      weightData.forEach((w) => {
        SCORE_CFG_MAP[w.field] = { label: w.label, direction: w.direction, formula: w.formula, formula_min: w.formula_min, formula_max: w.formula_max };
      });
      renderWeightItems();
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
    checkRefreshStatus();
  } finally {
    _settingsLoading = false;
  }
}


export function renderWeightItems() {
  const container = document.getElementById('weight-items');
  const enabled = weightData.filter((w) => w.enabled);
  const disabled = weightData.filter((w) => !w.enabled);
  // Build weight items using DOM to avoid inline onclick XSS
  container.innerHTML = '';

  enabled.forEach((w) => {
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
    valSpan.textContent = w.weight.toFixed(1);
    header.appendChild(valSpan);

    const cfgBtn = document.createElement('button');
    cfgBtn.className = 'weight-cfg-btn';
    cfgBtn.title = 'Advanced';
    cfgBtn.innerHTML = '&#9881;';
    cfgBtn.addEventListener('click', () => toggleWeightConfig(sf));
    header.appendChild(cfgBtn);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-sm btn-red';
    removeBtn.title = 'Remove';
    removeBtn.innerHTML = '&#128465;';
    removeBtn.addEventListener('click', () => removeWeight(sf));
    header.appendChild(removeBtn);

    item.appendChild(header);

    // Config section
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
    slider.value = w.weight;
    slider.id = 'w-' + sf;
    slider.className = 'weight-slider';
    slider.addEventListener('input', () => onWeightSlider(sf));
    item.appendChild(slider);

    container.appendChild(item);
  });

  // Dropdown to add disabled weights
  if (disabled.length) {
    const placeholder = '\u2014 ' + t('btn_add_weight') + ' \u2014';
    const addRow = document.createElement('div');
    addRow.className = 'weight-add-row';

    const addSelect = document.createElement('select');
    addSelect.className = 'field-select';
    addSelect.id = 'weight-add-select';
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = placeholder;
    addSelect.appendChild(placeholderOpt);
    disabled.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach((w) => {
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
  enabled.forEach((w) => {
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
function debouncedSaveWeights() { clearTimeout(_weightSaveTimer); _weightSaveTimer = setTimeout(saveWeights, 400); }

export function removeWeight(field) {
  const item = weightData.find((w) => w.field === field);
  if (item) { item.enabled = false; item.weight = 0; }
  renderWeightItems();
  debouncedSaveWeights();
}

export function addWeightFromDropdown() {
  const sel = document.getElementById('weight-add-select');
  if (!sel || !sel.value) return;
  const item = weightData.find((w) => w.field === sel.value);
  if (item) { item.enabled = true; if (item.weight === 0) item.weight = 10; }
  renderWeightItems();
  debouncedSaveWeights();
}

export function onWeightDirection(field) {
  const item = weightData.find((w) => w.field === field);
  if (item) item.direction = document.getElementById('wd-' + field).value;
  debouncedSaveWeights();
}

export function onWeightFormula(field) {
  const item = weightData.find((w) => w.field === field);
  const val = document.getElementById('wf-' + field).value;
  if (item) item.formula = val;
  const minEl = document.getElementById('wn-' + field);
  const maxEl = document.getElementById('wm-' + field);
  if (minEl) minEl.style.display = val === 'direct' ? '' : 'none';
  if (maxEl) maxEl.style.display = val === 'direct' ? '' : 'none';
  debouncedSaveWeights();
}

export function onWeightMin(field) {
  const item = weightData.find((w) => w.field === field);
  if (item) item.formula_min = parseFloat(document.getElementById('wn-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightMax(field) {
  const item = weightData.find((w) => w.field === field);
  if (item) item.formula_max = parseFloat(document.getElementById('wm-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightSlider(field) {
  const val = parseFloat(document.getElementById('w-' + field).value);
  document.getElementById('wv-' + field).textContent = val.toFixed(1);
  const item = weightData.find((w) => w.field === field);
  if (item) item.weight = val;
  debouncedSaveWeights();
}

let _weightSaving = false;
export async function saveWeights() {
  if (_weightSaving) return;
  _weightSaving = true;
  try {
    const payload = weightData.map((w) => {
      if (!w.enabled) {
        // For disabled weights, preserve existing values from weightData
        return { field: w.field, enabled: w.enabled, weight: w.weight, direction: w.direction, formula: w.formula, formula_min: w.formula_min || 0, formula_max: w.formula_max || 0 };
      }
      const minEl = document.getElementById('wn-' + w.field);
      const maxEl = document.getElementById('wm-' + w.field);
      const sliderEl = document.getElementById('w-' + w.field);
      return { field: w.field, enabled: w.enabled, weight: parseFloat(sliderEl ? sliderEl.value : w.weight), direction: w.direction, formula: w.formula, formula_min: parseFloat(minEl ? minEl.value : 0) || 0, formula_max: parseFloat(maxEl ? maxEl.value : 0) || 0 };
    });
    await api('/api/weights', { method: 'PUT', body: JSON.stringify(payload) });
    showToast(t('toast_weights_saved'), 'success');
    loadData();
  } catch(e) { showToast(t('toast_save_error'), 'error'); }
  finally { _weightSaving = false; }
}


// ── Categories ──────────────────────────────────────
export async function loadCategories() {
  try {
    const cats = await api('/api/categories');
    const list = document.getElementById('cat-list');
    if (!cats.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No categories</p>'; return; }
    let h = '';
    cats.forEach((c) => {
      h += '<div class="cat-item"><span class="cat-item-emoji cat-item-emoji-edit" data-cat="' + esc(c.name) + '" title="' + t('label_change_emoji') + '">' + esc(c.emoji) + '</span>'
        + '<input class="cat-item-label-input" data-cat-name="' + esc(c.name) + '" value="' + esc(c.label) + '" title="' + t('label_display_name') + '">'
        + '<span class="cat-item-key">' + esc(c.name) + '</span><span class="cat-item-count">' + c.count + ' prod.</span>'
        + '<button class="btn-sm btn-red" data-action="delete-cat" data-cat-name="' + esc(c.name) + '" data-cat-label="' + esc(c.label) + '" data-cat-count="' + c.count + '">&#128465;</button></div>';
    });
    list.innerHTML = h;
    // Attach change handlers to label inputs
    list.querySelectorAll('input.cat-item-label-input[data-cat-name]').forEach((inp) => {
      inp.addEventListener('change', () => {
        updateCategoryLabel(inp.dataset.catName, inp.value);
      });
    });
    // Attach click handlers to delete buttons
    list.querySelectorAll('[data-action="delete-cat"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        deleteCategory(btn.dataset.catName, btn.dataset.catLabel, parseInt(btn.dataset.catCount, 10));
      });
    });
    // Init emoji pickers on each category emoji
    list.querySelectorAll('.cat-item-emoji-edit').forEach((el) => {
      const catName = el.getAttribute('data-cat');
      initEmojiPicker(el, null, (emoji) => {
        updateCategoryEmoji(catName, emoji);
      });
    });
  } catch(e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export async function updateCategoryLabel(name, val) {
  if (!val.trim()) { showToast(t('toast_display_name_empty'), 'error'); loadCategories(); return; }
  try {
    await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ label: val.trim() }) });
    showToast(t('toast_category_updated'), 'success');
    await fetchStats();
    updateStatsLine();
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function updateCategoryEmoji(name, emoji) {
  try {
    await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ emoji: emoji }) });
    showToast(t('toast_category_updated'), 'success');
    await fetchStats();
    updateStatsLine();
    loadCategories();
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addCategory() {
  const name = document.getElementById('cat-name').value.trim();
  const emoji = document.getElementById('cat-emoji').value.trim() || '\u{1F4E6}';
  const label = document.getElementById('cat-label').value.trim();
  if (!name || !label) { showToast(t('toast_name_display_required'), 'error'); return; }
  try {
    const res = await api('/api/categories', { method: 'POST', body: JSON.stringify({ name: name, emoji: emoji, label: label }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('cat-name').value = '';
    document.getElementById('cat-emoji').value = '';
    document.getElementById('cat-label').value = '';
    resetEmojiPicker(document.getElementById('cat-emoji-trigger'));
    showToast(t('toast_category_added', { name: label }), 'success');
    await fetchStats();
    updateStatsLine();
    loadCategories();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deleteCategory(name, label, count) {
  try {
    if (!count) {
      // No products – show confirmation modal
      if (!await showConfirmModal('\u{1F5D1}', label, t('confirm_delete_category', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
      const res = await api('/api/categories/' + encodeURIComponent(name), { method: 'DELETE' });
      if (res.error) { showToast(res.error, 'error'); return; }
      showToast(t('toast_category_deleted', { name: label }), 'success');
      await fetchStats();
      updateStatsLine();
      loadCategories();
      return;
    }
    // Has products – show reassignment modal
    const cats = await api('/api/categories');
    const others = cats.filter((c) => c.name !== name);
    if (!others.length) { showToast(t('toast_cannot_delete_only_category'), 'error'); return; }
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg cat-move-modal-bg';

    const modal = document.createElement('div');
    modal.className = 'scan-modal cat-move-modal';
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.innerHTML = '&#128465;';
    modal.appendChild(iconDiv);
    const h3 = document.createElement('h3');
    h3.textContent = label;
    modal.appendChild(h3);
    const p = document.createElement('p');
    p.textContent = t('confirm_move_products', { count: count });
    modal.appendChild(p);

    const sel = document.createElement('select');
    sel.className = 'field-select cat-move-select';
    others.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.emoji + ' ' + c.label;
      sel.appendChild(opt);
    });
    modal.appendChild(sel);

    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'scan-modal-btn-register cat-move-confirm';
    confirmBtn.textContent = t('btn_move_and_delete');
    actions.appendChild(confirmBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel cat-move-cancel';
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
      const moveTo = sel.value;
      const target = others.find((c) => c.name === moveTo);
      try {
        const delRes = await api('/api/categories/' + encodeURIComponent(name), {
          method: 'DELETE',
          body: JSON.stringify({ move_to: moveTo })
        });
        if (delRes.error) { showToast(delRes.error, 'error'); return; }
        close();
        showToast(t('toast_category_moved_deleted', { count: count, target: target ? target.label : moveTo, name: label }), 'success');
        await fetchStats();
        updateStatsLine();
        loadCategories();
      } catch(e2) {
        console.error(e2);
        showToast(t('toast_network_error'), 'error');
      }
    };
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

// ── Product Flags ───────────────────────────────────
export async function loadFlags() {
  try {
    const flags = await api('/api/flags');
    const list = document.getElementById('flag-list');
    if (!flags.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No flags</p>'; return; }
    let h = '';
    flags.forEach((f) => {
      const isSystem = f.type === 'system';
      h += '<div class="cat-item flag-item' + (isSystem ? ' flag-item-system' : '') + '">';
      if (isSystem) {
        h += '<span class="flag-type-badge flag-type-system">system</span>';
        h += '<span class="flag-item-label-ro">' + esc(f.label) + '</span>';
      } else {
        h += '<span class="flag-type-badge flag-type-user">user</span>';
        h += '<input class="cat-item-label-input" data-flag-name="' + esc(f.name) + '" value="' + esc(f.label) + '" title="' + t('label_display_name') + '">';
      }
      h += '<span class="cat-item-key">' + esc(f.name) + '</span>';
      h += '<span class="cat-item-count">' + f.count + ' prod.</span>';
      if (!isSystem) {
        h += '<button class="btn-sm btn-red" data-action="delete-flag" data-flag-name="' + esc(f.name) + '" data-flag-label="' + esc(f.label) + '" data-flag-count="' + f.count + '">&#128465;</button>';
      }
      h += '</div>';
    });
    list.innerHTML = h;
    list.querySelectorAll('input.cat-item-label-input[data-flag-name]').forEach((inp) => {
      inp.addEventListener('change', () => {
        updateFlagLabel(inp.dataset.flagName, inp.value);
      });
    });
    list.querySelectorAll('[data-action="delete-flag"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        deleteFlag(btn.dataset.flagName, btn.dataset.flagLabel, parseInt(btn.dataset.flagCount, 10));
      });
    });
  } catch(e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export async function updateFlagLabel(name, val) {
  if (!val.trim()) { showToast(t('toast_display_name_empty'), 'error'); loadFlags(); return; }
  try {
    await api('/api/flags/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ label: val.trim() }) });
    showToast(t('toast_flag_updated'), 'success');
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addFlag() {
  const name = document.getElementById('flag-add-name').value.trim();
  const label = document.getElementById('flag-add-label').value.trim();
  if (!name || !label) { showToast(t('toast_name_display_required'), 'error'); return; }
  try {
    const res = await api('/api/flags', { method: 'POST', body: JSON.stringify({ name: name, label: label }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('flag-add-name').value = '';
    document.getElementById('flag-add-label').value = '';
    showToast(t('toast_flag_added', { name: label }), 'success');
    loadFlags();
    _refreshFlagConfig();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deleteFlag(name, label, count) {
  const msg = count > 0
    ? t('confirm_delete_flag_body', { name: label, count: count })
    : t('confirm_delete_flag_body_empty', { name: label });
  if (!await showConfirmModal('\u{1F5D1}', label, msg, t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/flags/' + encodeURIComponent(name), { method: 'DELETE' });
    showToast(t('toast_flag_deleted', { name: label }), 'success');
    loadFlags();
    _refreshFlagConfig();
  } catch(e) { console.error(e); showToast(t('toast_network_error'), 'error'); }
}

async function _refreshFlagConfig() {
  try {
    const { loadFlagConfig } = await import('./render.js');
    await loadFlagConfig();
  } catch(e) { /* ignore */ }
}

// ── Protein Quality Settings ────────────────────────
let pqData = [];

export async function loadPq() {
  try { pqData = await api('/api/protein-quality'); } catch(e) { pqData = []; showToast(t('toast_load_error'), 'error'); }
  renderPqTable();
}

export function renderPqTable() {
  const container = document.getElementById('pq-list');
  if (!pqData.length) { container.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px;text-align:center;padding:20px">No protein sources</p>'; return; }
  let h = '';
  pqData.forEach((row) => {
    h += '<div class="pq-card">'
      + '<div class="pq-card-top">'
      + '<input class="cat-item-label-input" id="pqe-label-' + row.id + '" value="' + esc(row.label || row.keywords[0]) + '" title="Name">'
      + '<span class="pq-badges"><span class="pq-badge"><span class="pq-badge-label">P </span>'
      + '<input class="pq-inline-num mono" id="pqe-pdcaas-' + row.id + '" type="number" step="0.01" min="0" max="1" value="' + row.pdcaas + '">'
      + '</span><span class="pq-badge"><span class="pq-badge-label">D </span>'
      + '<input class="pq-inline-num mono" id="pqe-diaas-' + row.id + '" type="number" step="0.01" min="0" max="1.2" value="' + row.diaas + '">'
      + '</span></span>'
      + '<button class="btn-sm btn-red" data-action="delete-pq" data-pq-id="' + row.id + '" data-pq-label="' + esc(row.label || row.keywords[0]) + '">&#128465;</button>'
      + '</div>'
      + '<input class="pq-kw-input" id="pqe-kw-' + row.id + '" value="' + esc(row.keywords.join(', ')) + '" placeholder="Keywords (comma separated)">'
      + '</div>';
  });
  container.innerHTML = h;
  // Attach change handlers for autosave
  pqData.forEach((row) => {
    const labelEl = document.getElementById('pqe-label-' + row.id);
    const pdcaasEl = document.getElementById('pqe-pdcaas-' + row.id);
    const diaasEl = document.getElementById('pqe-diaas-' + row.id);
    const kwEl = document.getElementById('pqe-kw-' + row.id);
    [labelEl, pdcaasEl, diaasEl, kwEl].forEach((el) => {
      if (el) el.addEventListener('change', () => { autosavePq(row.id); });
    });
  });
  // Attach delete handlers
  container.querySelectorAll('[data-action="delete-pq"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      deletePq(parseInt(btn.dataset.pqId, 10), btn.dataset.pqLabel);
    });
  });
}

const _pqSaveTimers = {};
export function autosavePq(id) { clearTimeout(_pqSaveTimers[id]); _pqSaveTimers[id] = setTimeout(() => { savePqField(id); }, 400); }

export async function savePqField(id) {
  const label = document.getElementById('pqe-label-' + id);
  const kw = document.getElementById('pqe-kw-' + id);
  const pdcaas = document.getElementById('pqe-pdcaas-' + id);
  const diaas = document.getElementById('pqe-diaas-' + id);
  if (!label || !kw || !pdcaas || !diaas) return;
  const kwVal = kw.value.trim();
  const pdVal = parseFloat(pdcaas.value);
  const diVal = parseFloat(diaas.value);
  if (!kwVal || isNaN(pdVal) || isNaN(diVal)) return;
  const keywords = kwVal.split(',').map((k) => k.trim()).filter(Boolean);
  try {
    const res = await api('/api/protein-quality/' + id, { method: 'PUT', body: JSON.stringify({ label: label.value.trim(), keywords: keywords, pdcaas: pdVal, diaas: diVal }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    showToast(t('toast_updated'), 'success');
    const item = pqData.find((r) => r.id === id);
    if (item) { item.label = label.value.trim(); item.keywords = keywords; item.pdcaas = pdVal; item.diaas = diVal; }
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addPq() {
  const label = document.getElementById('pq-add-label').value.trim();
  const kw = document.getElementById('pq-add-kw').value.trim();
  const pdcaas = parseFloat(document.getElementById('pq-add-pdcaas').value);
  const diaas = parseFloat(document.getElementById('pq-add-diaas').value);
  if (!kw || isNaN(pdcaas) || isNaN(diaas)) { showToast(t('toast_pq_keywords_required'), 'error'); return; }
  const keywords = kw.split(',').map((k) => k.trim()).filter(Boolean);
  try {
    const res = await api('/api/protein-quality', { method: 'POST', body: JSON.stringify({ label: label, keywords: keywords, pdcaas: pdcaas, diaas: diaas }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('pq-add-label').value = '';
    document.getElementById('pq-add-kw').value = '';
    document.getElementById('pq-add-pdcaas').value = '';
    document.getElementById('pq-add-diaas').value = '';
    showToast(t('toast_pq_added', { name: (label || keywords[0]) }), 'success');
    loadPq();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deletePq(id, label) {
  if (!await showConfirmModal('\u{1F5D1}', label, t('confirm_delete_product', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/protein-quality/' + id, { method: 'DELETE' });
    showToast(t('toast_pq_deleted', { name: label }), 'success');
    loadPq();
  } catch(e) { console.error(e); showToast(t('toast_network_error'), 'error'); }
}

// ── Backup / Restore / Import ───────────────────────
export function downloadBackup() {
  window.location.href = '/api/backup';
  showToast(t('toast_backup_downloaded'), 'success');
}

export async function handleRestore(input) {
  if (!input.files.length) return;
  if (!await showConfirmModal('\u26A0', t('restore_title'), t('restore_confirm'), t('btn_restore'), t('btn_cancel'))) { input.value = ''; return; }
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const res = await api('/api/restore', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else { state.imageCache = {}; showToast(res.message, 'success'); loadData(); if (state.currentView === 'settings') loadSettings(); }
    } catch(err) { showToast(t('toast_invalid_file'), 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

function _buildRadioGroup(name, options, defaultValue) {
  const wrap = document.createElement('div');
  wrap.className = 'import-dup-radios';
  for (const opt of options) {
    const label = document.createElement('label');
    label.className = 'import-dup-radio-label';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = name;
    input.value = opt.value;
    if (opt.value === defaultValue) input.checked = true;
    label.appendChild(input);
    const span = document.createElement('span');
    span.textContent = opt.label;
    label.appendChild(span);
    wrap.appendChild(label);
  }
  return wrap;
}

function showImportDuplicateDialog() {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal import-dup-modal';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '\u2699\uFE0F';
    modal.appendChild(iconDiv);

    const h3 = document.createElement('h3');
    h3.textContent = t('import_dup_title');
    modal.appendChild(h3);

    const desc = document.createElement('p');
    desc.className = 'import-dup-desc';
    desc.textContent = t('import_dup_desc');
    modal.appendChild(desc);

    // Match criteria section
    const matchSection = document.createElement('div');
    matchSection.className = 'import-dup-section';
    const matchLabel = document.createElement('div');
    matchLabel.className = 'import-dup-section-label';
    matchLabel.textContent = t('import_dup_match_label');
    matchSection.appendChild(matchLabel);
    matchSection.appendChild(_buildRadioGroup('match_criteria', [
      { value: 'ean', label: t('import_dup_match_ean') },
      { value: 'name', label: t('import_dup_match_name') },
      { value: 'both', label: t('import_dup_match_both') },
    ], 'both'));
    modal.appendChild(matchSection);

    // Action section
    const actionSection = document.createElement('div');
    actionSection.className = 'import-dup-section';
    const actionLabel = document.createElement('div');
    actionLabel.className = 'import-dup-section-label';
    actionLabel.textContent = t('import_dup_action_label');
    actionSection.appendChild(actionLabel);
    actionSection.appendChild(_buildRadioGroup('on_duplicate', [
      { value: 'skip', label: t('import_dup_action_skip') },
      { value: 'overwrite', label: t('import_dup_action_overwrite') },
      { value: 'merge', label: t('import_dup_action_merge') },
      { value: 'allow_duplicate', label: t('import_dup_action_allow') },
    ], 'skip'));
    modal.appendChild(actionSection);

    // Merge rules sub-section (shown only when "merge" selected)
    const mergeSection = document.createElement('div');
    mergeSection.className = 'import-dup-section import-dup-merge-rules';
    mergeSection.style.display = 'none';

    const mergeInfo = document.createElement('div');
    mergeInfo.className = 'import-dup-merge-info';
    mergeInfo.innerHTML = t('import_dup_merge_rules_desc');
    mergeSection.appendChild(mergeInfo);

    const mergePriorityLabel = document.createElement('div');
    mergePriorityLabel.className = 'import-dup-section-label';
    mergePriorityLabel.textContent = t('import_dup_merge_priority_label');
    mergeSection.appendChild(mergePriorityLabel);
    mergeSection.appendChild(_buildRadioGroup('merge_priority', [
      { value: 'keep_existing', label: t('import_dup_merge_keep_existing') },
      { value: 'use_imported', label: t('import_dup_merge_use_imported') },
    ], 'keep_existing'));
    modal.appendChild(mergeSection);

    // Toggle merge rules visibility based on action selection
    actionSection.addEventListener('change', () => {
      const sel = modal.querySelector('input[name="on_duplicate"]:checked');
      mergeSection.style.display = sel && sel.value === 'merge' ? '' : 'none';
    });

    // Buttons
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const startBtn = document.createElement('button');
    startBtn.className = 'scan-modal-btn-register';
    startBtn.textContent = t('import_dup_start');
    actions.appendChild(startBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel';
    cancelBtn.textContent = t('btn_cancel');
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);

    bg.appendChild(modal);
    document.body.appendChild(bg);

    function close(val) {
      document.removeEventListener('keydown', onKeyDown);
      bg.remove();
      resolve(val);
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close(null);
    }
    document.addEventListener('keydown', onKeyDown);
    bg.addEventListener('click', (e) => { if (e.target === bg) close(null); });
    cancelBtn.onclick = () => close(null);
    startBtn.onclick = () => {
      const mc = modal.querySelector('input[name="match_criteria"]:checked');
      const od = modal.querySelector('input[name="on_duplicate"]:checked');
      const mp = modal.querySelector('input[name="merge_priority"]:checked');
      close({
        match_criteria: mc ? mc.value : 'both',
        on_duplicate: od ? od.value : 'skip',
        merge_priority: mp ? mp.value : 'keep_existing',
      });
    };
    startBtn.focus();
  });
}

export function handleImport(input) {
  if (!input.files.length) return;
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const dupSettings = await showImportDuplicateDialog();
      if (!dupSettings) { input.value = ''; return; }
      data.match_criteria = dupSettings.match_criteria;
      data.on_duplicate = dupSettings.on_duplicate;
      data.merge_priority = dupSettings.merge_priority;
      const res = await api('/api/import', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else { state.imageCache = {}; showToast(res.message, 'success'); loadData(); if (state.currentView === 'settings') loadSettings(); }
    } catch(err) { showToast(t('toast_invalid_file'), 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

// ── Collapsible settings sections ───────────────────
export function toggleSettingsSection(header) {
  const body = header.nextElementSibling;
  if (!body) return;
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : '';
  header.classList.toggle('open', !isOpen);
  header.setAttribute('aria-expanded', String(!isOpen));
}

// Drag-and-drop for restore
export function initRestoreDragDrop() {
  const drop = document.getElementById('restore-drop');
  if (!drop) return;
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => { drop.classList.remove('dragover'); });
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      const fi = { files: e.dataTransfer.files };
      Object.defineProperty(fi, 'value', { set() {}, get() { return ''; } });
      handleRestore(fi);
    }
  });
}

// ── Bulk: Refresh all from OFF ───────────────────────
let _refreshEvtSource = null;

function _renderRefreshReport(report) {
  const container = document.getElementById('refresh-off-progress');
  if (!container) return;

  // Remove any previous report
  const prev = container.querySelector('.refresh-report');
  if (prev) prev.remove();

  const wrap = document.createElement('div');
  wrap.className = 'refresh-report';

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'refresh-report-toggle';
  toggleBtn.textContent = t('bulk_report_show', { count: report.length });
  wrap.appendChild(toggleBtn);

  const reasonKeys = {
    not_found: 'bulk_report_not_found',
    no_new_data: 'bulk_report_no_new_data',
    no_results: 'bulk_report_no_results',
    below_threshold: 'bulk_report_below_threshold',
  };

  function buildReportList() {
    const list = document.createElement('div');
    list.className = 'refresh-report-list';
    for (const item of report) {
      const row = document.createElement('div');
      row.className = 'refresh-report-row';

      const nameEl = document.createElement('span');
      nameEl.className = 'refresh-report-name';
      nameEl.textContent = item.name || item.ean || '—';
      nameEl.title = item.name || item.ean || '—';
      row.appendChild(nameEl);

      const badge = document.createElement('span');
      badge.className = 'refresh-report-badge ' + item.status;
      badge.textContent = t('bulk_report_' + item.status);
      row.appendChild(badge);

      const detail = document.createElement('span');
      detail.className = 'refresh-report-detail';
      if (item.status === 'updated' && item.fields) {
        detail.textContent = t('bulk_report_fields', { fields: item.fields.join(', ') });
      } else if (item.reason) {
        const key = reasonKeys[item.reason];
        let text = key ? t(key) : item.reason;
        if (item.detail) text += ' (' + item.detail + ')';
        detail.textContent = text;
      }
      detail.title = detail.textContent;
      row.appendChild(detail);

      list.appendChild(row);
    }
    return list;
  }

  function openReportModal() {
    const bg = document.createElement('div');
    bg.className = 'off-modal-bg';
    bg.id = 'refresh-report-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');

    const modal = document.createElement('div');
    modal.className = 'off-modal';

    const head = document.createElement('div');
    head.className = 'off-modal-head';
    const h3 = document.createElement('h3');
    h3.textContent = t('bulk_report_show', { count: report.length });
    head.appendChild(h3);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'off-modal-close';
    closeBtn.textContent = '\u00D7';
    closeBtn.setAttribute('aria-label', t('btn_close'));
    head.appendChild(closeBtn);
    modal.appendChild(head);

    const body = document.createElement('div');
    body.className = 'off-modal-body';
    body.appendChild(buildReportList());
    modal.appendChild(body);

    bg.appendChild(modal);
    document.body.appendChild(bg);
    document.body.style.overflow = 'hidden';

    function close() {
      document.removeEventListener('keydown', onKeyDown);
      bg.remove();
      document.body.style.overflow = '';
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close();
    }
    document.addEventListener('keydown', onKeyDown);
    closeBtn.addEventListener('click', close);
    bg.addEventListener('click', (e) => { if (e.target === bg) close(); });
  }

  toggleBtn.addEventListener('click', openReportModal);

  container.appendChild(wrap);
}

function _connectRefreshStream() {
  const btn = document.getElementById('btn-refresh-all-off');
  const progressWrap = document.getElementById('refresh-off-progress');
  const bar = document.getElementById('refresh-off-bar');
  const status = document.getElementById('refresh-off-status');

  if (btn) btn.disabled = true;
  if (progressWrap) progressWrap.style.display = '';

  if (_refreshEvtSource) _refreshEvtSource.close();
  _refreshEvtSource = new EventSource('/api/bulk/refresh-off/stream');

  _refreshEvtSource.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch(_) { return; }
    if (data.running && data.total > 0) {
      const pct = Math.round((data.current / data.total) * 100);
      if (bar) bar.style.width = pct + '%';
      const label = data.name || data.ean;
      if (status) status.textContent = t('bulk_refresh_off_progress', { current: data.current, total: data.total, name: label });
    }
    if (data.done) {
      _refreshEvtSource.close();
      _refreshEvtSource = null;
      if (bar) bar.style.width = '100%';
      const msg = t('bulk_refresh_off_result', { total: data.total, updated: data.updated, skipped: data.skipped, errors: data.errors });
      if (status) status.textContent = msg;
      showToast(msg, 'success');
      if (data.report) _renderRefreshReport(data.report);
      if (btn) btn.disabled = false;
      loadData();
    }
  };

  _refreshEvtSource.onerror = () => {
    _refreshEvtSource.close();
    _refreshEvtSource = null;
    if (btn) btn.disabled = false;
    if (progressWrap) progressWrap.style.display = 'none';
  };
}

export async function checkRefreshStatus() {
  try {
    const status = await api('/api/bulk/refresh-off/status');
    if (status.running) _connectRefreshStream();
  } catch(e) { /* ignore */ }
}

function _showRefreshOffModal() {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '🔄';
    modal.appendChild(iconDiv);

    const h3 = document.createElement('h3');
    h3.textContent = t('bulk_refresh_off_title');
    modal.appendChild(h3);

    const pEl = document.createElement('p');
    pEl.textContent = t('bulk_refresh_off_confirm');
    modal.appendChild(pEl);

    // Options section
    const opts = document.createElement('div');
    opts.className = 'refresh-off-options';

    const cbLabel = document.createElement('label');
    cbLabel.className = 'refresh-off-cb-label';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    const cbText = document.createElement('span');
    cbText.textContent = t('bulk_refresh_off_search_missing');
    cbLabel.appendChild(cb);
    cbLabel.appendChild(cbText);
    opts.appendChild(cbLabel);

    const sliders = document.createElement('div');
    sliders.className = 'refresh-off-sliders';
    sliders.style.display = 'none';

    function makeSlider(labelKey, defaultVal) {
      const row = document.createElement('div');
      row.className = 'refresh-off-range-row';
      const lbl = document.createElement('label');
      lbl.className = 'form-sub';
      lbl.textContent = t(labelKey);
      const range = document.createElement('input');
      range.type = 'range';
      range.min = '0';
      range.max = '100';
      range.value = String(defaultVal);
      const val = document.createElement('span');
      val.className = 'refresh-off-range-val';
      val.textContent = String(defaultVal);
      range.addEventListener('input', () => { val.textContent = range.value; });
      row.appendChild(lbl);
      row.appendChild(range);
      row.appendChild(val);
      sliders.appendChild(row);
      return range;
    }

    const certSlider = makeSlider('bulk_refresh_off_min_certainty', 100);
    const compSlider = makeSlider('bulk_refresh_off_min_completeness', 75);
    opts.appendChild(sliders);
    modal.appendChild(opts);

    cb.addEventListener('change', () => {
      sliders.style.display = cb.checked ? '' : 'none';
    });

    // Actions
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const yesBtn = document.createElement('button');
    yesBtn.className = 'scan-modal-btn-register confirm-yes';
    yesBtn.textContent = t('btn_start');
    actions.appendChild(yesBtn);
    const noBtn = document.createElement('button');
    noBtn.className = 'scan-modal-btn-cancel confirm-no';
    noBtn.textContent = t('btn_cancel');
    actions.appendChild(noBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);

    function close(val) {
      document.removeEventListener('keydown', onKeyDown);
      bg.remove();
      resolve(val);
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close(null);
    }
    document.addEventListener('keydown', onKeyDown);
    noBtn.onclick = () => { close(null); };
    yesBtn.onclick = () => {
      close({
        searchMissing: cb.checked,
        minCertainty: parseInt(certSlider.value, 10),
        minCompleteness: parseInt(compSlider.value, 10),
      });
    };
    bg.addEventListener('click', (e) => { if (e.target === bg) close(null); });
    yesBtn.focus();
  });
}

export async function refreshAllFromOff() {
  const opts = await _showRefreshOffModal();
  if (!opts) return;
  const bar = document.getElementById('refresh-off-bar');
  if (bar) bar.style.width = '0%';
  // Clear previous report
  const prevReport = document.querySelector('.refresh-report');
  if (prevReport) prevReport.remove();
  try {
    const body = {};
    if (opts.searchMissing) {
      body.search_missing = true;
      body.min_certainty = opts.minCertainty;
      body.min_completeness = opts.minCompleteness;
    }
    const res = await api('/api/bulk/refresh-off/start', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (res.error === 'already_running') {
      _connectRefreshStream();
      return;
    }
    if (res.error) { showToast(res.error, 'error'); return; }
    _connectRefreshStream();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

// ── Bulk: Estimate PQ for all ────────────────────────
export async function estimateAllPq() {
  const btn = document.getElementById('btn-estimate-all-pq');
  const status = document.getElementById('estimate-pq-status');
  if (btn) btn.disabled = true;
  if (status) { status.style.display = ''; status.textContent = t('bulk_running'); }
  try {
    const res = await api('/api/bulk/estimate-pq', { method: 'POST' });
    if (res.error) { showToast(res.error, 'error'); return; }
    const msg = t('bulk_estimate_pq_result', { total: res.total, updated: res.updated, skipped: res.skipped });
    if (status) status.textContent = msg;
    showToast(msg, 'success');
    loadData();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
    if (status) status.style.display = 'none';
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── OFF Credentials ─────────────────────────────────
async function loadOffCredentials() {
  try {
    const data = await api('/api/settings/off-credentials');
    const el = document.getElementById('off-user-id');
    if (el) el.value = data.off_user_id || '';
    const pw = document.getElementById('off-password');
    if (pw) pw.value = data.has_password ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : '';
  } catch(e) { showToast(t('toast_load_error'), 'error'); }
}

export async function saveOffCredentials() {
  const userId = (document.getElementById('off-user-id').value || '').trim();
  let pw = document.getElementById('off-password').value || '';
  if (pw === '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022') pw = '';
  const body = { off_user_id: userId };
  if (pw) body.off_password = pw;
  try {
    await api('/api/settings/off-credentials', { method: 'PUT', body: JSON.stringify(body) });
    showToast(t('toast_off_credentials_saved'), 'success');
  } catch(e) {
    const msg = e.message === 'encryption_not_configured'
      ? t('toast_encryption_not_configured')
      : t('toast_save_error');
    showToast(msg, 'error');
  }
}
