let _tags = new Set();

export function initTagInput(existingTags) {
  _tags = new Set((existingTags || []).map(t => t.trim().toLowerCase()));
  _renderPills();
  _bindInput();
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
  const container = document.getElementById('tag-container-ed');
  if (!container) return;
  container.innerHTML = '';
  for (const tag of [..._tags].sort()) {
    container.insertAdjacentHTML(
      'beforeend',
      `<span class="tag-pill">${_escapeHtml(tag)}<button type="button" class="tag-remove" data-tag="${_escapeHtml(tag)}">&times;</button></span>`
    );
  }
  container.querySelectorAll('.tag-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      _tags.delete(btn.dataset.tag);
      _renderPills();
    });
  });
}

function _bindInput() {
  const input = document.getElementById('tag-input-ed');
  const list = document.getElementById('tag-suggestions-ed');
  if (!input || !list) return;

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
    }
  });

  input.addEventListener('blur', () => {
    setTimeout(() => { list.hidden = true; }, 150);
  });
}

function _escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
