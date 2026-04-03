// ── Settings: OCR Provider and Settings ──────────────
import { api, showToast, upgradeSelect } from './state.js';
import { t } from './i18n.js';

function _updateOcrFallbackVisibility() {
  const sel = document.getElementById('ocr-provider-select');
  const wrapper = document.getElementById('ocr-fallback-wrapper');
  const cb = document.getElementById('ocr-fallback-checkbox');
  if (!sel || !wrapper) return;
  if (sel.value === 'tesseract') {
    wrapper.classList.remove('visible');
    if (cb) cb.checked = false;
  } else {
    wrapper.classList.add('visible');
  }
}

export async function loadOcrProviders() {
  const sel = document.getElementById('ocr-provider-select');
  if (!sel) return;
  try {
    const data = await api('/api/ocr/providers');
    sel.innerHTML = '';
    (data.providers || []).forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.key;
      opt.textContent = p.label;
      sel.appendChild(opt);
    });
  } catch(e) {
    if (!sel.querySelector('option')) {
      sel.innerHTML = '<option value="tesseract" selected>Tesseract OCR</option>';
    }
    showToast(t('toast_ocr_settings_error'), 'error');
  }
  upgradeSelect(sel, _updateOcrFallbackVisibility);
}

export async function loadOcrSettings() {
  const sel = document.getElementById('ocr-provider-select');
  const cb = document.getElementById('ocr-fallback-checkbox');
  if (!sel) return;
  try {
    const data = await api('/api/ocr/settings');
    sel.value = data.provider || 'tesseract';
    if (cb) cb.checked = !!data.fallback_to_tesseract;
    _updateOcrFallbackVisibility();
  } catch(e) { /* settings may not exist yet — use defaults */ }
}

export async function saveOcrSettings() {
  const sel = document.getElementById('ocr-provider-select');
  const cb = document.getElementById('ocr-fallback-checkbox');
  if (!sel || !sel.value) return;
  const body = { provider: sel.value, fallback_to_tesseract: !!(cb && cb.checked) };
  try {
    await api('/api/ocr/settings', { method: 'POST', body: JSON.stringify(body) });
    showToast(t('toast_ocr_settings_saved'), 'success');
  } catch(e) { showToast(t('toast_ocr_settings_error'), 'error'); }
}
