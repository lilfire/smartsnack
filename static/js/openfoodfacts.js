// ── OpenFoodFacts Lookup & Protein Quality Estimation ─
import { state, api, esc, safeDataUri } from './state.js';
import { t } from './i18n.js';
import { resizeImage } from './images.js';
import { showToast } from './products.js';

export function isValidEan(v) {
  if (!v) return false;
  var s = v.replace(/\s/g, '');
  return /^\d{8,13}$/.test(s);
}

export function validateOffBtn(prefix) {
  var ean = document.getElementById(prefix + '-ean').value.trim();
  var name = document.getElementById(prefix + '-name').value.trim();
  var btn = document.getElementById(prefix + '-off-btn');
  if (btn) btn.disabled = !(isValidEan(ean) || name.length >= 2);
}

var _offCtx = { prefix: null, productId: null };

export async function lookupOFF(prefix, productId) {
  var ean = document.getElementById(prefix + '-ean').value.replace(/\s/g, '');
  var name = document.getElementById(prefix + '-name').value.trim();
  _offCtx = { prefix: prefix, productId: productId || null };

  if (isValidEan(ean)) {
    showOffPickerLoading(t('off_searching_ean', { ean: ean }));
    try {
      var res = await fetch('https://world.openfoodfacts.org/api/v2/product/' + ean + '.json');
      var data = await res.json();
      if (data.status !== 1 || !data.product) {
        updateOffPickerResults([], t('no_products_found') + ' (EAN ' + ean + ')', ean);
        return;
      }
      await applyOffProduct(data.product, prefix, productId);
      closeOffPicker();
    } catch(e) { console.error('OFF lookup error:', e); updateOffPickerResults([], 'Kunne ikke kontakte OpenFoodFacts'); }
  } else if (name.length >= 2) {
    showOffPickerLoading(t('off_searching_name', { name: name }));
    try {
      var products = await searchOFF(name);
      updateOffPickerResults(products);
      var si = document.getElementById('off-search-input');
      if (si) si.value = name;
    } catch(e) { console.error('OFF search error:', e); updateOffPickerResults([], 'Kunne ikke kontakte OpenFoodFacts'); }
  }
}

function showOffPickerLoading(msg) {
  closeOffPicker();
  document.body.style.overflow = 'hidden';
  var bg = document.createElement('div');
  bg.className = 'off-modal-bg';
  bg.id = 'off-modal-bg';
  bg.onclick = function(e) { if (e.target === bg) closeOffPicker(); };
  var h = '<div class="off-modal"><div class="off-modal-head"><h3>&#127758; OpenFoodFacts</h3><button class="off-modal-close" onclick="closeOffPicker()">&times;</button></div>'
    + '<div class="off-modal-search"><input id="off-search-input" placeholder="Search OpenFoodFacts..." disabled onkeydown="if(event.key===\'Enter\')offModalSearch()"><button id="off-search-btn" disabled onclick="offModalSearch()">Search</button></div>'
    + '<div class="off-modal-count" id="off-result-count">' + (msg || t('off_searching')) + '</div>'
    + '<div class="off-modal-body" id="off-results-body"><div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div></div></div>';
  bg.innerHTML = h;
  document.body.appendChild(bg);
}

function updateOffPickerResults(products, errorMsg, ean) {
  var body = document.getElementById('off-results-body');
  var count = document.getElementById('off-result-count');
  var si = document.getElementById('off-search-input');
  var sb = document.getElementById('off-search-btn');
  if (si) si.disabled = false;
  if (sb) { sb.disabled = false; sb.textContent = t('off_search_btn'); }
  if (!body) return;
  if (errorMsg) {
    var html = '<div class="off-modal-empty">' + esc(errorMsg);
    if (ean) {
      html += '<div style="margin-top:16px"><button class="btn-off" style="padding:8px 16px;font-size:13px" onclick="showOffAddReview(\'' + esc(ean) + '\')">🌎 ' + esc(t('off_add_to_off')) + '</button></div>';
    }
    html += '</div>';
    body.innerHTML = html;
    if (count) count.textContent = t('off_zero_results');
    return;
  }
  window._offPickerProducts = products;
  body.innerHTML = renderOffResults(products);
  if (count) count.textContent = t('off_result_count', { count: products.length });
}

