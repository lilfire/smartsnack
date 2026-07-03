// ── Settings: Nutrition Weights — renderer ────────────
// Extracted from settings-weights.js (LSO-1700 file-size constraint).
// settings-weights.js re-exports these, so importers can keep using it.
// The import cycle with settings-weights.js is safe: all imported bindings
// are only referenced at call time, never during module evaluation.
import { esc, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import {
  SCORE_COLORS,
  weightData,
  categoryScopeData,
  getActiveScope,
  removeWeight,
  addWeightFromDropdown,
  onWeightDirection,
  onWeightFormula,
  onWeightMin,
  onWeightMax,
  onWeightSlider,
} from './settings-weights.js';

// Identical UI for global and category scope.
// In category scope, "active" = is_overridden, "inactive" = inherited.
// In global scope,   "active" = enabled,       "inactive" = disabled.
export function renderWeightItems() {
  const container = document.getElementById('weight-items');
  if (!container) return;
  const isCategory = !!getActiveScope();
  const source = isCategory ? categoryScopeData : weightData;
  const isActive = (w) => isCategory ? !!w.is_overridden : !!w.enabled;
  const active = source.filter(isActive);
  const inactive = source.filter((w) => !isActive(w));
  container.innerHTML = '';

  active.forEach((w) => {
    const col = SCORE_COLORS[w.field] || '#888';
    const dirLower = w.direction === 'lower';
    const isDirect = w.formula === 'direct';
    const sf = w.field;

    const item = document.createElement('div');
    item.className = 'weight-item enabled';
    item.id = 'wi-' + sf;
    item.style.cssText = 'margin-bottom:10px;border-left:3px solid ' + col;

    const header = document.createElement('div');
    header.className = 'weight-header';

    const topDiv = document.createElement('div');
    topDiv.className = 'weight-top';
    const label = document.createElement('label');
    label.className = 'field-label';
    label.style.margin = '0';
    label.textContent = w.label;
    topDiv.appendChild(label);
    header.appendChild(topDiv);

    const valSpan = document.createElement('span');
    valSpan.className = 'weight-val mono accent';
    valSpan.id = 'wv-' + sf;
    valSpan.textContent = (w.weight != null ? w.weight : 0).toFixed(1);
    header.appendChild(valSpan);

    const cfgBtn = document.createElement('button');
    cfgBtn.className = 'weight-cfg-btn';
    cfgBtn.title = 'Advanced';
    cfgBtn.innerHTML = '&#9881;';
    cfgBtn.addEventListener('click', () => toggleWeightConfig(sf));
    header.appendChild(cfgBtn);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-sm btn-red';
    removeBtn.title = isCategory ? t('btn_remove_override') : 'Remove';
    removeBtn.innerHTML = '&#128465;';
    removeBtn.addEventListener('click', () => removeWeight(sf));
    header.appendChild(removeBtn);

    item.appendChild(header);

    const cfgDiv = document.createElement('div');
    cfgDiv.className = 'weight-config';
    cfgDiv.id = 'wcfg-' + sf;
    cfgDiv.style.display = 'none';

    const cfgRow = document.createElement('div');
    cfgRow.className = 'wc-row';

    const dirSelect = document.createElement('select');
    dirSelect.className = 'wc-select';
    dirSelect.id = 'wd-' + sf;
    dirSelect.innerHTML = '<option value="lower" ' + (dirLower ? 'selected' : '') + '>' + esc(t('direction_lower')) + '</option>'
      + '<option value="higher" ' + (!dirLower ? 'selected' : '') + '>' + esc(t('direction_higher')) + '</option>';
    dirSelect.addEventListener('change', () => onWeightDirection(sf));
    cfgRow.appendChild(dirSelect);

    const fmlaSelect = document.createElement('select');
    fmlaSelect.className = 'wc-select';
    fmlaSelect.id = 'wf-' + sf;
    fmlaSelect.innerHTML = '<option value="minmax" ' + (!isDirect ? 'selected' : '') + '>' + esc(t('formula_minmax')) + '</option>'
      + '<option value="direct" ' + (isDirect ? 'selected' : '') + '>' + esc(t('formula_direct')) + '</option>';
    fmlaSelect.addEventListener('change', () => onWeightFormula(sf));
    cfgRow.appendChild(fmlaSelect);

    const minInput = document.createElement('input');
    minInput.type = 'number';
    minInput.className = 'wc-max';
    minInput.id = 'wn-' + sf;
    minInput.value = w.formula_min != null ? w.formula_min : '';
    minInput.placeholder = 'Min';
    minInput.step = '0.01';
    minInput.style.display = isDirect ? '' : 'none';
    minInput.addEventListener('input', () => onWeightMin(sf));
    cfgRow.appendChild(minInput);

    const maxInput = document.createElement('input');
    maxInput.type = 'number';
    maxInput.className = 'wc-max';
    maxInput.id = 'wm-' + sf;
    maxInput.value = w.formula_max != null ? w.formula_max : '';
    maxInput.placeholder = 'Max';
    maxInput.step = '0.01';
    maxInput.style.display = isDirect ? '' : 'none';
    maxInput.addEventListener('input', () => onWeightMax(sf));
    cfgRow.appendChild(maxInput);

    cfgDiv.appendChild(cfgRow);
    item.appendChild(cfgDiv);

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '0';
    slider.max = '100';
    slider.step = '1';
    slider.value = w.weight != null ? w.weight : 0;
    slider.id = 'w-' + sf;
    slider.className = 'weight-slider';
    slider.addEventListener('input', () => onWeightSlider(sf));
    item.appendChild(slider);

    container.appendChild(item);
  });

  // Bottom "+ add weight / + add override" dropdown — same UI for both scopes.
  if (inactive.length) {
    const placeholder = '— ' + t(isCategory ? 'btn_add_override' : 'btn_add_weight') + ' —';
    const addRow = document.createElement('div');
    addRow.className = 'weight-add-row';

    const addSelect = document.createElement('select');
    addSelect.className = 'field-select';
    addSelect.id = 'weight-add-select';
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = placeholder;
    addSelect.appendChild(placeholderOpt);
    inactive.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach((w) => {
      const opt = document.createElement('option');
      opt.value = w.field;
      opt.textContent = w.label;
      addSelect.appendChild(opt);
    });
    addRow.appendChild(addSelect);

    const addBtn = document.createElement('button');
    addBtn.className = 'btn-register weight-add-btn';
    addBtn.textContent = '+';
    addBtn.addEventListener('click', addWeightFromDropdown);
    addRow.appendChild(addBtn);

    container.appendChild(addRow);
  }

  upgradeSelect(document.getElementById('weight-add-select'), () => {
    addWeightFromDropdown();
  });
  active.forEach((w) => {
    upgradeSelect(document.getElementById('wd-' + w.field), () => {
      onWeightDirection(w.field);
    });
    upgradeSelect(document.getElementById('wf-' + w.field), () => {
      onWeightFormula(w.field);
    });
  });
}

export function toggleWeightConfig(field) {
  const el = document.getElementById('wcfg-' + field);
  if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
}
