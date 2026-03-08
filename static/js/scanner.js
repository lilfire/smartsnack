// ── Barcode Scanner (all scanner sections) ──────────
import { state, api, esc, catEmoji, catLabel, safeDataUri, fetchProducts } from './state.js';
import { t } from './i18n.js';
import { buildFilters, rerender } from './filters.js';
import { loadProductImage } from './images.js';
import { showToast, switchView, loadData } from './products.js';
import { renderResults } from './render.js';

var _scanner = null;
var _scannerCtx = { prefix: null, productId: null };

export function openScanner(prefix, productId) {
  _scannerCtx = { prefix: prefix, productId: productId || null };

  if (typeof Html5Qrcode === 'undefined') {
    showToast(t('toast_scanner_load_error'), 'error');
    return;
  }

  var bg = document.createElement('div');
  bg.className = 'scanner-bg';
  bg.id = 'scanner-bg';
  document.body.style.overflow = 'hidden';
  bg.innerHTML = '<div class="scanner-header"><h3>\u{1F4F7} Scan barcode</h3><button class="scanner-close" onclick="closeScanner()">&times;</button></div>'
    + '<div class="scanner-video-wrap"><div id="scanner-reader"></div>'
    + '<div class="scanner-hint">Hold the barcode within the frame</div></div>';
  document.body.appendChild(bg);

  _scanner = new Html5Qrcode('scanner-reader');
  _scanner.start(
    { facingMode: 'environment' },
    { fps: 15, qrbox: function(vw, vh) {
      var w = Math.min(vw * 0.8, 300);
      return { width: Math.round(w), height: Math.round(w * 0.45) };
    },
    formatsToSupport: [
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8,
      Html5QrcodeSupportedFormats.UPC_A,
      Html5QrcodeSupportedFormats.UPC_E
    ] },
    function onSuccess(code) {
      onBarcodeDetected(code);
    },
    function onError() {}
  ).catch(function(err) {
    showToast(t('toast_scanner_load_error'), 'error');
    var wrap = document.querySelector('.scanner-video-wrap');
    if (wrap) wrap.innerHTML = '<div class="scanner-error"><div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p><button class="btn-sm btn-outline" style="margin-top:16px" onclick="closeScanner()">Close</button></div>';
  });
}

function onBarcodeDetected(code) {
  if (navigator.vibrate) navigator.vibrate(100);

  var prefix = _scannerCtx.prefix;
  var productId = _scannerCtx.productId;
  var eanEl = document.getElementById(prefix + '-ean');
  if (eanEl) eanEl.value = code;
  import('./openfoodfacts.js').then(function(mod) { mod.validateOffBtn(prefix); });

  closeScanner();

  showToast(t('toast_barcode_scanned', { code: code }), 'success');
  setTimeout(function() {
    import('./openfoodfacts.js').then(function(mod) { mod.lookupOFF(prefix, productId); });
  }, 300);
}

