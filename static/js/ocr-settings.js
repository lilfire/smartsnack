// ── OCR Settings ─────────────────────────────────────
import { api, showToast } from './state.js';
import { t } from './i18n.js';

export async function loadOcrSettings() {
  try {
    const data = await api('/api/settings/ocr');
    const providerEl = document.getElementById('ocr-provider');
    if (providerEl) providerEl.value = data.provider || 'easyocr';
    const modelEl = document.getElementById('ocr-model');
    if (modelEl) modelEl.value = data.model || '';
    const fallbackEl = document.getElementById('ocr-fallback');
    if (fallbackEl) fallbackEl.checked = !!data.fallback_to_tesseract;
    onOcrProviderChange();
  } catch (_) { /* ignore load errors */ }
}

export function onOcrProviderChange() {
  const providerEl = document.getElementById('ocr-provider');
  const modelRow = document.getElementById('ocr-model-row');
  if (!providerEl || !modelRow) return;
  modelRow.style.display = providerEl.value === 'tesseract' ? 'none' : '';
}

export async function saveOcrSettings() {
  const provider = document.getElementById('ocr-provider')?.value || 'easyocr';
  const model = document.getElementById('ocr-model')?.value || '';
  const fallback = document.getElementById('ocr-fallback')?.checked || false;
  try {
    await api('/api/settings/ocr', {
      method: 'PUT',
      body: JSON.stringify({ provider, model, fallback_to_tesseract: fallback }),
    });
    showToast(t('toast_updated') || 'Saved', 'success');
  } catch (_) {
    showToast(t('toast_save_error'), 'error');
  }
}
