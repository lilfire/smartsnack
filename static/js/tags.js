let _tags = new Set();

export function initTagInput(existingTags) {
  _tags = new Set((existingTags || []).map(t => t.trim().toLowerCase()));
  _renderPills();
  _bindInput();
}

export function getTagsForSave() {
  // Flush any uncommitted text from the inline input before returning
  const input = document.getElementById('tag-input-ed');
  if (input && input.value.trim()) {
    _addTag(input.value);
    input.value = '';
  }
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
  // Remove existing pill elements only (preserve input and suggestions list)
  field.querySelectorAll('.tag-pill').forEach(el => el.remove());
  const input = field.querySelector('#tag-input-ed');
  for (const tag of [..._tags].sort()) {
    const span = document.createElement('span');
    span.className = 'tag-pill';
    const textNode = document.createTextNode(tag);
    span.appendChild(textNode);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tag-remove';
    btn.setAttribute('data-tag', tag);
    btn.textContent = '\u00D7';
    btn.addEventListener('click', () => {
      _tags.delete(tag);
      _renderPills();
    });
    span.appendChild(btn);
    field.insertBefore(span, input);
  }
}

function _fetchSuggestions(q, list, input) {
  return fetch(`/api/products/tags/suggestions?q=${encodeURIComponent(q)}`)
    .then(res => res.json())
    .then(suggestions => {
      // Filter out already-selected tags
      const filtered = suggestions.filter(
        s => !_tags.has(s.trim().toLowerCase())
      );
      list.innerHTML = '';
      if (!filtered.length) { list.hidden = true; return; }
      for (const s of filtered) {
        const li = document.createElement('li');
        li.textContent = s;
        li.addEventListener('mousedown', e => {
          e.preventDefault();
          _addTag(s);
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

function _bindInput() {
  const field = document.getElementById('tag-field-ed');
  const input = document.getElementById('tag-input-ed');
  const list = document.getElementById('tag-suggestions-ed');
  if (!input || !list) return;

  // Click anywhere on the field container focuses the input
  if (field) {
    field.addEventListener('click', (e) => {
      if (e.target === field) input.focus();
    });
  }

  let _debounce = null;

  // On focus: fetch with empty query to show available suggestions
  input.addEventListener('focus', () => {
    clearTimeout(_debounce);
    _fetchSuggestions('', list, input);
  });

  input.addEventListener('input', () => {
    clearTimeout(_debounce);
    const q = input.value.trim();
    if (!q) { list.hidden = true; return; }
    _debounce = setTimeout(() => {
      _fetchSuggestions(q, list, input);
    }, 200);
  });

  input.addEventListener('keydown', e => {
    const items = list.hidden ? [] : [...list.querySelectorAll('li')];
    const highlighted = _getHighlighted(list);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!items.length) return;
      const current = highlighted;
      _clearHighlight(list);
      if (!current) {
        items[0].classList.add('highlighted');
      } else {
        const idx = items.indexOf(current);
        if (idx < items.length - 1) items[idx + 1].classList.add('highlighted');
        else items[idx].classList.add('highlighted');
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      const current = highlighted;
      _clearHighlight(list);
      if (!current) {
        items[items.length - 1].classList.add('highlighted');
      } else {
        const idx = items.indexOf(current);
        if (idx > 0) items[idx - 1].classList.add('highlighted');
        else items[idx].classList.add('highlighted');
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlighted) {
        _addTag(highlighted.textContent);
        input.value = '';
        list.hidden = true;
        _clearHighlight(list);
      } else if (input.value.trim()) {
        // No highlighted item: create new tag from input text if non-empty
        _addTag(input.value);
        input.value = '';
        list.hidden = true;
      }
      // If input is empty and nothing highlighted: do nothing
    } else if (e.key === 'Escape') {
      input.value = '';
      list.hidden = true;
      _clearHighlight(list);
    } else if (e.key === 'Tab' && !list.hidden) {
      // Tab selects first highlighted or first visible suggestion
      const first = highlighted || items[0];
      if (first) {
        e.preventDefault();
        _addTag(first.textContent);
        input.value = '';
        list.hidden = true;
        _clearHighlight(list);
      }
    } else if (e.key === 'Backspace' && input.value === '') {
      // Backspace with empty input removes the alphabetically last tag
      const sorted = [..._tags].sort();
      if (sorted.length > 0) {
        _tags.delete(sorted[sorted.length - 1]);
        _renderPills();
      }
    }
    // Comma key: no longer a trigger — ignore
  });

  input.addEventListener('blur', () => {
    setTimeout(() => {
      list.hidden = true;
      _clearHighlight(list);
    }, 150);
  });
}
