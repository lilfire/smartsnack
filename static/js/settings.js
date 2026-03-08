// ── Weights, Categories, Protein Quality, Backup ────
import { state, api, esc, fetchStats } from './state.js';
import { t, getCurrentLang } from './i18n.js';
import { showToast, loadData } from './products.js';

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

export async function loadSettings() {
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
      langs.forEach(function(l) {
        var opt = document.createElement('option');
        opt.value = l.code;
        opt.textContent = (l.flag ? l.flag + ' ' : '') + l.label;
        langSelect.appendChild(opt);
      });
    } catch(e) {}
    langSelect.value = getCurrentLang();
  }
  loadCategories();
  loadPq();
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
    h += '<div class="weight-item enabled" id="wi-' + w.field + '" style="margin-bottom:10px;border-left:3px solid ' + col + '">'
      + '<div class="weight-header">'
      + '<div class="weight-top">'
      + '<label class="field-label" style="margin:0">' + esc(w.label) + '</label></div>'
      + '<span class="weight-val mono accent" id="wv-' + w.field + '">' + w.weight.toFixed(1) + '</span>'
      + '<button class="weight-cfg-btn" onclick="toggleWeightConfig(\'' + w.field + '\')" title="Advanced">&#9881;</button>'
      + '<button class="btn-sm btn-red" onclick="removeWeight(\'' + w.field + '\')" title="Remove">&#128465;</button></div>'
      + '<div class="weight-config" id="wcfg-' + w.field + '" style="display:none">'
      + '<div class="wc-row">'
      + '<select class="wc-select" id="wd-' + w.field + '" onchange="onWeightDirection(\'' + w.field + '\')">'
      + '<option value="lower" ' + (dirLower ? 'selected' : '') + '>' + t('direction_lower') + '</option>'
      + '<option value="higher" ' + (!dirLower ? 'selected' : '') + '>' + t('direction_higher') + '</option></select>'
      + '<select class="wc-select" id="wf-' + w.field + '" onchange="onWeightFormula(\'' + w.field + '\')">'
      + '<option value="minmax" ' + (!isDirect ? 'selected' : '') + '>MinMax (category)</option>'
      + '<option value="direct" ' + (isDirect ? 'selected' : '') + '>Direct (fixed max)</option></select>'
      + '<input type="number" class="wc-max" id="wn-' + w.field + '" value="' + (w.formula_min != null ? w.formula_min : '') + '" placeholder="Min" step="0.01" oninput="onWeightMin(\'' + w.field + '\')" style="' + (isDirect ? '' : 'display:none') + '">'
      + '<input type="number" class="wc-max" id="wm-' + w.field + '" value="' + (w.formula_max != null ? w.formula_max : '') + '" placeholder="Max" step="0.01" oninput="onWeightMax(\'' + w.field + '\')" style="' + (isDirect ? '' : 'display:none') + '">'
      + '</div></div>'
      + '<input type="range" min="0" max="100" step="1" value="' + w.weight + '" id="w-' + w.field + '" class="weight-slider" oninput="onWeightSlider(\'' + w.field + '\')">'
      + '</div>';
  });
  // Dropdown to add disabled weights
  if (disabled.length) {
    h += '<div class="weight-add-row">'
      + '<select class="field-select" id="weight-add-select">'
      + '<option value="">\u2014 ' + t('btn_add_weight') + ' \u2014</option>';
    disabled.forEach(function(w) {
      h += '<option value="' + w.field + '">' + esc(w.label) + '</option>';
    });
    h += '</select>'
      + '<button class="btn-register weight-add-btn" onclick="addWeightFromDropdown()">+</button>'
      + '</div>';
  }
  container.innerHTML = h;
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
      var minEl = document.getElementById('wn-' + w.field);
      var maxEl = document.getElementById('wm-' + w.field);
      var sliderEl = document.getElementById('w-' + w.field);
      var obj = { field: w.field, enabled: w.enabled, weight: parseFloat(sliderEl ? sliderEl.value : w.weight), direction: w.direction, formula: w.formula, formula_min: parseFloat(minEl ? minEl.value : 0) || 0, formula_max: parseFloat(maxEl ? maxEl.value : 0) || 0 };
      return obj;
    });
    await api('/api/weights', { method: 'PUT', body: JSON.stringify(payload) });
    showToast(t('toast_weights_saved'), 'success');
    loadData();
  } catch(e) { console.error('saveWeights error:', e); showToast(t('toast_save_error'), 'error'); }
  _weightSaving = false;
}


