// ── Advanced Filters (Recursive Nested Groups) ─────────────────────────
import { state, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import { updateFilterToggle } from './filters.js';

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

const FLAG_FIELDS = [
  ['flag:is_discontinued', 'flag_is_discontinued'],
  ['flag:is_synced_with_off', 'flag_is_synced_with_off'],
];
const FLAG_OPS = [
  ['= true', 'adv_op_is_set'],
  ['= false', 'adv_op_is_not_set'],
];

const _TEXT_FIELD_SET = new Set(TEXT_FIELDS.map(f => f[0]));
const _FLAG_FIELD_SET = new Set(FLAG_FIELDS.map(f => f[0]));
const MAX_DEPTH = 4;
const MAX_CONDITIONS = 20;
let _rowCounter = 0;

export function toggleAdvancedFilters() {
  const panel = document.getElementById('advanced-filters');
  const toggle = document.getElementById('adv-filter-toggle');
  if (!panel) return;
  const visible = panel.classList.contains('open');
  const searchRow = document.querySelector('.search-row');
  const searchInput = document.getElementById('search-input');
  const searchClear = document.getElementById('search-clear');
  const filterToggle = document.getElementById('filter-toggle');
  const filterRow = document.getElementById('filter-row');

  if (visible) {
    // ── Close advanced mode ──
    panel.classList.remove('open');
    toggle.classList.remove('has-filter');
    state.advancedFilters = null;
    // Restore normal search UI
    if (searchRow) searchRow.classList.remove('advanced-active');
    if (searchInput) searchInput.disabled = false;
    if (filterToggle) filterToggle.style.display = '';
    _triggerReload();
  } else {
    // ── Open advanced mode ──
    // Clear normal search state to prevent ghost filtering
    if (searchInput) { searchInput.value = ''; searchInput.disabled = true; }
    if (searchClear) searchClear.classList.remove('visible');
    state.currentFilter = [];
    updateFilterToggle();
    // Dim search bar, hide category filters
    if (searchRow) searchRow.classList.add('advanced-active');
    if (filterToggle) filterToggle.style.display = 'none';
    if (filterRow) filterRow.classList.remove('open');
    // Slide panel open
    if (!panel.querySelector('.adv-group')) {
      _buildPanel(panel);
    }
    requestAnimationFrame(() => panel.classList.add('open'));
    toggle.classList.add('has-filter');
    _triggerReload();
  }
}

function _buildPanel(panel) {
  panel.innerHTML = '';
  // The panel itself hosts the root group
  _addGroup(panel, 0, true);
}

// ── Group (recursive) ────────────────────────────────────

function _addGroup(container, depth, isRoot) {
  const group = document.createElement('div');
  group.className = `adv-group adv-group-depth-${depth}`;
  group.dataset.depth = depth;
  if (isRoot) group.dataset.root = '1';

  // Header: logic toggle + remove button
  const header = document.createElement('div');
  header.className = 'adv-group-header';

  const logicBtn = document.createElement('button');
  logicBtn.className = 'adv-logic-btn adv-group-logic-btn';
  logicBtn.textContent = t('adv_logic_and');
  logicBtn.dataset.logic = 'and';
  logicBtn.style.visibility = 'hidden'; // shown when 2+ children
  logicBtn.addEventListener('click', () => {
    const next = logicBtn.dataset.logic === 'and' ? 'or' : 'and';
    logicBtn.dataset.logic = next;
    logicBtn.textContent = t(next === 'and' ? 'adv_logic_and' : 'adv_logic_or');
    _onFilterChange();
  });
  header.appendChild(logicBtn);

  if (!isRoot) {
    const removeBtn = document.createElement('button');
    removeBtn.className = 'adv-group-remove-btn';
    removeBtn.textContent = '\u00D7';
    removeBtn.title = t('adv_remove_group');
    removeBtn.addEventListener('click', () => {
      const parentChildren = group.parentElement; // .adv-group-children
      group.remove();
      _handleEmptyParent(parentChildren);
      _updateVisibilityAll();
      _onFilterChange();
    });
    header.appendChild(removeBtn);
  }

  group.appendChild(header);

  // Children container (holds both condition rows and sub-groups)
  const childrenDiv = document.createElement('div');
  childrenDiv.className = 'adv-group-children';
  group.appendChild(childrenDiv);

  // Add first condition row
  _addRow(childrenDiv);

  // Footer with add buttons
  const footer = document.createElement('div');
  footer.className = 'adv-group-footer';

  const addCondBtn = document.createElement('button');
  addCondBtn.className = 'adv-add-condition-btn';
  addCondBtn.textContent = t('adv_add_condition');
  addCondBtn.addEventListener('click', () => {
    if (_countConditions() >= MAX_CONDITIONS) return;
    _addRow(childrenDiv);
    _updateVisibilityAll();
  });
  footer.appendChild(addCondBtn);

  if (depth < MAX_DEPTH - 1) {
    const addSubBtn = document.createElement('button');
    addSubBtn.className = 'adv-add-condition-btn';
    addSubBtn.textContent = t('adv_add_subgroup');
    addSubBtn.addEventListener('click', () => {
      _addGroup(childrenDiv, depth + 1, false);
      _updateVisibilityAll();
      _onFilterChange();
    });
    footer.appendChild(addSubBtn);
  }

  group.appendChild(footer);
  container.appendChild(group);
  _updateVisibilityAll();
}

// ── Condition row ────────────────────────────────────────

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
  const flagGroup = document.createElement('optgroup');
  flagGroup.label = t('adv_group_flags');
  FLAG_FIELDS.forEach(([val, key]) => {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = t(key);
    flagGroup.appendChild(o);
  });
  fieldSel.appendChild(flagGroup);
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
    const parentChildren = container;
    row.remove();
    _handleEmptyParent(parentChildren);
    _updateVisibilityAll();
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
  _syncValInput(valInput, fieldSel.value, opSel.value);

  // Upgrade to custom styled selects
  upgradeSelect(fieldSel, (val) => {
    _updateOps(opSel, val);
    upgradeSelect(opSel);
    _syncValInput(valInput, val, opSel.value);
  });
  upgradeSelect(opSel, (val) => {
    _syncValInput(valInput, fieldSel.value, val);
    _onFilterChange();
  });
}