export function closeScanner() {
  if (_scanner) { _scanner.stop().then(function() { _scanner.clear(); }).catch(function() {}); _scanner = null; }
  var el = document.getElementById('scanner-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
}

// ── Search Scanner (scan to find product in DB) ─────
var _searchScanMode = false;

export function openSearchScanner() {
  _searchScanMode = true;
  _scannerCtx = { prefix: 'search', productId: null };

  if (typeof Html5Qrcode === 'undefined') {
    showToast(t('toast_scanner_not_loaded'), 'error');
    return;
  }

  var bg = document.createElement('div');
  bg.className = 'scanner-bg';
  bg.id = 'scanner-bg';
  document.body.style.overflow = 'hidden';
  bg.innerHTML = '<div class="scanner-header"><h3>\u{1F50D} Scan to find product</h3><button class="scanner-close" onclick="closeScanner();window._searchScanMode=false;">&times;</button></div>'
    + '<div class="scanner-video-wrap"><div id="scanner-reader"></div>'
    + '<div class="scanner-hint">Scan the barcode on the product</div></div>';
  document.body.appendChild(bg);

  _scanner = new Html5Qrcode('scanner-reader');
  _scanner.start(
    { facingMode: 'environment' },
    { fps: 15, qrbox: function(vw, vh) {
      var w = Math.min(vw * 0.8, 300);
      return { width: Math.round(w), height: Math.round(w * 0.45) };
    },
    formatsToSupport: [
      Html5QrcodeSupportedFormats.EAN_13,
      Html5QrcodeSupportedFormats.EAN_8,
      Html5QrcodeSupportedFormats.UPC_A,
      Html5QrcodeSupportedFormats.UPC_E
    ] },
    function onSuccess(code) {
      if (_searchScanMode) {
        _searchScanMode = false;
        onSearchScanDetected(code);
      }
    },
    function onError() {}
  ).catch(function(err) {
    showToast(t('toast_scanner_load_error'), 'error');
    var wrap = document.querySelector('.scanner-video-wrap');
    if (wrap) wrap.innerHTML = '<div class="scanner-error"><div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p><button class="btn-sm btn-outline" style="margin-top:16px" onclick="closeScanner();window._searchScanMode=false;">Close</button></div>';
  });
}

async function onSearchScanDetected(code) {
  if (navigator.vibrate) navigator.vibrate(100);
  closeScanner();
  showToast(t('toast_barcode_scanned', { code: code }), 'success');

  if (state.currentView !== 'search') switchView('search');

  var allProducts = await fetchProducts('', []);

  var found = null;
  for (var i = 0; i < allProducts.length; i++) {
    if (allProducts[i].ean === code) { found = allProducts[i]; break; }
  }

  if (found) {
    state.currentFilter = [found.type];
    buildFilters();

    state.sortCol = 'total_score';
    state.sortDir = 'desc';

    var filtered = await fetchProducts('', state.currentFilter);
    renderResults(filtered, '');

    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.remove('visible');

    var filterRow = document.getElementById('filter-row');
    var filterTog = document.getElementById('filter-toggle');
    if (!filterRow.classList.contains('open')) { filterRow.classList.add('open'); filterTog.classList.add('open'); }

    setTimeout(function() {
      var rowEl = document.querySelector('.table-row[onclick="toggleExpand(' + found.id + ')"]');
      if (rowEl) {
        rowEl.classList.add('scan-highlight');
        rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function() { rowEl.classList.remove('scan-highlight'); }, 5000);
      }
    }, 150);
  } else {
    showScanNotFoundModal(code);
  }
}

export function showScanNotFoundModal(ean) {
  var bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  bg.id = 'scan-modal-bg';
  bg.onclick = function(e) { if (e.target === bg) closeScanModal(); };
  bg.innerHTML = '<div class="scan-modal">'
    + '<div class="scan-modal-icon">\u{1F50D}</div>'
    + '<h3>Product not found</h3>'
    + '<div class="scan-modal-ean">EAN: ' + ean + '</div>'
    + '<p>This barcode is not in the database. What would you like to do?</p>'
    + '<div class="scan-modal-actions">'
    + '<button class="scan-modal-btn-register" onclick="scanRegisterNew(\'' + ean + '\')">+ Register new product</button>'
    + '<button class="scan-modal-btn-update" onclick="scanUpdateExisting(\'' + ean + '\')">\u270E Update existing product</button>'
    + '<button class="scan-modal-btn-cancel" onclick="closeScanModal()">Cancel</button>'
    + '</div></div>';
  document.body.appendChild(bg);
  document.body.style.overflow = 'hidden';
}

