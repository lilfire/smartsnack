// ── Settings: Feature Flags ──────────────────────────
import { api, esc, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';

export async function loadFlags() {
  try {
    const flags = await api('/api/flags');
    const list = document.getElementById('flag-list');
    if (!flags.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No flags</p>'; return; }
    let h = '';
    flags.forEach((f) => {
      const isSystem = f.type === 'system';
      h += '<div class="cat-item flag-item' + (isSystem ? ' flag-item-system' : '') + '">';
      if (isSystem) {
        h += '<span class="flag-type-badge flag-type-system">system</span>';
        h += '<span class="flag-item-label-ro">' + esc(f.label) + '</span>';
      } else {
        h += '<span class="flag-type-badge flag-type-user">user</span>';
        h += '<input class="cat-item-label-input" data-flag-name="' + esc(f.name) + '" value="' + esc(f.label) + '" title="' + t('label_display_name') + '">';
      }
      h += '<span class="cat-item-key">' + esc(f.name) + '</span>';
      h += '<span class="cat-item-count">' + f.count + ' prod.</span>';
      if (!isSystem) {
        h += '<button class="btn-sm btn-red" data-action="delete-flag" data-flag-name="' + esc(f.name) + '" data-flag-label="' + esc(f.label) + '" data-flag-count="' + f.count + '">&#128465;</button>';
      }
      h += '</div>';
    });
    list.innerHTML = h;
    list.querySelectorAll('input.cat-item-label-input[data-flag-name]').forEach((inp) => {
      inp.addEventListener('change', () => {
        updateFlagLabel(inp.dataset.flagName, inp.value);
      });
    });
    list.querySelectorAll('[data-action="delete-flag"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        deleteFlag(btn.dataset.flagName, btn.dataset.flagLabel, parseInt(btn.dataset.flagCount, 10));
      });
    });
  } catch(e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export async function updateFlagLabel(name, val) {
  if (!val.trim()) { showToast(t('toast_display_name_empty'), 'error'); loadFlags(); return; }
  try {
    await api('/api/flags/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ label: val.trim() }) });
    showToast(t('toast_flag_updated'), 'success');
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addFlag() {
  const name = document.getElementById('flag-add-name').value.trim();
  const label = document.getElementById('flag-add-label').value.trim();
  if (!name || !label) { showToast(t('toast_name_display_required'), 'error'); return; }
  try {
    const res = await api('/api/flags', { method: 'POST', body: JSON.stringify({ name: name, label: label }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('flag-add-name').value = '';
    document.getElementById('flag-add-label').value = '';
    showToast(t('toast_flag_added', { name: label }), 'success');
    loadFlags();
    _refreshFlagConfig();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deleteFlag(name, label, count) {
  const msg = count > 0
    ? t('confirm_delete_flag_body', { name: label, count: count })
    : t('confirm_delete_flag_body_empty', { name: label });
  if (!await showConfirmModal('\u{1F5D1}', label, msg, t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/flags/' + encodeURIComponent(name), { method: 'DELETE' });
    showToast(t('toast_flag_deleted', { name: label }), 'success');
    loadFlags();
    _refreshFlagConfig();
  } catch(e) { console.error(e); showToast(t('toast_network_error'), 'error'); }
}

async function _refreshFlagConfig() {
  try {
    const { loadFlagConfig } = await import('./render.js');
    await loadFlagConfig();
  } catch(e) { /* ignore */ }
}
