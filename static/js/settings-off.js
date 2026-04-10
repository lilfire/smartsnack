// ── Settings: OpenFoodFacts Credentials and Bulk Refresh ──
import { api, showToast } from './state.js';
import { t } from './i18n.js';
import { loadData } from './products.js';

export async function loadOffCredentials() {
  try {
    const data = await api('/api/settings/off-credentials');
    const el = document.getElementById('off-user-id');
    if (el) el.value = data.off_user_id || '';
    const pw = document.getElementById('off-password');
    if (pw) pw.value = data.has_password ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : '';
  } catch(e) { showToast(t('toast_load_error'), 'error'); }
}

export async function saveOffCredentials() {
  const userId = (document.getElementById('off-user-id').value || '').trim();
  let pw = document.getElementById('off-password').value || '';
  if (pw === '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022') pw = '';
  const body = { off_user_id: userId };
  if (pw) body.off_password = pw;
  try {
    await api('/api/settings/off-credentials', { method: 'PUT', body: JSON.stringify(body) });
    showToast(t('toast_off_credentials_saved'), 'success');
  } catch(e) {
    const msg = e.message === 'encryption_not_configured'
      ? t('toast_encryption_not_configured')
      : t('toast_save_error');
    showToast(msg, 'error');
  }
}

// ── Bulk: Refresh all from OFF ───────────────────────
let _refreshEvtSource = null;

function _renderRefreshReport(report) {
  const container = document.getElementById('refresh-off-progress');
  if (!container) return;

  // Remove any previous report
  const prev = container.querySelector('.refresh-report');
  if (prev) prev.remove();

  const wrap = document.createElement('div');
  wrap.className = 'refresh-report';

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'refresh-report-toggle';
  toggleBtn.textContent = t('bulk_report_show', { count: report.length });
  wrap.appendChild(toggleBtn);

  const reasonKeys = {
    not_found: 'bulk_report_not_found',
    no_new_data: 'bulk_report_no_new_data',
    no_results: 'bulk_report_no_results',
    below_threshold: 'bulk_report_below_threshold',
  };

  function buildReportList() {
    const list = document.createElement('div');
    list.className = 'refresh-report-list';
    for (const item of report) {
      const row = document.createElement('div');
      row.className = 'refresh-report-row';

      const nameEl = document.createElement('span');
      nameEl.className = 'refresh-report-name';
      nameEl.textContent = item.name || item.ean || '—';
      nameEl.title = item.name || item.ean || '—';
      row.appendChild(nameEl);

      const badge = document.createElement('span');
      badge.className = 'refresh-report-badge ' + item.status;
      badge.textContent = t('bulk_report_' + item.status);
      row.appendChild(badge);

      const detail = document.createElement('span');
      detail.className = 'refresh-report-detail';
      if (item.status === 'updated' && item.fields) {
        detail.textContent = t('bulk_report_fields', { fields: item.fields.join(', ') });
      } else if (item.reason) {
        const key = reasonKeys[item.reason];
        let text = key ? t(key) : item.reason;
        if (item.detail) text += ' (' + item.detail + ')';
        detail.textContent = text;
      }
      detail.title = detail.textContent;
      row.appendChild(detail);

      list.appendChild(row);
    }
    return list;
  }

  function openReportModal() {
    const bg = document.createElement('div');
    bg.className = 'off-modal-bg';
    bg.id = 'refresh-report-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');

    const modal = document.createElement('div');
    modal.className = 'off-modal';

    const head = document.createElement('div');
    head.className = 'off-modal-head';
    const h3 = document.createElement('h3');
    h3.textContent = t('bulk_report_show', { count: report.length });
    head.appendChild(h3);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'off-modal-close';
    closeBtn.textContent = '\u00D7';
    closeBtn.setAttribute('aria-label', t('btn_close'));
    head.appendChild(closeBtn);
    modal.appendChild(head);

    const body = document.createElement('div');
    body.className = 'off-modal-body';
    body.appendChild(buildReportList());
    modal.appendChild(body);

    bg.appendChild(modal);
    document.body.appendChild(bg);
    document.body.style.overflow = 'hidden';

    function close() {
      document.removeEventListener('keydown', onKeyDown);
      bg.remove();
      document.body.style.overflow = '';
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close();
    }
    document.addEventListener('keydown', onKeyDown);
    closeBtn.addEventListener('click', close);
    bg.addEventListener('click', (e) => { if (e.target === bg) close(); });
  }

  toggleBtn.addEventListener('click', openReportModal);

  container.appendChild(wrap);
}

