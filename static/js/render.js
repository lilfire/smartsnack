// ── Render ──────────────────────────────────────────
import { state, esc, safeDataUri, catEmoji, catLabel, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import { applySorting, sortIndicator } from './filters.js';
import { loadProductImage } from './images.js';
import { SCORE_COLORS, SCORE_CFG_MAP, weightData } from './settings-weights.js';
import { isValidEan } from './off-utils.js';

let _resultsAbort = null;
const _VOLUME_LABELS = { 1: 'volume_low', 2: 'volume_medium', 3: 'volume_high' };
function volumeLabel(val) { return _VOLUME_LABELS[val] ? t(_VOLUME_LABELS[val]) : val; }

// Flag definitions loaded dynamically from API
let _flagConfig = {};

export async function loadFlagConfig() {
  try {
    _flagConfig = await (await fetch('/api/flag-config')).json();
  } catch(e) { console.error('Failed to load flag config', e); }
}

export function getFlagConfig() { return _flagConfig; }

function _getUserFlags() {
  return Object.keys(_flagConfig).filter(f => _flagConfig[f].type === 'user');
}

export function renderNutriTable(p) {
  const rows = [
    [t('nutri_energy') + ' (kcal)', p.kcal, 'kcal'],
    [t('nutri_energy') + ' (kJ)', p.energy_kj, 'kJ'],
    [t('nutri_fat'), p.fat, 'g'],
    ['  ' + t('nutri_saturated'), p.saturated_fat, 'g', true],
    [t('nutri_carbs'), p.carbs, 'g'],
    ['  ' + t('nutri_sugar'), p.sugar, 'g', true],
    [t('nutri_protein'), p.protein, 'g'],
    [t('nutri_fiber'), p.fiber, 'g'],
    [t('nutri_salt'), p.salt, 'g'],
  ];
  let h = '<table class="nutri-table">';
  rows.forEach((r) => {
    const isSub = r[3];
    const val = r[1];
    const display = (val != null) ? parseFloat(val).toFixed(r[2] === 'g' ? 1 : 0) + ' ' + r[2] : '-';
    h += '<tr' + (isSub ? ' class="sub"' : '') + '><td>' + r[0] + '</td><td>' + display + '</td></tr>';
  });
  if (p.est_pdcaas || p.est_diaas) {
    if (p.est_pdcaas) h += '<tr><td style="color:#00e5cc">PDCAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00e5cc;font-family:\'Space Mono\',monospace">' + parseFloat(p.est_pdcaas).toFixed(2) + '</td></tr>';
    if (p.est_diaas) h += '<tr><td style="color:#00bfff">DIAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00bfff;font-family:\'Space Mono\',monospace">' + parseFloat(p.est_diaas).toFixed(2) + '</td></tr>';
  }
  h += '</table>';
  const extras = [];
  if (p.weight) extras.push(t('extra_weight', { val: p.weight }));
  if (p.portion) extras.push(t('extra_portion', { val: p.portion }));
  if (p.price) extras.push(t('extra_price', { val: p.price }));
  if (p.volume) extras.push(t('extra_volume', { val: volumeLabel(p.volume) }));
  if (extras.length) h += '<div style="margin-top:8px;font-size:11px;color:rgba(255,255,255,0.3)">' + extras.join(' \u00B7 ') + '</div>';
  return h;
}

// ── Dynamic column helpers ──────────────────────────
const COL_UNITS = { kcal: '', energy_kj: '', carbs: 'g', sugar: 'g', fat: 'g', saturated_fat: 'g', protein: 'g', fiber: 'g', salt: 'g', taste_score: '', volume: '', price: 'kr', pct_protein_cal: '%', pct_fat_cal: '%', pct_carb_cal: '%' };

export function fmtCell(field, val) {
  if (val == null) return '-';
  if (field === 'volume') return volumeLabel(val);
  if (field === 'taste_score') {
    const clamped = Math.max(0, Math.min(6, Math.round(val)));
    const st = '\u2605'.repeat(clamped);
    const dm = '\u2605'.repeat(6 - clamped);
    return '<span class="stars">' + st + '<span class="stars-dim">' + dm + '</span></span>';
  }
  if (field === 'price') return val ? Number(val).toFixed(0) + 'kr' : '-';
  if (field === 'pct_protein_cal' || field === 'pct_fat_cal' || field === 'pct_carb_cal') return parseFloat(val).toFixed(1) + '%';
  const u = COL_UNITS[field] || '';
  if (field === 'salt') return Number(val).toFixed(2) + u;
  if (field === 'kcal' || field === 'energy_kj') return Math.round(Number(val)) + u;
  return parseFloat(val).toFixed(1) + u;
}

export function getActiveCols() {
  const cols = [{ key: 'name', label: t('col_product'), width: '2.4fr' }];
  const enabled = weightData.filter((w) => w.enabled);
  const isMobile = window.innerWidth < 640;
  if (!isMobile) {
    enabled.forEach((w) => { cols.push({ key: w.field, label: w.label, width: '0.7fr' }); });
  }
  cols.push({ key: 'total_score', label: t('col_score'), width: '0.9fr' });
  return cols;
}

export function getGridTemplate(cols) {
  return cols.map((c) => c.width).join(' ');
}

// Re-render on resize (debounced)
let _resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(() => {
    if (state.editingId === null && state.currentView === 'search') {
      import('./filters.js').then((mod) => { mod.rerender(); });
    }
  }, 200);
});

