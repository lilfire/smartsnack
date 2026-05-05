// ── OFF Duplicates: combined duplicate-detection + merge-conflict modal ─
import { trapFocus } from './state.js';
import { t } from './i18n.js';
import { _fieldLabel, _volumeLabel, _esc } from './off-utils.js';
import { MERGE_CONFLICT_FIELDS, OFF_PROVIDED_FIELDS, USER_ONLY_MERGE_FIELDS } from './off-conflicts.js';

/**
 * Show a combined duplicate-detection + merge-conflict modal for the edit-save flow.
 *
 * Three scenarios:
 *  1. B (duplicate) is synced with OFF → A will be deleted, merged into B
 *  2. A (current) is synced but B is not → B will be deleted, merged into A
 *  3. Neither is synced → products merge (A survives, B deleted)
 *
 * Returns { scenario, choices: {field: value}, survivorId } or null on cancel.
 */
export function showDuplicateMergeModal(formData, duplicate, aIsSynced) {
  const bIsSynced = duplicate.is_synced_with_off;
  const aName = formData.name || '?';
  const bName = duplicate.name || '?';
  const aLabel = t('duplicate_merge_source_editing', { name: aName });
  const bLabel = t('duplicate_merge_source_other', { name: bName });

  let scenario, messageKey, fieldsToCheck;
  if (bIsSynced) {
    scenario = 'b_synced';
    messageKey = 'duplicate_merge_b_synced';
    fieldsToCheck = USER_ONLY_MERGE_FIELDS;
  } else if (aIsSynced) {
    scenario = 'a_synced';
    messageKey = 'duplicate_merge_a_synced';
    fieldsToCheck = USER_ONLY_MERGE_FIELDS;
  } else {
    scenario = 'neither';
    messageKey = 'duplicate_merge_neither';
    fieldsToCheck = MERGE_CONFLICT_FIELDS;
  }

  // Build auto-resolved values and conflicts
  const autoResolved = {};
  const conflicts = [];
  for (const f of fieldsToCheck) {
    const aVal = formData[f];
    const bVal = duplicate[f];
    const aEmpty = aVal === null || aVal === undefined || aVal === '';
    const bEmpty = bVal === null || bVal === undefined || bVal === '';

    if (aEmpty && bEmpty) continue;
    if (!aEmpty && !bEmpty && String(aVal) === String(bVal)) continue;

    if (aEmpty && !bEmpty) {
      autoResolved[f] = bVal;
    } else if (!aEmpty && bEmpty) {
      autoResolved[f] = aVal;
    } else {
      conflicts.push({ field: f, aVal, bVal });
    }
  }

  // Always show the dialog so the user can confirm the merge action
  return new Promise((resolve) => {
    const choices = {};
    // Default: keep A's values for conflicts
    for (const c of conflicts) choices[c.field] = c.aVal;

    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'conflict-modal';

    // Icon
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = '\u26A0\uFE0F';
    modal.appendChild(iconDiv);

    // Title
    const h3 = document.createElement('h3');
    h3.textContent = t('duplicate_found_title');
    modal.appendChild(h3);

    // Scenario message
    const msgEl = document.createElement('p');
    msgEl.textContent = t(messageKey, { match_type: duplicate.match_type, name: bName });
    modal.appendChild(msgEl);

    // Only show field choices section if there are conflicts
    const optionEls = [];
    if (conflicts.length > 0) {
      // Section header for field choices
      const chooseHeader = document.createElement('p');
      chooseHeader.style.cssText = 'font-size:13px;opacity:0.7;margin-top:12px';
      chooseHeader.textContent = t('duplicate_merge_choose_values');
      modal.appendChild(chooseHeader);

      // Bulk buttons
      const bulk = document.createElement('div');
      bulk.className = 'conflict-bulk';
      const keepAllA = document.createElement('button');
      keepAllA.textContent = t('duplicate_merge_keep_all_a', { name: aName });
      keepAllA.type = 'button';
      const keepAllB = document.createElement('button');
      keepAllB.textContent = t('duplicate_merge_keep_all_b', { name: bName });
      keepAllB.type = 'button';
      bulk.appendChild(keepAllA);
      bulk.appendChild(keepAllB);
      modal.appendChild(bulk);

      const fieldsContainer = document.createElement('div');
      fieldsContainer.className = 'conflict-fields';

      for (const c of conflicts) {
        const row = document.createElement('div');
        const label = document.createElement('div');
        label.className = 'conflict-row-label';
        label.textContent = _fieldLabel(c.field);
        row.appendChild(label);

        if (c.field === 'taste_score') {
          // Taste score uses a slider spanning both columns
          const slider = document.createElement('div');
          slider.className = 'conflict-taste-slider';

          const avg = Math.round(((c.aVal + c.bVal) / 2) * 2) / 2;
          choices[c.field] = avg;

          const labelA = document.createElement('div');
          labelA.className = 'conflict-taste-label conflict-taste-label-a';
          labelA.innerHTML = '<span class="conflict-taste-name">' + _esc(aLabel) + '</span>' +
            '<span class="conflict-taste-value">' + _esc(String(c.aVal)) + '</span>';

          const valDisplay = document.createElement('div');
          valDisplay.className = 'conflict-taste-current';
          valDisplay.textContent = String(avg);

          const labelB = document.createElement('div');
          labelB.className = 'conflict-taste-label conflict-taste-label-b';
          labelB.innerHTML = '<span class="conflict-taste-name">' + _esc(bLabel) + '</span>' +
            '<span class="conflict-taste-value">' + _esc(String(c.bVal)) + '</span>';

          const range = document.createElement('input');
          range.type = 'range';
          range.min = '0';
          range.max = '6';
          range.step = '0.5';
          range.value = String(avg);
          range.className = 'conflict-taste-range';

          const updateSlider = () => {
            const v = parseFloat(range.value);
            choices[c.field] = v;
            valDisplay.textContent = String(v);
          };
          range.addEventListener('input', updateSlider);

          optionEls.push({
            field: c.field, aVal: c.aVal, bVal: c.bVal,
            setA() { range.value = String(c.aVal); updateSlider(); },
            setB() { range.value = String(c.bVal); updateSlider(); },
          });

          const labelsRow = document.createElement('div');
          labelsRow.className = 'conflict-taste-labels';
          labelsRow.appendChild(labelA);
          labelsRow.appendChild(valDisplay);
          labelsRow.appendChild(labelB);
          slider.appendChild(labelsRow);
          slider.appendChild(range);
          row.appendChild(slider);
        } else {
          // Standard click-to-pick options
          const opts = document.createElement('div');
          opts.className = 'conflict-row-options';

          const displayA = c.field === 'volume' ? _volumeLabel(c.aVal) : c.aVal;
          const displayB = c.field === 'volume' ? _volumeLabel(c.bVal) : c.bVal;

          const optA = document.createElement('div');
          optA.className = 'conflict-option selected';
          optA.innerHTML =
            '<div class="conflict-option-source">' + _esc(aLabel) + '</div>' +
            '<div class="conflict-option-value">' + _esc(String(displayA)) + '</div>';

          const optB = document.createElement('div');
          optB.className = 'conflict-option';
          optB.innerHTML =
            '<div class="conflict-option-source">' + _esc(bLabel) + '</div>' +
            '<div class="conflict-option-value">' + _esc(String(displayB)) + '</div>';

          optionEls.push({
            field: c.field, aVal: c.aVal, bVal: c.bVal, optA, optB,
            setA() { optA.classList.add('selected'); optB.classList.remove('selected'); },
            setB() { optB.classList.add('selected'); optA.classList.remove('selected'); },
          });

          optA.addEventListener('click', () => {
            choices[c.field] = c.aVal;
            optA.classList.add('selected');
            optB.classList.remove('selected');
          });
          optB.addEventListener('click', () => {
            choices[c.field] = c.bVal;
            optB.classList.add('selected');
            optA.classList.remove('selected');
          });

          opts.appendChild(optA);
          opts.appendChild(optB);
          row.appendChild(opts);
        }
        fieldsContainer.appendChild(row);
      }

      keepAllA.addEventListener('click', () => {
        for (const o of optionEls) {
          choices[o.field] = o.aVal;
          o.setA();
        }
      });
      keepAllB.addEventListener('click', () => {
        for (const o of optionEls) {
          choices[o.field] = o.bVal;
          o.setB();
        }
      });

      modal.appendChild(fieldsContainer);
    }

    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const applyBtn = document.createElement('button');
    applyBtn.className = 'conflict-apply-btn';
    applyBtn.textContent = t('duplicate_merge_confirm');
    applyBtn.type = 'button';
    applyBtn.addEventListener('click', () => {
      bg.remove();
      resolve({ scenario, choices: Object.assign({}, autoResolved, choices) });
    });
    actions.appendChild(applyBtn);

    const skipBtn = document.createElement('button');
    skipBtn.className = 'scan-modal-btn-register';
    skipBtn.textContent = t('duplicate_not_same');
    skipBtn.type = 'button';
    skipBtn.addEventListener('click', () => { bg.remove(); resolve({ scenario: 'skip', choices: {} }); });
    actions.appendChild(skipBtn);

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
