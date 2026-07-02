// ── Scan Product Picker: search local DB to assign EAN ──
import { state, api, esc, catEmoji, catLabel, safeDataUri, fetchProducts, trapFocus } from './state.js';
import { t } from './i18n.js';
import { buildFilters, rerender } from './filters.js';
import { loadProductImage } from './images.js';
import { showToast, switchView, loadData } from './products.js';

let _scanPickerEan = null;

export function showScanProductPicker(ean) {
  _scanPickerEan = ean;
  document.body.style.overflow = 'hidden';
  const bg = document.createElement('div');
  bg.className = 'off-modal-bg';
  bg.id = 'scan-picker-bg';
  bg.onclick = (e) => { if (e.target === bg) closeScanPicker(); };

  const modal = document.createElement('div');
  modal.className = 'off-modal';

  const head = document.createElement('div');
  head.className = 'off-modal-head';
  const headH3 = document.createElement('h3');
  headH3.textContent = '\u270E ' + t('off_search_btn') + ' \u2014 EAN ' + ean;
  head.appendChild(headH3);
  const headClose = document.createElement('button');
  headClose.className = 'off-modal-close';
  headClose.textContent = '\u00D7';
  headClose.setAttribute('aria-label', t('btn_close'));
  headClose.addEventListener('click', () => { closeScanPicker(); });
  head.appendChild(headClose);
  modal.appendChild(head);

  const searchDiv = document.createElement('div');
  searchDiv.className = 'off-modal-search';
  const searchInput = document.createElement('input');
  searchInput.id = 'scan-picker-input';
  searchInput.placeholder = t('search_placeholder');
  searchInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') scanPickerSearch(); });
  searchDiv.appendChild(searchInput);
  const searchBtn = document.createElement('button');
  searchBtn.textContent = t('off_search_btn');
  searchBtn.addEventListener('click', () => { scanPickerSearch(); });
  searchDiv.appendChild(searchBtn);
  modal.appendChild(searchDiv);

  const countDiv = document.createElement('div');
  countDiv.className = 'off-modal-count';
  countDiv.id = 'scan-picker-count';
  countDiv.textContent = t('search_placeholder');
  modal.appendChild(countDiv);

  const bodyDiv = document.createElement('div');
  bodyDiv.className = 'off-modal-body';
  bodyDiv.id = 'scan-picker-body';
  bodyDiv.innerHTML = '<div class="off-modal-empty">\u{1F50D} ' + esc(t('search_placeholder')) + '</div>';
  modal.appendChild(bodyDiv);

  bg.setAttribute('role', 'dialog');
  bg.setAttribute('aria-modal', 'true');
  bg.appendChild(modal);
  document.body.appendChild(bg);
  trapFocus(bg);
  setTimeout(() => { if (searchInput) searchInput.focus(); }, 100);
}

