// tags.js — Tag input widget with modal + chips UI.
import { t } from './i18n.js';

// Internal state: Map<number, string> (id -> label).
let _tags = new Map();

export function initTagInput(existingTags) {
  _tags = new Map();
  for (const t of (existingTags || [])) {
    if (t && t.id != null && t.label != null) {
      _tags.set(Number(t.id), String(t.label));
    }
  }
  _renderPills();
  _setupAddTagButton();
}

export function getTagsForSave() {
  return Array.from(_tags.keys());
}

function _sortedEntries() {
  return Array.from(_tags.entries()).sort((a, b) => a[1].localeCompare(b[1]));
}

function _renderPills() {
  const field = document.getElementById('tag-field-ed');
  if (!field) return;
  field.querySelectorAll('.tag-pill').forEach(el => el.remove());
  const btn = field.querySelector('#add-tag-btn');
  for (const [id, label] of _sortedEntries()) {
    const span = document.createElement('span');
    span.className = 'tag-pill';
    span.dataset.tagId = id;
    span.appendChild(document.createTextNode(label));
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'tag-remove';
    removeBtn.setAttribute('aria-label', t('tag_remove_aria_label', { label }));
    removeBtn.textContent = '\u00D7';
    removeBtn.addEventListener('click', () => {
      _tags.delete(id);
      _renderPills();
    });
    span.appendChild(removeBtn);
    field.insertBefore(span, btn);
  }
}

function _setupAddTagButton() {
  const field = document.getElementById('tag-field-ed');
  if (!field) return;
  if (field.querySelector('#add-tag-btn')) return;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.id = 'add-tag-btn';
  btn.className = 'tag-add-btn';
  btn.textContent = t('tag_add_btn');
  btn.setAttribute('aria-haspopup', 'dialog');
  btn.addEventListener('click', _openModal);
  field.appendChild(btn);
}

async function _fetchSuggestions(q, list, input, onSelect) {
  try {
    const res = await fetch('/api/tags?q=' + encodeURIComponent(q));
    const suggestions = await res.json();
    const filtered = suggestions.filter(s => !_tags.has(Number(s.id)));
    list.innerHTML = '';
    if (!filtered.length) { list.hidden = true; return; }
    for (const s of filtered) {
      const li = document.createElement('li');
      li.dataset.tagId = s.id;
      li.dataset.tagLabel = s.label;
      li.textContent = s.label;
      li.addEventListener('mousedown', e => {
        e.preventDefault();
        onSelect(s);
      });
      list.appendChild(li);
    }
    list.hidden = false;
  } catch (_) {
    list.hidden = true;
  }
}

async function _createTag(label) {
  try {
    const res = await fetch('/api/tags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'SmartSnack' },
      body: JSON.stringify({ label }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (_) {
    return null;
  }
}

function _getHighlighted(list) {
  return list.querySelector('li.highlighted');
}

function _clearHighlight(list) {
  list.querySelectorAll('li.highlighted').forEach(li => li.classList.remove('highlighted'));
}

function _openModal() {
  const overlay = document.createElement('div');
  overlay.id = 'tag-modal-overlay';
  overlay.className = 'tag-modal-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', t('tag_modal_aria_label'));

  const modal = document.createElement('div');
  modal.className = 'tag-modal';

  const input = document.createElement('input');
  input.type = 'text';
  input.id = 'tag-modal-input';
  input.className = 'tag-modal-input';
  input.setAttribute('placeholder', t('tag_modal_search_placeholder'));
  input.setAttribute('autocomplete', 'off');

  const list = document.createElement('ul');
  list.id = 'tag-modal-suggestions';
  list.className = 'tag-suggestions';
  list.hidden = true;

  const actions = document.createElement('div');
  actions.className = 'tag-modal-actions';

  const confirmBtn = document.createElement('button');
  confirmBtn.type = 'button';
  confirmBtn.id = 'tag-modal-confirm';
  confirmBtn.className = 'tag-modal-confirm';
  confirmBtn.textContent = t('tag_modal_confirm');

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.id = 'tag-modal-cancel';
  cancelBtn.className = 'tag-modal-cancel';
  cancelBtn.textContent = t('tag_modal_cancel');

  actions.appendChild(confirmBtn);
  actions.appendChild(cancelBtn);
  modal.appendChild(input);
  modal.appendChild(list);
  modal.appendChild(actions);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  _bindModal(overlay, input, list, confirmBtn, cancelBtn);
  input.focus();
  _fetchSuggestions('', list, input, s => { _addTagObj(s); _closeModal(); });
}

function _closeModal() {
  const overlay = document.getElementById('tag-modal-overlay');
  if (overlay) overlay.remove();
}

function _addTagObj(s) {
  _tags.set(Number(s.id), s.label);
  _renderPills();
}

function _bindModal(overlay, input, list, confirmBtn, cancelBtn) {
  let _debounce = null;

  function _onSelect(s) {
    _addTagObj(s);
    _closeModal();
  }

  async function _confirmAdd() {
    const highlighted = _getHighlighted(list);
    if (highlighted) {
      _tags.set(Number(highlighted.dataset.tagId), highlighted.dataset.tagLabel);
      _renderPills();
      _closeModal();
      return;
    }
    const label = input.value.trim();
    if (!label) { _closeModal(); return; }
    const tag = await _createTag(label);
    if (tag) {
      _tags.set(Number(tag.id), tag.label);
      _renderPills();
    }
    _closeModal();
  }

  input.addEventListener('input', () => {
    clearTimeout(_debounce);
    const q = input.value.trim();
    if (!q) {
      _fetchSuggestions('', list, input, _onSelect);
      return;
    }
    _debounce = setTimeout(() => {
      _fetchSuggestions(q, list, input, _onSelect);
    }, 200);
  });

  input.addEventListener('keydown', e => {
    const items = list.hidden ? [] : [...list.querySelectorAll('li')];
    const highlighted = _getHighlighted(list);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!items.length) return;
      _clearHighlight(list);
      if (!highlighted) {
        items[0].classList.add('highlighted');
      } else {
        const idx = items.indexOf(highlighted);
        items[Math.min(idx + 1, items.length - 1)].classList.add('highlighted');
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      _clearHighlight(list);
      if (!highlighted) {
        items[items.length - 1].classList.add('highlighted');
      } else {
        const idx = items.indexOf(highlighted);
        items[Math.max(idx - 1, 0)].classList.add('highlighted');
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      _confirmAdd();
    } else if (e.key === 'Escape') {
      _closeModal();
    }
  });

  confirmBtn.addEventListener('click', _confirmAdd);
  cancelBtn.addEventListener('click', _closeModal);
  overlay.addEventListener('click', e => {
    if (e.target === overlay) _closeModal();
  });
}
