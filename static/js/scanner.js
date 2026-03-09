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

  var header = document.createElement('div');
  header.className = 'scanner-header';
  header.innerHTML = '<h3>\u{1F4F7} Scan barcode</h3>';
  var closeBtn = document.createElement('button');
  closeBtn.className = 'scanner-close';
  closeBtn.textContent = '\u00D7';
  closeBtn.addEventListener('click', function() { closeScanner(); });
  header.appendChild(closeBtn);
  bg.appendChild(header);

  var wrap = document.createElement('div');
  wrap.className = 'scanner-video-wrap';
  wrap.innerHTML = '<div id="scanner-reader"></div><div class="scanner-hint">Hold the barcode within the frame</div>';
  bg.appendChild(wrap);

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
    var videoWrap = document.querySelector('.scanner-video-wrap');
    if (videoWrap) {
      videoWrap.innerHTML = '';
      var errDiv = document.createElement('div');
      errDiv.className = 'scanner-error';
      errDiv.innerHTML = '<div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p>';
      var errBtn = document.createElement('button');
      errBtn.className = 'btn-sm btn-outline';
      errBtn.style.marginTop = '16px';
      errBtn.textContent = 'Close';
      errBtn.addEventListener('click', function() { closeScanner(); });
      errDiv.appendChild(errBtn);
      videoWrap.appendChild(errDiv);
    }
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

  var bg = document.createElement('div');
  bg.className = 'scanner-bg';
  bg.id = 'scanner-bg';
  document.body.style.overflow = 'hidden';

  var header = document.createElement('div');
  header.className = 'scanner-header';
  header.innerHTML = '<h3>\u{1F50D} Scan to find product</h3>';
  var closeBtn = document.createElement('button');
  closeBtn.className = 'scanner-close';
  closeBtn.textContent = '\u00D7';
  closeBtn.addEventListener('click', function() { closeSearchScanner(); });
  header.appendChild(closeBtn);
  bg.appendChild(header);

  var wrap = document.createElement('div');
  wrap.className = 'scanner-video-wrap';
  wrap.innerHTML = '<div id="scanner-reader"></div><div class="scanner-hint">Scan the barcode on the product</div>';
  bg.appendChild(wrap);

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
    var videoWrap = document.querySelector('.scanner-video-wrap');
    if (videoWrap) {
      videoWrap.innerHTML = '';
      var errDiv = document.createElement('div');
      errDiv.className = 'scanner-error';
      errDiv.innerHTML = '<div class="scanner-error-icon">\u{1F4F7}</div><p>Could not open the camera. Check that you have granted camera permission.</p>';
      var errBtn = document.createElement('button');
      errBtn.className = 'btn-sm btn-outline';
      errBtn.style.marginTop = '16px';
      errBtn.textContent = 'Close';
      errBtn.addEventListener('click', function() { closeSearchScanner(); });
      errDiv.appendChild(errBtn);
      videoWrap.appendChild(errDiv);
    }
  });
}

