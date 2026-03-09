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
  if (/^https?:\/\//.test(uri)) {
    // Encode for safe use in HTML src attributes
    try { return esc(new URL(uri).href); } catch(e) { return ''; }
  }
  return '';
}

export function fmtNum(v) {
  if (v == null) return '-';
  var n = parseFloat(v);
  if (isNaN(n)) return '-';
  return n.toFixed(n % 1 ? 1 : 0);
}

export function showToast(msg, type) {
  var toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast ' + type + ' show';
  setTimeout(function() { toast.classList.remove('show'); }, 3000);
}

export async function api(path, opts) {
  opts = opts || {};
  var controller = new AbortController();
  var timeoutId = setTimeout(function() { controller.abort(); }, 15000);
  try {
    var res = await fetch(path, Object.assign({ headers: { 'Content-Type': 'application/json' }, signal: controller.signal }, opts));
    var text = await res.text();
    var data;
    try { data = JSON.parse(text); } catch(e) { data = {}; }
    if (!res.ok) throw new Error(data.error || 'Request failed: ' + res.status);
    return data;
  } finally {
    clearTimeout(timeoutId);
  }
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
// Shows a styled confirmation modal. Returns a Promise that resolves true/false.
export function showConfirmModal(icon, title, message, confirmLabel, cancelLabel) {
  return new Promise(function(resolve) {
    var bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    var modal = document.createElement('div');
    modal.className = 'scan-modal';
    var iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.innerHTML = icon;
    modal.appendChild(iconDiv);
    var h3 = document.createElement('h3');
    h3.textContent = title;
    modal.appendChild(h3);
    var pEl = document.createElement('p');
    pEl.textContent = message;
    modal.appendChild(pEl);
    var actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    var yesBtn = document.createElement('button');
    yesBtn.className = 'scan-modal-btn-register confirm-yes';
    yesBtn.textContent = confirmLabel;
    actions.appendChild(yesBtn);
    var noBtn = document.createElement('button');
    noBtn.className = 'scan-modal-btn-cancel confirm-no';
    noBtn.textContent = cancelLabel;
    actions.appendChild(noBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);
    function close(val) { bg.remove(); resolve(val); }
    noBtn.onclick = function() { close(false); };
    yesBtn.onclick = function() { close(true); };
    bg.addEventListener('click', function(e) { if (e.target === bg) close(false); });
  });
}

// Wraps a native <select> with a styled custom dropdown.
// onSelect is called with the chosen value after selection.
// Supports re-calling to refresh options when the native <select> is repopulated.
var _docClickRegistered = false;
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
    if (!o.value && !o.textContent.trim()) return; // skip truly empty placeholders
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

    // Single delegated document listener instead of one per select
    if (!_docClickRegistered) {
      _docClickRegistered = true;
      document.addEventListener('click', function() { _closeAllCustomSelects(); });
    }
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
      var triggerEl = w.querySelector('.custom-select-trigger');
      if (triggerEl) triggerEl.setAttribute('aria-expanded', 'false');
    }
  });
}
