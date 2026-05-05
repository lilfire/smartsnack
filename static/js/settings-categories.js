// ── Settings: Category Management ───────────────────
import { state, api, esc, fetchStats, upgradeSelect, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';
import { initEmojiPicker, resetEmojiPicker } from './emoji-picker.js';
import { refreshScopeSelect } from './settings-weights.js';

function updateStatsLine() {
  const el = document.getElementById('stats-line');
  if (el && state.cachedStats) {
    el.textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  }
}

export async function loadCategories() {
  try {
    const cats = await api('/api/categories');
    const list = document.getElementById('cat-list');
    if (!cats.length) { list.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px">No categories</p>'; return; }
    let h = '';
    cats.forEach((c) => {
      h += '<div class="cat-item"><span class="cat-item-emoji cat-item-emoji-edit" data-cat="' + esc(c.name) + '" title="' + t('label_change_emoji') + '">' + esc(c.emoji) + '</span>'
        + '<input class="cat-item-label-input" data-cat-name="' + esc(c.name) + '" value="' + esc(c.label) + '" title="' + t('label_display_name') + '">'
        + '<span class="cat-item-key">' + esc(c.name) + '</span><span class="cat-item-count">' + c.count + ' prod.</span>'
        + '<button class="btn-sm btn-red" data-action="delete-cat" data-cat-name="' + esc(c.name) + '" data-cat-label="' + esc(c.label) + '" data-cat-count="' + c.count + '">&#128465;</button></div>';
    });
    list.innerHTML = h;
    // Attach change handlers to label inputs
    list.querySelectorAll('input.cat-item-label-input[data-cat-name]').forEach((inp) => {
      inp.addEventListener('change', () => {
        updateCategoryLabel(inp.dataset.catName, inp.value);
      });
    });
    // Attach click handlers to delete buttons
    list.querySelectorAll('[data-action="delete-cat"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        deleteCategory(btn.dataset.catName, btn.dataset.catLabel, parseInt(btn.dataset.catCount, 10));
      });
    });
    // Init emoji pickers on each category emoji
    list.querySelectorAll('.cat-item-emoji-edit').forEach((el) => {
      const catName = el.getAttribute('data-cat');
      initEmojiPicker(el, null, (emoji) => {
        updateCategoryEmoji(catName, emoji);
      });
    });
  } catch(e) {
    console.error(e);
    showToast(t('toast_load_error'), 'error');
  }
}

export async function updateCategoryLabel(name, val) {
  if (!val.trim()) { showToast(t('toast_display_name_empty'), 'error'); loadCategories(); return; }
  try {
    await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ label: val.trim() }) });
    showToast(t('toast_category_updated'), 'success');
    await fetchStats();
    updateStatsLine();
    refreshScopeSelect();
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function updateCategoryEmoji(name, emoji) {
  try {
    await api('/api/categories/' + encodeURIComponent(name), { method: 'PUT', body: JSON.stringify({ emoji: emoji }) });
    showToast(t('toast_category_updated'), 'success');
    await fetchStats();
    updateStatsLine();
    loadCategories();
    refreshScopeSelect();
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addCategory() {
  const name = document.getElementById('cat-name').value.trim();
  const emoji = document.getElementById('cat-emoji').value.trim() || '\u{1F4E6}';
  const label = document.getElementById('cat-label').value.trim();
  if (!name || !label) { showToast(t('toast_name_display_required'), 'error'); return; }
  try {
    const res = await api('/api/categories', { method: 'POST', body: JSON.stringify({ name: name, emoji: emoji, label: label }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('cat-name').value = '';
    document.getElementById('cat-emoji').value = '';
    document.getElementById('cat-label').value = '';
    resetEmojiPicker(document.getElementById('cat-emoji-trigger'));
    showToast(t('toast_category_added', { name: label }), 'success');
    await fetchStats();
    updateStatsLine();
    loadCategories();
    refreshScopeSelect();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deleteCategory(name, label, count) {
  try {
    if (!count) {
      // No products – show confirmation modal
      if (!await showConfirmModal('\u{1F5D1}', label, t('confirm_delete_category', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
      const res = await api('/api/categories/' + encodeURIComponent(name), { method: 'DELETE' });
      if (res.error) { showToast(res.error, 'error'); return; }
      showToast(t('toast_category_deleted', { name: label }), 'success');
      await fetchStats();
      updateStatsLine();
      loadCategories();
      refreshScopeSelect();
      return;
    }
    // Has products – show reassignment modal
    const cats = await api('/api/categories');
    const others = cats.filter((c) => c.name !== name);
    if (!others.length) { showToast(t('toast_cannot_delete_only_category'), 'error'); return; }
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg cat-move-modal-bg';

    const modal = document.createElement('div');
    modal.className = 'scan-modal cat-move-modal';
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.innerHTML = '&#128465;';
    modal.appendChild(iconDiv);
    const h3 = document.createElement('h3');
    h3.textContent = label;
    modal.appendChild(h3);
    const p = document.createElement('p');
    p.textContent = t('confirm_move_products', { count: count });
    modal.appendChild(p);

    const sel = document.createElement('select');
    sel.className = 'field-select cat-move-select';
    others.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.emoji + ' ' + c.label;
      sel.appendChild(opt);
    });
    modal.appendChild(sel);

    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'scan-modal-btn-register cat-move-confirm';
    confirmBtn.textContent = t('btn_move_and_delete');
    actions.appendChild(confirmBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel cat-move-cancel';
    cancelBtn.textContent = t('btn_cancel');
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);

    bg.appendChild(modal);
    document.body.appendChild(bg);
    upgradeSelect(sel);

    function close() { bg.remove(); }
    cancelBtn.onclick = close;
    bg.addEventListener('click', (e) => { if (e.target === bg) close(); });
    confirmBtn.onclick = async () => {
      const moveTo = sel.value;
      const target = others.find((c) => c.name === moveTo);
      try {
        const delRes = await api('/api/categories/' + encodeURIComponent(name), {
          method: 'DELETE',
          body: JSON.stringify({ move_to: moveTo })
        });
        if (delRes.error) { showToast(delRes.error, 'error'); return; }
        close();
        showToast(t('toast_category_moved_deleted', { count: count, target: target ? target.label : moveTo, name: label }), 'success');
        await fetchStats();
        updateStatsLine();
        loadCategories();
        refreshScopeSelect();
      } catch(e2) {
        console.error(e2);
        showToast(t('toast_network_error'), 'error');
      }
    };
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}
