// ── OFF Utilities: shared state, helpers, image handling, field application ─
import { state, api, esc, safeDataUri, showToast, trapFocus } from './state.js';
import { t } from './i18n.js';
import { resizeImage } from './images.js';

export const OFF_FETCH_TIMEOUT = 45000;

export const _FIELD_LABEL_KEYS = {
  name: 'label_name', brand: 'label_brand', stores: 'label_stores',
  ingredients: 'label_ingredients', ean: 'edit_label_ean', type: 'label_category',
  kcal: 'label_kcal', energy_kj: 'label_energy_kj', protein: 'label_protein',
  fat: 'label_fat', saturated_fat: 'label_saturated_fat', carbs: 'label_carbs',
  sugar: 'label_sugar', fiber: 'label_fiber', salt: 'label_salt',
  price: 'label_price', weight: 'label_weight', portion: 'label_portion',
  volume: 'label_volume', taste_score: 'weight_label_taste_score',
  est_pdcaas: 'weight_label_est_pdcaas', est_diaas: 'weight_label_est_diaas',
  total_score: 'adv_field_total_score', completeness: 'completeness_label',
};

export function _fieldLabel(field) { return t(_FIELD_LABEL_KEYS[field] || field) || field; }

export const _VOLUME_LABELS = { 1: 'volume_low', 2: 'volume_medium', 3: 'volume_high' };

export function _volumeLabel(val) { return _VOLUME_LABELS[val] ? t(_VOLUME_LABELS[val]) : val; }

export function fetchWithTimeout(url, opts) {
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
  if (btn) {
    btn.disabled = !(isValidEan(ean) || name.length >= 2);
    btn.title = btn.disabled ? t('btn_fetch_disabled_title') : '';
  }
}

export const offState = {
  ctx: { prefix: null, productId: null },
  pickerProducts: null,
  reviewResolve: null,
};

export const _nutritionCompareFields = ['kcal', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt'];

export function _gatherNutrition(prefix) {
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

export const _numericFields = new Set(['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion']);

export function _formatNumeric(key, val) {
  return (key === 'kcal' || key === 'energy_kj' || key === 'weight' || key === 'portion')
    ? String(Math.round(val))
    : parseFloat(val).toFixed(key === 'salt' ? 2 : 1);
}

export function _detectConflicts(offValues, prefix) {
  const autoApply = {};
  const conflicts = [];
  Object.keys(offValues).forEach((key) => {
    const offVal = offValues[key];
    const fieldEl = document.getElementById(prefix + '-' + key);
    if (!fieldEl) return;
    const localRaw = fieldEl.value.trim();
    const isNum = _numericFields.has(key);

    if (isNum) {
      const offNum = offVal != null ? parseFloat(offVal) : NaN;
      const offEmpty = isNaN(offNum) || offNum === 0;

      if (offEmpty) return; // keep local (or both empty)
      autoApply[key] = _formatNumeric(key, offNum);
    } else {
      const offStr = (offVal || '').trim();

      if (offStr === '') return; // keep local (or both empty)
      autoApply[key] = offStr;
    }
  });
  return { autoApply, conflicts };
}

export function _esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// Validate image URLs to prevent SSRF via the proxy endpoint
export function isValidImageUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch(e) {
    return false;
  }
}

export async function fetchImageAsDataUri(url) {
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

export function blobToResizedDataUri(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => { resizeImage(e.target.result, 400).then(resolve).catch(() => resolve(null)); };
    reader.onerror = () => { resolve(null); };
    reader.readAsDataURL(blob);
  });
}

export async function applyOffProduct(prod, prefix, productId, duplicateResolved) {
  window._pendingOFFSync = true;
  window._offAppliedFields = null;
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

  // Build unified OFF values map (nutrition + metadata)
  const serving = prod.serving_size || '';
  const servMatch = serving.match(/([\d.]+)\s*g/);
  if (servMatch) offMap.portion = parseFloat(servMatch[1]);
  const qty = prod.product_quantity || 0;
  if (qty) offMap.weight = parseFloat(qty);
  offMap.name = prod.product_name_no || prod.product_name || '';
  offMap.ean = prod.code || '';
  offMap.brand = prod.brands || '';
  let stores = '';
  if (prod.stores) stores = prod.stores;
  else if (prod.stores_tags?.length) stores = prod.stores_tags.map((s) => s.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())).join(', ');
  offMap.stores = stores;
  offMap.ingredients = prod.ingredients_text_no || prod.ingredients_text_en || prod.ingredients_text || '';

  const filled = [];

  if (duplicateResolved) {
    // OFF is authoritative: auto-apply all OFF values, no conflict modal
    const { autoApply } = _detectConflicts(offMap, prefix);

    Object.keys(autoApply).forEach((key) => {
      const el = document.getElementById(prefix + '-' + key);
      if (el) { el.value = autoApply[key]; filled.push(key); }
    });

    if (offMap.ingredients) updateEstimateBtn(prefix);
  } else {
    // Normal flow (no duplicate): OFF overwrites, but skip OFF 0 over local non-zero
    Object.keys(offMap).forEach((key) => {
      if (!_numericFields.has(key) && !['name', 'ean', 'brand', 'stores', 'ingredients'].includes(key)) return;
      const val = offMap[key];
      const fieldEl = document.getElementById(prefix + '-' + key);
      if (!fieldEl) return;

      if (_numericFields.has(key)) {
        if (val == null || val === '') return;
        const num = parseFloat(val);
        if (isNaN(num)) return;
        if (num === 0 && fieldEl.value !== '' && parseFloat(fieldEl.value) !== 0) return;
        fieldEl.value = _formatNumeric(key, num);
        filled.push(key);
      } else {
        const str = (typeof val === 'string' ? val : '').trim();
        if (!str) return;
        // ean: only fill if empty (name is overwritten with OFF value)
        if (key === 'ean' && fieldEl.value.trim()) return;
        fieldEl.value = str;
        filled.push(key);
        if (key === 'ingredients') updateEstimateBtn(prefix);
      }
    });
  }

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

  window._offAppliedFields = new Set(filled.filter(f => f !== 'image'));
  showToast(t('toast_off_fetched', { fields: filled.join(', ') }), 'success');
  if (offMap.ingredients) { setTimeout(() => { estimateProteinQuality(prefix); }, 300); }
}

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