function _connectRefreshStream() {
  const btn = document.getElementById('btn-refresh-all-off');
  const progressWrap = document.getElementById('refresh-off-progress');
  const bar = document.getElementById('refresh-off-bar');
  const status = document.getElementById('refresh-off-status');

  if (btn) btn.disabled = true;
  if (progressWrap) progressWrap.style.display = '';

  if (_refreshEvtSource) _refreshEvtSource.close();
  _refreshEvtSource = new EventSource('/api/bulk/refresh-off/stream');

  _refreshEvtSource.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch(_) { return; }
    if (data.running && data.total > 0) {
      const pct = Math.round((data.current / data.total) * 100);
      if (bar) bar.style.width = pct + '%';
      const label = data.name || data.ean;
      if (status) status.textContent = t('bulk_refresh_off_progress', { current: data.current, total: data.total, name: label });
    }
    if (data.done) {
      _refreshEvtSource.close();
      _refreshEvtSource = null;
      if (bar) bar.style.width = '100%';
      const msg = t('bulk_refresh_off_result', { total: data.total, updated: data.updated, skipped: data.skipped, errors: data.errors });
      if (status) status.textContent = msg;
      showToast(msg, 'success');
      if (data.report) _renderRefreshReport(data.report);
      if (btn) btn.disabled = false;
      loadData();
    }
  };

  _refreshEvtSource.onerror = () => {
    _refreshEvtSource.close();
    _refreshEvtSource = null;
    if (btn) btn.disabled = false;
    if (progressWrap) progressWrap.style.display = 'none';
  };
}

export async function checkRefreshStatus() {
  try {
    const status = await api('/api/bulk/refresh-off/status');
    if (status.running) _connectRefreshStream();
  } catch(e) { /* ignore */ }
}

function _showRefreshOffModal() {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '🔄';
    modal.appendChild(iconDiv);

    const h3 = document.createElement('h3');
    h3.textContent = t('bulk_refresh_off_title');
    modal.appendChild(h3);

    const pEl = document.createElement('p');
    pEl.textContent = t('bulk_refresh_off_confirm');
    modal.appendChild(pEl);

    // Options section
    const opts = document.createElement('div');
    opts.className = 'refresh-off-options';

    const cbLabel = document.createElement('label');
    cbLabel.className = 'refresh-off-cb-label';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    const cbText = document.createElement('span');
    cbText.textContent = t('bulk_refresh_off_search_missing');
    cbLabel.appendChild(cb);
    cbLabel.appendChild(cbText);
    opts.appendChild(cbLabel);

    const sliders = document.createElement('div');
    sliders.className = 'refresh-off-sliders';
    sliders.style.display = 'none';

    function makeSlider(labelKey, defaultVal) {
      const row = document.createElement('div');
      row.className = 'refresh-off-range-row';
      const lbl = document.createElement('label');
      lbl.className = 'form-sub';
      lbl.textContent = t(labelKey);
      const range = document.createElement('input');
      range.type = 'range';
      range.min = '0';
      range.max = '100';
      range.value = String(defaultVal);
      const val = document.createElement('span');
      val.className = 'refresh-off-range-val';
      val.textContent = String(defaultVal);
      range.addEventListener('input', () => { val.textContent = range.value; });
      row.appendChild(lbl);
      row.appendChild(range);
      row.appendChild(val);
      sliders.appendChild(row);
      return range;
    }

    const certSlider = makeSlider('bulk_refresh_off_min_certainty', 100);
    const compSlider = makeSlider('bulk_refresh_off_min_completeness', 75);
    opts.appendChild(sliders);
    modal.appendChild(opts);

    cb.addEventListener('change', () => {
      sliders.style.display = cb.checked ? '' : 'none';
    });

    // Actions
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const yesBtn = document.createElement('button');
    yesBtn.className = 'scan-modal-btn-register confirm-yes';
    yesBtn.textContent = t('btn_start');
    actions.appendChild(yesBtn);
    const noBtn = document.createElement('button');
    noBtn.className = 'scan-modal-btn-cancel confirm-no';
    noBtn.textContent = t('btn_cancel');
    actions.appendChild(noBtn);
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
    noBtn.onclick = () => { close(null); };
    yesBtn.onclick = () => {
      close({
        searchMissing: cb.checked,
        minCertainty: parseInt(certSlider.value, 10),
        minCompleteness: parseInt(compSlider.value, 10),
      });
    };
    bg.addEventListener('click', (e) => { if (e.target === bg) close(null); });
    yesBtn.focus();
  });
}

