// ── OFF API: EAN lookup and product search ─────────
import { showToast } from './state.js';
import { t } from './i18n.js';
import { fetchWithTimeout, isValidEan, offState, _gatherNutrition, applyOffProduct } from './off-utils.js';
import { showOffPickerLoading, updateOffPickerResults, closeOffPicker } from './off-picker.js';

export async function lookupOFF(prefix, productId, opts) {
  // opts.ean, when present, targets a specific EAN (e.g. per-row fetch on a
  // secondary EAN) without requiring the caller to mutate the hidden input.
  const explicitEan = opts && opts.ean ? String(opts.ean) : null;
  const ean = (explicitEan != null
    ? explicitEan
    : document.getElementById(prefix + '-ean').value
  ).replace(/\s/g, '');
  const name = document.getElementById(prefix + '-name').value.trim();
  offState.ctx = { prefix: prefix, productId: productId || null, autoClose: opts?.autoClose || false, offEan: explicitEan };

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
      await applyOffProduct(data.product, prefix, productId, false);
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
