// ── OpenFoodFacts Lookup & Protein Quality Estimation ─
import { state, api, esc, safeDataUri, showToast } from './state.js';
import { t } from './i18n.js';
import { resizeImage } from './images.js';

const OFF_FETCH_TIMEOUT = 45000;

function fetchWithTimeout(url, opts) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), OFF_FETCH_TIMEOUT);
  return fetch(url, Object.assign({ signal: controller.signal }, opts))
    .finally(() => clearTimeout(timeoutId));
}

export function isValidEan(v) {
  if (!v) return false;
  const s = v.replace(/\s/g, '');
  return /^\d{8,13}$/.test(s);
}

export function validateOffBtn(prefix) {
  const ean = document.getElementById(prefix + '-ean').value.trim();
  const name = document.getElementById(prefix + '-name').value.trim();
  const btn = document.getElementById(prefix + '-off-btn');
  if (btn) btn.disabled = !(isValidEan(ean) || name.length >= 2);
}

let _offCtx = { prefix: null, productId: null };
let _offPickerProducts = null;

const _nutritionCompareFields = ['kcal', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt'];

function _gatherNutrition(prefix) {
  const nutrition = {};
  _nutritionCompareFields.forEach((f) => {
    const el = document.getElementById(prefix + '-' + f);
    if (el && el.value.trim()) {
      const v = parseFloat(el.value);
      if (!isNaN(v)) nutrition[f] = v;
    }
  });
  return Object.keys(nutrition).length > 0 ? nutrition : null;
}

export async function lookupOFF(prefix, productId) {
  const ean = document.getElementById(prefix + '-ean').value.replace(/\s/g, '');
  const name = document.getElementById(prefix + '-name').value.trim();
  _offCtx = { prefix: prefix, productId: productId || null };

  if (isValidEan(ean)) {
    showOffPickerLoading(t('off_searching_ean', { ean: ean }));
    try {
      const res = await fetchWithTimeout('/api/off/product/' + ean);
      if (!res.ok) { updateOffPickerResults([], t('toast_network_error')); return; }
      const data = await res.json();
      if (data.status !== 1 || !data.product) {
        updateOffPickerResults([], t('no_products_found') + ' (EAN ' + ean + ')', ean);
        return;
      }
      await applyOffProduct(data.product, prefix, productId);
      closeOffPicker();
    } catch(e) { showToast(t('toast_network_error'), 'error'); updateOffPickerResults([], t('toast_network_error')); }
  } else if (name.length >= 2) {
    showOffPickerLoading(t('off_searching_name', { name: name }));
    try {
      const category = document.getElementById(prefix + '-type')?.value || '';
      const products = await searchOFF(name, _gatherNutrition(prefix), category);
      updateOffPickerResults(products);
      const si = document.getElementById('off-search-input');
      if (si) si.value = name;
    } catch(e) { showToast(t('toast_network_error'), 'error'); updateOffPickerResults([], t('toast_network_error')); }
  }
}

function showOffPickerLoading(msg) {
  closeOffPicker();
  document.body.style.overflow = 'hidden';
  const bg = document.createElement('div');
  bg.className = 'off-modal-bg';
  bg.id = 'off-modal-bg';
  bg.setAttribute('role', 'dialog');
  bg.setAttribute('aria-modal', 'true');
  bg.onclick = (e) => { if (e.target === bg) closeOffPicker(); };

  const modal = document.createElement('div');
  modal.className = 'off-modal';

  const head = document.createElement('div');
  head.className = 'off-modal-head';
  head.innerHTML = '<h3>&#127758; OpenFoodFacts</h3>';
  const closeBtn = document.createElement('button');
  closeBtn.className = 'off-modal-close';
  closeBtn.textContent = '\u00D7';
  closeBtn.setAttribute('aria-label', t('btn_close'));
  closeBtn.addEventListener('click', closeOffPicker);
  head.appendChild(closeBtn);
  modal.appendChild(head);

  const searchDiv = document.createElement('div');
  searchDiv.className = 'off-modal-search';
  const searchInput = document.createElement('input');
  searchInput.id = 'off-search-input';
  searchInput.placeholder = t('off_search_placeholder');
  searchInput.disabled = true;
  searchInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') offModalSearch(); });
  searchDiv.appendChild(searchInput);
  const searchBtn = document.createElement('button');
  searchBtn.id = 'off-search-btn';
  searchBtn.disabled = true;
  searchBtn.textContent = t('off_search_btn');
  searchBtn.addEventListener('click', offModalSearch);
  searchDiv.appendChild(searchBtn);
  modal.appendChild(searchDiv);

  const countDiv = document.createElement('div');
  countDiv.className = 'off-modal-count';
  countDiv.id = 'off-result-count';
  countDiv.textContent = msg || t('off_searching');
  modal.appendChild(countDiv);

  const bodyDiv = document.createElement('div');
  bodyDiv.className = 'off-modal-body';
  bodyDiv.id = 'off-results-body';
  bodyDiv.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  modal.appendChild(bodyDiv);

  bg.appendChild(modal);
  document.body.appendChild(bg);
}

function updateOffPickerResults(products, errorMsg, ean) {
  const body = document.getElementById('off-results-body');
  const count = document.getElementById('off-result-count');
  const si = document.getElementById('off-search-input');
  const sb = document.getElementById('off-search-btn');
  if (si) si.disabled = false;
  if (sb) { sb.disabled = false; sb.textContent = t('off_search_btn'); }
  if (!body) return;
  // Capture context snapshot at render time to avoid race conditions
  const ctxSnapshot = { prefix: _offCtx.prefix, productId: _offCtx.productId };
  if (errorMsg) {
    const errDiv = document.createElement('div');
    errDiv.className = 'off-modal-empty';
    errDiv.textContent = errorMsg;
    if (ean) {
      const addDiv = document.createElement('div');
      addDiv.style.marginTop = '16px';
      const addBtn = document.createElement('button');
      addBtn.className = 'btn-off';
      addBtn.style.cssText = 'padding:8px 16px;font-size:13px';
      addBtn.textContent = '\u{1F30E} ' + t('off_add_to_off');
      addBtn.addEventListener('click', () => { showOffAddReview(ean); });
      addDiv.appendChild(addBtn);
      errDiv.appendChild(addDiv);
    }
    body.innerHTML = '';
    body.appendChild(errDiv);
    if (count) count.textContent = t('off_zero_results');
    return;
  }
  _offPickerProducts = products;
  // Replace body element to clear old event listeners
  const newBody = body.cloneNode(false);
  newBody.innerHTML = renderOffResults(products);
  body.parentNode.replaceChild(newBody, body);
  // Fix inline onerror: attach via JS after innerHTML
  newBody.querySelectorAll('.off-result-img-el').forEach((img) => {
    img.addEventListener('error', () => { img.style.display = 'none'; });
  });
  // Attach click handlers via event delegation
  newBody.addEventListener('click', (e) => {
    const row = e.target.closest('[data-action="off-select"]');
    if (row) selectOffResult(parseInt(row.dataset.idx, 10), ctxSnapshot);
  });
  if (count) count.textContent = t('off_result_count', { count: products.length });
}

export async function searchOFF(query, nutrition, category) {
  const body = { q: query };
  if (nutrition) body.nutrition = nutrition;
  if (category) body.category = category;
  const res = await fetchWithTimeout('/api/off/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Search failed: ' + res.status);
  const data = await res.json();
  return (data.products || []).filter((p) => p.product_name || p.product_name_no);
}

function renderOffResults(products) {
  if (!products.length) return '<div class="off-modal-empty">' + esc(t('off_no_results_try_different')) + '</div>';
  let h = '';
  products.forEach((p, i) => {
    const name = p.product_name_no || p.product_name || t('off_unknown_product');
    const brand = p.brands || '';
    const img = p.image_front_small_url || '';
    const n = p.nutriments || {};
    const kcal = Math.round(n['energy-kcal_100g'] ?? n['energy-kcal'] ?? 0);
    const pro = parseFloat(n['proteins_100g'] ?? n['proteins'] ?? 0).toFixed(1);
    const carb = parseFloat(n['carbohydrates_100g'] ?? n['carbohydrates'] ?? 0).toFixed(1);
    const code = p.code || '';
    h += '<div class="off-result" data-action="off-select" data-idx="' + i + '">';
    if (img) h += '<img class="off-result-img off-result-img-el" src="' + esc(img) + '">';
    else h += '<div class="off-result-img" style="display:flex;align-items:center;justify-content:center;font-size:20px;opacity:0.2">&#127828;</div>';
    h += '<div class="off-result-info"><div class="off-result-name">' + esc(name) + '</div>';
    if (brand) h += '<div class="off-result-brand">' + esc(brand) + '</div>';
    h += '<div class="off-result-nutri">' + kcal + ' kcal \u00B7 ' + pro + 'g protein \u00B7 ' + carb + 'g carbs</div>';
    if (code) h += '<div class="off-result-ean">EAN: ' + esc(code) + '</div>';
    const cert = p.certainty != null ? p.certainty : null;
    if (cert != null) {
      const certColor = cert >= 70 ? '#4caf50' : cert >= 40 ? '#ff9800' : '#f44336';
      h += '<div class="off-result-completeness">';
      h += '<div class="off-result-completeness-bar"><div class="off-result-completeness-fill" style="width:' + cert + '%;background:' + certColor + '"></div></div>';
      h += '<span class="off-result-completeness-pct">' + t('off_certainty_label') + ' ' + cert + '%</span>';
      h += '</div>';
    }
    const comp = Math.round((p.completeness || 0) * 100);
    const compColor = comp >= 70 ? '#4caf50' : comp >= 40 ? '#ff9800' : '#f44336';
    h += '<div class="off-result-completeness">';
    h += '<div class="off-result-completeness-bar"><div class="off-result-completeness-fill" style="width:' + comp + '%;background:' + compColor + '"></div></div>';
    h += '<span class="off-result-completeness-pct">' + comp + '%</span>';
    h += '</div>';
    h += '</div></div>';
  });
  return h;
}

export async function offModalSearch() {
  const input = document.getElementById('off-search-input');
  const btn = document.getElementById('off-search-btn');
  const query = (input ? input.value : '').trim();
  if (query.length < 2) return;
  if (input) input.disabled = true;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  const bodyEl = document.getElementById('off-results-body');
  const cnt = document.getElementById('off-result-count');
  if (bodyEl) bodyEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px 0"><span class="spinner"></span></div>';
  if (cnt) cnt.textContent = t('off_searching_name', { name: query });
  try {
    const category = document.getElementById(_offCtx.prefix + '-type')?.value || '';
    const products = await searchOFF(query, _gatherNutrition(_offCtx.prefix), category);
    updateOffPickerResults(products);
  } catch(e) { updateOffPickerResults([], t('toast_network_error')); }
}

export function closeOffPicker() {
  const el = document.getElementById('off-modal-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
  _offPickerProducts = null;
}

export async function selectOffResult(idx, ctxSnapshot) {
  const products = _offPickerProducts;
  if (!products || !products[idx]) return;
  const selected = products[idx];
  closeOffPicker();

  const code = selected.code;
  const ctx = ctxSnapshot || _offCtx;
  const prefix = ctx.prefix;
  const productId = ctx.productId;
  const btn = document.getElementById(prefix + '-off-btn');
  if (btn) { btn.classList.add('loading'); btn.disabled = true; }

  try {
    if (code) {
      const res = await fetchWithTimeout('/api/off/product/' + code);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 1 && data.product) {
          const eanEl = document.getElementById(prefix + '-ean');
          if (eanEl) eanEl.value = code;
          await applyOffProduct(data.product, prefix, productId);
        } else {
          await applyOffProduct(selected, prefix, productId);
        }
      } else {
        await applyOffProduct(selected, prefix, productId);
      }
    } else {
      await applyOffProduct(selected, prefix, productId);
    }
  } catch(e) {
    showToast(t('toast_network_error'), 'error');
    await applyOffProduct(selected, prefix, productId);
  } finally {
    if (btn) { btn.classList.remove('loading'); validateOffBtn(prefix); }
  }
}

