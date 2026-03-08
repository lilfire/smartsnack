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
      var offUrl = 'https://world.openfoodfacts.org/cgi/product.pl?code=' + encodeURIComponent(ean);
      var prefix = _offCtx.prefix;
      var isRegister = (prefix === 'f');
      if (isRegister) {
        var nameEl = document.getElementById(prefix + '-name');
        var hasName = nameEl && nameEl.value.trim().length >= 2;
        html += '<div style="margin-top:16px;padding:12px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);text-align:left">';
        html += '<div style="margin-bottom:8px;font-weight:600">' + esc(t('off_add_to_off')) + '</div>';
        if (!hasName) {
          html += '<div style="margin-bottom:8px;color:#ff9800;font-size:12px">⚠ ' + esc(t('off_add_name_required')) + '</div>';
        }
        html += '<div style="margin-bottom:12px;font-size:12px;opacity:0.6">' + esc(t('off_add_to_off_tip')) + '</div>';
        html += '<a href="' + esc(offUrl) + '" target="_blank" rel="noopener" class="btn-off" style="display:inline-block;text-decoration:none;text-align:center;padding:8px 16px;font-size:13px' + (!hasName ? ';opacity:0.4;pointer-events:none' : '') + '">🌎 Open Food Facts ↗</a>';
        html += '</div>';
      } else {
        html += '<div style="margin-top:16px"><a href="' + esc(offUrl) + '" target="_blank" rel="noopener" class="btn-off" style="display:inline-block;text-decoration:none;text-align:center;padding:8px 16px;font-size:13px">🌎 ' + esc(t('off_add_to_off')) + ' ↗</a></div>';
      }
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
