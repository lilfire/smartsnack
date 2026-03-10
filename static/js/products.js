// ── Product CRUD & Registration ─────────────────────
import { state, api, fetchProducts, fetchStats, NUTRI_IDS, showConfirmModal, showToast, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import { buildFilters, rerender, buildTypeSelect } from './filters.js';
import { renderResults } from './render.js';
import { isValidEan } from './openfoodfacts.js';

// Re-export showToast so existing importers continue to work
export { showToast };

function numOrNull(id) { const el = document.getElementById(id); if (!el) return null; const v = el.value; return v === '' ? null : +v; }

function collectFormFields(prefix) {
  return {
    name: document.getElementById(prefix + '-name').value.trim(),
    type: document.getElementById(prefix + '-type').value,
    ean: document.getElementById(prefix + '-ean').value.trim(),
    brand: (document.getElementById(prefix + '-brand') || { value: '' }).value.trim(),
    stores: (document.getElementById(prefix + '-stores') || { value: '' }).value.trim(),
    ingredients: (document.getElementById(prefix + '-ingredients') || { value: '' }).value.trim(),
    taste_score: numOrNull(prefix + '-smak'),
    kcal: numOrNull(prefix + '-kcal'),
    energy_kj: numOrNull(prefix + '-energy_kj'),
    fat: numOrNull(prefix + '-fat'),
    saturated_fat: numOrNull(prefix + '-saturated_fat'),
    carbs: numOrNull(prefix + '-carbs'),
    sugar: numOrNull(prefix + '-sugar'),
    protein: numOrNull(prefix + '-protein'),
    fiber: numOrNull(prefix + '-fiber'),
    salt: numOrNull(prefix + '-salt'),
    weight: numOrNull(prefix + '-weight'),
    portion: numOrNull(prefix + '-portion'),
    volume: numOrNull(prefix + '-volume'),
    price: numOrNull(prefix + '-price'),
    est_pdcaas: numOrNull(prefix + '-est_pdcaas'),
    est_diaas: numOrNull(prefix + '-est_diaas'),
    flags: ['is_discontinued'].reduce((acc, f) => {
      const cb = document.getElementById(prefix + '-flag-' + f);
      if (cb && cb.checked) acc.push(f);
      return acc;
    }, []),
  };
}

export function startEdit(id) { state.editingId = id; rerender(); }

export async function saveProduct(id) {
  const data = collectFormFields('ed');
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
    const product = state.cachedResults && state.cachedResults.find((p) => p.id === id);
    name = product ? product.name : '';
  }
  if (!await showConfirmModal('\u{1F5D1}', name, t('confirm_delete_product', { name: name }), t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/products/' + id, { method: 'DELETE' });
    delete state.imageCache[id];
    state.expandedId = null;
    state.editingId = null;
    showToast(t('toast_product_deleted', { name: name }), 'success');
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
    const search = state.currentView === 'search' ? document.getElementById('search-input').value.trim() : '';
    const results = await fetchProducts(search, state.currentFilter);
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
  document.querySelectorAll('.nav-tab').forEach((tab) => { tab.classList.toggle('active', tab.dataset.view === v); });
  document.getElementById('view-search').style.display = v === 'search' ? '' : 'none';
  document.getElementById('view-register').style.display = v === 'register' ? '' : 'none';
  document.getElementById('view-settings').style.display = v === 'settings' ? '' : 'none';
  if (v === 'settings') {
    import('./settings.js').then((mod) => { mod.loadSettings(); });
  } else {
    loadData();
  }
  if (v === 'search') document.getElementById('search-input').focus();
}

export function setFilter(f) {
  if (f === 'all') {
    state.currentFilter = [];
  } else {
    const i = state.currentFilter.indexOf(f);
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
  const el = document.getElementById('search-input');
  if (el.disabled) return;
  const v = el.value;
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
  const name = document.getElementById('f-name').value.trim();
  if (!name) { showToast(t('toast_product_name_required'), 'error'); return; }
  const ean = document.getElementById('f-ean').value.trim();
  if (ean && !isValidEan(ean)) { showToast(t('toast_invalid_ean'), 'error'); return; }
  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.textContent = t('toast_saving');
  try {
    const body = collectFormFields('f');
    if (window._pendingOFFSync) { body.from_off = true; window._pendingOFFSync = null; }
    const registeredType = body.type;
    const result = await api('/api/products', { method: 'POST', body: JSON.stringify(body) });
    const newProductId = result.id;
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
    const pqw = document.getElementById('f-protein-quality-wrap');
    if (pqw) pqw.style.display = 'none';
    const pqr = document.getElementById('f-pq-result');
    if (pqr) pqr.style.display = 'none';
    // Lazy import to avoid circular dep
    import('./openfoodfacts.js').then((mod) => { mod.validateOffBtn('f'); });
    NUTRI_IDS.forEach((id) => { document.getElementById('f-' + id).value = ''; });
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
    const filterRow = document.getElementById('filter-row');
    const filterTog = document.getElementById('filter-toggle');
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
      setTimeout(() => {
        const rowEl = document.querySelector('.table-row[data-product-id="' + newProductId + '"]');
        if (rowEl) {
          rowEl.classList.add('scan-highlight');
          rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(() => { rowEl.classList.remove('scan-highlight'); }, 5000);
        }
      }, 500);
    }
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
  finally {
    btn.disabled = false;
    btn.textContent = t('btn_register_product');
  }
}
