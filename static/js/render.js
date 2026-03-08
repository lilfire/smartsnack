// ── Render ──────────────────────────────────────────
import { state, esc, safeDataUri, catEmoji, catLabel } from './state.js';
import { t } from './i18n.js';
import { applySorting, sortIndicator } from './filters.js';
import { loadProductImage } from './images.js';
import { SCORE_COLORS, SCORE_CFG_MAP, weightData } from './settings.js';

var _VOLUME_LABELS = { 1: 'volume_low', 2: 'volume_medium', 3: 'volume_high' };
function volumeLabel(val) { return _VOLUME_LABELS[val] ? t(_VOLUME_LABELS[val]) : val; }

export function renderNutriTable(p) {
  var rows = [
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
  var h = '<table class="nutri-table">';
  rows.forEach(function(r) {
    var isSub = r[3];
    var val = r[1];
    var display = (val != null) ? parseFloat(val).toFixed(r[2] === 'g' ? 1 : 0) + ' ' + r[2] : '-';
    h += '<tr' + (isSub ? ' class="sub"' : '') + '><td>' + r[0] + '</td><td>' + display + '</td></tr>';
  });
  if (p.est_pdcaas || p.est_diaas) {
    if (p.est_pdcaas) h += '<tr><td style="color:#00e5cc">PDCAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00e5cc;font-family:\'Space Mono\',monospace">' + parseFloat(p.est_pdcaas).toFixed(2) + '</td></tr>';
    if (p.est_diaas) h += '<tr><td style="color:#00bfff">DIAAS <span style="font-size:9px;opacity:0.5">(est.)</span></td><td style="color:#00bfff;font-family:\'Space Mono\',monospace">' + parseFloat(p.est_diaas).toFixed(2) + '</td></tr>';
  }
  h += '</table>';
  var extras = [];
  if (p.weight) extras.push(t('extra_weight', { val: p.weight }));
  if (p.portion) extras.push(t('extra_portion', { val: p.portion }));
  if (p.price) extras.push(t('extra_price', { val: p.price }));
  if (p.volume) extras.push(t('extra_volume', { val: volumeLabel(p.volume) }));
  if (extras.length) h += '<div style="margin-top:8px;font-size:11px;color:rgba(255,255,255,0.3)">' + extras.join(' \u00B7 ') + '</div>';
  return h;
}

// ── Dynamic column helpers ──────────────────────────
var COL_UNITS = { kcal: '', energy_kj: '', carbs: 'g', sugar: 'g', fat: 'g', saturated_fat: 'g', protein: 'g', fiber: 'g', salt: 'g', taste_score: '', volume: '', price: 'kr', pct_protein_cal: '%', pct_fat_cal: '%', pct_carb_cal: '%' };

export function fmtCell(field, val) {
  if (val == null) return '-';
  if (field === 'volume') return volumeLabel(val);
  if (field === 'taste_score') {
    var st = '\u2605'.repeat(Math.round(val)), dm = '\u2605'.repeat(6 - Math.round(val));
    return '<span class="stars">' + st + '<span class="stars-dim">' + dm + '</span></span>';
  }
  if (field === 'price') return val ? val.toFixed(0) + 'kr' : '-';
  if (field === 'pct_protein_cal' || field === 'pct_fat_cal' || field === 'pct_carb_cal') return parseFloat(val).toFixed(1) + '%';
  var u = COL_UNITS[field] || '';
  if (field === 'salt') return val.toFixed(2) + u;
  if (field === 'kcal' || field === 'energy_kj') return Math.round(val) + u;
  return parseFloat(val).toFixed(1) + u;
}

export function getActiveCols() {
  var cols = [{ key: 'name', label: t('col_product'), width: '2.4fr' }];
  var enabled = weightData.filter(function(w) { return w.enabled; });
  var isMobile = window.innerWidth < 640;
  if (!isMobile) {
    enabled.forEach(function(w) { cols.push({ key: w.field, label: w.label, width: '0.7fr' }); });
  }
  cols.push({ key: 'total_score', label: t('col_score'), width: '0.9fr' });
  return cols;
}

export function getGridTemplate(cols) {
  return cols.map(function(c) { return c.width; }).join(' ');
}

// Re-render on resize (debounced)
var _resizeTimer = null;
window.addEventListener('resize', function() {
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(function() {
    if (state.editingId === null) {
      import('./filters.js').then(function(mod) { mod.rerender(); });
    }
  }, 200);
});

export function renderResults(results, search) {
  state.cachedResults = results;
  document.getElementById('result-count').textContent = search
    ? (results.length !== 1 ? t('result_count_search_plural', { count: results.length, query: search }) : t('result_count_search', { count: results.length, query: search }))
    : (results.length !== 1 ? t('result_count_plural', { count: results.length }) : t('result_count', { count: results.length }));
  var container = document.getElementById('results-container');
  if (!results.length) {
    container.innerHTML = '<div class="empty"><div class="empty-icon">\u{1F50D}</div><p>' + t('no_products_found') + '</p>'
      + (search ? '<button class="btn-create-from-search" onclick="window._createFromSearch()">' + t('create_product') + '</button>' : '')
      + '</div>';
    if (search) {
      window._createFromSearch = function() {
        if (isValidEan(search)) {
          document.getElementById('f-ean').value = search;
        } else {
          document.getElementById('f-name').value = search;
        }
        window.switchView('register');
      };
    }
    return;
  }
  var sorted = applySorting(results);
  var cols = getActiveCols();
  var gridTpl = getGridTemplate(cols);
  var h = '<div class="table-wrap"><div class="table-head" style="grid-template-columns:' + gridTpl + '">';
  cols.forEach(function(c, i) {
    h += '<span class="th-sort' + (state.sortCol === c.key ? ' th-active' : '') + '" onclick="setSort(\'' + c.key + '\')"' + (i > 0 ? ' style="text-align:right"' : '') + '>' + c.label + ' ' + sortIndicator(c.key) + '</span>';
  });
  h += '</div>';
  sorted.forEach(function(p) {
    var hasImg = p.has_image;
    var thumbHtml = hasImg ? '<img class="prod-thumb" id="thumb-' + p.id + '" src="" alt="">' : '';
    var eanHtml = p.ean ? '<span class="prod-ean">EAN: ' + esc(p.ean) + '</span>' : '';
    var brandHtml = p.brand ? '<span style="color:rgba(255,255,255,0.3)">' + esc(p.brand) + '</span>' : '';
    h += '<div class="table-row" style="grid-template-columns:' + gridTpl + '" onclick="toggleExpand(' + p.id + ')">'
      + '<div><div style="display:flex;align-items:center;gap:8px"><span style="font-size:14px">' + catEmoji(p.type) + '</span>' + thumbHtml + '<span class="prod-name">' + esc(p.name) + '</span></div>'
      + '<div class="prod-meta"><span>' + catLabel(p.type) + '</span>' + brandHtml + eanHtml + '</div></div>';
    for (var ci = 1; ci < cols.length; ci++) {
      var c = cols[ci];
      if (c.key === 'total_score') {
        h += '<span class="cell-score">' + p.total_score.toFixed(1) + (p.has_missing_scores ? '<span style="color:#f5a623;margin-left:1px" title="Score based on incomplete data — some values are 0 or missing">*</span>' : '') + '</span>';
      } else {
        h += '<span class="cell-right">' + fmtCell(c.key, p[c.key]) + '</span>';
      }
    }
    h += '</div>';
    if (state.expandedId === p.id) {
      h += '<div class="expanded"><div class="expanded-top">'
        + '<div class="expanded-img-area" onclick="event.stopPropagation();triggerImageUpload(' + p.id + ')">'
        + '<div id="prod-img-wrap-' + p.id + '">' + (hasImg ? '<img id="prod-img-' + p.id + '" src="" style="width:100%;height:100%;object-fit:cover">' : '<div class="expanded-img-placeholder">\u{1F4F7}</div>') + '</div>'
        + '<div class="expanded-img-overlay">' + (hasImg ? t('expanded_change_image') : t('expanded_upload_image')) + '</div></div>'
        + '<div class="expanded-right">';
      h += '<p class="expanded-title">' + t('expanded_score_breakdown') + '</p><div class="score-grid">';
      var sc = p.scores || {};
      for (var sf in sc) {
        var scfg = SCORE_CFG_MAP[sf];
        if (!scfg) continue;
        var sv = sc[sf];
        var pct = Math.min(sv, 100);
        var col = SCORE_COLORS[sf] || '#888';
        h += '<div><div class="score-label">' + scfg.label + '</div><div class="score-bar-bg"><div class="score-bar-fill" style="width:' + pct + '%;background:' + col + '"></div></div><span class="score-val">' + sv.toFixed(1) + '</span></div>';
      }
      if (!Object.keys(sc).length) h += '<div style="color:rgba(255,255,255,0.3);font-size:12px;grid-column:1/-1">' + t('expanded_no_weights') + '</div>';
      h += '</div>';
      if (p.has_missing_scores && p.missing_fields && p.missing_fields.length) {
        var mLabels = p.missing_fields.map(function(f) { var c = SCORE_CFG_MAP[f]; return c ? c.label : f; }).join(', ');
        h += '<div style="margin-top:8px;padding:8px 10px;border-radius:7px;background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.18);font-size:11px;color:rgba(245,166,35,0.85)"><span style="margin-right:4px">⚠</span> ' + t('expanded_missing_data', { fields: esc(mLabels) }) + '</div>';
      }
      // Nutrition table
      h += '<p class="nutri-section-title">' + t('expanded_nutrition_title') + '</p>';
      h += renderNutriTable(p);
      if (p.brand || p.stores || p.ingredients) {
        h += '<p class="nutri-section-title">' + t('expanded_product_info') + '</p>';
        if (p.brand) h += '<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">' + t('expanded_label_brand') + '</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">' + esc(p.brand) + '</span></div>';
        if (p.stores) h += '<div style="margin-bottom:5px"><span style="font-size:10px;color:rgba(255,255,255,0.35)">' + t('expanded_label_stores') + '</span><span style="font-size:12px;color:rgba(255,255,255,0.7)">' + esc(p.stores) + '</span></div>';
        if (p.ingredients) h += '<div style="margin-top:4px"><span style="font-size:10px;color:rgba(255,255,255,0.35);display:block;margin-bottom:3px">' + t('expanded_label_ingredients') + '</span><span style="font-size:11px;color:rgba(255,255,255,0.5);line-height:1.5">' + esc(p.ingredients) + '</span></div>';
      }
      h += '</div></div>';

      if (state.editingId === p.id) {
        var opts = '';
        state.categories.slice().sort(function(a, b) { return a.label.localeCompare(b.label); }).forEach(function(c) { opts += '<option value="' + esc(c.name) + '"' + (c.name === p.type ? ' selected' : '') + '>' + esc(c.emoji) + ' ' + esc(c.label) + '</option>'; });
        h += '<div class="edit-form"><div class="edit-grid">'
          + '<div class="edit-grid-2"><label>' + t('edit_label_name') + '</label><input id="ed-name" value="' + esc(p.name) + '" oninput="validateOffBtn(\'ed\')"></div>'
          + '<div><label>' + t('edit_label_ean') + '</label><div class="ean-row"><div><input id="ed-ean" value="' + esc(p.ean || '') + '" oninput="validateOffBtn(\'ed\')"></div><button class="btn-scan" onclick="event.stopPropagation();openScanner(\'ed\',' + p.id + ')" title="' + t('btn_scan_title') + '">&#128247;</button><button class="btn-off" id="ed-off-btn" ' + ((isValidEan(p.ean) || p.name.trim()) ? '' : 'disabled') + ' onclick="event.stopPropagation();lookupOFF(\'ed\',' + p.id + ')"><span class="off-spin"></span><span class="off-label">' + t('btn_fetch') + '</span></button></div></div>'
          + '<div><label>' + t('edit_label_category') + '</label><select id="ed-type">' + opts + '</select></div>'
          + '<div><label>' + t('edit_label_brand') + '</label><input id="ed-brand" value="' + esc(p.brand || '') + '"></div>'
          + '<div><label>' + t('edit_label_stores') + '</label><input id="ed-stores" value="' + esc(p.stores || '') + '"></div>'
          + '<div class="edit-grid-2"><label>' + t('edit_label_ingredients') + '</label><textarea id="ed-ingredients" rows="2" style="resize:vertical;min-height:50px;width:100%;padding:7px 9px;border-radius:7px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);color:#e8e6e3;font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none" oninput="updateEstimateBtn(\'ed\')">' + esc(p.ingredients || '') + '</textarea></div>';
        function ev(v) { return v == null ? '' : v; }
        h += '<div><label>' + t('edit_label_kcal') + '</label><input type="number" step="1" id="ed-kcal" value="' + ev(p.kcal) + '"></div>'
          + '<div><label>' + t('edit_label_energy_kj') + '</label><input type="number" step="1" id="ed-energy_kj" value="' + ev(p.energy_kj) + '"></div>'
          + '<div><label>' + t('edit_label_fat') + '</label><input type="number" step="0.1" id="ed-fat" value="' + ev(p.fat) + '"></div>'
          + '<div><label>' + t('edit_label_saturated_fat') + '</label><input type="number" step="0.1" id="ed-saturated_fat" value="' + ev(p.saturated_fat) + '"></div>'
          + '<div><label>' + t('edit_label_carbs') + '</label><input type="number" step="0.1" id="ed-carbs" value="' + ev(p.carbs) + '"></div>'
          + '<div><label>' + t('edit_label_sugar') + '</label><input type="number" step="0.1" id="ed-sugar" value="' + ev(p.sugar) + '"></div>'
          + '<div><label>' + t('edit_label_protein') + '</label><input type="number" step="0.1" id="ed-protein" value="' + ev(p.protein) + '"></div>'
          + '<div><label>' + t('edit_label_fiber') + '</label><input type="number" step="0.1" id="ed-fiber" value="' + ev(p.fiber) + '"></div>'
          + '<div><label>' + t('edit_label_salt') + '</label><input type="number" step="0.01" id="ed-salt" value="' + ev(p.salt) + '"></div>'
          + '<div><label>' + t('edit_label_weight') + '</label><input type="number" step="1" id="ed-weight" value="' + ev(p.weight) + '"></div>'
          + '<div><label>' + t('edit_label_portion') + '</label><input type="number" step="1" id="ed-portion" value="' + ev(p.portion) + '"></div>'
          + '<div><label>' + t('edit_label_volume') + '</label><select class="field-select" id="ed-volume"><option value="">-</option><option value="1"' + (p.volume == 1 ? ' selected' : '') + '>' + t('volume_low') + '</option><option value="2"' + (p.volume == 2 ? ' selected' : '') + '>' + t('volume_medium') + '</option><option value="3"' + (p.volume == 3 ? ' selected' : '') + '>' + t('volume_high') + '</option></select></div>'
          + '<div><label>' + t('edit_label_price') + '</label><input type="number" step="1" id="ed-price" value="' + ev(p.price) + '"></div>'
          + '<div><label>' + t('edit_label_taste') + '</label><input type="number" step="0.5" min="0" max="6" id="ed-smak" value="' + ev(p.taste_score) + '"></div>'
          + '</div>'
          + (p.ingredients
            ? '<div style="display:flex;align-items:center;justify-content:space-between;margin:10px 0 4px">'
              + '<span style="font-size:9px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.06em;font-family:\'Space Mono\',monospace">Protein quality (estimated)</span>'
              + '<button type="button" class="btn-off" id="ed-estimate-btn" onclick="event.stopPropagation();estimateProteinQuality(\'ed\')" style="font-size:11px;padding:5px 10px"><span class="off-spin"></span><span class="off-label">&#9881; Estimate</span></button></div>'
              + '<div id="ed-pq-result" style="' + (p.est_pdcaas || p.est_diaas ? '' : 'display:none;') + 'padding:10px;border-radius:8px;background:rgba(0,229,204,0.06);border:1px solid rgba(0,229,204,0.15);margin-bottom:8px">'
              + '<div style="display:flex;gap:16px;margin-bottom:4px"><span style="font-size:11px;color:rgba(255,255,255,0.4)">PDCAAS: <span id="ed-pdcaas-val" style="color:#00e5cc;font-weight:700;font-family:\'Space Mono\',monospace">' + (p.est_pdcaas ? parseFloat(p.est_pdcaas).toFixed(2) : '–') + '</span></span>'
              + '<span style="font-size:11px;color:rgba(255,255,255,0.4)">DIAAS: <span id="ed-diaas-val" style="color:#00bfff;font-weight:700;font-family:\'Space Mono\',monospace">' + (p.est_diaas ? parseFloat(p.est_diaas).toFixed(2) : '–') + '</span></span></div>'
              + '<div id="ed-pq-sources" style="font-size:10px;color:rgba(255,255,255,0.3)"></div></div>'
            : '')
          + '<input type="hidden" id="ed-est_pdcaas" value="' + (p.est_pdcaas != null ? p.est_pdcaas : '') + '">'
          + '<input type="hidden" id="ed-est_diaas" value="' + (p.est_diaas != null ? p.est_diaas : '') + '">'
          + '<div style="display:flex;gap:8px">'
          + '<button class="btn-sm btn-green" onclick="event.stopPropagation();saveProduct(' + p.id + ')">' + t('btn_save') + '</button>'
          + '<button class="btn-sm btn-outline" onclick="event.stopPropagation();editingId=null;rerender()">' + t('btn_cancel') + '</button>'
          + '</div></div>';
      } else {
        h += '<div class="expanded-actions">'
          + '<button class="btn-sm btn-outline" onclick="event.stopPropagation();startEdit(' + p.id + ')">' + t('btn_edit') + '</button>';
        if (hasImg) h += '<button class="btn-sm btn-outline" onclick="event.stopPropagation();removeProductImage(' + p.id + ')">' + t('btn_remove_image') + '</button>';
        h += '<button class="btn-sm btn-red" onclick="event.stopPropagation();deleteProduct(' + p.id + ',\'' + esc(p.name).replace(/'/g, "\\'") + '\')">' + t('btn_delete') + '</button>'
          + '</div>';
      }
      h += '</div>';
    }
  });
  h += '</div>';
  container.innerHTML = h;
  sorted.forEach(function(p) {
    if (p.has_image) {
      loadProductImage(p.id).then(function(dataUri) {
        if (!dataUri) return;
        var thumb = document.getElementById('thumb-' + p.id);
        if (thumb) thumb.src = dataUri;
        var full = document.getElementById('prod-img-' + p.id);
        if (full) full.src = dataUri;
      });
    }
  });
}

// isValidEan is needed for the edit form rendering
function isValidEan(v) {
  if (!v) return false;
  var s = v.replace(/\s/g, '');
  return /^\d{8,13}$/.test(s);
}
