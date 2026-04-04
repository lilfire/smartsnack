// tags.js — Tag input widget. Internal state: Map<number, string> (id → label).
let _tags = new Map();

export function initTagInput(existingTags) {
  _tags = new Map();
  for (const t of (existingTags || [])) {
    if (t && t.id != null && t.label != null) {
      _tags.set(Number(t.id), String(t.label));
    }
  }
  _renderPills();
  _bindInput();
}

export function getTagsForSave() {
  const input = document.getElementById('tag-input-ed');
  if (input && input.value.trim()) {
    input.value = '';
  }
  return Array.from(_tags.keys());
}

function _sortedEntries() {
  return Array.from(_tags.entries()).sort((a, b) => a[1].localeCompare(b[1]));
}

function _renderPills() {
  const field = document.getElementById('tag-field-ed');
  if (!field) return;
  field.querySelectorAll('.tag-pill').forEach(el => el.remove());
  const inputEl = field.querySelector('#tag-input-ed');
  for (const [id, label] of _sortedEntries()) {
    const span = document.createElement('span');
    span.className = 'tag-pill';
    span.dataset.tagId = id;
    span.appendChild(document.createTextNode(label));
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tag-remove';
    btn.setAttribute('aria-label', 'Remove tag ' + label);
    btn.textContent = '\u00D7';
    btn.addEventListener('click', () => {
      _tags.delete(id);
      _renderPills();
    });
    span.appendChild(btn);
    field.insertBefore(span, inputEl);
  }
}

async function _fetchSuggestions(q, list, input) {
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
        _tags.set(Number(s.id), s.label);
        _renderPills();
        input.value = '';
        list.hidden = true;
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

function _bindInput() {
  const field = document.getElementById('tag-field-ed');
  const input = document.getElementById('tag-input-ed');
  const list = document.getElementById('tag-suggestions-ed');
  if (!input || !list) return;

  if (field) {
    field.addEventListener('click', e => {
      if (e.target === field) input.focus();
    });
  }

  let _debounce = null;

  input.addEventListener('focus', () => {
    clearTimeout(_debounce);
    _fetchSuggestions('', list, input);
  });

  input.addEventListener('input', () => {
    clearTimeout(_debounce);
    const q = input.value.trim();
    if (!q) { list.hidden = true; return; }
    _debounce = setTimeout(() => _fetchSuggestions(q, list, input), 200);
  });

  input.addEventListener('keydown', async e => {
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
        items[idx < items.length - 1 ? idx + 1 : idx].classList.add('highlighted');
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      _clearHighlight(list);
      if (!highlighted) {
        items[items.length - 1].classList.add('highlighted');
      } else {
        const idx = items.indexOf(highlighted);
        items[idx > 0 ? idx - 1 : idx].classList.add('highlighted');
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlighted) {
        _tags.set(Number(highlighted.dataset.tagId), highlighted.dataset.tagLabel);
        _renderPills();
        input.value = '';
        list.hidden = true;
        _clearHighlight(list);
      } else if (input.value.trim()) {
        const label = input.value.trim();
        const tag = await _createTag(label);
        if (tag) {
          _tags.set(Number(tag.id), tag.label);
          _renderPills();
        }
        input.value = '';
        list.hidden = true;
      }
    } else if (e.key === 'Escape') {
      input.value = '';
      list.hidden = true;
      _clearHighlight(list);
    } else if (e.key === 'Tab' && !list.hidden) {
      const first = highlighted || items[0];
      if (first) {
        e.preventDefault();
        _tags.set(Number(first.dataset.tagId), first.dataset.tagLabel);
        _renderPills();
        input.value = '';
        list.hidden = true;
        _clearHighlight(list);
      }
    } else if (e.key === 'Backspace' && input.value === '') {
      const sorted = _sortedEntries();
      if (sorted.length) {
        _tags.delete(sorted[sorted.length - 1][0]);
        _renderPills();
      }
    }
  });

  input.addEventListener('blur', () => {
    setTimeout(() => {
      list.hidden = true;
      _clearHighlight(list);
    }, 150);
  });
}
