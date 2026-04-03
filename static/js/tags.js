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

  input.addEventListener('input', () => {
    clearTimeout(_debounce);
    const q = input.value.trim();
    if (!q) { list.hidden = true; return; }
    _debounce = setTimeout(async () => {
      try {
        const res = await fetch(`/api/products/tags/suggestions?q=${encodeURIComponent(q)}`);
        const suggestions = await res.json();
        list.innerHTML = '';
        if (!suggestions.length) { list.hidden = true; return; }
        for (const s of suggestions) {
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
      } catch (_) {
        list.hidden = true;
      }
    }, 200);
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      _addTag(input.value);
      input.value = '';
      list.hidden = true;
    } else if (e.key === 'Tab' && !list.hidden) {
      // Tab completes the first visible suggestion
      const first = list.querySelector('li');
      if (first) {
        e.preventDefault();
        _addTag(first.textContent);
        input.value = '';
        list.hidden = true;
      }
    } else if (e.key === 'Backspace' && input.value === '') {
      // Backspace with empty input removes the last tag
      const sorted = [..._tags].sort();
      if (sorted.length > 0) {
        _tags.delete(sorted[sorted.length - 1]);
        _renderPills();
      }
    }
  });

  input.addEventListener('blur', () => {
    setTimeout(() => { list.hidden = true; }, 150);
  });
}

function _escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
