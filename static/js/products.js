// ── Product CRUD & Registration ─────────────────────
import { state, api, fetchProducts, fetchStats, NUTRI_IDS, esc, showConfirmModal, showToast, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import { buildFilters, rerender, buildTypeSelect } from './filters.js';
import { renderResults } from './render.js';
import { isValidEan } from './openfoodfacts.js';

// Re-export showToast so existing importers continue to work
export { showToast };

function numOrNull(id) { var v = document.getElementById(id).value; return v === '' ? null : +v; }

export function startEdit(id) { state.editingId = id; rerender(); }

export async function saveProduct(id) {
  var data = {
    name: document.getElementById('ed-name').value.trim(),
    type: document.getElementById('ed-type').value,
    ean: document.getElementById('ed-ean').value.trim(),
    brand: (document.getElementById('ed-brand') || { value: '' }).value.trim(),
    stores: (document.getElementById('ed-stores') || { value: '' }).value.trim(),
    ingredients: (document.getElementById('ed-ingredients') || { value: '' }).value.trim(),
    taste_score: numOrNull('ed-smak'),
    kcal: numOrNull('ed-kcal'),
    energy_kj: numOrNull('ed-energy_kj'),
    fat: numOrNull('ed-fat'),
    saturated_fat: numOrNull('ed-saturated_fat'),
    carbs: numOrNull('ed-carbs'),
    sugar: numOrNull('ed-sugar'),
    protein: numOrNull('ed-protein'),
    fiber: numOrNull('ed-fiber'),
    salt: numOrNull('ed-salt'),
    weight: numOrNull('ed-weight'),
    portion: numOrNull('ed-portion'),
    volume: numOrNull('ed-volume'),
    price: numOrNull('ed-price'),
    est_pdcaas: numOrNull('ed-est_pdcaas'),
    est_diaas: numOrNull('ed-est_diaas'),
  };
  if (!data.name) { showToast(t('toast_name_required'), 'error'); return; }
  if (data.ean && !isValidEan(data.ean)) { showToast(t('toast_invalid_ean'), 'error'); return; }
  try {
    await api('/api/products/' + id, { method: 'PUT', body: JSON.stringify(data) });
    state.editingId = null;
    showToast(t('toast_product_updated'), 'success');
    loadData();
  } catch(e) {
    console.error(e);
    showToast(t('toast_save_error'), 'error');
  }
}

export async function deleteProduct(id, name) {
  if (!name) {
    var product = state.cachedResults && state.cachedResults.find(function(p) { return p.id === id; });
    name = product ? product.name : '';
  }
  if (!await showConfirmModal('&#128465;', esc(name), t('confirm_delete_product', { name: esc(name) }), t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/products/' + id, { method: 'DELETE' });
    delete state.imageCache[id];
    state.expandedId = null;
    state.editingId = null;
    showToast(t('toast_product_deleted', { name: name }), 'error');
    loadData();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function loadData() {
  try {
    await fetchStats();
    buildFilters();
    document.getElementById('stats-line').textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
    buildTypeSelect();
    upgradeSelect(document.getElementById('f-volume'));
    var search = state.currentView === 'search' ? document.getElementById('search-input').value.trim() : '';
    var results = await fetchProducts(search, state.currentFilter);
    renderResults(results, search);
  } catch (e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export function switchView(v) {
  state.currentView = v;
  state.expandedId = null;
  state.editingId = null;
  document.querySelectorAll('.nav-tab').forEach(function(tab) { tab.classList.toggle('active', tab.dataset.view === v); });
  document.getElementById('view-search').style.display = v === 'search' ? '' : 'none';
  document.getElementById('view-register').style.display = v === 'register' ? '' : 'none';
  document.getElementById('view-settings').style.display = v === 'settings' ? '' : 'none';
  if (v === 'settings') {
    import('./settings.js').then(function(mod) { mod.loadSettings(); });
  } else {
    loadData();
  }
  if (v === 'search') document.getElementById('search-input').focus();
}

export function setFilter(f) {
  if (f === 'all') {
    state.currentFilter = [];
  } else {
    var i = state.currentFilter.indexOf(f);
    if (i >= 0) state.currentFilter.splice(i, 1);
    else state.currentFilter.push(f);
  }
  buildFilters();
  loadData();
}

export function toggleExpand(id) {
  state.expandedId = (state.expandedId === id) ? null : id;
  state.editingId = null;
  rerender();
}

export function onSearchInput() {
  var v = document.getElementById('search-input').value;
  document.getElementById('search-clear').classList.toggle('visible', v.length > 0);
  state.expandedId = null;
  state.editingId = null;
  clearTimeout(state.searchTimeout);
  state.searchTimeout = setTimeout(loadData, 250);
}

export function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear').classList.remove('visible');
  state.expandedId = null;
  state.editingId = null;
  loadData();
  document.getElementById('search-input').focus();
}

export async function registerProduct() {
  var name = document.getElementById('f-name').value.trim();
  if (!name) { showToast(t('toast_product_name_required'), 'error'); return; }
  var ean = document.getElementById('f-ean').value.trim();
  if (ean && !isValidEan(ean)) { showToast(t('toast_invalid_ean'), 'error'); return; }
  var btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.textContent = t('toast_saving');
  try {
    var body = {
      type: document.getElementById('f-type').value,
      name: name,
      ean: document.getElementById('f-ean').value.trim(),
      brand: document.getElementById('f-brand').value.trim(),
      stores: document.getElementById('f-stores').value.trim(),
      ingredients: document.getElementById('f-ingredients').value.trim(),
      taste_score: numOrNull('f-smak'),
      kcal: numOrNull('f-kcal'),
      energy_kj: numOrNull('f-energy_kj'),
      fat: numOrNull('f-fat'),
      saturated_fat: numOrNull('f-saturated_fat'),
      carbs: numOrNull('f-carbs'),
      sugar: numOrNull('f-sugar'),
      protein: numOrNull('f-protein'),
      fiber: numOrNull('f-fiber'),
      salt: numOrNull('f-salt'),
      weight: numOrNull('f-weight'),
      portion: numOrNull('f-portion'),
      volume: numOrNull('f-volume'),
      price: numOrNull('f-price'),
      est_pdcaas: numOrNull('f-est_pdcaas'),
      est_diaas: numOrNull('f-est_diaas'),
    };
    var registeredType = body.type;
    var result = await api('/api/products', { method: 'POST', body: JSON.stringify(body) });
    var newProductId = result.id;
    if (window._pendingImage && newProductId) {
      try { await api('/api/products/' + newProductId + '/image', { method: 'PUT', body: JSON.stringify({ image: window._pendingImage }) }); } catch(ie) { showToast(t('toast_image_upload_error'), 'error'); }
      window._pendingImage = null;
    }
    document.getElementById('f-name').value = '';
    document.getElementById('f-ean').value = '';
    document.getElementById('f-brand').value = '';
    document.getElementById('f-stores').value = '';
    document.getElementById('f-ingredients').value = '';
    document.getElementById('f-est_pdcaas').value = '';
    document.getElementById('f-est_diaas').value = '';
    var pqw = document.getElementById('f-protein-quality-wrap');
    if (pqw) pqw.style.display = 'none';
    var pqr = document.getElementById('f-pq-result');
    if (pqr) pqr.style.display = 'none';
    // Lazy import to avoid circular dep
    import('./openfoodfacts.js').then(function(mod) { mod.validateOffBtn('f'); });
    NUTRI_IDS.forEach(function(id) { document.getElementById('f-' + id).value = ''; });
    document.getElementById('f-volume').value = '';
    upgradeSelect(document.getElementById('f-volume'));
    document.getElementById('f-price').value = '';
    document.getElementById('f-smak').value = '3';
    document.getElementById('smak-val').textContent = '3';
    showToast(t('toast_product_added', { name: name }), 'success');

    // Switch to search view filtered by the registered category
    state.currentFilter = [registeredType];
    switchView('search');
    // Open filters to show selected category
    var filterRow = document.getElementById('filter-row');
    var filterTog = document.getElementById('filter-toggle');
    if (filterRow && !filterRow.classList.contains('open')) {
      filterRow.classList.add('open');
      if (filterTog) filterTog.classList.add('open');
    }
    // Clear search input
    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.remove('visible');
    // switchView already calls loadData() which fetches and renders.
    // Wait for DOM to settle, then scroll to and highlight the new product.
    if (newProductId) {
      setTimeout(function() {
        var rowEl = document.querySelector('.table-row[data-product-id="' + newProductId + '"]');
        if (rowEl) {
          rowEl.classList.add('scan-highlight');
          rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(function() { rowEl.classList.remove('scan-highlight'); }, 5000);
        }
      }, 500);
    }
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
  btn.disabled = false;
  btn.textContent = t('btn_register_product');
}