// ── OFF Language Priority ────────────────────────────
let _offLangPriority = [];
let _offAllLangs = [];

function _renderOffLangPriority() {
  const list = document.getElementById('off-lang-priority-list');
  const addSelect = document.getElementById('off-lang-add-select');
  if (!list) return;

  list.innerHTML = '';
  _offLangPriority.forEach((code, idx) => {
    const item = document.createElement('div');
    item.className = 'off-lang-item';

    const label = document.createElement('span');
    label.className = 'off-lang-code';
    label.textContent = code;
    item.appendChild(label);

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'btn-sm';
    upBtn.textContent = '↑';
    upBtn.setAttribute('aria-label', t('off_lang_move_up'));
    upBtn.disabled = idx === 0;
    upBtn.addEventListener('click', () => {
      _offLangPriority.splice(idx - 1, 0, _offLangPriority.splice(idx, 1)[0]);
      _renderOffLangPriority();
      _saveOffLangPriority();
    });
    item.appendChild(upBtn);

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'btn-sm';
    downBtn.textContent = '↓';
    downBtn.setAttribute('aria-label', t('off_lang_move_down'));
    downBtn.disabled = idx === _offLangPriority.length - 1;
    downBtn.addEventListener('click', () => {
      _offLangPriority.splice(idx + 1, 0, _offLangPriority.splice(idx, 1)[0]);
      _renderOffLangPriority();
      _saveOffLangPriority();
    });
    item.appendChild(downBtn);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn-sm btn-red';
    removeBtn.textContent = t('off_lang_remove');
    removeBtn.disabled = _offLangPriority.length === 1;
    removeBtn.addEventListener('click', () => {
      _offLangPriority.splice(idx, 1);
      _renderOffLangPriority();
      _saveOffLangPriority();
    });
    item.appendChild(removeBtn);

    list.appendChild(item);
  });

  if (addSelect) {
    addSelect.innerHTML = '';
    const available = _offAllLangs.filter((l) => !_offLangPriority.includes(l.code));
    available.forEach((l) => {
      const opt = document.createElement('option');
      opt.value = l.code;
      opt.textContent = l.name || l.code;
      addSelect.appendChild(opt);
    });
    const addBtn = document.getElementById('off-lang-add-btn');
    if (addBtn) addBtn.disabled = available.length === 0;
  }
}

async function _saveOffLangPriority() {
  try {
    await api('/api/settings/off-language-priority', {
      method: 'PUT',
      body: JSON.stringify({ languages: _offLangPriority }),
    });
    showToast(t('toast_off_lang_priority_saved'), 'success');
  } catch(e) {
    showToast(t('toast_save_error'), 'error');
  }
}

export async function loadOffLanguagePriority() {
  const list = document.getElementById('off-lang-priority-list');
  if (!list) return;
  try {
    const [priority, langs] = await Promise.all([
      api('/api/settings/off-language-priority'),
      api('/api/settings/off-languages'),
    ]);
    _offLangPriority = priority.languages || [];
    _offAllLangs = langs.languages || [];
    _renderOffLangPriority();

    const addBtn = document.getElementById('off-lang-add-btn');
    if (addBtn && !addBtn.dataset.bound) {
      addBtn.dataset.bound = '1';
      addBtn.addEventListener('click', () => {
        const addSelect = document.getElementById('off-lang-add-select');
        if (!addSelect || !addSelect.value) return;
        _offLangPriority.push(addSelect.value);
        _renderOffLangPriority();
        _saveOffLangPriority();
      });
    }
  } catch(e) {
    showToast(t('toast_load_error'), 'error');
  }
}

export async function refreshAllFromOff() {
  const opts = await _showRefreshOffModal();
  if (!opts) return;
  const bar = document.getElementById('refresh-off-bar');
  if (bar) bar.style.width = '0%';
  // Clear previous report
  const prevReport = document.querySelector('.refresh-report');
  if (prevReport) prevReport.remove();
  try {
    const body = {};
    if (opts.searchMissing) {
      body.search_missing = true;
      body.min_certainty = opts.minCertainty;
      body.min_completeness = opts.minCompleteness;
    }
    const res = await api('/api/bulk/refresh-off/start', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (res.error === 'already_running') {
      _connectRefreshStream();
      return;
    }
    if (res.error) { showToast(res.error, 'error'); return; }
    _connectRefreshStream();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}