export function closeScanPicker() {
  const el = document.getElementById('scan-picker-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
  _scanPickerEan = null;
}

export async function scanPickerSearch() {
  const inp = document.getElementById('scan-picker-input');
  const query = inp ? inp.value.trim() : '';
  if (!query) { showToast(t('toast_enter_product_name'), 'error'); return; }
  const body = document.getElementById('scan-picker-body');
  const cnt = document.getElementById('scan-picker-count');
  body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if (cnt) cnt.textContent = t('scan_searching', { query: query });
  try {
    const raw = await fetchProducts(query, []);
    const results = Array.isArray(raw) ? raw : (raw.products || []);
    if (!results.length) {
      body.innerHTML = '<div class="off-modal-empty">' + esc(t('off_no_results_for', { query: query })) + '</div>';
      if (cnt) cnt.textContent = t('off_zero_results');
      return;
    }
    if (cnt) cnt.textContent = t(results.length === 1 ? 'scan_result_count_one' : 'scan_result_count_other', { count: results.length });
    let h = '';
    results.forEach((p) => {
      const imgTag = p.has_image ? '<div class="off-result-img" id="scan-pick-img-' + p.id + '" style="background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center"><span style="opacity:0.2">' + esc(catEmoji(p.type)) + '</span></div>'
        : '<div class="off-result-img" style="display:flex;align-items:center;justify-content:center"><span style="font-size:20px">' + esc(catEmoji(p.type)) + '</span></div>';
      const eanInfo = p.ean ? '<span class="off-result-ean">EAN: ' + esc(p.ean) + '</span>' : '<span class="off-result-ean" style="color:rgba(255,100,100,0.5)">' + esc(t('scan_no_ean')) + '</span>';
      h += '<div class="off-result" data-action="pick" data-id="' + p.id + '">'
        + imgTag
        + '<div class="off-result-info"><div class="off-result-name">' + esc(p.name) + '</div>'
        + '<div class="off-result-brand">' + esc(catLabel(p.type)) + (p.brand ? ' \u00B7 ' + esc(p.brand) : '') + '</div>'
        + eanInfo + '</div></div>';
    });
    // Replace body to clear old event listeners
    const newBody = body.cloneNode(false);
    newBody.innerHTML = h;
    body.parentNode.replaceChild(newBody, body);
    // Attach click handlers via event delegation on the new element
    newBody.addEventListener('click', (e) => {
      const row = e.target.closest('[data-action="pick"]');
      if (row) scanPickerSelect(parseInt(row.dataset.id, 10));
    });
    results.forEach((p) => {
      if (p.has_image) {
        loadProductImage(p.id).then((dataUri) => {
          if (!dataUri) return;
          const imgEl = document.getElementById('scan-pick-img-' + p.id);
          if (imgEl) { const safe = safeDataUri(dataUri); if (safe) imgEl.innerHTML = '<img src="' + safe + '" style="width:100%;height:100%;object-fit:cover;border-radius:8px">'; }
        });
      }
    });
  } catch(e) {
    const currentBody = document.getElementById('scan-picker-body');
    if (currentBody) currentBody.innerHTML = '<div class="off-modal-empty">' + esc(t('toast_network_error')) + '</div>';
    if (cnt) cnt.textContent = t('toast_network_error');
  }
}

export async function scanPickerSelect(productId) {
  const ean = _scanPickerEan;
  if (!ean) return;
  closeScanPicker();

  showToast(t('toast_saving_ean', { ean: ean }), 'info');
  try {
    const prod = await api('/api/products/' + productId);
    prod.ean = ean;
    delete prod.has_image; // computed column, rejected by update_product
    await api('/api/products/' + productId, { method: 'PUT', body: JSON.stringify(prod) });
    showToast(t('toast_ean_saved', { name: prod.name }), 'success');
  } catch(e) {
    showToast(t('toast_ean_save_error'), 'error');
    return;
  }

  showScanOffConfirm(ean, productId);
}

export function showScanOffConfirm(ean, productId) {
  document.body.style.overflow = 'hidden';
  const bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  bg.id = 'scan-off-confirm-bg';
  bg.onclick = (e) => { if (e.target === bg) closeScanOffConfirm(); };

  const modal = document.createElement('div');
  modal.className = 'scan-modal';
  const iconDiv = document.createElement('div');
  iconDiv.className = 'scan-modal-icon';
  iconDiv.textContent = '\u{1F30E}';
  modal.appendChild(iconDiv);
  const h3 = document.createElement('h3');
  h3.textContent = t('scan_fetch_off_title');
  modal.appendChild(h3);
  const eanDiv = document.createElement('div');
  eanDiv.className = 'scan-modal-ean';
  eanDiv.textContent = 'EAN: ' + ean;
  modal.appendChild(eanDiv);
  const p = document.createElement('p');
  p.textContent = t('scan_fetch_off_description');
  modal.appendChild(p);
  const actions = document.createElement('div');
  actions.className = 'scan-modal-actions';
  modal.appendChild(actions);

  const fetchBtn = document.createElement('button');
  fetchBtn.className = 'scan-modal-btn-register';
  fetchBtn.textContent = '\u{1F30E} ' + t('scan_fetch_data');
  fetchBtn.addEventListener('click', () => { scanOffFetch(ean, productId); });
  actions.appendChild(fetchBtn);

  const skipBtn = document.createElement('button');
  skipBtn.className = 'scan-modal-btn-cancel';
  skipBtn.textContent = t('scan_no_skip');
  skipBtn.addEventListener('click', () => { closeScanOffConfirm(); loadData(); });
  actions.appendChild(skipBtn);

  bg.setAttribute('role', 'dialog');
  bg.setAttribute('aria-modal', 'true');
  bg.appendChild(modal);
  document.body.appendChild(bg);
  trapFocus(bg);
  fetchBtn.focus();
}

export function closeScanOffConfirm() {
  const el = document.getElementById('scan-off-confirm-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
}

export async function scanOffFetch(ean, productId) {
  closeScanOffConfirm();
  if (state.currentView !== 'search') switchView('search');
  state.currentFilter = [];
  buildFilters();
  await loadData();
  state.expandedId = productId;
  state.editingId = productId;
  rerender();
  setTimeout(() => {
    const eanEl = document.getElementById('ed-ean');
    if (eanEl) eanEl.value = ean;
    Promise.all([import('./off-utils.js'), import('./off-api.js')]).then(([utilsMod, apiMod]) => {
      utilsMod.validateOffBtn('ed');
      setTimeout(() => { apiMod.lookupOFF('ed', productId); }, 200);
    });
  }, 300);
}
