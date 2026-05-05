// ── Settings: OCR Provider and Settings ──────────────
import { api, showToast } from './state.js';
import { t } from './i18n.js';

// Cache of provider key → models list (populated by loadOcrProviders)
const _providerModels = {};
// Cache of provider key → free_text_model flag
const _providerFreeText = {};

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

function _updateOcrModelSelector(providerKey, selectedModel) {
  const row = document.getElementById('ocr-model-row');
  const selectEl = document.getElementById('ocr-model-select');
  const inputEl = document.getElementById('ocr-model-input');
  if (!row || !selectEl || !inputEl) return;

  if (providerKey === 'tesseract') {
    row.style.display = 'none';
    return;
  }

  const models = _providerModels[providerKey] || [];
  const isFreeText = _providerFreeText[providerKey] || models.length === 0;

  if (isFreeText) {
    row.style.display = '';
    selectEl.style.display = 'none';
    inputEl.style.display = '';
    inputEl.value = selectedModel || '';
  } else {
    row.style.display = '';
    inputEl.style.display = 'none';
    selectEl.style.display = '';
    selectEl.innerHTML = '';
    models.forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      selectEl.appendChild(opt);
    });
    selectEl.value = (selectedModel && models.includes(selectedModel)) ? selectedModel : models[0];
    // Refresh the custom dropdown wrapper so its trigger and option list reflect
    // the new model set — otherwise the wrapper (created at app init when the
    // native select was empty) shows an empty dropdown.
    upgradeSelect(selectEl);
  }
}

function _onProviderChange() {
  const sel = document.getElementById('ocr-provider-select');
  if (!sel) return;
  _updateOcrFallbackVisibility();
  _updateOcrModelSelector(sel.value, null);
}

export async function loadOcrProviders() {
  const sel = document.getElementById('ocr-provider-select');
  if (!sel) return;
  sel.onchange = _onProviderChange;
  try {
    const data = await api('/api/ocr/providers');
    sel.innerHTML = '';
    (data.providers || []).forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.key;
      opt.textContent = p.label;
      sel.appendChild(opt);
      _providerModels[p.key] = p.models || [];
      _providerFreeText[p.key] = !!p.free_text_model;
    });
  } catch(e) {
    if (!sel.querySelector('option')) {
      sel.innerHTML = '<option value="tesseract" selected>Tesseract OCR</option>';
    }
    showToast(t('toast_ocr_settings_error'), 'error');
  }
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
    const savedModels = data.models || {};
    _updateOcrModelSelector(sel.value, savedModels[sel.value] || null);
  } catch(e) { /* settings may not exist yet — use defaults */ }
}

export async function saveOcrSettings() {
  const sel = document.getElementById('ocr-provider-select');
  const cb = document.getElementById('ocr-fallback-checkbox');
  if (!sel || !sel.value) return;

  const provider = sel.value;
  const models = {};
  if (provider !== 'tesseract') {
    const isFreeText = _providerFreeText[provider] || (_providerModels[provider] || []).length === 0;
    const selectEl = document.getElementById('ocr-model-select');
    const inputEl = document.getElementById('ocr-model-input');
    const modelVal = isFreeText ? (inputEl && inputEl.value.trim()) : (selectEl && selectEl.value);
    if (modelVal) {
      models[provider] = modelVal;
    }
  }

  const body = { provider, fallback_to_tesseract: !!(cb && cb.checked) };
  if (Object.keys(models).length > 0) body.models = models;
  try {
    await api('/api/ocr/settings', { method: 'POST', body: JSON.stringify(body) });
    showToast(t('toast_ocr_settings_saved'), 'success');
  } catch(e) { showToast(t('toast_ocr_settings_error'), 'error'); }
}
