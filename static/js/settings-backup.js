// ── Settings: Backup, Restore, and Import ───────────
import { state, api, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';
import { loadData } from './products.js';

export function downloadBackup() {
  const apiKey = window.SMARTSNACK_API_KEY;
  const url = apiKey ? '/api/backup?api_key=' + encodeURIComponent(apiKey) : '/api/backup';
  window.location.href = url;
  showToast(t('toast_backup_downloaded'), 'success');
}

export async function handleRestore(input) {
  if (!input.files.length) return;
  if (!await showConfirmModal('\u26A0', t('restore_title'), t('restore_confirm'), t('btn_restore'), t('btn_cancel'))) { input.value = ''; return; }
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const res = await api('/api/restore', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else {
        state.imageCache = {};
        showToast(res.message, 'success');
        loadData();
        if (state.currentView === 'settings') {
          const { loadSettings } = await import('./settings-weights.js');
          loadSettings();
        }
      }
    } catch(err) { showToast(err instanceof SyntaxError ? t('toast_invalid_file') : err.message, 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

function _buildRadioGroup(name, options, defaultValue) {
  const wrap = document.createElement('div');
  wrap.className = 'import-dup-radios';
  for (const opt of options) {
    const label = document.createElement('label');
    label.className = 'import-dup-radio-label';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = name;
    input.value = opt.value;
    if (opt.value === defaultValue) input.checked = true;
    label.appendChild(input);
    const span = document.createElement('span');
    span.textContent = opt.label;
    label.appendChild(span);
    wrap.appendChild(label);
  }
  return wrap;
}

function showImportDuplicateDialog() {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal import-dup-modal';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '\u2699\uFE0F';
    modal.appendChild(iconDiv);

    const h3 = document.createElement('h3');
    h3.textContent = t('import_dup_title');
    modal.appendChild(h3);

    const desc = document.createElement('p');
    desc.className = 'import-dup-desc';
    desc.textContent = t('import_dup_desc');
    modal.appendChild(desc);

    // Match criteria section
    const matchSection = document.createElement('div');
    matchSection.className = 'import-dup-section';
    const matchLabel = document.createElement('div');
    matchLabel.className = 'import-dup-section-label';
    matchLabel.textContent = t('import_dup_match_label');
    matchSection.appendChild(matchLabel);
    matchSection.appendChild(_buildRadioGroup('match_criteria', [
      { value: 'ean', label: t('label_ean') },
      { value: 'name', label: t('import_dup_match_name') },
      { value: 'both', label: t('import_dup_match_both') },
    ], 'both'));
    modal.appendChild(matchSection);

    // Action section
    const actionSection = document.createElement('div');
    actionSection.className = 'import-dup-section';
    const actionLabel = document.createElement('div');
    actionLabel.className = 'import-dup-section-label';
    actionLabel.textContent = t('import_dup_action_label');
    actionSection.appendChild(actionLabel);
    actionSection.appendChild(_buildRadioGroup('on_duplicate', [
      { value: 'skip', label: t('import_dup_action_skip') },
      { value: 'overwrite', label: t('import_dup_action_overwrite') },
      { value: 'merge', label: t('import_dup_action_merge') },
      { value: 'allow_duplicate', label: t('import_dup_action_allow') },
    ], 'skip'));
    modal.appendChild(actionSection);

    // Merge rules sub-section (shown only when "merge" selected)
    const mergeSection = document.createElement('div');
    mergeSection.className = 'import-dup-section import-dup-merge-rules';
    mergeSection.style.display = 'none';

    const mergeRulesTitle = document.createElement('div');
    mergeRulesTitle.className = 'import-dup-section-label';
    mergeRulesTitle.textContent = t('import_dup_merge_winner_title');
    mergeSection.appendChild(mergeRulesTitle);

    const rulesList = document.createElement('ul');
    rulesList.className = 'import-dup-merge-rules-list';
    const rules = [
      t('import_dup_merge_rule_one_synced'),
      t('import_dup_merge_rule_both_synced'),
      t('import_dup_merge_rule_neither_synced'),
    ];
    rules.forEach(r => {
      const li = document.createElement('li');
      li.innerHTML = r;
      rulesList.appendChild(li);
    });
    mergeSection.appendChild(rulesList);

    const mergeNote = document.createElement('div');
    mergeNote.className = 'import-dup-merge-note';
    mergeNote.textContent = t('import_dup_merge_single_value_note');
    mergeSection.appendChild(mergeNote);

    const mergePriorityLabel = document.createElement('div');
    mergePriorityLabel.className = 'import-dup-section-label';
    mergePriorityLabel.style.marginTop = '10px';
    mergePriorityLabel.textContent = t('import_dup_merge_priority_label');
    mergeSection.appendChild(mergePriorityLabel);
    mergeSection.appendChild(_buildRadioGroup('merge_priority', [
      { value: 'keep_existing', label: t('import_dup_merge_keep_existing') },
      { value: 'use_imported', label: t('import_dup_merge_use_imported') },
    ], 'keep_existing'));
    modal.appendChild(mergeSection);

    // Toggle merge rules visibility based on action selection
    actionSection.addEventListener('change', () => {
      const sel = modal.querySelector('input[name="on_duplicate"]:checked');
      mergeSection.style.display = sel && sel.value === 'merge' ? '' : 'none';
    });

    // Buttons
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const startBtn = document.createElement('button');
    startBtn.className = 'scan-modal-btn-register';
    startBtn.textContent = t('import_dup_start');
    actions.appendChild(startBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel';
    cancelBtn.textContent = t('btn_cancel');
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);

    bg.appendChild(modal);
    document.body.appendChild(bg);

    function close(val) {
      document.removeEventListener('keydown', onKeyDown);
      bg.remove();
      resolve(val);
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close(null);
    }
    document.addEventListener('keydown', onKeyDown);
    bg.addEventListener('click', (e) => { if (e.target === bg) close(null); });
    cancelBtn.onclick = () => close(null);
    startBtn.onclick = () => {
      const mc = modal.querySelector('input[name="match_criteria"]:checked');
      const od = modal.querySelector('input[name="on_duplicate"]:checked');
      const mp = modal.querySelector('input[name="merge_priority"]:checked');
      close({
        match_criteria: mc ? mc.value : 'both',
        on_duplicate: od ? od.value : 'skip',
        merge_priority: mp ? mp.value : 'keep_existing',
      });
    };
    startBtn.focus();
  });
}

export function handleImport(input) {
  if (!input.files.length) return;
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const dupSettings = await showImportDuplicateDialog();
      if (!dupSettings) { input.value = ''; return; }
      data.match_criteria = dupSettings.match_criteria;
      data.on_duplicate = dupSettings.on_duplicate;
      data.merge_priority = dupSettings.merge_priority;
      const res = await api('/api/import', { method: 'POST', body: JSON.stringify(data) });
      if (res.error) { showToast(res.error, 'error'); }
      else {
        state.imageCache = {};
        showToast(res.message, 'success');
        loadData();
        if (state.currentView === 'settings') {
          const { loadSettings } = await import('./settings-weights.js');
          loadSettings();
        }
      }
    } catch(err) { showToast(t('toast_invalid_file'), 'error'); }
    input.value = '';
  };
  reader.readAsText(input.files[0]);
}

