// ── Weights, Categories, Protein Quality, Backup ────
import { state, api, esc, fetchStats, upgradeSelect, showConfirmModal, showToast } from './state.js';
import { t, getCurrentLang, changeLanguage } from './i18n.js';
import { loadData } from './products.js';
import { initEmojiPicker, resetEmojiPicker } from './emoji-picker.js';

// Re-export showToast so existing importers continue to work
export { showToast };

// ── Score config (shared with render.js) ────────────
export var SCORE_COLORS = {
  kcal: '#aa66ff', energy_kj: '#9955ee', carbs: '#ff44aa', sugar: '#ff66cc',
  fat: '#ff8844', saturated_fat: '#ffaa66', protein: '#00d4ff', fiber: '#44ff88',
  salt: '#ff4444', taste_score: '#E8B84B', volume: '#ff8800', price: '#ff6600',
  est_pdcaas: '#00e5cc', est_diaas: '#00bfff',
  pct_protein_cal: '#00d4ff', pct_fat_cal: '#ff8844', pct_carb_cal: '#ff44aa'
};
export var SCORE_CFG_MAP = {};
export var weightData = [];

var _settingsLoading = false;

export async function loadSettings() {
  if (_settingsLoading) return;
  _settingsLoading = true;
  try {
    document.getElementById('settings-loading').style.display = '';
    document.getElementById('settings-content').style.display = 'none';
    try {
      weightData.length = 0;
      var wd = await api('/api/weights');
      wd.forEach(function(w) { weightData.push(w); });
      // Reset and rebuild SCORE_CFG_MAP
      Object.keys(SCORE_CFG_MAP).forEach(function(k) { delete SCORE_CFG_MAP[k]; });
      weightData.forEach(function(w) {
        SCORE_CFG_MAP[w.field] = { label: w.label, direction: w.direction, formula: w.formula, formula_min: w.formula_min, formula_max: w.formula_max };
      });
      renderWeightItems();
    } catch(e) { showToast(t('toast_load_error'), 'error'); }
    document.getElementById('settings-loading').style.display = 'none';
    document.getElementById('settings-content').style.display = '';
    // Populate language dropdown dynamically
    var langSelect = document.getElementById('language-select');
    if (langSelect) {
      try {
        var langs = await api('/api/languages');
        langSelect.innerHTML = '';
        langs.sort(function(a, b) { return a.label.localeCompare(b.label); });
        langs.forEach(function(l) {
          var opt = document.createElement('option');
          opt.value = l.code;
          opt.textContent = (l.flag ? l.flag + ' ' : '') + l.label;
          langSelect.appendChild(opt);
        });
      } catch(e) { showToast(t('toast_load_error'), 'error'); }
      langSelect.value = getCurrentLang();
      upgradeSelect(langSelect, function(val) { changeLanguage(val); });
    }
    loadCategories();
    initEmojiPicker(document.getElementById('cat-emoji-trigger'), document.getElementById('cat-emoji'));
    loadPq();
    loadOffCredentials();
  } finally {
    _settingsLoading = false;
  }
}


