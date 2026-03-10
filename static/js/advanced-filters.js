// ── Advanced Filters ─────────────────────────────────
import { state, upgradeSelect } from './state.js';
import { t } from './i18n.js';

// Field definitions: [field_key, i18n_key, type]
const TEXT_FIELDS = [
  ['name', 'adv_field_name'],
  ['brand', 'adv_field_brand'],
  ['stores', 'adv_field_stores'],
  ['ingredients', 'adv_field_ingredients'],
  ['ean', 'adv_field_ean'],
  ['type', 'adv_field_type'],
];
const NUMERIC_FIELDS = [
  ['kcal', 'adv_field_kcal'],
  ['energy_kj', 'adv_field_energy_kj'],
  ['protein', 'adv_field_protein'],
  ['fat', 'adv_field_fat'],
  ['saturated_fat', 'adv_field_saturated_fat'],
  ['carbs', 'adv_field_carbs'],
  ['sugar', 'adv_field_sugar'],
  ['fiber', 'adv_field_fiber'],
  ['salt', 'adv_field_salt'],
  ['price', 'adv_field_price'],
  ['weight', 'adv_field_weight'],
  ['portion', 'adv_field_portion'],
  ['volume', 'adv_field_volume'],
  ['taste_score', 'adv_field_taste_score'],
  ['est_pdcaas', 'adv_field_est_pdcaas'],
  ['est_diaas', 'adv_field_est_diaas'],
];

const TEXT_OPS = [
  ['contains', 'adv_op_contains'],
  ['=', 'adv_op_eq'],
  ['!=', 'adv_op_neq'],
];
const NUMERIC_OPS = [
  ['<', 'adv_op_lt'],
  ['>', 'adv_op_gt'],
  ['=', 'adv_op_eq'],
  ['<=', 'adv_op_lte'],
  ['>=', 'adv_op_gte'],
  ['!=', 'adv_op_neq'],
];

const _TEXT_FIELD_SET = new Set(TEXT_FIELDS.map(f => f[0]));
let _rowCounter = 0;

export function toggleAdvancedFilters() {
  const panel = document.getElementById('advanced-filters');
  const toggle = document.getElementById('adv-filter-toggle');
  if (!panel) return;
  const visible = panel.style.display !== 'none';
  if (visible) {
    panel.style.display = 'none';
    toggle.classList.remove('has-filter');
    // Clear filters and reload
    state.advancedFilters = null;
    _triggerReload();
  } else {
    panel.style.display = '';
    toggle.classList.add('has-filter');
    if (!panel.querySelector('.adv-row')) {
      _buildPanel(panel);
    }
  }
}

function _buildPanel(panel) {
  panel.innerHTML = '';

  // Logic toggle (AND/OR)
  const logicWrap = document.createElement('div');
  logicWrap.className = 'adv-logic-wrap';
  const logicBtn = document.createElement('button');
  logicBtn.className = 'adv-logic-btn';
  logicBtn.textContent = t('adv_logic_and');
  logicBtn.dataset.logic = 'and';
  logicBtn.addEventListener('click', () => {
    const next = logicBtn.dataset.logic === 'and' ? 'or' : 'and';
    logicBtn.dataset.logic = next;
    logicBtn.textContent = t(next === 'and' ? 'adv_logic_and' : 'adv_logic_or');
    _onFilterChange();
  });
  logicWrap.appendChild(logicBtn);
  panel.appendChild(logicWrap);

  // Rows container
  const rowsDiv = document.createElement('div');
  rowsDiv.id = 'adv-rows';
  panel.appendChild(rowsDiv);

  // Add first row
  _addRow(rowsDiv);

  // Add filter button
  const addBtn = document.createElement('button');
  addBtn.className = 'adv-add-btn';
  addBtn.textContent = t('adv_add_filter');
  addBtn.addEventListener('click', () => { _addRow(rowsDiv); });
  panel.appendChild(addBtn);
}