export async function searchOFF(query) {
  var q = encodeURIComponent(query);
  var url = 'https://world.openfoodfacts.org/cgi/search.pl?search_terms=' + q + '&search_simple=1&action=process&json=1&page_size=20&fields=code,product_name,product_name_no,brands,stores,stores_tags,nutriments,image_front_small_url,image_front_url,image_url,serving_size,product_quantity,ingredients_text,ingredients_text_no,ingredients_text_en';
  var res = await fetch(url);
  var data = await res.json();
  return (data.products || []).filter(function(p) { return p.product_name || p.product_name_no; });
}

function renderOffResults(products) {
  if (!products.length) return '<div class="off-modal-empty">No results. Try different search terms.</div>';
  var h = '';
  products.forEach(function(p, i) {
    var name = p.product_name_no || p.product_name || 'Ukjent';
    var brand = p.brands || '';
    var img = p.image_front_small_url || '';
    var n = p.nutriments || {};
    var kcal = Math.round(n['energy-kcal_100g'] || n['energy-kcal'] || 0);
    var pro = parseFloat(n['proteins_100g'] || n['proteins'] || 0).toFixed(1);
    var carb = parseFloat(n['carbohydrates_100g'] || n['carbohydrates'] || 0).toFixed(1);
    var code = p.code || '';
    h += '<div class="off-result" onclick="selectOffResult(' + i + ')">';
    if (img) h += '<img class="off-result-img" src="' + esc(img) + '" onerror="this.style.display=\'none\'">';
    else h += '<div class="off-result-img" style="display:flex;align-items:center;justify-content:center;font-size:20px;opacity:0.2">&#127828;</div>';
    h += '<div class="off-result-info"><div class="off-result-name">' + esc(name) + '</div>';
    if (brand) h += '<div class="off-result-brand">' + esc(brand) + '</div>';
    h += '<div class="off-result-nutri">' + kcal + ' kcal \u00B7 ' + pro + 'g protein \u00B7 ' + carb + 'g carbs</div>';
    if (code) h += '<div class="off-result-ean">EAN: ' + esc(code) + '</div>';
    h += '</div></div>';
  });
  return h;
}

export async function offModalSearch() {
  var input = document.getElementById('off-search-input');
  var btn = document.getElementById('off-search-btn');
  var query = (input ? input.value : '').trim();
  if (query.length < 2) return;
  if (input) input.disabled = true;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  var body = document.getElementById('off-results-body');
  var cnt = document.getElementById('off-result-count');
  if (body) body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if (cnt) cnt.textContent = t('off_searching_name', { name: query });
  try {
    var products = await searchOFF(query);
    updateOffPickerResults(products);
  } catch(e) { updateOffPickerResults([], t('toast_save_error')); }
}