export function renderWeightItems() {
  var container = document.getElementById('weight-items');
  var enabled = weightData.filter(function(w) { return w.enabled; });
  var disabled = weightData.filter(function(w) { return !w.enabled; });
  var h = '';
  enabled.forEach(function(w) {
    var col = SCORE_COLORS[w.field] || '#888';
    var dirLower = w.direction === 'lower';
    var isDirect = w.formula === 'direct';
    var sf = esc(w.field);
    h += '<div class="weight-item enabled" id="wi-' + sf + '" style="margin-bottom:10px;border-left:3px solid ' + col + '">'
      + '<div class="weight-header">'
      + '<div class="weight-top">'
      + '<label class="field-label" style="margin:0">' + esc(w.label) + '</label></div>'
      + '<span class="weight-val mono accent" id="wv-' + sf + '">' + w.weight.toFixed(1) + '</span>'
      + '<button class="weight-cfg-btn" onclick="toggleWeightConfig(\'' + sf + '\')" title="Advanced">&#9881;</button>'
      + '<button class="btn-sm btn-red" onclick="removeWeight(\'' + sf + '\')" title="Remove">&#128465;</button></div>'
      + '<div class="weight-config" id="wcfg-' + sf + '" style="display:none">'
      + '<div class="wc-row">'
      + '<select class="wc-select" id="wd-' + sf + '" onchange="onWeightDirection(\'' + sf + '\')">'
      + '<option value="lower" ' + (dirLower ? 'selected' : '') + '>' + t('direction_lower') + '</option>'
      + '<option value="higher" ' + (!dirLower ? 'selected' : '') + '>' + t('direction_higher') + '</option></select>'
      + '<select class="wc-select" id="wf-' + sf + '" onchange="onWeightFormula(\'' + sf + '\')">'
      + '<option value="minmax" ' + (!isDirect ? 'selected' : '') + '>' + t('formula_minmax') + '</option>'
      + '<option value="direct" ' + (isDirect ? 'selected' : '') + '>' + t('formula_direct') + '</option></select>'
      + '<input type="number" class="wc-max" id="wn-' + sf + '" value="' + (w.formula_min != null ? w.formula_min : '') + '" placeholder="Min" step="0.01" oninput="onWeightMin(\'' + sf + '\')" style="' + (isDirect ? '' : 'display:none') + '">'
      + '<input type="number" class="wc-max" id="wm-' + sf + '" value="' + (w.formula_max != null ? w.formula_max : '') + '" placeholder="Max" step="0.01" oninput="onWeightMax(\'' + sf + '\')" style="' + (isDirect ? '' : 'display:none') + '">'
      + '</div></div>'
      + '<input type="range" min="0" max="100" step="1" value="' + w.weight + '" id="w-' + sf + '" class="weight-slider" oninput="onWeightSlider(\'' + sf + '\')">'
      + '</div>';
  });
  // Dropdown to add disabled weights
  if (disabled.length) {
    var placeholder = '\u2014 ' + t('btn_add_weight') + ' \u2014';
    h += '<div class="weight-add-row">'
      + '<select class="field-select" id="weight-add-select">'
      + '<option value="">' + placeholder + '</option>';
    disabled.slice().sort(function(a, b) { return a.label.localeCompare(b.label); }).forEach(function(w) {
      h += '<option value="' + w.field + '">' + esc(w.label) + '</option>';
    });
    h += '</select>'
      + '<button class="btn-register weight-add-btn" onclick="addWeightFromDropdown()">+</button>'
      + '</div>';
  }
  container.innerHTML = h;
  upgradeSelect(document.getElementById('weight-add-select'), function() {
    addWeightFromDropdown();
  });
  enabled.forEach(function(w) {
    upgradeSelect(document.getElementById('wd-' + w.field), function(val) {
      onWeightDirection(w.field);
    });
    upgradeSelect(document.getElementById('wf-' + w.field), function(val) {
      onWeightFormula(w.field);
    });
  });
}

export function toggleWeightConfig(field) {
  var el = document.getElementById('wcfg-' + field);
  if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
}

var _weightSaveTimer = null;
function debouncedSaveWeights() { clearTimeout(_weightSaveTimer); _weightSaveTimer = setTimeout(saveWeights, 400); }

export function removeWeight(field) {
  var item = weightData.find(function(w) { return w.field === field; });
  if (item) { item.enabled = false; item.weight = 0; }
  renderWeightItems();
  debouncedSaveWeights();
}

export function addWeightFromDropdown() {
  var sel = document.getElementById('weight-add-select');
  if (!sel || !sel.value) return;
  var item = weightData.find(function(w) { return w.field === sel.value; });
  if (item) { item.enabled = true; if (item.weight === 0) item.weight = 10; }
  renderWeightItems();
  debouncedSaveWeights();
}

export function onWeightDirection(field) {
  var item = weightData.find(function(w) { return w.field === field; });
  if (item) item.direction = document.getElementById('wd-' + field).value;
  debouncedSaveWeights();
}

export function onWeightFormula(field) {
  var item = weightData.find(function(w) { return w.field === field; });
  var val = document.getElementById('wf-' + field).value;
  if (item) item.formula = val;
  var minEl = document.getElementById('wn-' + field);
  var maxEl = document.getElementById('wm-' + field);
  if (minEl) minEl.style.display = val === 'direct' ? '' : 'none';
  if (maxEl) maxEl.style.display = val === 'direct' ? '' : 'none';
  debouncedSaveWeights();
}

