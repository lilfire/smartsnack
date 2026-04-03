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
          if (res.fallback) {
            // Success via fallback provider
            const reason = res.error_detail || 'primary provider unavailable';
            showToast(
              t('toast_ocr_fallback', { fallback_provider: res.provider || 'unknown', reason: reason }),
              'warning',
              { title: t('toast_ocr_title_fallback'), duration: 5000 }
            );
          } else {
            // Success via primary provider
            showToast(
              t('toast_ocr_success_provider', { provider: res.provider || 'OCR' }),
              'success',
              { title: t('toast_ocr_title_success'), duration: 3000 }
            );
          }
        } else {
          showToast(t('toast_ocr_no_text'), 'error');
        }
      } catch (err) {
        const errorData = err.data || {};
        if (errorData.error_type === 'token_limit_exceeded') {
          showToast(
            t('toast_ocr_token_limit'),
            'error',
            { title: t('toast_ocr_title_failed'), duration: 5000 }
          );
        } else if (errorData.error_type === 'invalid_image') {
          showToast(t('toast_ocr_invalid_image'), 'error', { title: t('toast_ocr_title_failed'), duration: 5000 });
        } else if (errorData.error_type === 'provider_timeout') {
          showToast(t('toast_ocr_provider_timeout'), 'error', { title: t('toast_ocr_title_failed'), duration: 5000 });
        } else if (errorData.error_type === 'provider_quota') {
          showToast(
            t('toast_ocr_provider_quota'),
            'error',
            { title: t('toast_ocr_title_failed'), duration: 6000 }
          );
        } else if (errorData.error_type === 'no_text') {
          showToast(t('toast_ocr_no_text'), 'error', { title: t('toast_ocr_title_failed'), duration: 5000 });
        } else {
          const detail = errorData.error_detail || 'an unexpected error occurred';
          showToast(
            t('toast_ocr_generic_error', { error_detail: detail }),
            'error',
            { title: t('toast_ocr_title_failed'), duration: 5000 }
          );
        }
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