function _updateOps(opSel, fieldValue) {
  let ops;
  if (_FLAG_FIELD_SET.has(fieldValue)) {
    ops = FLAG_OPS;
  } else if (_TEXT_FIELD_SET.has(fieldValue)) {
    ops = TEXT_OPS;
  } else {
    ops = NUMERIC_OPS;
  }
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

function _syncValInput(valInput, fieldValue, opValue) {
  if (_FLAG_FIELD_SET.has(fieldValue)) {
    // Flag fields: value is encoded in the operator, hide the input
    valInput.style.display = 'none';
    valInput.value = opValue === '= true' ? 'true' : 'false';
  } else {
    valInput.style.display = '';
    valInput.type = _TEXT_FIELD_SET.has(fieldValue) ? 'text' : 'number';
    valInput.step = 'any';
  }
}

// ── Cleanup ──────────────────────────────────────────────

function _handleEmptyParent(childrenDiv) {
  // If group's children container is empty and it's not root, remove the group
  const directChildren = childrenDiv.querySelectorAll(':scope > .adv-row, :scope > .adv-group');
  if (directChildren.length > 0) return;

  const groupEl = childrenDiv.closest('.adv-group');
  if (!groupEl) return;

  if (groupEl.dataset.root === '1') {
    // Root group: add back an empty row
    _addRow(childrenDiv);
  } else {
    // Non-root empty group: remove it
    const parentChildrenDiv = groupEl.parentElement;
    groupEl.remove();
    _handleEmptyParent(parentChildrenDiv);
  }
}

// ── Visibility ───────────────────────────────────────────

function _updateVisibilityAll() {
  const rootGroup = document.querySelector('#advanced-filters > .adv-group');
  if (rootGroup) _updateGroupVisibility(rootGroup);
}

function _updateGroupVisibility(groupEl) {
  const childrenDiv = groupEl.querySelector(':scope > .adv-group-children');
  if (!childrenDiv) return;

  // Count direct children (rows + sub-groups)
  const directChildren = childrenDiv.querySelectorAll(':scope > .adv-row, :scope > .adv-group');
  const childCount = directChildren.length;

  // Logic toggle: visible when 2+ direct children
  const logicBtn = groupEl.querySelector(':scope > .adv-group-header > .adv-group-logic-btn');
  if (logicBtn) {
    logicBtn.style.visibility = childCount >= 2 ? 'visible' : 'hidden';
  }

  // Remove button on non-root groups: visible when parent has 2+ children
  if (groupEl.dataset.root !== '1') {
    const removeBtn = groupEl.querySelector(':scope > .adv-group-header > .adv-group-remove-btn');
    if (removeBtn) {
      const parentChildrenDiv = groupEl.parentElement;
      const siblingCount = parentChildrenDiv
        ? parentChildrenDiv.querySelectorAll(':scope > .adv-row, :scope > .adv-group').length
        : 1;
      removeBtn.style.display = siblingCount >= 2 ? '' : 'none';
    }
  }

  // Recurse into sub-groups
  const subGroups = childrenDiv.querySelectorAll(':scope > .adv-group');
  subGroups.forEach(sub => _updateGroupVisibility(sub));
}

// ── Condition counting ───────────────────────────────────

function _countConditions() {
  const panel = document.getElementById('advanced-filters');
  if (!panel) return 0;
  return panel.querySelectorAll('.adv-row').length;
}

// ── Serialization ────────────────────────────────────────

function _serializeGroup(groupEl) {
  const logicBtn = groupEl.querySelector(':scope > .adv-group-header > .adv-group-logic-btn');
  const logic = logicBtn ? logicBtn.dataset.logic : 'and';
  const childrenDiv = groupEl.querySelector(':scope > .adv-group-children');
  if (!childrenDiv) return null;

  const children = [];
  const directChildren = childrenDiv.querySelectorAll(':scope > .adv-row, :scope > .adv-group');

  for (const child of directChildren) {
    if (child.classList.contains('adv-row')) {
      const field = child.querySelector('.adv-field-select').value;
      const opRaw = child.querySelector('.adv-op-select').value;
      const valInput = child.querySelector('.adv-value-input');
      if (_FLAG_FIELD_SET.has(field)) {
        // Flag field: op encodes the boolean, serialize as op="=" value="true"/"false"
        const value = opRaw === '= true' ? 'true' : 'false';
        children.push({ field, op: '=', value });
      } else {
        const value = valInput.value.trim();
        if (field && opRaw && value !== '') {
          children.push({ field, op: opRaw, value });
        }
      }
    } else if (child.classList.contains('adv-group')) {
      const sub = _serializeGroup(child);
      if (sub && sub.children.length > 0) {
        children.push(sub);
      }
    }
  }

  return children.length > 0 ? { logic, children } : null;
}

function _onFilterChange() {
  const rootGroup = document.querySelector('#advanced-filters > .adv-group');
  if (!rootGroup) {
    state.advancedFilters = null;
    _triggerReload();
    return;
  }

  const tree = _serializeGroup(rootGroup);
  if (tree && tree.children.length > 0) {
    state.advancedFilters = JSON.stringify(tree);
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
