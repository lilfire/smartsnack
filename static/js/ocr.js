// -- OCR ingredient & nutrition scanning ──────────────────────────
import { api, showToast } from './state.js';
import { t } from './i18n.js';
import { resizeImage } from './images.js';

// Canonical nutrition fields the scanNutrition flow knows how to populate.
// The server only returns keys from this set, but we keep a local allow-list
// so a malformed response can never touch unrelated inputs.
const _NUTRITION_FIELDS = [
  'kcal',
  'energy_kj',
  'fat',
  'saturated_fat',
  'carbs',
  'sugar',
  'fiber',
  'protein',
  'salt',
];

function _setBusy(btn, busy) {
  if (!btn) return;
  btn.disabled = busy;
  const spin = btn.querySelector('.ocr-spin');
  if (spin) spin.style.display = busy ? 'inline-block' : 'none';
}

function _handleOcrError(err) {
  const errorData = (err && err.data) || {};
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
}

function _showOcrProviderToast(res, successKey, extraParams) {
  const params = Object.assign({ provider: res.provider || 'OCR' }, extraParams || {});
  if (res.fallback) {
    const reason = res.error_detail || 'primary provider unavailable';
    showToast(
      t('toast_ocr_fallback', Object.assign({ fallback_provider: res.provider || 'unknown', reason }, extraParams || {})),
      'warning',
      { title: t('toast_ocr_title_fallback'), duration: 5000 }
    );
  } else {
    showToast(
      t(successKey, params),
      'success',
      { title: t('toast_ocr_title_success'), duration: 3000 }
    );
  }
}

// Shared file-picker + resize + POST + error-handling pipeline.
// onSuccess(res) handles the success path (caller-specific population + toast).
function _runOcrScan({ endpoint, btnId, onSuccess }) {
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

    const btn = document.getElementById(btnId);
    _setBusy(btn, true);

    const reader = new FileReader();
    reader.onerror = () => {
      showToast(t('toast_ocr_error'), 'error');
      _setBusy(btn, false);
    };
    reader.onload = async (e) => {
      try {
        const resized = await resizeImage(e.target.result, 1200);
        const res = await api(endpoint, {
          method: 'POST',
          body: JSON.stringify({ image: resized }),
        });
        onSuccess(res);
      } catch (err) {
        _handleOcrError(err);
      } finally {
        _setBusy(btn, false);
      }
    };
    reader.readAsDataURL(file);
  };
  inp.click();
}

export function scanIngredients(prefix) {
  const textarea = document.getElementById(prefix + '-ingredients');
  if (!textarea) return;

  _runOcrScan({
    endpoint: '/api/ocr/ingredients',
    btnId: prefix + '-ocr-btn',
    onSuccess: (res) => {
      if (res.text) {
        const existing = textarea.value.trim();
        textarea.value = existing ? existing + '\n' + res.text : res.text;
        textarea.dispatchEvent(new Event('input'));
        _showOcrProviderToast(res, 'toast_ocr_success_provider');
      } else {
        showToast(t('toast_ocr_no_text'), 'error');
      }
    },
  });
}

export function scanNutrition(prefix) {
  _runOcrScan({
    endpoint: '/api/ocr/nutrition',
    btnId: prefix + '-ocr-nutri-btn',
    onSuccess: (res) => {
      const values = (res && res.values) || {};
      const fieldsPresent = Object.keys(values).filter((k) => _NUTRITION_FIELDS.includes(k));

      if (!fieldsPresent.length || res.error_type === 'no_values') {
        showToast(
          t('toast_ocr_nutrition_no_values'),
          'warning',
          { title: t('toast_ocr_title_failed'), duration: 5000 }
        );
        return;
      }

      let filled = 0;
      let skipped = 0;
      for (const field of fieldsPresent) {
        const input = document.getElementById(prefix + '-' + field);
        if (!input) continue;
        const current = (input.value || '').trim();
        if (current !== '') {
          skipped += 1;
          continue;
        }
        input.value = String(values[field]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.classList.add('ocr-flash');
        setTimeout(() => input.classList.remove('ocr-flash'), 1200);
        filled += 1;
      }

      if (filled === 0) {
        showToast(
          t('toast_ocr_nutrition_all_skipped', { skipped }),
          'warning',
          { title: t('toast_ocr_title_success'), duration: 5000 }
        );
        return;
      }

      _showOcrProviderToast(res, 'toast_ocr_nutrition_success_provider', {
        filled,
        skipped,
      });
    },
  });
}

// Expose for inline onclick handlers in templates/render.js.
if (typeof window !== 'undefined') {
  window.scanIngredients = scanIngredients;
  window.scanNutrition = scanNutrition;
}
