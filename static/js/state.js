// ── Shared state & utilities ─────────────────────────

export const state = {
  currentView: 'search',
  currentFilter: [],
  expandedId: null,
  editingId: null,
  searchTimeout: null,
  cachedStats: null,
  cachedResults: [],
  sortCol: 'total_score',
  sortDir: 'desc',
  categories: [],
  imageCache: {},
};

// All nutrition field IDs used in register/edit forms
export var NUTRI_IDS = ['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'];

export function catEmoji(typeName) {
  var c = state.categories.find(function(x) { return x.name === typeName; });
  return c ? c.emoji : '\u{1F4E6}';
}

export function catLabel(typeName) {
  var c = state.categories.find(function(x) { return x.name === typeName; });
  return c ? c.label : typeName;
}

export function esc(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

export function safeDataUri(uri) {
  if (typeof uri !== 'string') return '';
  if (/^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/.test(uri)) return uri;
  if (/^https?:\/\//.test(uri)) return esc(uri);
  return '';
}

export function fmtNum(v) {
  if (v == null) return '-';
  return parseFloat(v).toFixed(v % 1 ? 1 : 0);
}

export async function api(path, opts) {
  opts = opts || {};
  var res = await fetch(path, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
  return res.json();
}

export async function fetchProducts(search, types) {
  var p = new URLSearchParams();
  if (search) p.set('search', search);
  if (types && types.length) p.set('type', types.join(','));
  return api('/api/products?' + p);
}

export async function fetchStats() {
  state.cachedStats = await api('/api/stats');
  state.categories = state.cachedStats.categories || [];
  return state.cachedStats;
}

// ── Custom select dropdown (desktop only) ────────
// Wraps a native <select> with a styled custom dropdown.
// onSelect is called with the chosen value after selection.
// Supports re-calling to refresh options when the native <select> is repopulated.
export function upgradeSelect(sel, onSelect) {
  if (!sel || window.innerWidth < 640) return;

  var wrap, trigger, optionsDiv;
  var isNew = !(sel.parentNode && sel.parentNode.classList.contains('custom-select-wrap'));

  if (isNew) {
    wrap = document.createElement('div');
    wrap.className = 'custom-select-wrap';
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);

    trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.tabIndex = 0;
    trigger.setAttribute('aria-expanded', 'false');
    wrap.appendChild(trigger);

    optionsDiv = document.createElement('div');
    optionsDiv.className = 'custom-select-options';
    optionsDiv.setAttribute('role', 'listbox');
    wrap.appendChild(optionsDiv);
  } else {
    wrap = sel.parentNode;
    trigger = wrap.querySelector('.custom-select-trigger');
    optionsDiv = wrap.querySelector('.custom-select-options');
    optionsDiv.innerHTML = '';
  }

  // Store callback on the wrapper so refresh calls can use it
  if (onSelect) wrap._onSelect = onSelect;
  var cb = wrap._onSelect;

  // Sync trigger text with current selection
  var selectedOpt = sel.options[sel.selectedIndex];
  trigger.textContent = selectedOpt ? selectedOpt.textContent : '';

  // Build custom option items
  sel.querySelectorAll('option').forEach(function(o) {
    if (!o.value) return; // skip placeholder
    var div = document.createElement('div');
    div.className = 'custom-select-option';
    div.setAttribute('role', 'option');
    div.setAttribute('data-value', o.value);
    div.textContent = o.textContent;
    if (o.value === sel.value) div.classList.add('selected');
    optionsDiv.appendChild(div);
    div.addEventListener('click', function(e) {
      e.stopPropagation();
      _pick(div.getAttribute('data-value'), div.textContent);
    });
  });

  var highlighted = -1;

  // Only attach trigger/document listeners once
  if (isNew) {
    trigger.addEventListener('click', function(e) {
      e.stopPropagation();
      _closeAllCustomSelects(wrap);
      var isOpen = wrap.classList.toggle('open');
      trigger.setAttribute('aria-expanded', isOpen);
      highlighted = -1;
      _clearHL();
    });

    trigger.addEventListener('keydown', function(e) {
      var curItems = wrap.querySelectorAll('.custom-select-option');
      if (!wrap.classList.contains('open')) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          _closeAllCustomSelects(wrap);
          wrap.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
          highlighted = 0;
          _updateHL();
        }
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        highlighted = Math.min(highlighted + 1, curItems.length - 1);
        _updateHL();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlighted = Math.max(highlighted - 1, 0);
        _updateHL();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlighted >= 0 && highlighted < curItems.length) {
          _pick(curItems[highlighted].getAttribute('data-value'), curItems[highlighted].textContent);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        _close();
      }
    });

    document.addEventListener('click', function() { _close(); });
  }

  function _close() {
    wrap.classList.remove('open');
    trigger.setAttribute('aria-expanded', 'false');
    highlighted = -1;
    _clearHL();
  }
  function _clearHL() {
    wrap.querySelectorAll('.custom-select-option').forEach(function(o) { o.classList.remove('highlighted'); });
  }
  function _updateHL() {
    _clearHL();
    var curItems = wrap.querySelectorAll('.custom-select-option');
    if (highlighted >= 0 && highlighted < curItems.length) {
      curItems[highlighted].classList.add('highlighted');
      curItems[highlighted].scrollIntoView({ block: 'nearest' });
    }
  }
  function _pick(value, label) {
    sel.value = value;
    trigger.textContent = label;
    _close();
    if (cb) cb(value);
  }
}

function _closeAllCustomSelects(except) {
  document.querySelectorAll('.custom-select-wrap.open').forEach(function(w) {
    if (w !== except) {
      w.classList.remove('open');
      var t = w.querySelector('.custom-select-trigger');
      if (t) t.setAttribute('aria-expanded', 'false');
    }
  });
}