export function onWeightMin(field) {
  var item = weightData.find(function(w) { return w.field === field; });
  if (item) item.formula_min = parseFloat(document.getElementById('wn-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightMax(field) {
  var item = weightData.find(function(w) { return w.field === field; });
  if (item) item.formula_max = parseFloat(document.getElementById('wm-' + field).value) || 0;
  debouncedSaveWeights();
}

export function onWeightSlider(field) {
  var val = parseFloat(document.getElementById('w-' + field).value);
  document.getElementById('wv-' + field).textContent = val.toFixed(1);
  var item = weightData.find(function(w) { return w.field === field; });
  if (item) item.weight = val;
  debouncedSaveWeights();
}

var _weightSaving = false;
export async function saveWeights() {
  if (_weightSaving) return;
  _weightSaving = true;
  try {
    var payload = weightData.map(function(w) {
      if (!w.enabled) {
        // For disabled weights, preserve existing values from weightData
        return { field: w.field, enabled: w.enabled, weight: w.weight, direction: w.direction, formula: w.formula, formula_min: w.formula_min || 0, formula_max: w.formula_max || 0 };
      }
      var minEl = document.getElementById('wn-' + w.field);
      var maxEl = document.getElementById('wm-' + w.field);
      var sliderEl = document.getElementById('w-' + w.field);
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
    var cats = await api('/api/categories');
    var list = document.getElementById('cat-list');
    if (!cats.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No categories</p>'; return; }
    var h = '';
    cats.forEach(function(c) {
      h += '<div class="cat-item"><span class="cat-item-emoji cat-item-emoji-edit" data-cat="' + esc(c.name) + '" title="' + t('label_change_emoji') + '">' + esc(c.emoji) + '</span>'
        + '<input class="cat-item-label-input" data-cat-name="' + esc(c.name) + '" value="' + esc(c.label) + '" title="' + t('label_display_name') + '">'
        + '<span class="cat-item-key">' + esc(c.name) + '</span><span class="cat-item-count">' + c.count + ' prod.</span>'
        + '<button class="btn-sm btn-red" data-action="delete-cat" data-cat-name="' + esc(c.name) + '" data-cat-label="' + esc(c.label) + '" data-cat-count="' + c.count + '">&#128465;</button></div>';
    });
    list.innerHTML = h;
    // Attach change handlers to label inputs
    list.querySelectorAll('input.cat-item-label-input[data-cat-name]').forEach(function(inp) {
      inp.addEventListener('change', function() {
        updateCategoryLabel(inp.dataset.catName, inp.value);
      });
    });
    // Attach click handlers to delete buttons
    list.querySelectorAll('[data-action="delete-cat"]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        deleteCategory(btn.dataset.catName, btn.dataset.catLabel, parseInt(btn.dataset.catCount, 10));
      });
    });
    // Init emoji pickers on each category emoji
    list.querySelectorAll('.cat-item-emoji-edit').forEach(function(el) {
      var catName = el.getAttribute('data-cat');
      initEmojiPicker(el, null, function(emoji) {
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
    document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function updateCategoryEmoji(name, emoji) {
  try {
    await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ emoji: emoji }) });
    showToast(t('toast_category_updated'), 'success');
    await fetchStats();
    document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
    loadCategories();
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addCategory() {
  var name = document.getElementById('cat-name').value.trim();
  var emoji = document.getElementById('cat-emoji').value.trim() || '\u{1F4E6}';
  var label = document.getElementById('cat-label').value.trim();
  if (!name || !label) { showToast(t('toast_name_display_required'), 'error'); return; }
  var res = await api('/api/categories', { method: 'POST', body: JSON.stringify({ name: name, emoji: emoji, label: label }) });
  if (res.error) { showToast(res.error, 'error'); return; }
  document.getElementById('cat-name').value = '';
  document.getElementById('cat-emoji').value = '';
  document.getElementById('cat-label').value = '';
  resetEmojiPicker(document.getElementById('cat-emoji-trigger'));
  showToast(t('toast_category_added', { name: label }), 'success');
  await fetchStats();
  document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  loadCategories();
}

export async function deleteCategory(name, label, count) {
  try {
    if (!count) {
      // No products – show confirmation modal
      if (!await showConfirmModal('&#128465;', esc(label), t('confirm_delete_category', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
      var res = await api('/api/categories/' + encodeURIComponent(name), { method: 'DELETE' });
      if (res.error) { showToast(res.error, 'error'); return; }
      showToast(t('toast_category_deleted', { name: label }), 'success');
      await fetchStats();
      document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
      loadCategories();
      return;
    }
    // Has products – show reassignment modal
    var cats = await api('/api/categories');
    var others = cats.filter(function(c) { return c.name !== name; });
    if (!others.length) { showToast(t('toast_cannot_delete_only_category'), 'error'); return; }
    var bg = document.createElement('div');
    bg.className = 'scan-modal-bg cat-move-modal-bg';
    var options = others.map(function(c) {
      return '<option value="' + esc(c.name) + '">' + esc(c.emoji) + ' ' + esc(c.label) + '</option>';
    }).join('');
    bg.innerHTML = '<div class="scan-modal cat-move-modal">'
      + '<div class="scan-modal-icon">&#128465;</div>'
      + '<h3>' + esc(label) + '</h3>'
      + '<p>' + t('confirm_move_products', { count: count }) + '</p>'
      + '<select class="field-select cat-move-select">' + options + '</select>'
      + '<div class="scan-modal-actions">'
      + '<button class="scan-modal-btn-register cat-move-confirm">' + t('btn_move_and_delete') + '</button>'
      + '<button class="scan-modal-btn-cancel cat-move-cancel">' + t('btn_cancel') + '</button>'
      + '</div></div>';
    document.body.appendChild(bg);
    var sel = bg.querySelector('.cat-move-select');
    upgradeSelect(sel);
    function close() { bg.remove(); }
    bg.querySelector('.cat-move-cancel').onclick = close;
    bg.addEventListener('click', function(e) { if (e.target === bg) close(); });
    bg.querySelector('.cat-move-confirm').onclick = async function() {
      var moveTo = sel.value;
      var target = others.find(function(c) { return c.name === moveTo; });
      close();
      try {
        var delRes = await api('/api/categories/' + encodeURIComponent(name), {
          method: 'DELETE',
          body: JSON.stringify({ move_to: moveTo })
        });
        if (delRes.error) { showToast(delRes.error, 'error'); return; }
        showToast(t('toast_category_moved_deleted', { count: count, target: target ? target.label : moveTo, name: label }), 'success');
        await fetchStats();
        document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
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

// ── Protein Quality Settings ────────────────────────
var pqData = [];

export async function loadPq() {
  try { pqData = await api('/api/protein-quality'); } catch(e) { pqData = []; showToast(t('toast_load_error'), 'error'); }
  renderPqTable();
}

export function renderPqTable() {
  var container = document.getElementById('pq-list');
  if (!pqData.length) { container.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px;text-align:center;padding:20px">No protein sources</p>'; return; }
  var h = '';
  pqData.forEach(function(row) {
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
  pqData.forEach(function(row) {
    var labelEl = document.getElementById('pqe-label-' + row.id);
    var pdcaasEl = document.getElementById('pqe-pdcaas-' + row.id);
    var diaasEl = document.getElementById('pqe-diaas-' + row.id);
    var kwEl = document.getElementById('pqe-kw-' + row.id);
    [labelEl, pdcaasEl, diaasEl, kwEl].forEach(function(el) {
      if (el) el.addEventListener('change', function() { autosavePq(row.id); });
    });
  });
  // Attach delete handlers
  container.querySelectorAll('[data-action="delete-pq"]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      deletePq(parseInt(btn.dataset.pqId, 10), btn.dataset.pqLabel);
    });
  });
}

var _pqSaveTimers = {};
export function autosavePq(id) { clearTimeout(_pqSaveTimers[id]); _pqSaveTimers[id] = setTimeout(function() { savePqField(id); }, 400); }

export async function savePqField(id) {
  var label = document.getElementById('pqe-label-' + id);
  var kw = document.getElementById('pqe-kw-' + id);
  var pdcaas = document.getElementById('pqe-pdcaas-' + id);
  var diaas = document.getElementById('pqe-diaas-' + id);
  if (!label || !kw || !pdcaas || !diaas) return;
  var kwVal = kw.value.trim();
  var pdVal = parseFloat(pdcaas.value);
  var diVal = parseFloat(diaas.value);
  if (!kwVal || isNaN(pdVal) || isNaN(diVal)) return;
  var keywords = kwVal.split(',').map(function(k) { return k.trim(); }).filter(Boolean);
  try {
    var res = await api('/api/protein-quality/' + id, { method: 'PUT', body: JSON.stringify({ label: label.value.trim(), keywords: keywords, pdcaas: pdVal, diaas: diVal }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    showToast(t('toast_updated'), 'success');
    var item = pqData.find(function(r) { return r.id === id; });
    if (item) { item.label = label.value.trim(); item.keywords = keywords; item.pdcaas = pdVal; item.diaas = diVal; }
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addPq() {
  var label = document.getElementById('pq-add-label').value.trim();
  var kw = document.getElementById('pq-add-kw').value.trim();
  var pdcaas = parseFloat(document.getElementById('pq-add-pdcaas').value);
  var diaas = parseFloat(document.getElementById('pq-add-diaas').value);
  if (!kw || isNaN(pdcaas) || isNaN(diaas)) { showToast(t('toast_pq_keywords_required'), 'error'); return; }
  var keywords = kw.split(',').map(function(k) { return k.trim(); }).filter(Boolean);
  var res = await api('/api/protein-quality', { method: 'POST', body: JSON.stringify({ label: label, keywords: keywords, pdcaas: pdcaas, diaas: diaas }) });
  if (res.error) { showToast(res.error, 'error'); return; }
  document.getElementById('pq-add-label').value = '';
  document.getElementById('pq-add-kw').value = '';
  document.getElementById('pq-add-pdcaas').value = '';
  document.getElementById('pq-add-diaas').value = '';
  showToast(t('toast_pq_added', { name: (label || keywords[0]) }), 'success');
  loadPq();
}

export async function deletePq(id, label) {
  if (!await showConfirmModal('&#128465;', esc(label), t('confirm_delete_product', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
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
  if (!await showConfirmModal('&#9888;', t('restore_title') || 'Restore database', t('restore_confirm') || 'Are you sure? This replaces ALL existing data in the database.', t('btn_restore') || 'Restore', t('btn_cancel'))) { input.value = ''; return; }
  var reader = new FileReader();
  reader.onload = async function(e) {
    try {
      var data = JSON.parse(e.target.result);
      var res = await api('/api/restore', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else { state.imageCache = {}; showToast(res.message, 'success'); loadData(); if (state.currentView === 'settings') loadSettings(); }
    } catch(err) { showToast(t('toast_invalid_file'), 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

export function handleImport(input) {
  if (!input.files.length) return;
  var reader = new FileReader();
  reader.onload = async function(e) {
    try {
      var data = JSON.parse(e.target.result);
      var res = await api('/api/import', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else { state.imageCache = {}; showToast(res.message, 'success'); loadData(); if (state.currentView === 'settings') loadSettings(); }
    } catch(err) { showToast(t('toast_invalid_file'), 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

// ── Collapsible settings sections ───────────────────
export function toggleSettingsSection(header) {
  var body = header.nextElementSibling;
  if (!body) return;
  var isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : '';
  header.classList.toggle('open', !isOpen);
}

// Drag-and-drop for restore
export function initRestoreDragDrop() {
  var drop = document.getElementById('restore-drop');
  if (!drop) return;
  drop.addEventListener('dragover', function(e) { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', function() { drop.classList.remove('dragover'); });
  drop.addEventListener('drop', function(e) {
    e.preventDefault();
    drop.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      var fi = { files: e.dataTransfer.files };
      Object.defineProperty(fi, 'value', { set: function() {}, get: function() { return ''; } });
      handleRestore(fi);
    }
  });
}

// ── OFF Credentials ─────────────────────────────────
async function loadOffCredentials() {
  try {
    var data = await api('/api/settings/off-credentials');
    var el = document.getElementById('off-user-id');
    if (el) el.value = data.off_user_id || '';
    var pw = document.getElementById('off-password');
    if (pw) pw.value = data.has_password ? '••••••••' : '';
  } catch(e) { showToast(t('toast_load_error'), 'error'); }
}

export async function saveOffCredentials() {
  var userId = (document.getElementById('off-user-id').value || '').trim();
  var pw = document.getElementById('off-password').value || '';
  if (pw === '••••••••') pw = '';
  var body = { off_user_id: userId };
  if (pw) body.off_password = pw;
  try {
    await api('/api/settings/off-credentials', { method: 'PUT', body: JSON.stringify(body) });
    showToast(t('toast_off_credentials_saved'), 'success');
  } catch(e) { showToast(t('toast_save_error'), 'error'); }
}
