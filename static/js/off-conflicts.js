// ── OFF Conflicts: edit-duplicate modal and merge-conflict modal ─
import { trapFocus } from './state.js';
import { t } from './i18n.js';
import { _fieldLabel, _esc } from './off-utils.js';

/**
 * Fields eligible for conflict resolution during merge (excludes identity fields).
 */
export const MERGE_CONFLICT_FIELDS = [
  'brand', 'stores', 'ingredients', 'taste_note', 'taste_score',
  'kcal', 'energy_kj', 'carbs', 'sugar', 'fat', 'saturated_fat',
  'protein', 'fiber', 'salt', 'weight', 'portion', 'volume', 'price',
  'est_pdcaas', 'est_diaas',
];

/**
 * Fields whose values originate from OpenFoodFacts when a product is synced.
 */
export const OFF_PROVIDED_FIELDS = new Set([
  'name', 'ean', 'brand', 'stores', 'ingredients',
  'kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar',
  'protein', 'fiber', 'salt', 'weight', 'portion',
]);

/**
 * Non-OFF (user-only) merge fields — used when one product is OFF-synced.
 */
export const USER_ONLY_MERGE_FIELDS = MERGE_CONFLICT_FIELDS.filter(f => !OFF_PROVIDED_FIELDS.has(f));

export function showEditDuplicateModal(duplicate) {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal';
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '\u26A0\uFE0F';
    modal.appendChild(iconDiv);
    const h3 = document.createElement('h3');
    h3.textContent = t('duplicate_found_title');
    modal.appendChild(h3);
    const pEl = document.createElement('p');
    const msgKey = duplicate.is_synced_with_off ? 'duplicate_edit_synced' : 'duplicate_edit_unsynced';
    pEl.textContent = t(msgKey, { match_type: duplicate.match_type, name: duplicate.name });
    modal.appendChild(pEl);
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    if (duplicate.is_synced_with_off) {
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'scan-modal-btn-register confirm-yes';
      deleteBtn.textContent = t('duplicate_action_delete');
      deleteBtn.addEventListener('click', () => { bg.remove(); resolve('delete'); });
      actions.appendChild(deleteBtn);
    } else {
      const mergeBtn = document.createElement('button');
      mergeBtn.className = 'scan-modal-btn-register confirm-yes';
      mergeBtn.textContent = t('duplicate_action_merge_into');
      mergeBtn.addEventListener('click', () => { bg.remove(); resolve('merge'); });
      actions.appendChild(mergeBtn);
    }
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel confirm-no';
    cancelBtn.textContent = t('btn_cancel');
    cancelBtn.addEventListener('click', () => { bg.remove(); resolve('cancel'); });
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);
    trapFocus(bg);
  });
}

/**
 * Show a conflict resolution modal when merging two products that both have
 * values for the same fields.  Returns a dict of {field: chosenValue} or null
 * if the user cancels.
 */
