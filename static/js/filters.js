// ── Filters & Sorting ───────────────────────────────
import { state, esc, upgradeSelect } from './state.js';
import { t } from './i18n.js';

export function buildFilters() {
  if (!state.cachedStats) return;
  const row = document.getElementById('filter-row');
  if (!row) return;
  // Build filter pills using DOM to avoid XSS from category names in onclick
  row.innerHTML = '';
  const allBtn = document.createElement('button');
  allBtn.className = 'pill' + (state.currentFilter.length === 0 ? ' active' : '');
  allBtn.textContent = t('filter_all') + ' (' + state.cachedStats.total + ')';
  allBtn.addEventListener('click', () => window.setFilter('all'));
  row.appendChild(allBtn);

  state.categories.forEach((c) => {
    const n = state.cachedStats.type_counts[c.name] || 0;
    const active = state.currentFilter.indexOf(c.name) >= 0;
    const btn = document.createElement('button');
    btn.className = 'pill' + (active ? ' active' : '');
    btn.textContent = c.emoji + ' ' + c.label + ' (' + n + ')';
    btn.addEventListener('click', () => window.setFilter(c.name));
    row.appendChild(btn);
  });
  updateFilterToggle();
}

export function updateFilterToggle() {
  const tog = document.getElementById('filter-toggle');
  const label = document.getElementById('filter-toggle-label');
  if (!tog || !label) return;
  if (state.currentFilter.length > 0) {
    const names = state.currentFilter.map((f) => {
      const cat = state.categories.find((c) => c.name === f);
      return cat ? (cat.emoji + ' ' + cat.label) : f;
    });
    label.textContent = names.length <= 2 ? names.join(', ') : t('filter_count', { count: names.length });
    tog.classList.add('has-filter');
  } else {
    label.textContent = t('filter_all');
    tog.classList.remove('has-filter');
  }
}

export function toggleFilters() {
  const row = document.getElementById('filter-row');
  const tog = document.getElementById('filter-toggle');
  if (row) row.classList.toggle('open');
  if (tog) tog.classList.toggle('open');
}

export function buildTypeSelect() {
  const sel = document.getElementById('f-type');
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '';
  state.categories.slice().sort((a, b) => a.label.localeCompare(b.label)).forEach((c) => {
    const o = document.createElement('option');
    o.value = c.name;
    o.textContent = c.emoji + ' ' + c.label;
    sel.appendChild(o);
  });
  if (prev) {
    for (let i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === prev) { sel.value = prev; break; }
    }
  }
  upgradeSelect(sel);
}

export function sortIndicator(col) {
  if (state.sortCol !== col) return '<span class="sort-arrow dim">\u2195</span>';
  return state.sortDir === 'asc' ? '<span class="sort-arrow">\u2191</span>' : '<span class="sort-arrow">\u2193</span>';
}

export function setSort(col) {
  if (state.sortCol === col) {
    state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
  } else {
    state.sortCol = col;
    state.sortDir = col === 'name' ? 'asc' : 'desc';
  }
  rerender();
}

export function applySorting(res) {
  return res.slice().sort((a, b) => {
    let va = a[state.sortCol], vb = b[state.sortCol];
    if (typeof va === 'string' || typeof vb === 'string') {
      va = (va || '').toLowerCase();
      vb = (vb || '').toLowerCase();
      return state.sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    if (va == null) va = state.sortDir === 'asc' ? Infinity : -Infinity;
    if (vb == null) vb = state.sortDir === 'asc' ? Infinity : -Infinity;
    return state.sortDir === 'asc' ? va - vb : vb - va;
  });
}

export function rerender() {
  // Lazy import to avoid circular dependency
  import('./render.js').then((mod) => {
    const searchEl = document.getElementById('search-input');
    mod.renderResults(state.cachedResults, searchEl ? searchEl.value.trim() : '');
  }).catch((e) => { console.error('Failed to load render module:', e); });
}
