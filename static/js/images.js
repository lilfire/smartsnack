// ── Image handling ──────────────────────────────────
import { state, api, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';
import { rerender } from './filters.js';

export async function loadProductImage(id) {
  if (state.imageCache[id] !== undefined) return state.imageCache[id];
  try {
    const res = await fetch('/api/products/' + id + '/image');
    if (!res.ok) {
      // Only cache null for 404 (no image); transient errors should allow retry
      if (res.status === 404) state.imageCache[id] = null;
      return null;
    }
    const d = await res.json();
    state.imageCache[id] = d.image;
    return d.image;
  } catch(e) { return null; }
}

export function triggerImageUpload(id) {
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/png,image/jpeg,image/gif,image/webp';
  inp.onchange = async () => {
    if (!inp.files.length) return;
    const file = inp.files[0];
    if (file.size > 10 * 1024 * 1024) { showToast(t('toast_image_too_large'), 'error'); return; }
    const reader = new FileReader();
    reader.onerror = () => { showToast(t('toast_image_upload_error'), 'error'); };
    reader.onload = async (e) => {
      try {
        showToast(t('toast_uploading'), 'info');
        const resized = await resizeImage(e.target.result, 400);
        await api('/api/products/' + id + '/image', { method: 'PUT', body: JSON.stringify({ image: resized }) });
        state.imageCache[id] = resized;
        const p = state.cachedResults && state.cachedResults.find((x) => x.id === id);
        if (p) p.has_image = 1;
        showToast(t('toast_image_saved'), 'success');
        rerender();
      } catch(err) { showToast(t('toast_image_upload_error'), 'error'); }
    };
    reader.readAsDataURL(file);
  };
  inp.click();
}

export function resizeImage(dataUri, maxSize) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const w = img.width, h = img.height;
      if (w <= maxSize && h <= maxSize) { resolve(dataUri); return; }
      const ratio = Math.min(maxSize / w, maxSize / h);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(w * ratio);
      canvas.height = Math.round(h * ratio);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { resolve(dataUri); };
    img.src = dataUri;
  });
}

export async function removeProductImage(id) {
  if (!await showConfirmModal('\u{1F4F7}', t('remove_image_title'), t('remove_image_confirm'), t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/products/' + id + '/image', { method: 'DELETE' });
    state.imageCache[id] = null;
    const p = state.cachedResults && state.cachedResults.find((x) => x.id === id);
    if (p) p.has_image = 0;
    showToast(t('toast_image_removed'), 'success');
    rerender();
  } catch(e) {
    showToast(t('toast_network_error'), 'error');
  }
}
