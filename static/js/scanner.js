// ── Barcode Scanner (all scanner sections) ──────────
import { state, fetchProducts, trapFocus } from './state.js';
import { t } from './i18n.js';
import { buildFilters } from './filters.js';
import { showToast, switchView } from './products.js';
import { renderResults } from './render.js';
import { createTorchButton, checkTorchSupport, resetTorch } from './scanner-torch.js';
import { showScanProductPicker } from './scan-picker.js';
// Scan-picker section lives in scan-picker.js; re-exported here so existing
// importers (app.js, tests, dynamic imports) keep working after the split.
export {
  showScanProductPicker, closeScanPicker, scanPickerSearch, scanPickerSelect,
  showScanOffConfirm, closeScanOffConfirm, scanOffFetch,
} from './scan-picker.js';

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

// One-shot guard: the camera keeps decoding frames after the first hit, so
// without this the callback fires once per decoded frame (duplicate lookups).
let _registerScanDone = false;

export function openScanner(prefix, productId) {
  _scannerCtx = { prefix: prefix, productId: productId || null };
  _registerScanDone = false;

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
    (code) => {
      if (_registerScanDone) return;
      _registerScanDone = true;
      onBarcodeDetected(code);
    },
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

    const raw = await fetchProducts(code, []);
    const products = Array.isArray(raw) ? raw : (raw.products || []);
    let found = null;
    if (products.length === 1) {
      found = products[0];
    } else if (products.length > 1) {
      found = products.find((p) => p.ean === code) || null;
    }

    if (found) {
      state.currentFilter = [found.type];
      buildFilters();

      state.sortCol = 'total_score';
      state.sortDir = 'desc';

      const filteredRaw = await fetchProducts('', state.currentFilter);
      const filtered = Array.isArray(filteredRaw) ? filteredRaw : (filteredRaw.products || []);
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
