// ── Product Delete with 5s Undo Window ──────────────
import { state, api, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';
import { rerender } from './filters.js';
import { loadData } from './products.js';

let _pendingDelete = null;

export async function deleteProduct(id, name) {
  if (!name) {
    const product = state.cachedResults && state.cachedResults.find((p) => p.id === id);
    name = product ? product.name : '';
  }
  if (!await showConfirmModal('\u{1F5D1}', name, t('confirm_delete_product', { name: name }), t('btn_delete'), t('btn_cancel'), true)) return;

  // Flush any previous pending delete: fire its DELETE now instead of
  // silently dropping it (a dropped timer left the product on the server).
  if (_pendingDelete) {
    clearTimeout(_pendingDelete.timer);
    const flushId = _pendingDelete.id;
    _pendingDelete = null;
    try {
      await api('/api/products/' + flushId, { method: 'DELETE' });
    } catch(e) {
      console.error('Flush delete failed', e);
      showToast(t('toast_network_error'), 'error');
    }
  }

  // Cache the product data for undo
  const cachedProduct = state.cachedResults && state.cachedResults.find((p) => p.id === id);
  const cachedImage = state.imageCache[id];

  // Remove from UI immediately
  state.cachedResults = (state.cachedResults || []).filter((p) => p.id !== id);
  delete state.imageCache[id];
  state.expandedId = null;
  state.editingId = null;
  rerender();

  // Schedule actual delete after 5 seconds
  var pending = {
    id: id,
    timer: setTimeout(async () => {
      _pendingDelete = null;
      try {
        await api('/api/products/' + id, { method: 'DELETE' });
      } catch(e) {
        console.error(e);
        showToast(t('toast_network_error'), 'error');
        // Restore on failure
        if (cachedProduct) { state.cachedResults.push(cachedProduct); }
        if (cachedImage) { state.imageCache[id] = cachedImage; }
        loadData();
      }
    }, 5000)
  };
  _pendingDelete = pending;

  showToast(t('toast_product_deleted', { name: name }), 'success', {
    duration: 5000,
    onUndo: function() {
      if (_pendingDelete === pending) {
        clearTimeout(pending.timer);
        _pendingDelete = null;
      }
      // Restore product to cached results
      if (cachedProduct) { state.cachedResults.push(cachedProduct); }
      if (cachedImage) { state.imageCache[id] = cachedImage; }
      rerender();
      showToast(t('toast_delete_undone'), 'info');
    }
  });
}