async function applyOffProduct(prod, prefix, productId) {
  window._pendingOFFSync = true;
  const n = prod.nutriments || {};
  const offMap = {
    kcal: n['energy-kcal_100g'] ?? n['energy-kcal'] ?? null,
    energy_kj: n['energy-kj_100g'] ?? n['energy-kj'] ?? n['energy_100g'] ?? null,
    fat: n['fat_100g'] ?? n['fat'] ?? null,
    saturated_fat: n['saturated-fat_100g'] ?? n['saturated-fat'] ?? null,
    carbs: n['carbohydrates_100g'] ?? n['carbohydrates'] ?? null,
    sugar: n['sugars_100g'] ?? n['sugars'] ?? null,
    protein: n['proteins_100g'] ?? n['proteins'] ?? null,
    fiber: n['fiber_100g'] ?? n['fiber'] ?? null,
    salt: n['salt_100g'] ?? n['salt'] ?? null,
  };

  const filled = [];
  Object.keys(offMap).forEach((key) => {
    const val = offMap[key];
    if (val == null) return;
    const fieldEl = document.getElementById(prefix + '-' + key);
    if (!fieldEl) return;
    // Don't overwrite existing local values with 0 from OFF (likely missing data)
    if (val === 0 && fieldEl.value !== '' && parseFloat(fieldEl.value) !== 0) return;
    fieldEl.value = (key === 'kcal' || key === 'energy_kj') ? Math.round(val) : parseFloat(val).toFixed(key === 'salt' ? 2 : 1);
    filled.push(key);
  });

  const serving = prod.serving_size || '';
  const servMatch = serving.match(/([\d.]+)\s*g/);
  if (servMatch) { const portionEl = document.getElementById(prefix + '-portion'); if (portionEl) { portionEl.value = Math.round(parseFloat(servMatch[1])); filled.push('portion'); } }

  const qty = prod.product_quantity || 0;
  if (qty) { const weightEl = document.getElementById(prefix + '-weight'); if (weightEl) { weightEl.value = Math.round(parseFloat(qty)); filled.push('weight'); } }

  const nameEl = document.getElementById(prefix + '-name');
  if (nameEl && !nameEl.value.trim()) { const pname = prod.product_name_no || prod.product_name || ''; if (pname) { nameEl.value = pname; filled.push('name'); } }

  if (prod.code) {
    const codeEl = document.getElementById(prefix + '-ean');
    if (codeEl && !codeEl.value.trim()) { codeEl.value = prod.code; filled.push('ean'); }
  }

  const brand = prod.brands || '';
  if (brand) { const brandEl = document.getElementById(prefix + '-brand'); if (brandEl) { brandEl.value = brand; filled.push('brand'); } }

  let stores = '';
  if (prod.stores) stores = prod.stores;
  else if (prod.stores_tags?.length) stores = prod.stores_tags.map((s) => s.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())).join(', ');
  if (stores) { const storesEl = document.getElementById(prefix + '-stores'); if (storesEl) { storesEl.value = stores; filled.push('stores'); } }

  const ing = prod.ingredients_text_no || prod.ingredients_text_en || prod.ingredients_text || '';
  if (ing) { const ingEl = document.getElementById(prefix + '-ingredients'); if (ingEl) { ingEl.value = ing; filled.push('ingredients'); updateEstimateBtn(prefix); } }

  const imgUrl = prod.image_front_url || prod.image_url || prod.image_front_small_url || '';
  if (imgUrl && isValidImageUrl(imgUrl)) {
    try {
      const imgDataUri = await fetchImageAsDataUri(imgUrl);
      if (imgDataUri) {
        if (productId) {
          await api('/api/products/' + productId + '/image', { method: 'PUT', body: JSON.stringify({ image: imgDataUri }) });
          state.imageCache[productId] = imgDataUri;
          const imgEl = document.getElementById('prod-img-' + productId);
          if (imgEl) imgEl.src = imgDataUri;
          else { const wrap = document.getElementById('prod-img-wrap-' + productId); if (wrap) { const safe = safeDataUri(imgDataUri); if (safe) wrap.innerHTML = '<img id="prod-img-' + productId + '" src="' + safe + '" style="width:100%;height:100%;object-fit:cover">'; } }
        } else {
          window._pendingImage = imgDataUri;
        }
        filled.push('image');
      }
    } catch(ie) { showToast(t('toast_image_upload_error'), 'error'); }
  }

  // Duplicate check in edit mode
  if (productId) {
    const offEan = prod.code || '';
    const offName = prod.product_name_no || prod.product_name || '';
    if (offEan || offName) {
      try {
        const dupResult = await api('/api/products/' + productId + '/check-duplicate', {
          method: 'POST', body: JSON.stringify({ ean: offEan, name: offName })
        });
        if (dupResult.duplicate) {
          const dup = dupResult.duplicate;
          const choice = await _showEditDuplicateModal(dup);
          if (choice === 'delete') {
            await api('/api/products/' + dup.id, { method: 'DELETE' });
            showToast(t('toast_duplicate_deleted'), 'success');
          } else if (choice === 'merge') {
            await api('/api/products/' + productId + '/merge', {
              method: 'POST', body: JSON.stringify({ source_id: dup.id })
            });
            showToast(t('toast_duplicate_merged'), 'success');
          }
        }
      } catch(e) { console.error('Duplicate check failed:', e); }
    }
  }

  showToast(t('toast_off_fetched', { fields: filled.join(', ') }), 'success');
  if (ing) { setTimeout(() => { estimateProteinQuality(prefix); }, 300); }
}

