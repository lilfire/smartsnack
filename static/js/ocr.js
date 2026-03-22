// -- OCR ingredient scanning ──────────────────────────
import { api, showToast } from './state.js';
import { t } from './i18n.js';
import { resizeImage } from './images.js';

export function scanIngredients(prefix) {
  const textarea = document.getElementById(prefix + '-ingredients');
  if (!textarea) return;

  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/*';
  inp.setAttribute('capture', 'environment');

  inp.onchange = async () => {
    if (!inp.files.length) return;
    const file = inp.files[0];
    if (file.size > 10 * 1024 * 1024) {
      showToast(t('toast_image_too_large'), 'error');
      return;
    }

    const btn = document.getElementById(prefix + '-ocr-btn');
    if (btn) {
      btn.disabled = true;
      const spin = btn.querySelector('.ocr-spin');
      if (spin) spin.style.display = 'inline-block';
    }

    const reader = new FileReader();
    reader.onerror = () => {
      showToast(t('toast_ocr_error'), 'error');
      if (btn) {
        btn.disabled = false;
        const spin = btn.querySelector('.ocr-spin');
        if (spin) spin.style.display = 'none';
      }
    };
    reader.onload = async (e) => {
      try {
        const resized = await resizeImage(e.target.result, 1200);
        const res = await api('/api/ocr/ingredients', {
          method: 'POST',
          body: JSON.stringify({ image: resized })
        });
        if (res.text) {
          const existing = textarea.value.trim();
          textarea.value = existing ? existing + '\n' + res.text : res.text;
          textarea.dispatchEvent(new Event('input'));
          showToast(t('toast_ocr_success'), 'success');
        } else {
          showToast(t('toast_ocr_no_text'), 'error');
        }
      } catch (err) {
        showToast(t('toast_ocr_error'), 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          const spin = btn.querySelector('.ocr-spin');
          if (spin) spin.style.display = 'none';
        }
      }
    };
    reader.readAsDataURL(file);
  };
  inp.click();
}
