// ── Product CRUD & Registration ─────────────────────
import { state, api, fetchProducts, fetchStats, NUTRI_IDS, showConfirmModal, showToast, upgradeSelect, announceStatus, trapFocus, esc } from './state.js';
import { initInfiniteScroll, teardownInfiniteScroll } from './scroll.js';
import { t } from './i18n.js';
import { buildFilters, rerender, buildTypeSelect } from './filters.js';
import { renderResults, getFlagConfig } from './render.js';
import { isValidEan } from './off-utils.js';
import { showEditDuplicateModal, showMergeConflictModal } from './off-conflicts.js';
import { showDuplicateMergeModal } from './off-duplicates.js';
import { showOffAddReview } from './off-review.js';
import { initTagInput, getTagsForSave } from './tags.js';
import { loadEanManager } from './ean-manager.js';
export { loadEanManager, addEan, deleteEan, setEanPrimary, unsyncEan } from './ean-manager.js';

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
    taste_note: (document.getElementById(prefix + '-taste_note') || { value: '' }).value.trim(),
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
    flags: Object.entries(getFlagConfig()).filter(([, v]) => v.type === 'user').reduce((acc, [f]) => {
      const cb = document.getElementById(prefix + '-flag-' + f);
      if (cb && cb.checked) acc.push(f);
      return acc;
    }, []),
    ...(prefix === 'ed' ? { tagIds: getTagsForSave() } : {}),
  };
}

export function startEdit(id) {
  state.editingId = id;
  rerender();
  requestAnimationFrame(() => {
    const form = document.querySelector('.edit-form');
    if (form) {
      form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      const firstInput = form.querySelector('#ed-name');
      if (firstInput) firstInput.focus();
    }
  });
}

export async function saveProduct(id) {
  const data = collectFormFields('ed');
  if (window._pendingOFFSync) {
    data.from_off = true;
    window._pendingOFFSync = null;
    // If the OFF fetch targeted a specific (possibly non-primary) EAN, pass
    // it through so the backend marks THAT row as synced without swapping
    // which EAN is primary.
    if (window._pendingOFFEan) {
      data.from_off_ean = window._pendingOFFEan;
      window._pendingOFFEan = null;
    }
  }
  const offAppliedFields = window._offAppliedFields; window._offAppliedFields = null;
  if (!data.name) { showToast(t('toast_name_required'), 'error'); return; }
  if (data.ean && !isValidEan(data.ean)) { showToast(t('toast_invalid_ean'), 'error'); return; }
  const saveBtn = document.querySelector('[data-action="save-product"][data-id="' + id + '"]');
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = t('toast_saving'); }
  // Check for duplicate EAN/name before saving
  let mergedOrDeleted = false;
  if (data.ean || data.name) {
    try {
      const dupResult = await api('/api/products/' + id + '/check-duplicate', {
        method: 'POST', body: JSON.stringify({ ean: data.ean, name: data.name })
      });
      if (dupResult.duplicate) {
        const aIsSynced = dupResult.a_is_synced_with_off;
        const result = await showDuplicateMergeModal(data, dupResult.duplicate, aIsSynced);
        if (result === null) return; // User cancelled
        const { scenario, choices } = result;

        if (scenario === 'skip') {
          // User confirmed this is not the same product — skip merge, continue saving
        } else if (scenario === 'b_synced') {
          // B (duplicate) is synced with OFF — A will be deleted, merge into B
          // If user fetched fresh OFF data, include OFF-provided fields so B gets updated
          if (offAppliedFields) {
            for (const f of offAppliedFields) {
              if (data[f] != null && data[f] !== '') choices[f] = data[f];
            }
          }
          await api('/api/products/' + dupResult.duplicate.id + '/merge', {
            method: 'POST', body: JSON.stringify({ source_id: id, choices: choices })
          });
          showToast(t('toast_duplicate_merged'), 'success');
          state.editingId = null;
          state.cachedResults = state.cachedResults.filter(p => p.id !== id);
          loadData();
          // Expand the surviving product (B)
          setTimeout(() => { state.expandedId = dupResult.duplicate.id; }, 300);
          return; // Don't save A — it's been deleted by the merge
        } else if (scenario === 'a_synced') {
          // A is synced, B is not — B will be deleted, merge into A
          for (const [field, val] of Object.entries(choices)) {
            data[field] = val;
          }
          await api('/api/products/' + id + '/merge', {
            method: 'POST', body: JSON.stringify({ source_id: dupResult.duplicate.id, choices: choices })
          });
          showToast(t('toast_duplicate_merged'), 'success');
          mergedOrDeleted = true;
          state.cachedResults = state.cachedResults.filter(p => p.id !== dupResult.duplicate.id);
        } else {
          // Neither synced — merge into A (A becomes the merged product), delete B
          for (const [field, val] of Object.entries(choices)) {
            data[field] = val;
          }
          await api('/api/products/' + id + '/merge', {
            method: 'POST', body: JSON.stringify({ source_id: dupResult.duplicate.id, choices: choices })
          });
          showToast(t('toast_duplicate_merged'), 'success');
          mergedOrDeleted = true;
          state.cachedResults = state.cachedResults.filter(p => p.id !== dupResult.duplicate.id);
        }
      }
    } catch (e) {
      console.error('Duplicate check failed:', e);
      showToast(t('toast_network_error'), 'error');
      return;
    }
  }
  try {
    await api('/api/products/' + id, { method: 'PUT', body: JSON.stringify(data) });
    state.editingId = null;
    showToast(t('toast_product_updated'), 'success');
    loadData();
  } catch(e) {
    console.error(e);
    showToast(t('toast_save_error'), 'error');
    if (mergedOrDeleted) {
      state.editingId = null;
      loadData();
    }
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = t('btn_save'); }
  }
}