export function closeOffPicker() {
  var el = document.getElementById('off-modal-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
  window._offPickerProducts = null;
}

export async function selectOffResult(idx) {
  var products = window._offPickerProducts;
  if (!products || !products[idx]) return;
  var selected = products[idx];
  closeOffPicker();

  var code = selected.code;
  var prefix = _offCtx.prefix;
  var productId = _offCtx.productId;
  var btn = document.getElementById(prefix + '-off-btn');
  if (btn) { btn.classList.add('loading'); btn.disabled = true; }

  try {
    if (code) {
      var res = await fetch('https://world.openfoodfacts.org/api/v2/product/' + code + '.json');
      var data = await res.json();
      if (data.status === 1 && data.product) {
        var eanEl = document.getElementById(prefix + '-ean');
        if (eanEl) eanEl.value = code;
        await applyOffProduct(data.product, prefix, productId);
      } else {
        await applyOffProduct(selected, prefix, productId);
      }
    } else {
      await applyOffProduct(selected, prefix, productId);
    }
  } catch(e) {
    console.error('OFF select error:', e);
    await applyOffProduct(selected, prefix, productId);
  }

  if (btn) { btn.classList.remove('loading'); validateOffBtn(prefix); }
}

async function applyOffProduct(prod, prefix, productId) {
  var n = prod.nutriments || {};
  var offMap = {
    kcal: n['energy-kcal_100g'] != null ? n['energy-kcal_100g'] : n['energy-kcal'] != null ? n['energy-kcal'] : null,
    energy_kj: n['energy-kj_100g'] != null ? n['energy-kj_100g'] : n['energy-kj'] != null ? n['energy-kj'] : n['energy_100g'] != null ? n['energy_100g'] : null,
    fat: n['fat_100g'] != null ? n['fat_100g'] : n['fat'] != null ? n['fat'] : null,
    saturated_fat: n['saturated-fat_100g'] != null ? n['saturated-fat_100g'] : n['saturated-fat'] != null ? n['saturated-fat'] : null,
    carbs: n['carbohydrates_100g'] != null ? n['carbohydrates_100g'] : n['carbohydrates'] != null ? n['carbohydrates'] : null,
    sugar: n['sugars_100g'] != null ? n['sugars_100g'] : n['sugars'] != null ? n['sugars'] : null,
    protein: n['proteins_100g'] != null ? n['proteins_100g'] : n['proteins'] != null ? n['proteins'] : null,
    fiber: n['fiber_100g'] != null ? n['fiber_100g'] : n['fiber'] != null ? n['fiber'] : null,
    salt: n['salt_100g'] != null ? n['salt_100g'] : n['salt'] != null ? n['salt'] : null,
  };

  var filled = [];
  for (var key in offMap) {
    var val = offMap[key];
    if (val == null) continue;
    var el = document.getElementById(prefix + '-' + key);
    if (el) {
      el.value = (key === 'kcal' || key === 'energy_kj') ? Math.round(val) : parseFloat(val).toFixed(key === 'salt' ? 2 : 1);
      filled.push(key);
    }
  }

  var serving = prod.serving_size || '';
  var servMatch = serving.match(/([\d.]+)\s*g/);
  if (servMatch) { var el = document.getElementById(prefix + '-portion'); if (el) { el.value = Math.round(parseFloat(servMatch[1])); filled.push('portion'); } }

  var qty = prod.product_quantity || 0;
  if (qty) { var el = document.getElementById(prefix + '-weight'); if (el) { el.value = Math.round(parseFloat(qty)); filled.push('weight'); } }

  var nameEl = document.getElementById(prefix + '-name');
  if (nameEl) { var pname = prod.product_name_no || prod.product_name || ''; if (pname) { nameEl.value = pname; filled.push('name'); } }

  if (prod.code) {
    var eanEl = document.getElementById(prefix + '-ean');
    if (eanEl && !eanEl.value.trim()) { eanEl.value = prod.code; filled.push('ean'); }
  }

  var brand = prod.brands || '';
  if (brand) { var brandEl = document.getElementById(prefix + '-brand'); if (brandEl) { brandEl.value = brand; filled.push('brand'); } }

  var stores = '';
  if (prod.stores) stores = prod.stores;
  else if (prod.stores_tags && prod.stores_tags.length) stores = prod.stores_tags.map(function(s) { return s.replace(/-/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); }); }).join(', ');
  if (stores) { var storesEl = document.getElementById(prefix + '-stores'); if (storesEl) { storesEl.value = stores; filled.push('stores'); } }

  var ing = prod.ingredients_text_no || prod.ingredients_text_en || prod.ingredients_text || '';
  if (ing) { var ingEl2 = document.getElementById(prefix + '-ingredients'); if (ingEl2) { ingEl2.value = ing; filled.push('ingredients'); updateEstimateBtn(prefix); } }

  var imgUrl = prod.image_front_url || prod.image_url || prod.image_front_small_url || '';
  if (imgUrl) {
    try {
      var imgDataUri = await fetchImageAsDataUri(imgUrl);
      if (imgDataUri) {
        if (productId) {
          await api('/api/products/' + productId + '/image', { method: 'PUT', body: JSON.stringify({ image: imgDataUri }) });
          state.imageCache[productId] = imgDataUri;
          var imgEl = document.getElementById('prod-img-' + productId);
          if (imgEl) imgEl.src = imgDataUri;
          else { var wrap = document.getElementById('prod-img-wrap-' + productId); if (wrap) { var safe = safeDataUri(imgDataUri); if (safe) wrap.innerHTML = '<img id="prod-img-' + productId + '" src="' + safe + '" style="width:100%;height:100%;object-fit:cover">'; } }
        } else {
          window._pendingImage = imgDataUri;
        }
        filled.push('image');
      }
    } catch(ie) { console.log('Image fetch failed:', ie); }
  }

  showToast('Fetched from OFF: ' + filled.join(', '), 'success');
  if (ing) { setTimeout(function() { estimateProteinQuality(prefix); }, 300); }
}

