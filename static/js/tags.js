let _tags = new Set();

export function initTagInput(existingTags) {
  _tags = new Set((existingTags || []).map(t => t.trim().toLowerCase()));
  _renderPills();
  _setupAddTagButton();
}

export function getTagsForSave() {
  return Array.from(_tags);
}

function _addTag(value) {
  const tag = value.trim().toLowerCase();
  if (!tag || tag.length > 50 || _tags.has(tag)) return;
  _tags.add(tag);
  _renderPills();
}

function _renderPills() {
  const field = document.getElementById('tag-field-ed');
  if (!field) return;
  field.querySelectorAll('.tag-pill').forEach(el => el.remove());
  const btn = field.querySelector('#add-tag-btn');
  for (const tag of [..._tags].sort()) {
    const span = document.createElement('span');
    span.className = 'tag-pill';
    span.appendChild(document.createTextNode(tag));
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'tag-remove';
    removeBtn.setAttribute('data-tag', tag);
    removeBtn.textContent = '\u00D7';
    removeBtn.setAttribute('aria-label', 'Remove tag ' + tag);
    removeBtn.addEventListener('click', () => {
      _tags.delete(tag);
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
  btn.textContent = '+ Add Tag';
  btn.setAttribute('aria-haspopup', 'dialog');
  btn.addEventListener('click', _openModal);
  field.appendChild(btn);
}

function _fetchSuggestions(q, list, input, onSelect) {
  return fetch(`/api/products/tags/suggestions?q=${encodeURIComponent(q)}`)
    .then(res => res.json())
    .then(suggestions => {
      const filtered = suggestions.filter(s => !_tags.has(s.trim().toLowerCase()));
      list.innerHTML = '';
      if (!filtered.length) { list.hidden = true; return; }
      for (const s of filtered) {
        const li = document.createElement('li');
        li.textContent = s;
        li.addEventListener('mousedown', e => {
          e.preventDefault();
          onSelect(s);
          input.value = '';
          list.hidden = true;
        });
        list.appendChild(li);
      }
      list.hidden = false;
    })
    .catch(() => { list.hidden = true; });
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
  overlay.setAttribute('aria-label', 'Add tag');

  const modal = document.createElement('div');
  modal.className = 'tag-modal';

  const input = document.createElement('input');
  input.type = 'text';
  input.id = 'tag-modal-input';
  input.className = 'tag-modal-input';
  input.setAttribute('placeholder', 'Type to search or add tag\u2026');
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
  confirmBtn.textContent = 'Add';

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.id = 'tag-modal-cancel';
  cancelBtn.className = 'tag-modal-cancel';
  cancelBtn.textContent = 'Cancel';

  actions.appendChild(confirmBtn);
  actions.appendChild(cancelBtn);
  modal.appendChild(input);
  modal.appendChild(list);
  modal.appendChild(actions);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  _bindModal(overlay, input, list, confirmBtn, cancelBtn);
  input.focus();
  _fetchSuggestions('', list, input, tag => { _addTag(tag); _closeModal(); });
}

function _closeModal() {
  const overlay = document.getElementById('tag-modal-overlay');
  if (overlay) overlay.remove();
}

function _bindModal(overlay, input, list, confirmBtn, cancelBtn) {
  let _debounce = null;

  function _onSelect(tag) {
    _addTag(tag);
    _closeModal();
  }

  function _confirmAdd() {
    const highlighted = _getHighlighted(list);
    const value = highlighted ? highlighted.textContent : input.value;
    if (value.trim()) _addTag(value);
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
