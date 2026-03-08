// ── Image handling ──────────────────────────────────
import { state, api, showConfirmModal } from './state.js';
import { t } from './i18n.js';
import { rerender } from './filters.js';

export async function loadProductImage(id) {
  if (state.imageCache[id] !== undefined) return state.imageCache[id];
  try {
    var res = await fetch('/api/products/' + id + '/image');
    if (!res.ok) { state.imageCache[id] = null; return null; }
    var d = await res.json();
    state.imageCache[id] = d.image;
    return d.image;
  } catch(e) { state.imageCache[id] = null; return null; }
}

export function triggerImageUpload(id) {
  var inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/*';
  inp.onchange = async function() {
    if (!inp.files.length) return;
    var file = inp.files[0];
    if (file.size > 10 * 1024 * 1024) { showToast(t('toast_image_too_large'), 'error'); return; }
    var reader = new FileReader();
    reader.onload = async function(e) {
      var resized = await resizeImage(e.target.result, 400);
      try {
        await api('/api/products/' + id + '/image', { method: 'PUT', body: JSON.stringify({ image: resized }) });
        state.imageCache[id] = resized;
        var p = state.cachedResults && state.cachedResults.find(function(x) { return x.id === id; });
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
  return new Promise(function(resolve) {
    var img = new Image();
    img.onload = function() {
      var w = img.width, h = img.height;
      if (w <= maxSize && h <= maxSize) { resolve(dataUri); return; }
      var ratio = Math.min(maxSize / w, maxSize / h);
      var canvas = document.createElement('canvas');
      canvas.width = w * ratio;
      canvas.height = h * ratio;
      var ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    img.src = dataUri;
  });
}

export async function removeProductImage(id) {
  if (!await showConfirmModal('&#128247;', t('remove_image_title') || 'Remove image', t('remove_image_confirm') || 'Remove image?', t('btn_delete'), t('btn_cancel'))) return;
  await api('/api/products/' + id + '/image', { method: 'DELETE' });
  state.imageCache[id] = null;
  var p = state.cachedResults && state.cachedResults.find(function(x) { return x.id === id; });
  if (p) p.has_image = 0;
  showToast(t('toast_image_removed'), 'success');
  rerender();
}

// Import showToast lazily to avoid circular deps
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast ' + type + ' show';
  setTimeout(function() { toast.classList.remove('show'); }, 3000);
}