async function fetchImageAsDataUri(url) {
  try {
    var r = await fetch(url);
    if (!r.ok) throw new Error('Not ok');
    var blob = await r.blob();
    return await blobToResizedDataUri(blob);
  } catch(e) {
    try {
      var r3 = await fetch('/api/proxy-image?url=' + encodeURIComponent(url));
      if (!r3.ok) return null;
      var blob3 = await r3.blob();
      return await blobToResizedDataUri(blob3);
    } catch(e3) { return null; }
  }
}

function blobToResizedDataUri(blob) {
  return new Promise(function(resolve) {
    var reader = new FileReader();
    reader.onload = function(e) { resizeImage(e.target.result, 400).then(resolve); };
    reader.onerror = function() { resolve(null); };
    reader.readAsDataURL(blob);
  });
}

// ── Add Product to OFF ──────────────────────────────
var _offReviewFields = [
  { key: 'name', offKey: 'product_name', label: 'label_product_name', required: true },
  { key: 'brand', offKey: 'brands', label: 'label_brand' },
  { key: 'stores', offKey: 'stores', label: 'label_stores' },
  { key: 'ingredients', offKey: 'ingredients_text', label: 'label_ingredients' },
  { key: 'kcal', offKey: 'energy-kcal', label: 'label_kcal' },
  { key: 'energy_kj', offKey: 'energy-kj', label: 'label_energy_kj' },
  { key: 'fat', offKey: 'fat', label: 'label_fat' },
  { key: 'saturated_fat', offKey: 'saturated-fat', label: 'label_saturated_fat' },
  { key: 'carbs', offKey: 'carbohydrates', label: 'label_carbs' },
  { key: 'sugar', offKey: 'sugars', label: 'label_sugar' },
  { key: 'protein', offKey: 'proteins', label: 'label_protein' },
  { key: 'fiber', offKey: 'fiber', label: 'label_fiber' },
  { key: 'salt', offKey: 'salt', label: 'label_salt' },
  { key: 'weight', offKey: 'quantity', label: 'label_weight' },
  { key: 'portion', offKey: 'serving_size', label: 'label_portion' },
];

export function showOffAddReview(ean) {
  var prefix = _offCtx.prefix;
  var filled = [];
  var empty = [];
  _offReviewFields.forEach(function(f) {
    var el = document.getElementById(prefix + '-' + f.key);
    var val = el ? el.value.trim() : '';
    var label = t(f.label);
    if (val) {
      filled.push({ label: label, value: val, required: f.required });
    } else {
      empty.push({ label: label, required: f.required });
    }
  });

  var hasName = filled.some(function(f) { return f.required; });
  var h = '<div style="text-align:left;max-height:60vh;overflow-y:auto;padding:4px">';
  h += '<div style="font-weight:600;margin-bottom:4px">EAN: ' + esc(ean) + '</div>';

  if (filled.length) {
    h += '<div style="margin:12px 0 6px;font-size:12px;opacity:0.5;text-transform:uppercase">' + esc(t('off_review_filled')) + '</div>';
    filled.forEach(function(f) {
      var display = f.value.length > 50 ? f.value.substring(0, 50) + '...' : f.value;
      h += '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">';
      h += '<span style="color:#4caf50">&#10003;</span>';
      h += '<span style="opacity:0.6;min-width:100px">' + esc(f.label) + '</span>';
      h += '<span style="font-family:\'Space Mono\',monospace;font-size:12px">' + esc(display) + '</span>';
      h += '</div>';
    });
  }

  if (empty.length) {
    h += '<div style="margin:12px 0 6px;font-size:12px;opacity:0.5;text-transform:uppercase">' + esc(t('off_review_empty')) + '</div>';
    empty.forEach(function(f) {
      h += '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">';
      h += '<span style="color:' + (f.required ? '#f44336' : '#ff9800') + '">' + (f.required ? '&#10007;' : '&#9888;') + '</span>';
      h += '<span style="opacity:0.6">' + esc(f.label) + (f.required ? ' *' : '') + '</span>';
      h += '</div>';
    });
  }

  if (!hasName) {
    h += '<div style="margin-top:12px;color:#f44336;font-size:12px">&#9888; ' + esc(t('off_add_name_required')) + '</div>';
  }

  h += '</div>';
  h += '<div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">';
  h += '<button class="btn-off" style="padding:8px 16px;font-size:13px;opacity:0.7" onclick="closeOffAddReview()">' + esc(t('btn_cancel')) + '</button>';
  h += '<button class="btn-register" id="off-submit-btn" style="padding:8px 20px;font-size:13px' + (!hasName ? ';opacity:0.4;pointer-events:none' : '') + '" onclick="submitToOff(\'' + esc(ean) + '\')">🌎 ' + esc(t('off_submit_btn')) + '</button>';
  h += '</div>';

  var bg = document.getElementById('off-add-review-bg');
  if (!bg) {
    bg = document.createElement('div');
    bg.className = 'off-modal-bg';
    bg.id = 'off-add-review-bg';
    bg.onclick = function(e) { if (e.target === bg) closeOffAddReview(); };
    document.body.appendChild(bg);
  }
  bg.innerHTML = '<div class="off-modal"><div class="off-modal-head"><h3>🌎 ' + esc(t('off_add_to_off')) + '</h3><button class="off-modal-close" onclick="closeOffAddReview()">&times;</button></div><div class="off-modal-body" style="padding:16px">' + h + '</div></div>';
}

