// ── Advanced Filters (Grouped) ─────────────────────────
import { state, upgradeSelect } from './state.js';
import { t } from './i18n.js';

// Field definitions: [field_key, i18n_key]
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
  ['total_score', 'adv_field_total_score'],
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
    state.advancedFilters = null;
    _triggerReload();
  } else {
    panel.style.display = '';
    toggle.classList.add('has-filter');
    if (!panel.querySelector('.adv-group')) {
      _buildPanel(panel);
    }
  }
}

function _buildPanel(panel) {
  panel.innerHTML = '';

  // Top-level logic toggle (between groups) — hidden when only 1 group
  const topLogicWrap = document.createElement('div');
  topLogicWrap.className = 'adv-logic-wrap';
  topLogicWrap.style.display = 'none';
  const topLogicBtn = document.createElement('button');
  topLogicBtn.className = 'adv-logic-btn adv-top-logic-btn';
  topLogicBtn.textContent = t('adv_logic_and');
  topLogicBtn.dataset.logic = 'and';
  topLogicBtn.addEventListener('click', () => {
    const next = topLogicBtn.dataset.logic === 'and' ? 'or' : 'and';
    topLogicBtn.dataset.logic = next;
    topLogicBtn.textContent = t(next === 'and' ? 'adv_logic_and' : 'adv_logic_or');
    _onFilterChange();
  });
  topLogicWrap.appendChild(topLogicBtn);
  panel.appendChild(topLogicWrap);

  // Groups container
  const groupsDiv = document.createElement('div');
  groupsDiv.id = 'adv-groups';
  panel.appendChild(groupsDiv);

  // Add first group
  _addGroup(groupsDiv);

  // Add group button
  const addGroupBtn = document.createElement('button');
  addGroupBtn.className = 'adv-add-btn';
  addGroupBtn.textContent = t('adv_add_group');
  addGroupBtn.addEventListener('click', () => {
    _addGroup(groupsDiv);
    _updateVisibility();
    _onFilterChange();
  });
  panel.appendChild(addGroupBtn);
}

function _addGroup(container) {
  const group = document.createElement('div');
  group.className = 'adv-group';

  // Group header: logic toggle + remove button
  const header = document.createElement('div');
  header.className = 'adv-group-header';

  const groupLogicBtn = document.createElement('button');
  groupLogicBtn.className = 'adv-logic-btn adv-group-logic-btn';
  groupLogicBtn.textContent = t('adv_logic_and');
  groupLogicBtn.dataset.logic = 'and';
  groupLogicBtn.style.visibility = 'hidden'; // hidden until 2+ conditions
  groupLogicBtn.addEventListener('click', () => {
    const next = groupLogicBtn.dataset.logic === 'and' ? 'or' : 'and';
    groupLogicBtn.dataset.logic = next;
    groupLogicBtn.textContent = t(next === 'and' ? 'adv_logic_and' : 'adv_logic_or');
    _onFilterChange();
  });
  header.appendChild(groupLogicBtn);

  const removeGroupBtn = document.createElement('button');
  removeGroupBtn.className = 'adv-group-remove-btn';
  removeGroupBtn.textContent = '\u00D7';
  removeGroupBtn.title = t('adv_remove_group');
  removeGroupBtn.addEventListener('click', () => {
    group.remove();
    _updateVisibility();
    _onFilterChange();
  });
  header.appendChild(removeGroupBtn);

  group.appendChild(header);

  // Rows container within group
  const rowsDiv = document.createElement('div');
  rowsDiv.className = 'adv-group-rows';
  group.appendChild(rowsDiv);

  // Add first condition row
  _addRow(rowsDiv);

  // Add condition button within group
  const addCondBtn = document.createElement('button');
  addCondBtn.className = 'adv-add-condition-btn';
  addCondBtn.textContent = t('adv_add_condition');
  addCondBtn.addEventListener('click', () => {
    _addRow(rowsDiv);
    _updateVisibility();
  });
  group.appendChild(addCondBtn);

  // Insert before the "between groups" logic separator if needed
  container.appendChild(group);
  _updateVisibility();
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
    const groupRows = container;
    row.remove();
    // If group has no rows left, remove the group (unless it's the only one)
    if (groupRows.querySelectorAll('.adv-row').length === 0) {
      const groupEl = groupRows.closest('.adv-group');
      const allGroups = document.querySelectorAll('#adv-groups .adv-group');
      if (allGroups.length > 1) {
        groupEl.remove();
      } else {
        // Last group — add back an empty row
        _addRow(groupRows);
      }
    }
    _updateVisibility();
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

function _updateVisibility() {
  // Top-level logic toggle: visible only when 2+ groups
  const topLogicWrap = document.querySelector('.adv-logic-wrap');
  const groupCount = document.querySelectorAll('#adv-groups .adv-group').length;
  if (topLogicWrap) {
    topLogicWrap.style.display = groupCount >= 2 ? '' : 'none';
  }

  // Group remove buttons: only visible when 2+ groups
  document.querySelectorAll('.adv-group-remove-btn').forEach(btn => {
    btn.style.display = groupCount >= 2 ? '' : 'none';
  });

  // Group-level logic toggles: visible only when group has 2+ conditions
  document.querySelectorAll('#adv-groups .adv-group').forEach(group => {
    const logicBtn = group.querySelector('.adv-group-logic-btn');
    const rowCount = group.querySelectorAll('.adv-row').length;
    if (logicBtn) {
      logicBtn.style.visibility = rowCount >= 2 ? 'visible' : 'hidden';
    }
  });
}

function _onFilterChange() {
  const topLogicBtn = document.querySelector('.adv-top-logic-btn');
  const topLogic = topLogicBtn ? topLogicBtn.dataset.logic : 'and';

  const groupEls = document.querySelectorAll('#adv-groups .adv-group');
  const groups = [];

  groupEls.forEach(groupEl => {
    const groupLogicBtn = groupEl.querySelector('.adv-group-logic-btn');
    const groupLogic = groupLogicBtn ? groupLogicBtn.dataset.logic : 'and';
    const rows = groupEl.querySelectorAll('.adv-row');
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
      groups.push({ logic: groupLogic, conditions });
    }
  });

  if (groups.length > 0) {
    state.advancedFilters = JSON.stringify({ logic: topLogic, groups });
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
