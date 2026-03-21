// ── Advanced Filters (Recursive Nested Groups) ─────────────────────────
import { state, upgradeSelect } from './state.js';
import { t } from './i18n.js';
import { updateFilterToggle } from './filters.js';
import { getFlagConfig } from './render.js';

// Field definitions: [field_key, i18n_key]
const TEXT_FIELDS = [
  ['name', 'label_name'],
  ['brand', 'label_brand'],
  ['stores', 'label_stores'],
  ['ingredients', 'label_ingredients'],
  ['ean', 'edit_label_ean'],
];
const CATEGORY_FIELD = ['type', 'label_category'];
const CATEGORY_OPS = [
  ['', 'adv_op_flag_select'],
  ['=', 'adv_op_is'],
  ['!=', 'adv_op_is_not'],
];
const NUMERIC_FIELDS = [
  ['kcal', 'label_kcal'],
  ['energy_kj', 'label_energy_kj'],
  ['protein', 'label_protein'],
  ['fat', 'label_fat'],
  ['saturated_fat', 'label_saturated_fat'],
  ['carbs', 'label_carbs'],
  ['sugar', 'label_sugar'],
  ['fiber', 'label_fiber'],
  ['salt', 'label_salt'],
  ['price', 'label_price'],
  ['weight', 'label_weight'],
  ['portion', 'label_portion'],
  ['volume', 'label_volume'],
  ['taste_score', 'weight_label_taste_score'],
  ['est_pdcaas', 'weight_label_est_pdcaas'],
  ['est_diaas', 'weight_label_est_diaas'],
  ['total_score', 'adv_field_total_score'],
  ['completeness', 'completeness_label'],
];

const TEXT_OPS = [
  ['contains', 'adv_op_contains'],
  ['=', 'adv_op_eq'],
  ['!=', 'adv_op_neq'],
  ['is_not_set', 'adv_op_is_not_set'],
  ['is_set', 'adv_op_has_value'],
];
const NUMERIC_OPS = [
  ['<', 'adv_op_lt'],
  ['>', 'adv_op_gt'],
  ['=', 'adv_op_eq'],
  ['<=', 'adv_op_lte'],
  ['>=', 'adv_op_gte'],
  ['!=', 'adv_op_neq'],
  ['is_not_set', 'adv_op_is_not_set'],
  ['is_set', 'adv_op_has_value'],
];

function _getFlagFields() {
  const cfg = getFlagConfig();
  return Object.entries(cfg).map(([name, c]) => ['flag:' + name, c.label]);
}
const FLAG_OPS = [
  ['', 'adv_op_flag_select'],
  ['= true', 'adv_op_is_set'],
  ['= false', 'adv_op_is_not_set'],
];

const _TEXT_FIELD_SET = new Set(TEXT_FIELDS.map(f => f[0]));
const _CATEGORY_FIELD_NAME = CATEGORY_FIELD[0];
function _getFlagFieldSet() {
  return new Set(_getFlagFields().map(f => f[0]));
}
const MAX_DEPTH = 4;
const MAX_CONDITIONS = 20;
let _rowCounter = 0;