export function closeOffAddReview() {
  var el = document.getElementById('off-add-review-bg');
  if (el) el.remove();
}

export async function submitToOff(ean) {
  var prefix = _offCtx.prefix;
  var btn = document.getElementById('off-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  var body = { code: ean };
  _offReviewFields.forEach(function(f) {
    var el = document.getElementById(prefix + '-' + f.key);
    var val = el ? el.value.trim() : '';
    if (val) body[f.offKey] = val;
  });

  // Convert quantity/serving_size to string with unit
  if (body.quantity) body.quantity = body.quantity + ' g';
  if (body.serving_size) body.serving_size = body.serving_size + ' g';

  try {
    var res = await api('/api/off/add-product', {
      method: 'POST',
      body: JSON.stringify(body)
    });
    if (res.error) {
      showToast(t('toast_error_prefix', { msg: res.error }), 'error');
      if (btn) { btn.disabled = false; btn.textContent = t('off_submit_btn'); }
      return;
    }
    closeOffAddReview();
    closeOffPicker();
    showToast(t('toast_off_product_added'), 'success');
  } catch(e) {
    showToast(t('toast_error_prefix', { msg: e.message || 'Network error' }), 'error');
    if (btn) { btn.disabled = false; btn.textContent = t('off_submit_btn'); }
  }
}

// ── Protein Quality Estimation ─────────────────────
export function updateEstimateBtn(prefix) {
  var ing = document.getElementById(prefix + '-ingredients');
  var wrap = document.getElementById(prefix + '-protein-quality-wrap');
  if (ing && wrap) wrap.style.display = ing.value.trim() ? '' : 'none';
}

export async function estimateProteinQuality(prefix) {
  var ingEl = document.getElementById(prefix + '-ingredients');
  var btn = document.getElementById(prefix + '-estimate-btn');
  var resultEl = document.getElementById(prefix + '-pq-result');
  var pdcaasEl = document.getElementById(prefix + '-pdcaas-val');
  var diEl = document.getElementById(prefix + '-diaas-val');
  var sourcesEl = document.getElementById(prefix + '-pq-sources');
  var hiddenPd = document.getElementById(prefix + '-est_pdcaas');
  var hiddenDi = document.getElementById(prefix + '-est_diaas');
  if (!ingEl || !ingEl.value.trim()) { showToast('Ingredients missing', 'error'); return; }
  if (btn) { btn.classList.add('loading'); btn.disabled = true; }
  try {
    var res = await fetch('/api/estimate-protein-quality', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredients: ingEl.value })
    });
    var data = await res.json();
    if (data.error) { showToast(t('toast_error_prefix', { msg: data.error }), 'error'); return; }
    if (pdcaasEl) pdcaasEl.textContent = data.est_pdcaas.toFixed(2);
    if (diEl) diEl.textContent = data.est_diaas.toFixed(2);
    if (sourcesEl && data.sources && data.sources.length) sourcesEl.textContent = t('sources_label', { sources: data.sources.join(', ') });
    if (hiddenPd) hiddenPd.value = data.est_pdcaas != null ? data.est_pdcaas : '';
    if (hiddenDi) hiddenDi.value = data.est_diaas != null ? data.est_diaas : '';
    if (resultEl) resultEl.style.display = '';
    if (!data.est_pdcaas && !data.est_diaas) showToast(t('toast_no_protein_sources'), 'error');
    else showToast(t('toast_protein_estimated'), 'success');
  } catch(e) { showToast(t('toast_network_error'), 'error'); }
  if (btn) { btn.classList.remove('loading'); btn.disabled = false; }
}
