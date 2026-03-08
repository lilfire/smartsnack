// ── Filters & Sorting ───────────────────────────────
import { state, esc, upgradeSelect } from './state.js';
import { t } from './i18n.js';

export function buildFilters() {
  if (!state.cachedStats) return;
  var row = document.getElementById('filter-row');
  var h = '<button class="pill ' + (state.currentFilter.length === 0 ? 'active' : '') + '" onclick="setFilter(\'all\')">' + t('filter_all') + ' (' + state.cachedStats.total + ')</button>';
  state.categories.forEach(function(c) {
    var n = state.cachedStats.type_counts[c.name] || 0;
    var active = state.currentFilter.indexOf(c.name) >= 0;
    h += '<button class="pill ' + (active ? 'active' : '') + '" onclick="setFilter(\'' + esc(c.name) + '\')">' + esc(c.emoji) + ' ' + esc(c.label) + ' (' + n + ')</button>';
  });
  row.innerHTML = h;
  updateFilterToggle();
}

export function updateFilterToggle() {
  var tog = document.getElementById('filter-toggle');
  var label = document.getElementById('filter-toggle-label');
  if (!tog || !label) return;
  if (state.currentFilter.length > 0) {
    var names = state.currentFilter.map(function(f) {
      var cat = state.categories.find(function(c) { return c.name === f; });
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
  var row = document.getElementById('filter-row');
  var tog = document.getElementById('filter-toggle');
  row.classList.toggle('open');
  tog.classList.toggle('open');
}

export function buildTypeSelect() {
  var sel = document.getElementById('f-type');
  var prev = sel.value;
  sel.innerHTML = '';
  state.categories.slice().sort(function(a, b) { return a.label.localeCompare(b.label); }).forEach(function(c) {
    var o = document.createElement('option');
    o.value = c.name;
    o.textContent = c.emoji + ' ' + c.label;
    sel.appendChild(o);
  });
  if (prev) {
    for (var i = 0; i < sel.options.length; i++) {
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
  return res.slice().sort(function(a, b) {
    var va = a[state.sortCol], vb = b[state.sortCol];
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
  import('./render.js').then(function(mod) {
    mod.renderResults(state.cachedResults, document.getElementById('search-input').value.trim());
  });
}