function _addRow(container) {
  const row = document.createElement('div');
  row.className = 'adv-row';
  const rowId = ++_rowCounter;
  row.dataset.rowId = rowId;

  // Field select
  const fieldSel = document.createElement('select');
  fieldSel.className = 'adv-field-select';
  const textGroup = document.createElement('optgroup');
  textGroup.label = t('adv_group_text');
  TEXT_FIELDS.forEach(([val, key]) => {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = t(key);
    textGroup.appendChild(o);
  });
  fieldSel.appendChild(textGroup);
  const numGroup = document.createElement('optgroup');
  numGroup.label = t('adv_group_nutrition');
  NUMERIC_FIELDS.forEach(([val, key]) => {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = t(key);
    numGroup.appendChild(o);
  });
  fieldSel.appendChild(numGroup);
  row.appendChild(fieldSel);

  // Operator select
  const opSel = document.createElement('select');
  opSel.className = 'adv-op-select';
  row.appendChild(opSel);

  // Value input
  const valInput = document.createElement('input');
  valInput.className = 'adv-value-input';
  valInput.type = 'text';
  valInput.placeholder = t('adv_placeholder_value');
  row.appendChild(valInput);

  // Remove button
  const removeBtn = document.createElement('button');
  removeBtn.className = 'adv-remove-btn';
  removeBtn.textContent = '\u00D7';
  removeBtn.title = t('adv_remove_filter');
  removeBtn.addEventListener('click', () => {
    row.remove();
    _onFilterChange();
  });
  row.appendChild(removeBtn);

  // Trigger filter on value change (debounced)
  let valTimer = null;
  valInput.addEventListener('input', () => {
    clearTimeout(valTimer);
    valTimer = setTimeout(_onFilterChange, 300);
  });

  container.appendChild(row);

  // Initialize ops for default field
  _updateOps(opSel, fieldSel.value);
  valInput.type = _TEXT_FIELD_SET.has(fieldSel.value) ? 'text' : 'number';
  valInput.step = 'any';

  // Upgrade to custom styled selects
  upgradeSelect(fieldSel, (val) => {
    _updateOps(opSel, val);
    upgradeSelect(opSel);
    valInput.type = _TEXT_FIELD_SET.has(val) ? 'text' : 'number';
    valInput.step = 'any';
  });
  upgradeSelect(opSel, () => { _onFilterChange(); });
}

function _updateOps(opSel, fieldValue) {
  const ops = _TEXT_FIELD_SET.has(fieldValue) ? TEXT_OPS : NUMERIC_OPS;
  const prev = opSel.value;
  opSel.innerHTML = '';
  ops.forEach(([val, key]) => {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = t(key);
    opSel.appendChild(o);
  });
  // Restore previous op if still valid
  for (let i = 0; i < opSel.options.length; i++) {
    if (opSel.options[i].value === prev) { opSel.value = prev; return; }
  }
}

function _onFilterChange() {
  const rows = document.querySelectorAll('#adv-rows .adv-row');
  const logicBtn = document.querySelector('.adv-logic-btn');
  const logic = logicBtn ? logicBtn.dataset.logic : 'and';

  const conditions = [];
  rows.forEach(row => {
    const field = row.querySelector('.adv-field-select').value;
    const op = row.querySelector('.adv-op-select').value;
    const value = row.querySelector('.adv-value-input').value.trim();
    if (field && op && value !== '') {
      conditions.push({ field, op, value });
    }
  });

  if (conditions.length > 0) {
    state.advancedFilters = JSON.stringify({ logic, conditions });
  } else {
    state.advancedFilters = null;
  }
  _triggerReload();
}

let _reloadTimer = null;
function _triggerReload() {
  clearTimeout(_reloadTimer);
  _reloadTimer = setTimeout(() => {
    // Use dynamic import to avoid circular dependency
    import('./products.js').then(mod => { mod.loadData(); });
  }, 100);
}