export function showMergeConflictModal(formData, duplicate, offAppliedFields) {
  // Build list of conflicting fields
  const resolved = {};  // fields auto-resolved by OFF data
  const conflicts = [];
  for (const f of MERGE_CONFLICT_FIELDS) {
    const formVal = formData[f];
    const dupVal = duplicate[f];
    const formEmpty = formVal === null || formVal === undefined || formVal === '' || formVal === 0;
    const dupEmpty = dupVal === null || dupVal === undefined || dupVal === '' || dupVal === 0;

    // If OFF provided this field, auto-resolve to form value (which has the OFF value)
    if (offAppliedFields && offAppliedFields.has(f) && !formEmpty) {
      resolved[f] = formVal;
      continue;
    }

    if (!formEmpty && !dupEmpty && String(formVal) !== String(dupVal)) {
      conflicts.push({ field: f, formVal, dupVal });
    }
  }

  if (conflicts.length === 0) return Promise.resolve(resolved);

  return new Promise((resolve) => {
    const choices = {};
    // Default: keep current (form) values
    for (const c of conflicts) choices[c.field] = c.formVal;

    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'conflict-modal';

    const h3 = document.createElement('h3');
    h3.textContent = t('merge_conflict_title');
    modal.appendChild(h3);
    const desc = document.createElement('p');
    desc.textContent = t('merge_conflict_desc', { name: duplicate.name });
    modal.appendChild(desc);

    // Bulk buttons
    const bulk = document.createElement('div');
    bulk.className = 'conflict-bulk';
    const keepAllCurrent = document.createElement('button');
    keepAllCurrent.textContent = t('merge_keep_all_current');
    keepAllCurrent.type = 'button';
    const keepAllDup = document.createElement('button');
    keepAllDup.textContent = t('merge_keep_all_other');
    keepAllDup.type = 'button';
    bulk.appendChild(keepAllCurrent);
    bulk.appendChild(keepAllDup);
    modal.appendChild(bulk);

    const fieldsContainer = document.createElement('div');
    fieldsContainer.className = 'conflict-fields';

    const optionEls = [];

    for (const c of conflicts) {
      const row = document.createElement('div');
      const label = document.createElement('div');
      label.className = 'conflict-row-label';
      label.textContent = _fieldLabel(c.field);
      row.appendChild(label);

      const opts = document.createElement('div');
      opts.className = 'conflict-row-options';

      const optCurrent = document.createElement('div');
      optCurrent.className = 'conflict-option selected';
      optCurrent.innerHTML =
        '<div class="conflict-option-source">' + t('merge_source_current') + '</div>' +
        '<div class="conflict-option-value">' + _esc(String(c.formVal)) + '</div>';

      const optDup = document.createElement('div');
      optDup.className = 'conflict-option';
      optDup.innerHTML =
        '<div class="conflict-option-source">' + t('merge_source_other') + '</div>' +
        '<div class="conflict-option-value">' + _esc(String(c.dupVal)) + '</div>';

      optionEls.push({ field: c.field, formVal: c.formVal, dupVal: c.dupVal, optCurrent, optDup });

      optCurrent.addEventListener('click', () => {
        choices[c.field] = c.formVal;
        optCurrent.classList.add('selected');
        optDup.classList.remove('selected');
      });
      optDup.addEventListener('click', () => {
        choices[c.field] = c.dupVal;
        optDup.classList.add('selected');
        optCurrent.classList.remove('selected');
      });

      opts.appendChild(optCurrent);
      opts.appendChild(optDup);
      row.appendChild(opts);
      fieldsContainer.appendChild(row);
    }

    keepAllCurrent.addEventListener('click', () => {
      for (const o of optionEls) {
        choices[o.field] = o.formVal;
        o.optCurrent.classList.add('selected');
        o.optDup.classList.remove('selected');
      }
    });
    keepAllDup.addEventListener('click', () => {
      for (const o of optionEls) {
        choices[o.field] = o.dupVal;
        o.optDup.classList.add('selected');
        o.optCurrent.classList.remove('selected');
      }
    });

    modal.appendChild(fieldsContainer);

    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const applyBtn = document.createElement('button');
    applyBtn.className = 'conflict-apply-btn';
    applyBtn.textContent = t('merge_apply');
    applyBtn.type = 'button';
    applyBtn.addEventListener('click', () => { bg.remove(); resolve(Object.assign({}, resolved, choices)); });
    actions.appendChild(applyBtn);

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'scan-modal-btn-cancel confirm-no';
    cancelBtn.textContent = t('btn_cancel');
    cancelBtn.type = 'button';
    cancelBtn.addEventListener('click', () => { bg.remove(); resolve(null); });
    actions.appendChild(cancelBtn);
    modal.appendChild(actions);

    bg.appendChild(modal);
    document.body.appendChild(bg);
    trapFocus(bg);
  });
}