// ── Collapsible settings sections ───────────────────
export function toggleSettingsSection(header) {
  const body = header.nextElementSibling;
  if (!body) return;
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : '';
  header.classList.toggle('open', !isOpen);
  header.setAttribute('aria-expanded', String(!isOpen));
}

// Drag-and-drop for restore
export function initRestoreDragDrop() {
  const drop = document.getElementById('restore-drop');
  if (!drop) return;
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => { drop.classList.remove('dragover'); });
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      const fi = { files: e.dataTransfer.files };
      Object.defineProperty(fi, 'value', { set() {}, get() { return ''; } });
      handleRestore(fi);
    }
  });
}

// ── Bulk: Estimate PQ for all ────────────────────────
export async function estimateAllPq() {
  const btn = document.getElementById('btn-estimate-all-pq');
  const status = document.getElementById('estimate-pq-status');
  if (btn) btn.disabled = true;
  if (status) { status.style.display = ''; status.textContent = t('bulk_running'); }
  try {
    const res = await api('/api/bulk/estimate-pq', { method: 'POST' });
    if (res.error) { showToast(res.error, 'error'); return; }
    const msg = t('bulk_estimate_pq_result', { total: res.total, updated: res.updated, skipped: res.skipped });
    if (status) status.textContent = msg;
    showToast(msg, 'success');
    loadData();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
    if (status) status.style.display = 'none';
  } finally {
    if (btn) btn.disabled = false;
  }
}
