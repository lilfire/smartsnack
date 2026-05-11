// ── OFF Review: add-to-OFF product review and submission ─
import { api, esc, showToast, state, trapFocus } from './state.js';
import { t } from './i18n.js';
import { offState } from './off-utils.js';
import { closeOffPicker } from './off-picker.js';

let _pendingOffProductId = null;

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

export function showOffAddReview(ean, prefixOverride, productId) {
  if (offState.reviewResolve) offState.reviewResolve();
  const prefix = prefixOverride || offState.ctx.prefix;
  _pendingOffProductId = productId != null ? productId : null;
  const reviewPromise = new Promise((resolve) => { offState.reviewResolve = resolve; });
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
  headClose.setAttribute('aria-label', t('btn_close'));
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
  submitBtn.addEventListener('click', () => { submitToOff(ean, prefix); });
  btnRow.appendChild(submitBtn);
  bodyDiv.appendChild(btnRow);

  modalDiv.appendChild(bodyDiv);
  bg.innerHTML = '';
  bg.setAttribute('role', 'dialog');
  bg.setAttribute('aria-modal', 'true');
  bg.appendChild(modalDiv);
  trapFocus(bg);
  return reviewPromise;
}

export function closeOffAddReview() {
  const el = document.getElementById('off-add-review-bg');
  if (el) el.remove();
  if (offState.reviewResolve) { offState.reviewResolve(); offState.reviewResolve = null; }
}

export async function submitToOff(ean, prefixOverride) {
  const prefix = prefixOverride || offState.ctx.prefix;
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

  const productId = _pendingOffProductId;
  if (productId != null) body.product_id = productId;

  try {
    const resp = await api('/api/off/add-product', {
      method: 'POST',
      body: JSON.stringify(body)
    });
    closeOffAddReview();
    closeOffPicker();
    showToast(t('toast_off_product_added'), 'success');
    if (resp && resp.image_warning) {
      showToast(t('toast_off_image_upload_failed'), 'warning');
    }
    if (resp && resp.synced_flag_set && productId != null && state.cachedResults) {
      const cached = state.cachedResults.find((x) => x.id === productId);
      if (cached) cached.is_synced_with_off = 1;
    }
    _pendingOffProductId = null;
  } catch(e) {
    const msg = e.message && t(e.message) !== e.message ? t(e.message) : (e.message || t('toast_network_error'));
    showToast(msg, 'error');
    if (btn) { btn.disabled = false; btn.textContent = t('off_submit_btn'); }
  }
}