export function closeScanModal() {
  var el = document.getElementById('scan-modal-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
}

export function scanRegisterNew(ean) {
  closeScanModal();
  switchView('register');
  var eanEl = document.getElementById('f-ean');
  if (eanEl) eanEl.value = ean;
  import('./openfoodfacts.js').then(function(mod) {
    mod.validateOffBtn('f');
    setTimeout(function() { mod.lookupOFF('f'); }, 300);
  });
}

export function scanUpdateExisting(ean) {
  closeScanModal();
  showScanProductPicker(ean);
}

// ── Scan Product Picker: search local DB to assign EAN ──
var _scanPickerEan = null;

export function showScanProductPicker(ean) {
  _scanPickerEan = ean;
  document.body.style.overflow = 'hidden';
  var bg = document.createElement('div');
  bg.className = 'off-modal-bg';
  bg.id = 'scan-picker-bg';
  bg.onclick = function(e) { if (e.target === bg) closeScanPicker(); };
  bg.innerHTML = '<div class="off-modal"><div class="off-modal-head"><h3>\u270E ' + t('off_search_btn') + ' — EAN ' + ean + '</h3><button class="off-modal-close" onclick="closeScanPicker()">&times;</button></div>'
    + '<div class="off-modal-search"><input id="scan-picker-input" placeholder="' + t('search_placeholder') + '" onkeydown="if(event.key===\'Enter\')scanPickerSearch()"><button onclick="scanPickerSearch()">' + t('off_search_btn') + '</button></div>'
    + '<div class="off-modal-count" id="scan-picker-count">' + t('search_placeholder') + '</div>'
    + '<div class="off-modal-body" id="scan-picker-body"><div class="off-modal-empty">\u{1F50D} ' + t('search_placeholder') + '</div></div></div>';
  document.body.appendChild(bg);
  setTimeout(function() { var inp = document.getElementById('scan-picker-input'); if (inp) inp.focus(); }, 100);
}

export function closeScanPicker() {
  var el = document.getElementById('scan-picker-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
  _scanPickerEan = null;
}

export async function scanPickerSearch() {
  var inp = document.getElementById('scan-picker-input');
  var query = inp ? inp.value.trim() : '';
  if (!query) { showToast(t('toast_enter_product_name'), 'error'); return; }
  var body = document.getElementById('scan-picker-body');
  var cnt = document.getElementById('scan-picker-count');
  body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if (cnt) cnt.textContent = 'Searching for "' + query + '"...';
  try {
    var results = await fetchProducts(query, []);
    if (!results.length) {
      body.innerHTML = '<div class="off-modal-empty">No products found for "' + esc(query) + '"</div>';
      if (cnt) cnt.textContent = t('off_zero_results');
      return;
    }
    if (cnt) cnt.textContent = results.length + ' resultat' + (results.length !== 1 ? 'er' : '');
    var h = '';
    results.forEach(function(p, idx) {
      var imgTag = p.has_image ? '<div class="off-result-img" id="scan-pick-img-' + p.id + '" style="background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center"><span style="opacity:0.2">' + catEmoji(p.type) + '</span></div>'
        : '<div class="off-result-img" style="display:flex;align-items:center;justify-content:center"><span style="font-size:20px">' + catEmoji(p.type) + '</span></div>';
      var eanInfo = p.ean ? '<span class="off-result-ean">EAN: ' + esc(p.ean) + '</span>' : '<span class="off-result-ean" style="color:rgba(255,100,100,0.5)">No EAN</span>';
      h += '<div class="off-result" onclick="scanPickerSelect(' + p.id + ')">'
        + imgTag
        + '<div class="off-result-info"><div class="off-result-name">' + esc(p.name) + '</div>'
        + '<div class="off-result-brand">' + catLabel(p.type) + (p.brand ? ' \u00B7 ' + esc(p.brand) : '') + '</div>'
        + eanInfo + '</div></div>';
    });
    body.innerHTML = h;
    results.forEach(function(p) {
      if (p.has_image) {
        loadProductImage(p.id).then(function(dataUri) {
          if (!dataUri) return;
          var el = document.getElementById('scan-pick-img-' + p.id);
          if (el) { var safe = safeDataUri(dataUri); if (safe) el.innerHTML = '<img src="' + safe + '" style="width:100%;height:100%;object-fit:cover;border-radius:8px">'; }
        });
      }
    });
  } catch(e) {
    body.innerHTML = '<div class="off-modal-empty">' + t('toast_save_error') + '</div>';
    if (cnt) cnt.textContent = t('toast_save_error');
  }
}

export async function scanPickerSelect(productId) {
  var ean = _scanPickerEan;
  if (!ean) return;
  closeScanPicker();

  showToast(t('toast_saving_ean', { ean: ean }), 'info');
  try {
    var prod = await api('/api/products/' + productId);
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
  var bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  bg.id = 'scan-off-confirm-bg';
  bg.onclick = function(e) { if (e.target === bg) closeScanOffConfirm(); };
  bg.innerHTML = '<div class="scan-modal">'
    + '<div class="scan-modal-icon">\u{1F30E}</div>'
    + '<h3>Fetch data from OpenFoodFacts?</h3>'
    + '<div class="scan-modal-ean">EAN: ' + ean + '</div>'
    + '<p>Look up nutrition and product info from OpenFoodFacts for this barcode?</p>'
    + '<div class="scan-modal-actions">'
    + '<button class="scan-modal-btn-register" onclick="scanOffFetch(\'' + ean + '\',' + productId + ')">\u{1F30E} Yes, fetch data</button>'
    + '<button class="scan-modal-btn-cancel" onclick="closeScanOffConfirm();loadData();">No, skip</button>'
    + '</div></div>';
  document.body.appendChild(bg);
}

export function closeScanOffConfirm() {
  var el = document.getElementById('scan-off-confirm-bg');
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
  setTimeout(function() {
    var eanEl = document.getElementById('ed-ean');
    if (eanEl) eanEl.value = ean;
    import('./openfoodfacts.js').then(function(mod) {
      mod.validateOffBtn('ed');
      setTimeout(function() { mod.lookupOFF('ed', productId); }, 200);
    });
  }, 300);
}
