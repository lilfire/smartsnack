// ── Barcode Scanner (all scanner sections) ──────────
import { state, api, esc, catEmoji, catLabel, safeDataUri, fetchProducts, trapFocus } from './state.js';
import { t } from './i18n.js';
import { buildFilters, rerender } from './filters.js';
import { loadProductImage } from './images.js';
import { showToast, switchView, loadData } from './products.js';
import { renderResults } from './render.js';
import { createTorchButton, checkTorchSupport, resetTorch } from './scanner-torch.js';

let _scanner = null;
let _scannerCtx = { prefix: null, productId: null };

// Shared scanner UI builder to avoid duplication between openScanner and openSearchScanner
function buildScannerUI(headerHtml, hintText, closeFn) {
  const bg = document.createElement('div');
  bg.className = 'scanner-bg';
  bg.id = 'scanner-bg';
  document.body.style.overflow = 'hidden';

  const header = document.createElement('div');
  header.className = 'scanner-header';
  const h3 = document.createElement('h3');
  h3.textContent = headerHtml;
  header.appendChild(h3);
  const closeBtn = document.createElement('button');
  closeBtn.className = 'scanner-close';
  closeBtn.textContent = '\u00D7';
  closeBtn.addEventListener('click', closeFn);
  header.appendChild(closeBtn);
  bg.appendChild(header);

  const wrap = document.createElement('div');
  wrap.className = 'scanner-video-wrap';
  const readerDiv = document.createElement('div');
  readerDiv.id = 'scanner-reader';
  wrap.appendChild(readerDiv);
  const hint = document.createElement('div');
  hint.className = 'scanner-hint';
  hint.textContent = hintText;
  wrap.appendChild(hint);
  wrap.appendChild(createTorchButton());

  bg.appendChild(wrap);

  document.body.appendChild(bg);
  return bg;
}

function startScannerHardware(onSuccess, closeFn) {
  _scanner = new Html5Qrcode('scanner-reader');
  _scanner.start(
    { facingMode: 'environment' },
    { fps: 15, qrbox: (vw) => {
      const w = Math.min(vw * 0.8, 300);
      return { width: Math.round(w), height: Math.round(w * 0.45) };
    },
    formatsToSupport: [
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8,
      Html5QrcodeSupportedFormats.UPC_A,
      Html5QrcodeSupportedFormats.UPC_E
    ] },
    onSuccess,
    () => {}
  ).then(() => { setTimeout(checkTorchSupport, 600); }).catch((err) => {
    showToast(t('toast_scanner_load_error'), 'error');
    const videoWrap = document.querySelector('.scanner-video-wrap');
    if (videoWrap) {
      videoWrap.innerHTML = '';
      const errDiv = document.createElement('div');
      errDiv.className = 'scanner-error';
      const iconDiv = document.createElement('div');
      iconDiv.className = 'scanner-error-icon';
      iconDiv.textContent = '\u{1F4F7}';
      errDiv.appendChild(iconDiv);
      const p = document.createElement('p');
      p.textContent = t('scan_camera_error');
      errDiv.appendChild(p);
      const errBtn = document.createElement('button');
      errBtn.className = 'btn-sm btn-outline';
      errBtn.style.marginTop = '16px';
      errBtn.textContent = t('btn_cancel');
      errBtn.addEventListener('click', closeFn);
      errDiv.appendChild(errBtn);
      videoWrap.appendChild(errDiv);
    }
  });
}

export function openScanner(prefix, productId) {
  _scannerCtx = { prefix: prefix, productId: productId || null };

  if (typeof Html5Qrcode === 'undefined') {
    showToast(t('toast_scanner_load_error'), 'error');
    return;
  }

  buildScannerUI(
    '\u{1F4F7} ' + t('scan_barcode_title'),
    t('scan_hold_barcode_hint'),
    () => closeScanner()
  );

  startScannerHardware(
    (code) => onBarcodeDetected(code),
    () => closeScanner()
  );
}

function onBarcodeDetected(code) {
  if (navigator.vibrate) navigator.vibrate(100);

  const prefix = _scannerCtx.prefix;
  const productId = _scannerCtx.productId;
  const eanEl = document.getElementById(prefix + '-ean');
  if (eanEl) eanEl.value = code;
  import('./off-utils.js').then((mod) => { mod.validateOffBtn(prefix); });

  closeScanner();

  showToast(t('toast_barcode_scanned', { code: code }), 'success');
  setTimeout(() => {
    import('./off-api.js').then((mod) => { mod.lookupOFF(prefix, productId); });
  }, 300);
}