export async function unlockEan(id) {
  try {
    await api('/api/products/' + id + '/unsync', { method: 'POST' });
    const p = state.cachedResults.find(x => x.id === id);
    if (p) p.flags = (p.flags || []).filter(f => f !== 'is_synced_with_off');
    const mgr = document.getElementById('ean-manager-' + id);
    if (mgr) mgr.dataset.locked = '0';
    const unlockBtn = document.querySelector('[data-action="unlock-ean"][data-id="' + id + '"]');
    if (unlockBtn) unlockBtn.style.display = 'none';
    await loadEanManager(id, false);
    showToast(t('toast_ean_unlocked'), 'success');
  } catch (e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

let _pendingDelete = null;

export async function deleteProduct(id, name) {
  if (!name) {
    const product = state.cachedResults && state.cachedResults.find((p) => p.id === id);
    name = product ? product.name : '';
  }
  if (!await showConfirmModal('\u{1F5D1}', name, t('confirm_delete_product', { name: name }), t('btn_delete'), t('btn_cancel'), true)) return;

  // Cancel any previous pending delete
  if (_pendingDelete) { clearTimeout(_pendingDelete.timer); _pendingDelete = null; }

  // Cache the product data for undo
  const cachedProduct = state.cachedResults && state.cachedResults.find((p) => p.id === id);
  const cachedImage = state.imageCache[id];

  // Remove from UI immediately
  state.cachedResults = (state.cachedResults || []).filter((p) => p.id !== id);
  delete state.imageCache[id];
  state.expandedId = null;
  state.editingId = null;
  rerender();

  // Schedule actual delete after 5 seconds
  var pending = {
    timer: setTimeout(async () => {
      _pendingDelete = null;
      try {
        await api('/api/products/' + id, { method: 'DELETE' });
      } catch(e) {
        console.error(e);
        showToast(t('toast_network_error'), 'error');
        // Restore on failure
        if (cachedProduct) { state.cachedResults.push(cachedProduct); }
        if (cachedImage) { state.imageCache[id] = cachedImage; }
        loadData();
      }
    }, 5000)
  };
  _pendingDelete = pending;

  showToast(t('toast_product_deleted', { name: name }), 'success', {
    duration: 5000,
    onUndo: function() {
      if (_pendingDelete === pending) {
        clearTimeout(pending.timer);
        _pendingDelete = null;
      }
      // Restore product to cached results
      if (cachedProduct) { state.cachedResults.push(cachedProduct); }
      if (cachedImage) { state.imageCache[id] = cachedImage; }
      rerender();
      showToast(t('toast_delete_undone'), 'info');
    }
  });
}

export async function loadData() {
  try {
    // Reset pagination for fresh load
    teardownInfiniteScroll();
    state.pagination.offset = 0;
    state.pagination.total = null;
    state.pagination.inFlight = false;

    await fetchStats();
    buildFilters();
    const statsEl = document.getElementById('stats-line');
    if (statsEl) statsEl.textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
    buildTypeSelect();
    upgradeSelect(document.getElementById('f-volume'));
    const searchInputEl = document.getElementById('search-input');
    const search = state.currentView === 'search' && searchInputEl ? searchInputEl.value.trim() : '';
    const data = await fetchProducts(search, state.currentFilter, {
      limit: state.pagination.pageSize,
      offset: 0,
    });
    // Handle {products, total} response or plain array (backend compat)
    const results = Array.isArray(data) ? data : (data.products || []);
    const total = Array.isArray(data) ? null : (data.total != null ? data.total : null);
    if (total !== null) state.pagination.total = total;
    state.pagination.offset = results.length > 0 ? state.pagination.pageSize : 0;
    renderResults(results, search);
    announceStatus(t('stats_line', { total: results.length, types: state.cachedStats.types }));
    // Set up infinite scroll if more results may exist
    const allLoaded = total !== null && results.length >= total;
    if (!allLoaded) {
      initInfiniteScroll(() => {
        const si = document.getElementById('search-input');
        return state.currentView === 'search' && si ? si.value.trim() : '';
      });
    }
  } catch (e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export function switchView(v) {
  teardownInfiniteScroll();
  state.cachedResults = [];
  state.currentView = v;
  state.expandedId = null;
  state.editingId = null;
  document.querySelectorAll('.nav-tab').forEach((tab) => { tab.classList.toggle('active', tab.dataset.view === v); });
  document.getElementById('view-search').style.display = v === 'search' ? '' : 'none';
  document.getElementById('view-register').style.display = v === 'register' ? '' : 'none';
  document.getElementById('view-settings').style.display = v === 'settings' ? '' : 'none';
  if (v === 'settings') {
    import('./settings-weights.js').then((mod) => { mod.loadSettings(); });
  } else {
    loadData();
  }
  if (v === 'search') { const si = document.getElementById('search-input'); if (si) si.focus(); }
}

export function setFilter(f) {
  if (f === 'all') {
    state.currentFilter = [];
  } else {
    const i = state.currentFilter.indexOf(f);
    if (i >= 0) state.currentFilter.splice(i, 1);
    else state.currentFilter.push(f);
  }
  state.cachedResults = [];
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
  state.cachedResults = [];
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

function _showDuplicateModal(duplicate) {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal';
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '\u26A0\uFE0F';
    modal.appendChild(iconDiv);
    const h3 = document.createElement('h3');
    h3.textContent = t('duplicate_found_title');
    modal.appendChild(h3);
    const pEl = document.createElement('p');
    const msgKey = duplicate.is_synced_with_off ? 'duplicate_found_synced' : 'duplicate_found_unsynced';
    pEl.textContent = t(msgKey, { match_type: duplicate.match_type, name: duplicate.name });
    modal.appendChild(pEl);
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    if (!duplicate.is_synced_with_off) {
      const mergeBtn = document.createElement('button');
      mergeBtn.className = 'scan-modal-btn-register confirm-yes';
      mergeBtn.textContent = t('duplicate_action_merge');
      mergeBtn.addEventListener('click', () => { bg.remove(); resolve('overwrite'); });
      actions.appendChild(mergeBtn);
      const createBtn = document.createElement('button');
      createBtn.className = 'scan-modal-btn-register';
      createBtn.textContent = t('duplicate_action_create_new');
      createBtn.addEventListener('click', () => { bg.remove(); resolve('create_new'); });
      actions.appendChild(createBtn);
    }
    const cancelBtn = document.createElement('button');
    cancelBtn.className = duplicate.is_synced_with_off ? 'scan-modal-btn-register confirm-yes' : 'scan-modal-btn-cancel confirm-no';
    cancelBtn.textContent = duplicate.is_synced_with_off ? t('btn_ok') : t('btn_cancel');
    cancelBtn.addEventListener('click', () => { bg.remove(); resolve('cancel'); });
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);
    trapFocus(bg);
  });
}

async function _submitProduct(body, on_duplicate) {
  const payload = Object.assign({}, body);
  if (on_duplicate) payload.on_duplicate = on_duplicate;
  return await api('/api/products', { method: 'POST', body: JSON.stringify(payload) });
}

export async function registerProduct() {
  const nameInput = document.getElementById('f-name');
  const nameError = document.getElementById('f-name-error');
  const eanInput = document.getElementById('f-ean');
  const eanError = document.getElementById('f-ean-error');
  const name = nameInput.value.trim();

  // Clear previous validation state
  nameInput.setAttribute('aria-invalid', 'false');
  if (nameError) nameError.style.display = 'none';
  eanInput.setAttribute('aria-invalid', 'false');
  if (eanError) eanError.style.display = 'none';

  if (!name) {
    nameInput.setAttribute('aria-invalid', 'true');
    if (nameError) nameError.style.display = '';
    nameInput.focus();
    showToast(t('toast_product_name_required'), 'error');
    return;
  }
  const ean = eanInput.value.trim();
  if (ean && !isValidEan(ean)) {
    eanInput.setAttribute('aria-invalid', 'true');
    if (eanError) eanError.style.display = '';
    eanInput.focus();
    showToast(t('toast_invalid_ean'), 'error');
    return;
  }
  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.textContent = t('toast_saving');
  try {
    const body = collectFormFields('f');
    if (window._pendingOFFSync) { body.from_off = true; window._pendingOFFSync = null; }
    const registeredType = body.type;
    let result;
    try {
      result = await _submitProduct(body);
    } catch(e) {
      if (e.status === 409 && e.data && e.data.duplicate) {
        const dup = e.data.duplicate;
        if (dup.is_synced_with_off) {
          // Synced with OFF — show info-only modal, no merge allowed
          await _showDuplicateModal(dup);
          return;
        }
        const choice = await _showDuplicateModal(dup);
        if (choice === 'cancel') { return; }
        if (choice === 'overwrite') {
          result = await _submitProduct(body, 'overwrite');
        } else {
          result = await _submitProduct(body, 'allow_duplicate');
        }
      } else {
        throw e;
      }
    }
    const newProductId = result.id;
    if (window._pendingImage && newProductId) {
      try { await api('/api/products/' + newProductId + '/image', { method: 'PUT', body: JSON.stringify({ image: window._pendingImage }) }); } catch(ie) { showToast(t('toast_image_upload_error'), 'error'); }
      window._pendingImage = null;
    }
    // Ask if user wants to add product to OFF (only if not already from OFF and has EAN)
    if (!body.from_off && ean) {
      const wantsOff = await showConfirmModal(
        '\u{1F30E}', t('off_ask_add_to_off_title'),
        t('off_ask_add_to_off'),
        t('btn_yes'), t('btn_no')
      );
      if (wantsOff) {
        await showOffAddReview(ean, 'f');
      }
    }
    document.getElementById('f-name').value = '';
    document.getElementById('f-ean').value = '';
    document.getElementById('f-brand').value = '';
    document.getElementById('f-stores').value = '';
    document.getElementById('f-ingredients').value = '';
    document.getElementById('f-taste_note').value = '';
    document.getElementById('f-est_pdcaas').value = '';
    document.getElementById('f-est_diaas').value = '';
    const pqw = document.getElementById('f-protein-quality-wrap');
    if (pqw) pqw.style.display = 'none';
    const pqr = document.getElementById('f-pq-result');
    if (pqr) pqr.style.display = 'none';
    // Lazy import to avoid circular dep
    import('./off-utils.js').then((mod) => { mod.validateOffBtn('f'); }).catch(() => {});
    NUTRI_IDS.forEach((id) => { document.getElementById('f-' + id).value = ''; });
    document.getElementById('f-volume').value = '';
    upgradeSelect(document.getElementById('f-volume'));
    document.getElementById('f-price').value = '';
    document.getElementById('f-type').value = '';
    document.getElementById('f-smak').value = '3';
    document.getElementById('smak-val').textContent = '3';
    const tasteLabel = document.getElementById('smak-label-text');
    if (tasteLabel) { tasteLabel.setAttribute('data-i18n-param-val', '3'); tasteLabel.textContent = t('label_taste', { val: '3' }); }
    const toastKey = result.merged ? 'toast_product_merged' : 'toast_product_added';
    showToast(t(toastKey, { name: name }), 'success');
    announceStatus(t(toastKey, { name: name }));

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
  } catch(e) { console.error(e); showToast(e.message || t('toast_save_error'), 'error'); }
  finally {
    btn.disabled = false;
    btn.textContent = t('btn_register_product');
  }
}
