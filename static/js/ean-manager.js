// ── EAN Manager ──────────────────────────────────────
import { api, esc, showToast } from './state.js';
import { t } from './i18n.js';
import { isValidEan } from './off-utils.js';
import { lookupOFF } from './off-api.js';

function _renderEanList(productId, eans, locked) {
  const container = document.getElementById('ean-manager-' + productId);
  if (!container) return;

  // Sync hidden ed-ean with current primary EAN for OFF/scan compatibility
  const primary = eans.find((e) => e.is_primary);
  const hiddenEan = document.getElementById('ed-ean');
  if (hiddenEan && primary) hiddenEan.value = primary.ean;

  let html = '<ul class="ean-list">';
  eans.forEach((e) => {
    html += '<li class="ean-item">';
    html += '<span class="ean-value">' + esc(e.ean) + '</span>';
    if (e.is_primary) {
      html += '<span class="ean-badge-primary">' + esc(t('label_ean_primary')) + '</span>';
      if (!locked) {
        html += '<span class="ean-badge-off" title="' + esc(t('ean_off_fetch_tooltip')) + '">OFF</span>';
      }
    } else if (!locked) {
      html += '<button class="btn-ean-action" data-ean-action="set-primary" data-product-id="' + productId + '" data-ean-id="' + e.id + '" data-ean-value="' + esc(e.ean) + '">' + t('btn_set_primary_ean') + '</button>';
      html += '<button class="btn-ean-off btn-ean-action" data-ean-action="fetch-ean-off" data-product-id="' + productId + '" data-ean-id="' + e.id + '" data-ean-value="' + esc(e.ean) + '" title="' + esc(t('ean_fetch_off_btn_tooltip')) + '" aria-label="' + esc(t('ean_fetch_off_btn_tooltip')) + '">\uD83C\uDF0D</button>';
    }
    if (!locked && eans.length > 1) {
      html += '<button class="btn-ean-action btn-ean-delete" data-ean-action="delete-ean" data-product-id="' + productId + '" data-ean-id="' + e.id + '" aria-label="' + esc(t('btn_delete')) + '">\u00D7</button>';
    }
    html += '</li>';
  });
  html += '</ul>';

  if (locked) {
    html += '<div class="ean-lock-notice">\uD83D\uDD12 ' + esc(t('ean_locked_notice')) + '</div>';
  }

  // Always render add-EAN row regardless of locked state
  html += '<div class="ean-add-row">'
    + '<input id="ean-add-input-' + productId + '" class="ean-add-input" placeholder="EAN..." maxlength="13" aria-label="' + esc(t('btn_add_ean')) + '">'
    + '<button class="btn-ean-add" data-ean-action="add-ean" data-product-id="' + productId + '">' + t('btn_add_ean') + '</button>'
    + '</div>'
    + '<div id="ean-error-' + productId + '" class="field-error" style="display:none"></div>';
  container.innerHTML = html;

  // Attach event delegation; set-primary/delete/fetch-ean-off are skipped when locked
  container.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-ean-action]');
    if (!btn) return;
    const action = btn.dataset.eanAction;
    const pid = parseInt(btn.dataset.productId, 10);
    const eid = btn.dataset.eanId ? parseInt(btn.dataset.eanId, 10) : null;
    const eanVal = btn.dataset.eanValue || null;
    if (action === 'add-ean') addEan(pid);
    else if (!locked) {
      if (action === 'delete-ean') deleteEan(pid, eid);
      else if (action === 'set-primary') setEanPrimary(pid, eid);
      else if (action === 'fetch-ean-off') _fetchEanOff(pid, eid, eanVal);
    }
  });

  // Allow Enter key in add input
  const addInput = document.getElementById('ean-add-input-' + productId);
  if (addInput) {
    addInput.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); addEan(productId); }
    });
  }
}

async function _fetchEanOff(productId, eanId, eanValue) {
  // Promote selected EAN to primary, update hidden field, then trigger OFF lookup
  await setEanPrimary(productId, eanId);
  const hiddenEan = document.getElementById('ed-ean');
  if (hiddenEan && eanValue) hiddenEan.value = eanValue;
  await lookupOFF('ed', productId);
}

export async function loadEanManager(productId, locked) {
  const container = document.getElementById('ean-manager-' + productId);
  if (!container) return;
  try {
    const eans = await api('/api/products/' + productId + '/eans');
    _renderEanList(productId, eans, locked);
  } catch (e) {
    console.error(e);
    if (container) container.innerHTML = '<div class="field-error">' + esc(t('toast_network_error')) + '</div>';
  }
}

export async function addEan(productId) {
  const input = document.getElementById('ean-add-input-' + productId);
  const errorEl = document.getElementById('ean-error-' + productId);
  if (!input) return;
  const ean = input.value.trim();
  if (errorEl) { errorEl.style.display = 'none'; errorEl.textContent = ''; }
  if (!ean) return;
  if (!isValidEan(ean)) { showToast(t('toast_invalid_ean'), 'error'); return; }
  try {
    await api('/api/products/' + productId + '/eans', { method: 'POST', body: JSON.stringify({ ean }) });
    input.value = '';
    await loadEanManager(productId);
    showToast(t('toast_ean_added', { ean }), 'success');
  } catch (e) {
    const msg = e.data && e.data.error === 'error_ean_already_exists'
      ? t('error_ean_already_exists')
      : (e.message || t('toast_network_error'));
    if (errorEl) { errorEl.textContent = msg; errorEl.style.display = ''; }
    else showToast(msg, 'error');
  }
}

export async function deleteEan(productId, eanId) {
  // Capture EAN value from DOM before removal for toast message
  const container = document.getElementById('ean-manager-' + productId);
  let eanValue = '';
  if (container) {
    const btn = container.querySelector('[data-ean-id="' + eanId + '"][data-ean-action="delete-ean"]');
    if (btn) {
      const li = btn.closest('.ean-item');
      if (li) eanValue = (li.querySelector('.ean-value') || {}).textContent || '';
    }
  }
  try {
    await api('/api/products/' + productId + '/eans/' + eanId, { method: 'DELETE' });
    await loadEanManager(productId);
    showToast(t('toast_ean_removed', { ean: eanValue }), 'success');
  } catch (e) {
    const msg = e.data && e.data.error === 'error_cannot_remove_only_ean'
      ? t('error_cannot_remove_only_ean')
      : (e.message || t('toast_network_error'));
    showToast(msg, 'error');
  }
}

export async function setEanPrimary(productId, eanId) {
  // Capture the EAN value before the request for the toast
  const container = document.getElementById('ean-manager-' + productId);
  let eanValue = '';
  if (container) {
    const btn = container.querySelector('[data-ean-id="' + eanId + '"][data-ean-action="set-primary"]');
    if (btn) {
      const li = btn.closest('.ean-item');
      if (li) eanValue = (li.querySelector('.ean-value') || {}).textContent || '';
    }
  }
  try {
    await api('/api/products/' + productId + '/eans/' + eanId + '/set-primary', { method: 'PATCH' });
    await loadEanManager(productId);
    showToast(t('toast_ean_set_primary', { ean: eanValue }), 'success');
  } catch (e) {
    showToast(e.message || t('toast_network_error'), 'error');
  }
}