// ── Categories ──────────────────────────────────────
export async function loadCategories() {
  var cats = await api('/api/categories');
  var list = document.getElementById('cat-list');
  if (!cats.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No categories</p>'; return; }
  var h = '';
  cats.forEach(function(c) {
    var canDel = c.count === 0;
    h += '<div class="cat-item"><span class="cat-item-emoji">' + esc(c.emoji) + '</span>'
      + '<input class="cat-item-label-input" value="' + esc(c.label) + '" onchange="updateCategoryLabel(\'' + esc(c.name).replace(/'/g, "\\'") + '\',this.value)" title="' + t('label_display_name') + '">'
      + '<span class="cat-item-key">' + esc(c.name) + '</span><span class="cat-item-count">' + c.count + ' prod.</span>'
      + '<button class="btn-sm btn-red" ' + (canDel ? '' : 'disabled') + ' onclick="deleteCategory(\'' + esc(c.name).replace(/'/g, "\\'") + '\',\'' + esc(c.label).replace(/'/g, "\\'") + '\')">&#128465;</button></div>';
  });
  list.innerHTML = h;
}

export async function updateCategoryLabel(name, val) {
  if (!val.trim()) { showToast(t('toast_display_name_empty'), 'error'); loadCategories(); return; }
  await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ label: val.trim() }) });
  showToast(t('toast_category_updated'), 'success');
  await fetchStats();
  document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
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
  showToast(t('toast_category_added', { name: label }), 'success');
  await fetchStats();
  document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  loadCategories();
}

export async function deleteCategory(name, label) {
  if (!confirm(t('confirm_delete_category', { name: label }))) return;
  var res = await api('/api/categories/' + encodeURIComponent(name), { method: 'DELETE' });
  if (res.error) { showToast(res.error, 'error'); return; }
  showToast(t('toast_category_deleted', { name: label }), 'success');
  await fetchStats();
  document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  loadCategories();
}

// ── Protein Quality Settings ────────────────────────
var pqData = [];

export async function loadPq() {
  try { pqData = await api('/api/protein-quality'); } catch(e) { pqData = []; }
  renderPqTable();
}

export function renderPqTable() {
  var container = document.getElementById('pq-list');
  if (!pqData.length) { container.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px;text-align:center;padding:20px">No protein sources</p>'; return; }
  var h = '';
  pqData.forEach(function(row) {
    h += '<div class="pq-card">'
      + '<div class="pq-card-top">'
      + '<input class="cat-item-label-input" id="pqe-label-' + row.id + '" value="' + esc(row.label || row.keywords[0]) + '" onchange="autosavePq(' + row.id + ')" title="Name">'
      + '<span class="pq-badges"><span class="pq-badge"><span class="pq-badge-label">P </span>'
      + '<input class="pq-inline-num mono" id="pqe-pdcaas-' + row.id + '" type="number" step="0.01" min="0" max="1" value="' + row.pdcaas + '" onchange="autosavePq(' + row.id + ')">'
      + '</span><span class="pq-badge"><span class="pq-badge-label">D </span>'
      + '<input class="pq-inline-num mono" id="pqe-diaas-' + row.id + '" type="number" step="0.01" min="0" max="1.2" value="' + row.diaas + '" onchange="autosavePq(' + row.id + ')">'
      + '</span></span>'
      + '<button class="btn-sm btn-red" onclick="deletePq(' + row.id + ',\'' + esc(row.label || row.keywords[0]).replace(/'/g, "\\'") + '\')">&#128465;</button>'
      + '</div>'
      + '<input class="pq-kw-input" id="pqe-kw-' + row.id + '" value="' + esc(row.keywords.join(', ')) + '" onchange="autosavePq(' + row.id + ')" placeholder="Keywords (comma separated)">'
      + '</div>';
  });
  container.innerHTML = h;
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
  var res = await api('/api/protein-quality/' + id, { method: 'PUT', body: JSON.stringify({ label: label.value.trim(), keywords: keywords, pdcaas: pdVal, diaas: diVal }) });
  if (res.error) { showToast(res.error, 'error'); return; }
  showToast(t('toast_updated'), 'success');
  var item = pqData.find(function(r) { return r.id === id; });
  if (item) { item.label = label.value.trim(); item.keywords = keywords; item.pdcaas = pdVal; item.diaas = diVal; }
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
  if (!confirm(t('confirm_delete_product', { name: label }))) return;
  await api('/api/protein-quality/' + id, { method: 'DELETE' });
  showToast(t('toast_pq_deleted', { name: label }), 'success');
  loadPq();
}

// ── Backup / Restore / Import ───────────────────────
export function downloadBackup() {
  window.location.href = '/api/backup';
  showToast(t('toast_backup_downloaded'), 'success');
}

export function handleRestore(input) {
  if (!input.files.length) return;
  if (!confirm('Are you sure? This replaces ALL existing data in the database.')) { input.value = ''; return; }
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