function _showEditDuplicateModal(duplicate) {
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
    const msgKey = duplicate.is_synced_with_off ? 'duplicate_edit_synced' : 'duplicate_edit_unsynced';
    pEl.textContent = t(msgKey, { match_type: duplicate.match_type, name: duplicate.name });
    modal.appendChild(pEl);
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    if (duplicate.is_synced_with_off) {
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'scan-modal-btn-register confirm-yes';
      deleteBtn.textContent = t('duplicate_action_delete');
      deleteBtn.addEventListener('click', () => { bg.remove(); resolve('delete'); });
      actions.appendChild(deleteBtn);
    } else {
      const mergeBtn = document.createElement('button');
      mergeBtn.className = 'scan-modal-btn-register confirm-yes';
      mergeBtn.textContent = t('duplicate_action_merge_into');
      mergeBtn.addEventListener('click', () => { bg.remove(); resolve('merge'); });
      actions.appendChild(mergeBtn);
    }
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel confirm-no';
    cancelBtn.textContent = t('btn_cancel');
    cancelBtn.addEventListener('click', () => { bg.remove(); resolve('cancel'); });
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);
  });
}

// Validate image URLs to prevent SSRF via the proxy endpoint
function isValidImageUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch(e) {
    return false;
  }
}

async function fetchImageAsDataUri(url) {
  try {
    const r = await fetchWithTimeout(url);
    if (!r.ok) throw new Error('Not ok');
    const blob = await r.blob();
    return await blobToResizedDataUri(blob);
  } catch(e) {
    try {
      const r3 = await fetchWithTimeout('/api/proxy-image?url=' + encodeURIComponent(url));
      if (!r3.ok) return null;
      const blob3 = await r3.blob();
      return await blobToResizedDataUri(blob3);
    } catch(e3) { return null; }
  }
}