async function onSearchScanDetected(code) {
  if (navigator.vibrate) navigator.vibrate(100);
  closeScanner();
  showToast(t('toast_barcode_scanned', { code: code }), 'success');

  try {
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
      if (filterRow && !filterRow.classList.contains('open')) { filterRow.classList.add('open'); if (filterTog) filterTog.classList.add('open'); }

      setTimeout(function() {
        var rowEl = document.querySelector('.table-row[data-product-id="' + found.id + '"]');
        if (rowEl) {
          rowEl.classList.add('scan-highlight');
          rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(function() { rowEl.classList.remove('scan-highlight'); }, 5000);
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
  var bg = document.createElement('div');
  bg.className = 'scan-modal-bg';
  bg.id = 'scan-modal-bg';
  bg.onclick = function(e) { if (e.target === bg) closeScanModal(); };

  var modal = document.createElement('div');
  modal.className = 'scan-modal';
  modal.innerHTML = '<div class="scan-modal-icon">\u{1F50D}</div>'
    + '<h3>Product not found</h3>'
    + '<div class="scan-modal-ean">EAN: ' + esc(ean) + '</div>'
    + '<p>This barcode is not in the database. What would you like to do?</p>'
    + '<div class="scan-modal-actions"></div>';

  var actions = modal.querySelector('.scan-modal-actions');

  var regBtn = document.createElement('button');
  regBtn.className = 'scan-modal-btn-register';
  regBtn.textContent = '+ Register new product';
  regBtn.addEventListener('click', function() { scanRegisterNew(ean); });
  actions.appendChild(regBtn);

  var updBtn = document.createElement('button');
  updBtn.className = 'scan-modal-btn-update';
  updBtn.textContent = '\u270E Update existing product';
  updBtn.addEventListener('click', function() { scanUpdateExisting(ean); });
  actions.appendChild(updBtn);

  var cancelBtn = document.createElement('button');
  cancelBtn.className = 'scan-modal-btn-cancel';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.addEventListener('click', function() { closeScanModal(); });
  actions.appendChild(cancelBtn);

  bg.appendChild(modal);
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

  var modal = document.createElement('div');
  modal.className = 'off-modal';

  var head = document.createElement('div');
  head.className = 'off-modal-head';
  head.innerHTML = '<h3>\u270E ' + esc(t('off_search_btn')) + ' — EAN ' + esc(ean) + '</h3>';
  var headClose = document.createElement('button');
  headClose.className = 'off-modal-close';
  headClose.textContent = '\u00D7';
  headClose.addEventListener('click', function() { closeScanPicker(); });
  head.appendChild(headClose);
  modal.appendChild(head);

  var searchDiv = document.createElement('div');
  searchDiv.className = 'off-modal-search';
  var searchInput = document.createElement('input');
  searchInput.id = 'scan-picker-input';
  searchInput.placeholder = t('search_placeholder');
  searchInput.addEventListener('keydown', function(event) { if (event.key === 'Enter') scanPickerSearch(); });
  searchDiv.appendChild(searchInput);
  var searchBtn = document.createElement('button');
  searchBtn.textContent = t('off_search_btn');
  searchBtn.addEventListener('click', function() { scanPickerSearch(); });
  searchDiv.appendChild(searchBtn);
  modal.appendChild(searchDiv);

  var countDiv = document.createElement('div');
  countDiv.className = 'off-modal-count';
  countDiv.id = 'scan-picker-count';
  countDiv.textContent = t('search_placeholder');
  modal.appendChild(countDiv);

  var bodyDiv = document.createElement('div');
  bodyDiv.className = 'off-modal-body';
  bodyDiv.id = 'scan-picker-body';
  bodyDiv.innerHTML = '<div class="off-modal-empty">\u{1F50D} ' + esc(t('search_placeholder')) + '</div>';
  modal.appendChild(bodyDiv);

  bg.appendChild(modal);
  document.body.appendChild(bg);
  setTimeout(function() { if (searchInput) searchInput.focus(); }, 100);
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
    results.forEach(function(p) {
      var imgTag = p.has_image ? '<div class="off-result-img" id="scan-pick-img-' + p.id + '" style="background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center"><span style="opacity:0.2">' + catEmoji(p.type) + '</span></div>'
        : '<div class="off-result-img" style="display:flex;align-items:center;justify-content:center"><span style="font-size:20px">' + catEmoji(p.type) + '</span></div>';
      var eanInfo = p.ean ? '<span class="off-result-ean">EAN: ' + esc(p.ean) + '</span>' : '<span class="off-result-ean" style="color:rgba(255,100,100,0.5)">No EAN</span>';
      h += '<div class="off-result" data-action="pick" data-id="' + p.id + '">'
        + imgTag
        + '<div class="off-result-info"><div class="off-result-name">' + esc(p.name) + '</div>'
        + '<div class="off-result-brand">' + catLabel(p.type) + (p.brand ? ' \u00B7 ' + esc(p.brand) : '') + '</div>'
        + eanInfo + '</div></div>';
    });
    body.innerHTML = h;
    // Attach click handlers via event delegation
    body.addEventListener('click', function(e) {
      var row = e.target.closest('[data-action="pick"]');
      if (row) scanPickerSelect(parseInt(row.dataset.id, 10));
    });
    results.forEach(function(p) {
      if (p.has_image) {
        loadProductImage(p.id).then(function(dataUri) {
          if (!dataUri) return;
          var imgEl = document.getElementById('scan-pick-img-' + p.id);
          if (imgEl) { var safe = safeDataUri(dataUri); if (safe) imgEl.innerHTML = '<img src="' + safe + '" style="width:100%;height:100%;object-fit:cover;border-radius:8px">'; }
        });
      }
    });
  } catch(e) {
    body.innerHTML = '<div class="off-modal-empty">' + esc(t('toast_save_error')) + '</div>';
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

  var modal = document.createElement('div');
  modal.className = 'scan-modal';
  modal.innerHTML = '<div class="scan-modal-icon">\u{1F30E}</div>'
    + '<h3>Fetch data from OpenFoodFacts?</h3>'
    + '<div class="scan-modal-ean">EAN: ' + esc(ean) + '</div>'
    + '<p>Look up nutrition and product info from OpenFoodFacts for this barcode?</p>'
    + '<div class="scan-modal-actions"></div>';

  var actions = modal.querySelector('.scan-modal-actions');

  var fetchBtn = document.createElement('button');
  fetchBtn.className = 'scan-modal-btn-register';
  fetchBtn.textContent = '\u{1F30E} Yes, fetch data';
  fetchBtn.addEventListener('click', function() { scanOffFetch(ean, productId); });
  actions.appendChild(fetchBtn);

  var skipBtn = document.createElement('button');
  skipBtn.className = 'scan-modal-btn-cancel';
  skipBtn.textContent = 'No, skip';
  skipBtn.addEventListener('click', function() { closeScanOffConfirm(); loadData(); });
  actions.appendChild(skipBtn);

  bg.appendChild(modal);
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