export function renderResults(results, search) {
  state.cachedResults = results;
  document.getElementById('result-count').textContent = search
    ? (results.length !== 1 ? t('result_count_search_plural', { count: results.length, query: search }) : t('result_count_search', { count: results.length, query: search }))
    : (results.length !== 1 ? t('result_count_plural', { count: results.length }) : t('result_count', { count: results.length }));
  const container = document.getElementById('results-container');
  if (!results.length) {
    container.innerHTML = '<div class="empty"><div class="empty-icon">\u{1F50D}</div><p>' + t('no_products_found') + '</p>'
      + (search ? '<button class="btn-create-from-search" data-action="create-from-search">' + t('create_product') + '</button>' : '')
      + '</div>';
    if (search) {
      const createBtn = container.querySelector('[data-action="create-from-search"]');
      if (createBtn) {
        createBtn.addEventListener('click', () => {
          if (isValidEan(search)) {
            document.getElementById('f-ean').value = search;
          } else {
            document.getElementById('f-name').value = search;
          }
          window.switchView('register');
        });
      }
    }
    return;
  }
  const sorted = applySorting(results);
  const cols = getActiveCols();
  const gridTpl = getGridTemplate(cols);
  let h = '<div class="table-wrap" role="table"><div class="table-head" role="row" style="grid-template-columns:' + gridTpl + '">';
  cols.forEach((c, i) => {
    h += '<span class="th-sort' + (state.sortCol === c.key ? ' th-active' : '') + '" data-action="sort" data-col="' + esc(c.key) + '" tabindex="0" role="columnheader" aria-sort="' + (state.sortCol === c.key ? (state.sortDir === 'asc' ? 'ascending' : 'descending') : 'none') + '"' + (i > 0 ? ' style="text-align:right"' : '') + '>' + esc(c.label) + ' ' + sortIndicator(c.key) + '</span>';
  });
  h += '</div>';
  sorted.forEach((p) => {
    const hasImg = p.has_image;
    const thumbHtml = '<div class="prod-thumb-wrap">' + (hasImg ? '<img class="prod-thumb" id="thumb-' + p.id + '" src="" alt="' + esc(p.name) + '">' : '') + '</div>';
    const eanCount = p.ean_count || 1;
    const eanSuffix = eanCount > 1 ? '<span class="ean-count-suffix"> (+' + (eanCount - 1) + ')</span>' : '';
    const eanHtml = p.ean ? '<span class="prod-ean">EAN: ' + esc(p.ean) + eanSuffix + '</span>' : '';
    const brandHtml = p.brand ? '<span class="prod-brand">' + esc(p.brand) + '</span>' : '';
    let prodName;
    if (p.brand && p.name.toLowerCase().startsWith(p.brand.toLowerCase())) {
      prodName = p.name.substring(p.brand.length).replace(/^\s+/, '');
    } else {
      prodName = p.name;
    }
    const nameHtml = '<span class="prod-name">' + esc(prodName) + '</span>';
    h += '<div class="table-row" data-product-id="' + p.id + '" style="grid-template-columns:' + gridTpl + '" data-action="toggle-expand" tabindex="0" role="row" aria-label="' + esc(p.name) + '">'
      + '<div><div style="display:flex;align-items:flex-start;gap:8px"><div class="prod-cat"><span style="font-size:14px">' + esc(catEmoji(p.type)) + '</span><span class="prod-cat-label">' + esc(catLabel(p.type)) + '</span></div>' + thumbHtml + '<div class="prod-info">' + brandHtml + nameHtml
      + '<div class="prod-meta">' + eanHtml
      + '<span class="completeness-badge" style="color:' + (p.completeness === 100 ? '#4ecdc4' : p.completeness >= 50 ? 'rgba(78,205,196,0.6)' : 'rgba(255,255,255,0.2)') + '">' + (p.completeness != null ? p.completeness + '%' : '') + '</span>'
      + '</div></div></div></div>';
    for (let ci = 1; ci < cols.length; ci++) {
      const c = cols[ci];
      if (c.key === 'total_score') {
        const scoreDisplay = (p.total_score != null) ? Number(p.total_score).toFixed(1) : '-';
        h += '<span class="cell-score">' + scoreDisplay + (p.has_missing_scores ? '<span style="color:#f5a623;margin-left:1px" title="Score based on incomplete data \u2014 some values are 0 or missing">*</span>' : '') + '</span>';
      } else {
        h += '<span class="cell-right">' + fmtCell(c.key, p[c.key]) + '</span>';
      }
    }
    h += '</div>';
    if (state.expandedId === p.id) {
      h += '<div class="expanded"><div class="expanded-top">'
        + '<div class="expanded-img-area" data-action="trigger-image" data-id="' + p.id + '">'
        + '<div id="prod-img-wrap-' + p.id + '">' + (hasImg ? '<img id="prod-img-' + p.id + '" src="" alt="' + esc(p.name) + '" style="width:100%;height:100%;object-fit:cover">' : '<div class="expanded-img-placeholder">\u{1F4F7}</div>') + '</div>'
        + '<div class="expanded-img-overlay">' + (hasImg ? t('expanded_change_image') : t('expanded_upload_image')) + '</div></div>'
        + '<div class="expanded-right">';
      h += '<p class="expanded-title">' + t('expanded_score_breakdown') + '</p><div class="score-grid">';
      const sc = p.scores || {};
      Object.keys(sc).forEach((sf) => {
        const scfg = SCORE_CFG_MAP[sf];
        if (!scfg) return;
        const sv = sc[sf];
        const pct = Math.min(sv, 100);
        const col = SCORE_COLORS[sf] || '#888';
        h += '<div><div class="score-label">' + esc(scfg.label) + '</div><div class="score-bar-bg"><div class="score-bar-fill" style="width:' + pct + '%;background:' + col + '"></div></div><span class="score-val">' + Number(sv).toFixed(1) + '</span></div>';
      });
      if (!Object.keys(sc).length) h += '<div style="color:rgba(255,255,255,0.3);font-size:12px;grid-column:1/-1">' + t('expanded_no_weights') + '</div>';
      h += '</div>';
      if (p.has_missing_scores && p.missing_fields && p.missing_fields.length) {
        const mLabels = p.missing_fields.map((f) => { const c = SCORE_CFG_MAP[f]; return c ? c.label : f; }).join(', ');
        h += '<div style="margin-top:8px;padding:8px 10px;border-radius:7px;background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.18);font-size:11px;color:rgba(245,166,35,0.85)"><span style="margin-right:4px">\u26A0</span> ' + t('expanded_missing_data', { fields: esc(mLabels) }) + '</div>';
      }
      // Completeness bar
      {
        const compPct = p.completeness != null ? p.completeness : 0;
        const compColor = compPct === 100 ? '#4ecdc4' : compPct >= 50 ? 'rgba(78,205,196,0.7)' : 'rgba(255,140,0,0.7)';
        h += '<div class="completeness-section">'
          + '<div class="completeness-header"><span class="completeness-label">' + t('completeness_label') + '</span>'
          + '<span class="completeness-pct" style="color:' + compColor + '">' + compPct + '%</span></div>'
          + '<div class="completeness-bar-bg"><div class="completeness-bar-fill" style="width:' + compPct + '%;background:' + compColor + '"></div></div>'
          + '</div>';
      }
      // Nutrition table
      h += '<p class="nutri-section-title">' + t('section_nutrition') + '</p>';
      h += renderNutriTable(p);
      if (p.brand || p.stores || p.ingredients || p.taste_note || p.taste_score != null) {
        h += '<p class="nutri-section-title">' + t('expanded_product_info') + '</p>';
        if (p.brand) h += '<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">' + t('expanded_label_brand') + '</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">' + esc(p.brand) + '</span></div>';
        if (p.stores) h += '<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">' + t('expanded_label_stores') + '</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">' + esc(p.stores) + '</span></div>';
        if (p.ingredients) h += '<div style="margin-top:4px"><span style="font-size:10px;color:rgba(255,255,255,0.35);display:block;margin-bottom:3px">' + t('expanded_label_ingredients') + '</span><span style="font-size:11px;color:rgba(255,255,255,0.5);line-height:1.5">' + esc(p.ingredients) + '</span></div>';
        if (p.taste_score != null) h += '<div style="margin-top:4px"><span style="font-size:10px;color:rgba(255,255,255,0.35);display:block;margin-bottom:3px">' + t('expanded_label_taste_score') + '</span><span style="font-size:14px;color:#E8B84B;font-weight:700;font-family:\'Space Mono\',monospace">' + Number(p.taste_score).toFixed(1) + ' / 6</span></div>';
        if (p.taste_note) h += '<div style="margin-top:4px"><span style="font-size:10px;color:rgba(255,255,255,0.35);display:block;margin-bottom:3px">' + t('expanded_label_taste_note') + '</span><span style="font-size:11px;color:rgba(255,255,255,0.5);line-height:1.5">' + esc(p.taste_note) + '</span></div>';
      }
      // Flag badges
      const flags = p.flags || [];
      if (flags.length) {
        h += '<div class="product-flags">';
        flags.forEach(f => {
          const cfg = _flagConfig[f];
          if (!cfg) return;
          h += '<span class="flag-badge flag-' + cfg.type + '">' + esc(cfg.label || t(cfg.labelKey)) + '</span>';
        });
        h += '</div>';
      }
      if (p.tags && p.tags.length > 0) {
        h += '<div class="product-tags">';
        for (const tag of p.tags) {
          h += '<span class="tag-badge">' + esc(tag) + '</span>';
        }
        h += '</div>';
      }
      h += '</div></div>';

      if (state.editingId === p.id) {
        let opts = '';
        state.categories.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach((c) => { opts += '<option value="' + esc(c.name) + '"' + (c.name === p.type ? ' selected' : '') + '>' + esc(c.emoji) + ' ' + esc(c.label) + '</option>'; });
        opts += '<option value=""' + (!p.type ? ' selected' : '') + '>\u{1F4E6} ' + esc(t('uncategorized')) + '</option>';
        const ev = (v) => v == null ? '' : v;
        h += '<div class="edit-form"><div class="edit-grid">'
          + '<div class="edit-grid-2"><label>' + t('label_name') + '</label><input id="ed-name" value="' + esc(p.name) + '"></div>'
          + (() => {
              const isSynced = (p.flags || []).includes('is_synced_with_off');
              return '<div class="edit-grid-2">'
                + '<label>' + t('label_eans') + '</label>'
                + '<input type="hidden" id="ed-ean" value="' + esc(p.ean || '') + '">'
                + '<div id="ean-manager-' + p.id + '" class="ean-manager"><div class="ean-manager-loading">\u2026</div></div>'
                + '<div class="ean-row" style="margin-top:6px">'
                + (isSynced ? '<button class="btn-ean-unlock" data-action="unlock-ean" data-id="' + p.id + '" title="' + t('btn_unlock_ean_title') + '">&#128275;</button>' : '')
                + '<button class="btn-scan" data-action="open-scanner" data-id="' + p.id + '" title="' + t('btn_scan_title') + '">&#128247;</button>'
                + '<button class="btn-off" id="ed-off-btn" ' + (!(isValidEan(p.ean) || p.name.trim()) ? 'disabled' : '') + ' data-action="lookup-off" data-id="' + p.id + '"><span class="off-spin"></span><span class="off-label">' + t('btn_fetch') + '</span></button>'
                + '</div>'
                + '</div>';
            })()
          + '<div><label>' + t('label_category') + '</label><select class="field-select" id="ed-type">' + opts + '</select></div>'
          + '<div><label>' + t('label_brand') + '</label><input id="ed-brand" value="' + esc(p.brand || '') + '"></div>'
          + '<div><label>' + t('label_stores') + '</label><input id="ed-stores" value="' + esc(p.stores || '') + '"></div>'
          + '<div class="edit-grid-2"><div style="display:flex;align-items:center;justify-content:space-between"><label>' + t('label_ingredients') + '</label><button type="button" class="btn-ocr" id="ed-ocr-btn" onclick="scanIngredients(\'ed\')" title="' + esc(t('btn_ocr_title')) + '"><span class="ocr-spin"></span><span class="ocr-label">&#128247;</span></button></div><textarea id="ed-ingredients" rows="2" style="resize:vertical;min-height:50px;width:100%;padding:7px 9px;border-radius:7px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);color:#e8e6e3;font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none">' + esc(p.ingredients || '') + '</textarea></div>'
        h += '<div><label>' + t('label_kcal') + '</label><input type="number" step="1" id="ed-kcal" value="' + ev(p.kcal) + '"></div>'
          + '<div><label>' + t('edit_label_energy_kj') + '</label><input type="number" step="1" id="ed-energy_kj" value="' + ev(p.energy_kj) + '"></div>'
          + '<div><label>' + t('label_fat') + '</label><input type="number" step="0.1" id="ed-fat" value="' + ev(p.fat) + '"></div>'
          + '<div><label>' + t('edit_label_saturated_fat') + '</label><input type="number" step="0.1" id="ed-saturated_fat" value="' + ev(p.saturated_fat) + '"></div>'
          + '<div><label>' + t('label_carbs') + '</label><input type="number" step="0.1" id="ed-carbs" value="' + ev(p.carbs) + '"></div>'
          + '<div><label>' + t('label_sugar') + '</label><input type="number" step="0.1" id="ed-sugar" value="' + ev(p.sugar) + '"></div>'
          + '<div><label>' + t('label_protein') + '</label><input type="number" step="0.1" id="ed-protein" value="' + ev(p.protein) + '"></div>'
          + '<div><label>' + t('label_fiber') + '</label><input type="number" step="0.1" id="ed-fiber" value="' + ev(p.fiber) + '"></div>'
          + '<div><label>' + t('label_salt') + '</label><input type="number" step="0.01" id="ed-salt" value="' + ev(p.salt) + '"></div>'
          + '<div><label>' + t('label_weight') + '</label><input type="number" step="1" id="ed-weight" value="' + ev(p.weight) + '"></div>'
          + '<div><label>' + t('label_portion') + '</label><input type="number" step="1" id="ed-portion" value="' + ev(p.portion) + '"></div>'
          + '<div><label>' + t('label_volume') + '</label><select class="field-select" id="ed-volume"><option value="">-</option><option value="1"' + (p.volume === 1 ? ' selected' : '') + '>' + t('volume_low') + '</option><option value="2"' + (p.volume === 2 ? ' selected' : '') + '>' + t('volume_medium') + '</option><option value="3"' + (p.volume === 3 ? ' selected' : '') + '>' + t('volume_high') + '</option></select></div>'
          + '<div><label>' + t('label_price') + '</label><input type="number" step="1" id="ed-price" value="' + ev(p.price) + '"></div>'
          + '<div><label>' + t('edit_label_taste') + '</label><div class="range-row"><input type="range" min="0" max="6" step="0.5" value="' + (p.taste_score != null ? p.taste_score : 3) + '" id="ed-smak" oninput="document.getElementById(\'ed-smak-val\').textContent=this.value"><span class="range-val" id="ed-smak-val">' + (p.taste_score != null ? p.taste_score : 3) + '</span></div></div>'
          + '<div class="edit-grid-2"><label>' + t('label_taste_note') + '</label><textarea id="ed-taste_note" rows="2" style="resize:vertical;min-height:50px;width:100%;padding:7px 9px;border-radius:7px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);color:#e8e6e3;font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none">' + esc(p.taste_note || '') + '</textarea></div>'
          + '</div>'
          + (p.ingredients
            ? '<div style="display:flex;align-items:center;justify-content:space-between;margin:10px 0 4px">'
              + '<span style="font-size:9px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.06em;font-family:\'Space Mono\',monospace">' + t('label_protein_quality_est') + '</span>'
              + '<button type="button" class="btn-off" id="ed-estimate-btn" data-action="estimate-protein" style="font-size:11px;padding:5px 10px"><span class="off-spin"></span><span class="off-label">&#9881; ' + t('btn_estimate') + '</span></button></div>'
              + '<div id="ed-pq-result" style="' + (p.est_pdcaas || p.est_diaas ? '' : 'display:none;') + 'padding:10px;border-radius:8px;background:rgba(0,229,204,0.06);border:1px solid rgba(0,229,204,0.15);margin-bottom:8px">'
              + '<div style="display:flex;gap:16px;margin-bottom:4px"><span style="font-size:11px;color:rgba(255,255,255,0.4)">PDCAAS: <span id="ed-pdcaas-val" style="color:#00e5cc;font-weight:700;font-family:\'Space Mono\',monospace">' + (p.est_pdcaas ? parseFloat(p.est_pdcaas).toFixed(2) : '\u2013') + '</span></span>'
              + '<span style="font-size:11px;color:rgba(255,255,255,0.4)">DIAAS: <span id="ed-diaas-val" style="color:#00bfff;font-weight:700;font-family:\'Space Mono\',monospace">' + (p.est_diaas ? parseFloat(p.est_diaas).toFixed(2) : '\u2013') + '</span></span></div>'
              + '<div id="ed-pq-sources" style="font-size:10px;color:rgba(255,255,255,0.3)"></div></div>'
            : '')
          + '<input type="hidden" id="ed-est_pdcaas" value="' + (p.est_pdcaas != null ? p.est_pdcaas : '') + '">'
          + '<input type="hidden" id="ed-est_diaas" value="' + (p.est_diaas != null ? p.est_diaas : '') + '">'
          + '<div class="edit-flags">'
          + _getUserFlags().map(f => {
              const cfg = _flagConfig[f];
              if (!cfg) return '';
              const checked = (p.flags || []).includes(f) ? ' checked' : '';
              return '<label class="flag-toggle"><input type="checkbox" id="ed-flag-' + f + '"' + checked + '> ' + esc(cfg.label || t(cfg.labelKey)) + '</label>';
            }).join('')
          + ((() => {
              const sysFlags = (p.flags || []).filter(f => _flagConfig[f] && _flagConfig[f].type === 'system');
              if (!sysFlags.length) return '';
              let badges = '<span style="margin-left:8px">' + sysFlags.map(f => '<span class="flag-badge flag-system">' + esc(_flagConfig[f].label || t(_flagConfig[f].labelKey)) + '</span>').join(' ');
              if (sysFlags.includes('is_synced_with_off') && p.ean)
                badges += ' <a href="https://world.openfoodfacts.org/product/' + encodeURIComponent(p.ean) + '" target="_blank" rel="noopener" class="btn-sm btn-outline" style="font-size:10px;padding:2px 8px;text-decoration:none;display:inline-flex;align-items:center;gap:4px;vertical-align:middle">' + t('btn_view_on_off') + ' &#8599;</a>';
              badges += '</span>';
              return badges;
            })())
          + '</div>'
          + '<div class="form-group">'
          + '<label data-i18n="tags">' + t('tags') + '</label>'
          + '<div class="tag-field" id="tag-field-ed">'
          + '<input type="text" id="tag-input-ed" class="tag-inline-input" placeholder="' + (t('tag_input_placeholder') || 'Add tag\u2026') + '" autocomplete="off" />'
          + '<ul id="tag-suggestions-ed" class="tag-suggestions" hidden></ul>'
          + '</div>'
          + '</div>'
          + '<div style="display:flex;gap:8px">'
          + '<button class="btn-sm btn-green" data-action="save-product" data-id="' + p.id + '">' + t('btn_save') + '</button>'
          + '<button class="btn-sm btn-outline" data-action="cancel-edit">' + t('btn_cancel') + '</button>'
          + '</div></div>';
      } else {
        h += '<div class="expanded-actions">'
          + '<button class="btn-sm btn-outline" data-action="start-edit" data-id="' + p.id + '">' + t('btn_edit') + '</button>';
        if (hasImg) h += '<button class="btn-sm btn-outline" data-action="remove-image" data-id="' + p.id + '">' + t('btn_remove_image') + '</button>';
        h += '<button class="btn-sm btn-red" data-action="delete" data-id="' + p.id + '">' + t('btn_delete') + '</button>'
          + '</div>';
      }
      h += '</div>';
    }
  });
  h += '</div>';
  container.innerHTML = h;

  // Abort previous delegated listeners to avoid duplicate handlers
  if (_resultsAbort) _resultsAbort.abort();
  _resultsAbort = new AbortController();

  // Attach all event handlers via delegation instead of inline onclick
  container.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    const action = target.dataset.action;
    const id = target.dataset.id ? parseInt(target.dataset.id, 10) : null;

    switch (action) {
      case 'sort':
        window.setSort(target.dataset.col);
        break;
      case 'toggle-expand': {
        // Don't expand if clicking inside expanded area or on buttons
        if (e.target.closest('.expanded') || e.target.closest('button') || e.target.closest('[data-action]:not([data-action="toggle-expand"])')) return;
        const rowId = target.dataset.productId ? parseInt(target.dataset.productId, 10) : id;
        window.toggleExpand(rowId);
      }
        break;
      case 'trigger-image':
        e.stopPropagation();
        window.triggerImageUpload(id);
        break;
      case 'save-product':
        e.stopPropagation();
        window.saveProduct(id);
        break;
      case 'cancel-edit':
        e.stopPropagation();
        state.editingId = null;
        import('./filters.js').then((mod) => mod.rerender());
        break;
      case 'start-edit':
        e.stopPropagation();
        window.startEdit(id);
        break;
      case 'remove-image':
        e.stopPropagation();
        window.removeProductImage(id);
        break;
      case 'delete':
        e.stopPropagation();
        window.deleteProduct(id);
        break;
      case 'unlock-ean':
        e.stopPropagation();
        window.unlockEan(id);
        break;
      case 'open-scanner':
        e.stopPropagation();
        window.openScanner('ed', id);
        break;
      case 'lookup-off':
        e.stopPropagation();
        window.lookupOFF('ed', id);
        break;
      case 'estimate-protein':
        e.stopPropagation();
        window.estimateProteinQuality('ed');
        break;
    }
  }, { signal: _resultsAbort.signal });

  // Attach input handlers for validation
  const edName = document.getElementById('ed-name');
  const edIngredients = document.getElementById('ed-ingredients');
  if (edName) edName.addEventListener('input', () => window.validateOffBtn('ed'));
  if (edIngredients) edIngredients.addEventListener('input', () => window.updateEstimateBtn('ed'));

  // Load EAN manager asynchronously after edit form renders
  if (state.editingId && document.getElementById('ean-manager-' + state.editingId)) {
    if (window.loadEanManager) window.loadEanManager(state.editingId);
  }

  const edType = document.getElementById('ed-type');
  if (edType) upgradeSelect(edType);
  const edVol = document.getElementById('ed-volume');
  if (edVol) upgradeSelect(edVol);
  sorted.forEach((p) => {
    if (p.has_image) {
      loadProductImage(p.id).then((dataUri) => {
        if (!dataUri) return;
        const thumb = document.getElementById('thumb-' + p.id);
        if (thumb) thumb.src = dataUri;
        const full = document.getElementById('prod-img-' + p.id);
        if (full) full.src = dataUri;
      });
    }
  });
}