function blobToResizedDataUri(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => { resizeImage(e.target.result, 400).then(resolve).catch(() => resolve(null)); };
    reader.onerror = () => { resolve(null); };
    reader.readAsDataURL(blob);
  });
}

// ── Add Product to OFF ──────────────────────────────
const _offReviewFields = [
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
  const prefix = _offCtx.prefix;
  const filled = [];
  const empty = [];
  _offReviewFields.forEach((f) => {
    const fieldEl = document.getElementById(prefix + '-' + f.key);
    const val = fieldEl ? fieldEl.value.trim() : '';
    const label = t(f.label);
    if (val) {
      filled.push({ label: label, value: val, required: f.required });
    } else {
      empty.push({ label: label, required: f.required });
    }
  });

  const hasName = filled.some((f) => f.required);
  let h = '<div style="text-align:left;max-height:60vh;overflow-y:auto;padding:4px">';
  h += '<div style="font-weight:600;margin-bottom:4px">EAN: ' + esc(ean) + '</div>';

  if (filled.length) {
    h += '<div style="margin:12px 0 6px;font-size:12px;opacity:0.5;text-transform:uppercase">' + esc(t('off_review_filled')) + '</div>';
    filled.forEach((f) => {
      const display = f.value.length > 50 ? f.value.substring(0, 50) + '...' : f.value;
      h += '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">';
      h += '<span style="color:#4caf50">&#10003;</span>';
      h += '<span style="opacity:0.6;min-width:100px">' + esc(f.label) + '</span>';
      h += '<span style="font-family:\'Space Mono\',monospace;font-size:12px">' + esc(display) + '</span>';
      h += '</div>';
    });
  }

  if (empty.length) {
    h += '<div style="margin:12px 0 6px;font-size:12px;opacity:0.5;text-transform:uppercase">' + esc(t('off_review_empty')) + '</div>';
    empty.forEach((f) => {
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

  let bg = document.getElementById('off-add-review-bg');
  if (!bg) {
    bg = document.createElement('div');
    bg.className = 'off-modal-bg';
    bg.id = 'off-add-review-bg';
    bg.onclick = (e) => { if (e.target === bg) closeOffAddReview(); };
    document.body.appendChild(bg);
  }

  const modalDiv = document.createElement('div');
  modalDiv.className = 'off-modal';

  const headDiv = document.createElement('div');
  headDiv.className = 'off-modal-head';
  headDiv.innerHTML = '<h3>\u{1F30E} ' + esc(t('off_add_to_off')) + '</h3>';
  const headClose = document.createElement('button');
  headClose.className = 'off-modal-close';
  headClose.textContent = '\u00D7';
  headClose.addEventListener('click', closeOffAddReview);
  headDiv.appendChild(headClose);
  modalDiv.appendChild(headDiv);

  const bodyDiv = document.createElement('div');
  bodyDiv.className = 'off-modal-body';
  bodyDiv.style.padding = '16px';
  bodyDiv.innerHTML = h;

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:8px;margin-top:16px;justify-content:flex-end';
  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn-off';
  cancelBtn.style.cssText = 'padding:8px 16px;font-size:13px;opacity:0.7';
  cancelBtn.textContent = t('btn_cancel');
  cancelBtn.addEventListener('click', closeOffAddReview);
  btnRow.appendChild(cancelBtn);
  const submitBtn = document.createElement('button');
  submitBtn.className = 'btn-register';
  submitBtn.id = 'off-submit-btn';
  submitBtn.style.cssText = 'padding:8px 20px;font-size:13px' + (!hasName ? ';opacity:0.4;pointer-events:none' : '');
  submitBtn.textContent = '\u{1F30E} ' + t('off_submit_btn');
  submitBtn.addEventListener('click', () => { submitToOff(ean); });
  btnRow.appendChild(submitBtn);
  bodyDiv.appendChild(btnRow);

  modalDiv.appendChild(bodyDiv);
  bg.innerHTML = '';
  bg.appendChild(modalDiv);
}

export function closeOffAddReview() {
  const el = document.getElementById('off-add-review-bg');
  if (el) el.remove();
}

export async function submitToOff(ean) {
  const prefix = _offCtx.prefix;
  const btn = document.getElementById('off-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  const body = { code: ean };
  _offReviewFields.forEach((f) => {
    const fieldEl = document.getElementById(prefix + '-' + f.key);
    const val = fieldEl ? fieldEl.value.trim() : '';
    if (val) body[f.offKey] = val;
  });

  // Convert quantity/serving_size to string with unit
  if (body.quantity) body.quantity = body.quantity + ' g';
  if (body.serving_size) body.serving_size = body.serving_size + ' g';

  try {
    await api('/api/off/add-product', {
      method: 'POST',
      body: JSON.stringify(body)
    });
    closeOffAddReview();
    closeOffPicker();
    showToast(t('toast_off_product_added'), 'success');
  } catch(e) {
    const msg = e.message && t(e.message) !== e.message ? t(e.message) : (e.message || t('toast_network_error'));
    showToast(msg, 'error');
    if (btn) { btn.disabled = false; btn.textContent = t('off_submit_btn'); }
  }
}

// ── Protein Quality Estimation ─────────────────────
export function updateEstimateBtn(prefix) {
  const ing = document.getElementById(prefix + '-ingredients');
  const wrap = document.getElementById(prefix + '-protein-quality-wrap');
  if (ing && wrap) wrap.style.display = ing.value.trim() ? '' : 'none';
}

export async function estimateProteinQuality(prefix) {
  const ingEl = document.getElementById(prefix + '-ingredients');
  const btn = document.getElementById(prefix + '-estimate-btn');
  const resultEl = document.getElementById(prefix + '-pq-result');
  const pdcaasEl = document.getElementById(prefix + '-pdcaas-val');
  const diEl = document.getElementById(prefix + '-diaas-val');
  const sourcesEl = document.getElementById(prefix + '-pq-sources');
  const hiddenPd = document.getElementById(prefix + '-est_pdcaas');
  const hiddenDi = document.getElementById(prefix + '-est_diaas');
  if (!ingEl || !ingEl.value.trim()) { showToast(t('toast_ingredients_missing'), 'error'); return; }
  if (btn) { btn.classList.add('loading'); btn.disabled = true; }
  try {
    const res = await fetch('/api/estimate-protein-quality', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredients: ingEl.value })
    });
    if (!res.ok) { showToast(t('toast_network_error'), 'error'); return; }
    const data = await res.json();
    if (data.error) { showToast(t('toast_error_prefix', { msg: data.error }), 'error'); return; }
    if (pdcaasEl) pdcaasEl.textContent = data.est_pdcaas != null ? Number(data.est_pdcaas).toFixed(2) : '\u2013';
    if (diEl) diEl.textContent = data.est_diaas != null ? Number(data.est_diaas).toFixed(2) : '\u2013';
    if (sourcesEl && data.sources && data.sources.length) sourcesEl.textContent = t('sources_label', { sources: data.sources.join(', ') });
    if (hiddenPd) hiddenPd.value = data.est_pdcaas != null ? data.est_pdcaas : '';
    if (hiddenDi) hiddenDi.value = data.est_diaas != null ? data.est_diaas : '';
    if (resultEl) resultEl.style.display = '';
    if (!data.est_pdcaas && !data.est_diaas) showToast(t('toast_no_protein_sources'), 'error');
    else showToast(t('toast_protein_estimated'), 'success');
  } catch(e) { showToast(t('toast_network_error'), 'error'); } finally {
    if (btn) { btn.classList.remove('loading'); btn.disabled = false; }
  }
}
