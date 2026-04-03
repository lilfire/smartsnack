// ── OFF Picker: search modal, result rendering, selection ─
import { showToast, trapFocus, esc } from './state.js';
import { t } from './i18n.js';
import { offState, fetchWithTimeout, applyOffProduct, validateOffBtn, _gatherNutrition } from './off-utils.js';
import { searchOFF } from './off-api.js';
import { showOffAddReview } from './off-review.js';

export function showOffPickerLoading(msg) {
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
  trapFocus(bg);
}

export function updateOffPickerResults(products, errorMsg, ean) {
  const body = document.getElementById('off-results-body');
  const count = document.getElementById('off-result-count');
  const si = document.getElementById('off-search-input');
  const sb = document.getElementById('off-search-btn');
  if (si) si.disabled = false;
  if (sb) { sb.disabled = false; sb.textContent = t('off_search_btn'); }
  if (!body) return;
  // Capture context snapshot at render time to avoid race conditions
  const ctxSnapshot = { prefix: offState.ctx.prefix, productId: offState.ctx.productId };
  if (errorMsg) {
    if (offState.ctx.autoClose && ean) {
      closeOffPicker();
      showToast(t('off_not_found_auto'), 'info');
      return;
    }
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
  offState.pickerProducts = products;
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
    const category = document.getElementById(offState.ctx.prefix + '-type')?.value || '';
    const products = await searchOFF(query, _gatherNutrition(offState.ctx.prefix), category);
    updateOffPickerResults(products);
  } catch(e) { updateOffPickerResults([], t('toast_network_error')); }
}

export function closeOffPicker() {
  const el = document.getElementById('off-modal-bg');
  if (el) el.remove();
  document.body.style.overflow = '';
  offState.pickerProducts = null;
}

export async function selectOffResult(idx, ctxSnapshot) {
  const products = offState.pickerProducts;
  if (!products || !products[idx]) return;
  const selected = products[idx];
  closeOffPicker();

  const code = selected.code;
  const ctx = ctxSnapshot || offState.ctx;
  const prefix = ctx.prefix;
  const productId = ctx.productId;
  const btn = document.getElementById(prefix + '-off-btn');
  if (btn) { btn.classList.add('loading'); btn.disabled = true; }

  let productToApply = selected;
  let resolvedEan = code || '';
  try {
    if (code) {
      const res = await fetchWithTimeout('/api/off/product/' + code);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 1 && data.product) {
          const eanEl = document.getElementById(prefix + '-ean');
          if (eanEl) eanEl.value = code;
          productToApply = data.product;
        }
      }
    }
  } catch(e) {
    showToast(t('toast_network_error'), 'error');
  }

  try {
    await applyOffProduct(productToApply, prefix, productId, false);
  } finally {
    if (btn) { btn.classList.remove('loading'); validateOffBtn(prefix); }
  }
}
