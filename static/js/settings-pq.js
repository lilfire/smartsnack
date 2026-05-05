// ── Settings: Protein Quality ────────────────────────
import { api, esc, showConfirmModal, showToast } from './state.js';
import { t } from './i18n.js';

let pqData = [];

export async function loadPq() {
  try { pqData = await api('/api/protein-quality'); } catch(e) { pqData = []; showToast(t('toast_load_error'), 'error'); }
  renderPqTable();
}

export function renderPqTable() {
  const container = document.getElementById('pq-list');
  if (!container) return;
  if (!pqData.length) { container.innerHTML = '<p style="color:rgba(255,255,255,0.3);font-size:13px;text-align:center;padding:20px">No protein sources</p>'; return; }
  let h = '';
  pqData.forEach((row) => {
    h += '<div class="pq-card">'
      + '<div class="pq-card-top">'
      + '<input class="cat-item-label-input" id="pqe-label-' + row.id + '" value="' + esc(row.label || row.keywords[0]) + '" title="Name">'
      + '<span class="pq-badges"><span class="pq-badge"><span class="pq-badge-label">P </span>'
      + '<input class="pq-inline-num mono" id="pqe-pdcaas-' + row.id + '" type="number" step="0.01" min="0" max="1" value="' + row.pdcaas + '">'
      + '</span><span class="pq-badge"><span class="pq-badge-label">D </span>'
      + '<input class="pq-inline-num mono" id="pqe-diaas-' + row.id + '" type="number" step="0.01" min="0" max="1.2" value="' + row.diaas + '">'
      + '</span></span>'
      + '<button class="btn-sm btn-red" data-action="delete-pq" data-pq-id="' + row.id + '" data-pq-label="' + esc(row.label || row.keywords[0]) + '">&#128465;</button>'
      + '</div>'
      + '<input class="pq-kw-input" id="pqe-kw-' + row.id + '" value="' + esc(row.keywords.join(', ')) + '" placeholder="Keywords (comma separated)">'
      + '</div>';
  });
  container.innerHTML = h;
  // Attach autosave handlers — both 'change' and 'blur' so that programmatic
  // fills (e.g. Playwright .fill()) followed by a Tab keypress reliably trigger
  // the save even when the browser skips the 'change' event.
  pqData.forEach((row) => {
    const labelEl = document.getElementById('pqe-label-' + row.id);
    const pdcaasEl = document.getElementById('pqe-pdcaas-' + row.id);
    const diaasEl = document.getElementById('pqe-diaas-' + row.id);
    const kwEl = document.getElementById('pqe-kw-' + row.id);
    [labelEl, pdcaasEl, diaasEl, kwEl].forEach((el) => {
      if (el) {
        el.addEventListener('change', () => { autosavePq(row.id); });
        el.addEventListener('blur', () => { autosavePq(row.id); });
      }
    });
  });
  // Attach delete handlers
  container.querySelectorAll('[data-action="delete-pq"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      deletePq(parseInt(btn.dataset.pqId, 10), btn.dataset.pqLabel);
    });
  });
}

const _pqSaveTimers = {};
export function autosavePq(id) { clearTimeout(_pqSaveTimers[id]); _pqSaveTimers[id] = setTimeout(() => { savePqField(id); }, 400); }

export async function savePqField(id) {
  const label = document.getElementById('pqe-label-' + id);
  const kw = document.getElementById('pqe-kw-' + id);
  const pdcaas = document.getElementById('pqe-pdcaas-' + id);
  const diaas = document.getElementById('pqe-diaas-' + id);
  if (!label || !kw || !pdcaas || !diaas) return;
  const kwVal = kw.value.trim();
  const pdVal = parseFloat(pdcaas.value);
  const diVal = parseFloat(diaas.value);
  if (!kwVal || isNaN(pdVal) || isNaN(diVal)) return;
  const keywords = kwVal.split(',').map((k) => k.trim()).filter(Boolean);
  try {
    const res = await api('/api/protein-quality/' + id, { method: 'PUT', body: JSON.stringify({ label: label.value.trim(), keywords: keywords, pdcaas: pdVal, diaas: diVal }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    showToast(t('toast_updated'), 'success');
    const item = pqData.find((r) => r.id === id);
    if (item) { item.label = label.value.trim(); item.keywords = keywords; item.pdcaas = pdVal; item.diaas = diVal; }
  } catch(e) { console.error(e); showToast(t('toast_save_error'), 'error'); }
}

export async function addPq() {
  const label = document.getElementById('pq-add-label').value.trim();
  const kw = document.getElementById('pq-add-kw').value.trim();
  const pdcaas = parseFloat(document.getElementById('pq-add-pdcaas').value);
  const diaas = parseFloat(document.getElementById('pq-add-diaas').value);
  if (!kw || isNaN(pdcaas) || isNaN(diaas)) { showToast(t('toast_pq_keywords_required'), 'error'); return; }
  const keywords = kw.split(',').map((k) => k.trim()).filter(Boolean);
  try {
    const res = await api('/api/protein-quality', { method: 'POST', body: JSON.stringify({ label: label, keywords: keywords, pdcaas: pdcaas, diaas: diaas }) });
    if (res.error) { showToast(res.error, 'error'); return; }
    document.getElementById('pq-add-label').value = '';
    document.getElementById('pq-add-kw').value = '';
    document.getElementById('pq-add-pdcaas').value = '';
    document.getElementById('pq-add-diaas').value = '';
    showToast(t('toast_pq_added', { name: (label || keywords[0]) }), 'success');
    loadPq();
  } catch(e) {
    console.error(e);
    showToast(t('toast_network_error'), 'error');
  }
}

export async function deletePq(id, label) {
  if (!await showConfirmModal('\u{1F5D1}', label, t('confirm_delete_product', { name: label }), t('btn_delete'), t('btn_cancel'))) return;
  try {
    await api('/api/protein-quality/' + id, { method: 'DELETE' });
    showToast(t('toast_pq_deleted', { name: label }), 'success');
    loadPq();
  } catch(e) { console.error(e); showToast(t('toast_network_error'), 'error'); }
}