export function rebuildAdvancedFilters() {
  const panel = document.getElementById('advanced-filters');
  if (!panel || !panel.classList.contains('open')) return;
  _buildPanel(panel);
}

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
    panel.innerHTML = '';
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
  // Category field (standalone group)
  const catGroup = document.createElement('optgroup');
  catGroup.label = t('adv_group_category');
  const catOpt = document.createElement('option');
  catOpt.value = CATEGORY_FIELD[0];
  catOpt.textContent = t(CATEGORY_FIELD[1]);
  catGroup.appendChild(catOpt);
  fieldSel.appendChild(catGroup);

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
  _getFlagFields().forEach(([val, label]) => {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = label;
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

  // Trigger filter on value change (debounced) + numeric validation
  let valTimer = null;
  valInput.addEventListener('input', () => {
    _validateNumericInput(valInput);
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
  if (fieldValue === _CATEGORY_FIELD_NAME) {
    ops = CATEGORY_OPS;
  } else if (_getFlagFieldSet().has(fieldValue)) {
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

function _validateNumericInput(valInput) {
  if (!valInput.dataset.numeric) {
    valInput.classList.remove('adv-value-invalid');
    return;
  }
  const v = valInput.value.trim();
  if (v === '' || /^-?\d*\.?\d+$/.test(v)) {
    valInput.classList.remove('adv-value-invalid');
  } else {
    valInput.classList.add('adv-value-invalid');
  }
}

function _syncValInput(valInput, fieldValue, opValue) {
  valInput.classList.remove('adv-value-invalid');
  const row = valInput.closest('.adv-row');
  // Remove any existing category select (may be inside a custom-select-wrap wrapper)
  if (row) {
    const existingWrapper = row.querySelector('.adv-category-wrapper');
    const existingCatSel = row.querySelector('.adv-category-select');
    if (existingWrapper || existingCatSel) {
      if (existingWrapper) existingWrapper.remove();
      if (existingCatSel) existingCatSel.remove();
      valInput.value = '';
    }
  }

  if (fieldValue === _CATEGORY_FIELD_NAME) {
    // Category field: show a combobox instead of text input
    valInput.style.display = 'none';
    const catSel = document.createElement('select');
    catSel.className = 'adv-category-select adv-value-input';
    // Add "not selected" placeholder
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '__none__';
    placeholderOpt.textContent = t('adv_op_flag_select');
    catSel.appendChild(placeholderOpt);
    // Populate from state.categories
    state.categories.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach(c => {
      const o = document.createElement('option');
      o.value = c.name;
      o.textContent = (c.emoji ? c.emoji + ' ' : '') + c.label;
      catSel.appendChild(o);
    });
    // Add "Uncategorized" option for products with no category
    const uncatOpt = document.createElement('option');
    uncatOpt.value = '';
    uncatOpt.textContent = '\u{1F4E6} ' + t('uncategorized');
    catSel.appendChild(uncatOpt);
    // Restore previous value if valid
    if (valInput.value) {
      for (let i = 0; i < catSel.options.length; i++) {
        if (catSel.options[i].value === valInput.value) { catSel.value = valInput.value; break; }
      }
    }
    // Sync hidden input value
    valInput.value = catSel.value;
    // Insert before the remove button
    const removeBtn = row.querySelector('.adv-remove-btn');
    row.insertBefore(catSel, removeBtn);
    catSel.addEventListener('change', () => {
      valInput.value = catSel.value;
      _onFilterChange();
    });
    upgradeSelect(catSel, (val) => {
      valInput.value = val;
      _onFilterChange();
    });
    // Add a marker class on the wrapper for cleanup
    const wrapper = catSel.closest('.custom-select-wrap');
    if (wrapper) wrapper.classList.add('adv-category-wrapper');
  } else if (_getFlagFieldSet().has(fieldValue)) {
    // Flag fields: value is encoded in the operator, hide the input
    valInput.style.display = 'none';
    valInput.value = opValue === '= true' ? 'true' : opValue === '= false' ? 'false' : '';
  } else if (opValue === 'is_not_set' || opValue === 'is_set') {
    // "is not set" / "has value" needs no value
    valInput.style.display = 'none';
    valInput.value = '';
  } else {
    valInput.style.display = '';
    const isNumeric = !_TEXT_FIELD_SET.has(fieldValue);
    valInput.type = 'text';
    if (isNumeric) {
      valInput.inputMode = 'decimal';
      valInput.dataset.numeric = '1';
    } else {
      delete valInput.dataset.numeric;
      valInput.inputMode = '';
    }
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
      if (_getFlagFieldSet().has(field)) {
        // Flag field: op encodes the boolean, serialize as op="=" value="true"/"false"
        if (opRaw === '') continue; // no selection yet
        const value = opRaw === '= true' ? 'true' : 'false';
        children.push({ field, op: '=', value });
      } else if (opRaw === 'is_not_set' || opRaw === 'is_set') {
        // "is not set" / "has value" needs no value
        children.push({ field, op: opRaw, value: '' });
      } else {
        const value = valInput.value.trim();
        if (field && opRaw && value !== '' && value !== '__none__') {
          // Skip invalid numeric values
          if (valInput.dataset.numeric && !/^-?\d*\.?\d+$/.test(value)) continue;
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
    import('./products.js').then(mod => { mod.loadData(); }).catch(e => { console.error('Failed to load products module:', e); });
  }, 100);
}