export function closeScanner() {
  resetTorch();
  if (_scanner) {
    const s = _scanner;
    _scanner = null;
    s.stop().then(() => { s.clear(); }).catch(() => {});
  }
  const el = document.getElementById('scanner-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
}

// ── Search Scanner (scan to find product in DB) ─────
let _searchScanMode = false;

function closeSearchScanner() {
  _searchScanMode = false;
  closeScanner();
}

export function openSearchScanner() {
  _searchScanMode = true;
  _scannerCtx = { prefix: 'search', productId: null };

  if (typeof Html5Qrcode === 'undefined') {
    showToast(t('toast_scanner_not_loaded'), 'error');
    return;
  }

  buildScannerUI(
    '\u{1F50D} ' + t('scan_find_product_title'),
    t('scan_barcode_on_product_hint'),
    () => closeSearchScanner()
  );

  startScannerHardware(
    (code) => {
      if (_searchScanMode) {
        _searchScanMode = false;
        onSearchScanDetected(code);
      }
    },
    () => closeSearchScanner()
  );
}

async function onSearchScanDetected(code) {
  if (navigator.vibrate) navigator.vibrate(100);
  closeScanner();
  showToast(t('toast_barcode_scanned', { code: code }), 'success');

  try {
    if (state.currentView !== 'search') switchView('search');

    const allProducts = await fetchProducts('', []);

    // First pass: check both legacy ean field and eans array
    let found = null;
    for (let i = 0; i < allProducts.length; i++) {
      const p = allProducts[i];
      const eans = Array.isArray(p.eans) ? p.eans : [];
      if (eans.includes(code) || p.ean === code) { found = p; break; }
    }

    // Second pass: if no primary match, search via backend (covers secondary EANs)
    if (!found) {
      const bySearch = await fetchProducts(code, []);
      if (bySearch.length === 1) {
        found = bySearch[0];
      } else if (bySearch.length > 1) {
        found = bySearch.find((p) => p.ean === code) || null;
      }
    }

    if (found) {
      state.currentFilter = [found.type];
      buildFilters();

      state.sortCol = 'total_score';
      state.sortDir = 'desc';

      const filtered = await fetchProducts('', state.currentFilter);
      renderResults(filtered, '');

      document.getElementById('search-input').value = '';
      document.getElementById('search-clear').classList.remove('visible');

      const filterRow = document.getElementById('filter-row');
      const filterTog = document.getElementById('filter-toggle');
      if (filterRow && !filterRow.classList.contains('open')) { filterRow.classList.add('open'); if (filterTog) filterTog.classList.add('open'); }

      setTimeout(() => {
        const rowEl = document.querySelector('.table-row[data-product-id="' + found.id + '"]');
        if (rowEl) {
          rowEl.classList.add('scan-highlight');
          rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(() => { rowEl.classList.remove('scan-highlight'); }, 5000);
        }
      }, 150);
    } else {
      showScanNotFoundModal(code);
    }
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export function showScanNotFoundModal(ean) {
  const bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  bg.id = 'scan-modal-bg';
  bg.onclick = (e) => { if (e.target === bg) closeScanModal(); };

  const modal = document.createElement('div');
  modal.className = 'scan-modal';
  const iconDiv = document.createElement('div');
  iconDiv.className = 'scan-modal-icon';
  iconDiv.textContent = '\u{1F50D}';
  modal.appendChild(iconDiv);
  const h3 = document.createElement('h3');
  h3.textContent = t('scan_product_not_found');
  modal.appendChild(h3);
  const eanDiv = document.createElement('div');
  eanDiv.className = 'scan-modal-ean';
  eanDiv.textContent = 'EAN: ' + ean;
  modal.appendChild(eanDiv);
  const p = document.createElement('p');
  p.textContent = t('scan_not_in_database');
  modal.appendChild(p);
  const actions = document.createElement('div');
  actions.className = 'scan-modal-actions';
  modal.appendChild(actions);

  const regBtn = document.createElement('button');
  regBtn.className = 'scan-modal-btn-register';
  regBtn.textContent = '+ ' + t('scan_register_new');
  regBtn.addEventListener('click', () => { scanRegisterNew(ean); });
  actions.appendChild(regBtn);

  const updBtn = document.createElement('button');
  updBtn.className = 'scan-modal-btn-update';
  updBtn.textContent = '\u270E ' + t('scan_update_existing');
  updBtn.addEventListener('click', () => { scanUpdateExisting(ean); });
  actions.appendChild(updBtn);

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'scan-modal-btn-cancel';
  cancelBtn.textContent = t('btn_cancel');
  cancelBtn.addEventListener('click', () => { closeScanModal(); });
  actions.appendChild(cancelBtn);

  bg.setAttribute('role', 'dialog');
  bg.setAttribute('aria-modal', 'true');
  bg.appendChild(modal);
  document.body.appendChild(bg);
  document.body.style.overflow = 'hidden';
  trapFocus(bg);
  regBtn.focus();
}

export function closeScanModal() {
  const el = document.getElementById('scan-modal-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
}

export function scanRegisterNew(ean) {
  closeScanModal();
  switchView('register');
  const eanEl = document.getElementById('f-ean');
  if (eanEl) eanEl.value = ean;
  Promise.all([import('./off-utils.js'), import('./off-api.js')]).then(([utilsMod, apiMod]) => {
    utilsMod.validateOffBtn('f');
    setTimeout(() => { apiMod.lookupOFF('f', null, { autoClose: true }); }, 300);
  });
}

export function scanUpdateExisting(ean) {
  closeScanModal();
  showScanProductPicker(ean);
}

// ── Scan Product Picker: search local DB to assign EAN ──
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
    const results = await fetchProducts(query, []);
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
