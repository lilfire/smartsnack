// ── Shared state & utilities ─────────────────────────

// Focus trap: keeps Tab/Shift+Tab cycling within a container.
// Returns a cleanup function that removes the event listener.
export function trapFocus(container) {
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function handler(e) {
    if (e.key !== 'Tab') return;
    const focusable = Array.from(container.querySelectorAll(FOCUSABLE));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }
  container.addEventListener('keydown', handler);
  return () => container.removeEventListener('keydown', handler);
}

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
  advancedFilters: null,
};

// All nutrition field IDs used in register/edit forms
export const NUTRI_IDS = ['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'];

// Translation function reference, set by i18n.js to avoid circular imports
let _tFunc = null;
export function setTranslationFunc(fn) { _tFunc = fn; }

export function catEmoji(typeName) {
  if (!typeName) return '\u{1F4E6}';
  const c = state.categories.find((x) => x.name === typeName);
  return c ? c.emoji : '\u{1F4E6}';
}

export function catLabel(typeName) {
  if (!typeName) return _tFunc ? _tFunc('uncategorized') : 'Uncategorized';
  const c = state.categories.find((x) => x.name === typeName);
  return c ? c.label : typeName;
}

// Singleton element for HTML escaping
const _escDiv = document.createElement('div');
export function esc(s) {
  if (s == null) return '';
  _escDiv.textContent = s;
  return _escDiv.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function safeDataUri(uri) {
  if (typeof uri !== 'string') return '';
  if (/^data:image\/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=]+$/.test(uri)) return uri;
  if (/^https?:\/\//.test(uri)) {
    // Encode for safe use in HTML src attributes
    try { return esc(new URL(uri).href); } catch(e) { return ''; }
  }
  return '';
}

export function fmtNum(v) {
  if (v == null) return '-';
  const n = parseFloat(v);
  if (isNaN(n)) return '-';
  return n.toFixed(n % 1 ? 1 : 0);
}

export function announceStatus(msg) {
  const el = document.getElementById('sr-status');
  if (el) { el.textContent = ''; requestAnimationFrame(() => { el.textContent = msg; }); }
}

let _toastTimer = null;
export function showToast(msg, type, opts) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.innerHTML = '';
  // Set aria-live based on severity: assertive for errors/warnings, polite for others
  toast.setAttribute('aria-live', (type === 'error' || type === 'warning') ? 'assertive' : 'polite');
  if (opts && opts.title) {
    const contentDiv = document.createElement('div');
    contentDiv.className = 'toast-content';
    const titleSpan = document.createElement('span');
    titleSpan.className = 'toast-title';
    titleSpan.textContent = opts.title;
    contentDiv.appendChild(titleSpan);
    const msgSpan = document.createElement('span');
    msgSpan.className = 'toast-message';
    msgSpan.textContent = msg;
    contentDiv.appendChild(msgSpan);
    toast.appendChild(contentDiv);
  } else {
    const textSpan = document.createElement('span');
    textSpan.textContent = msg;
    toast.appendChild(textSpan);
  }
  if (opts && opts.onUndo) {
    const undoBtn = document.createElement('button');
    undoBtn.className = 'toast-undo';
    undoBtn.textContent = _tFunc ? _tFunc('btn_undo') : 'Undo';
    undoBtn.addEventListener('click', () => {
      toast.classList.remove('show');
      if (_toastTimer) { clearTimeout(_toastTimer); _toastTimer = null; }
      opts.onUndo();
    });
    toast.appendChild(undoBtn);
  }
  const closeBtn = document.createElement('button');
  closeBtn.className = 'toast-close';
  closeBtn.textContent = '\u00D7';
  closeBtn.setAttribute('aria-label', _tFunc ? _tFunc('btn_close') : 'Close');
  closeBtn.addEventListener('click', () => { toast.classList.remove('show'); if (_toastTimer) { clearTimeout(_toastTimer); _toastTimer = null; } });
  toast.appendChild(closeBtn);
  toast.className = 'toast ' + type + ' show';
  if (_toastTimer) clearTimeout(_toastTimer);
  var duration = (opts && opts.duration) || 3000;
  _toastTimer = setTimeout(() => { toast.classList.remove('show'); _toastTimer = null; }, duration);
}

export async function api(path, opts) {
  opts = opts || {};
  const controller = new AbortController();
  const timeoutId = setTimeout(() => { controller.abort(); }, 15000);
  try {
    const defaultHeaders = opts.body && !(opts.body instanceof FormData)
      ? { 'Content-Type': 'application/json', 'X-Requested-With': 'SmartSnack' }
      : { 'X-Requested-With': 'SmartSnack' };
    const headers = Object.assign(defaultHeaders, opts.headers || {});
    const res = await fetch(path, Object.assign({}, opts, { headers, signal: controller.signal }));
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch(e) { data = {}; }
    if (!res.ok) {
      const err = new Error(data.error || 'Request failed: ' + res.status);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchProducts(search, types) {
  const p = new URLSearchParams();
  if (search) p.set('search', search);
  if (types && types.length) p.set('type', types.join(','));
  if (state.advancedFilters) p.set('filters', state.advancedFilters);
  return api('/api/products?' + p);
}

export async function fetchStats() {
  state.cachedStats = await api('/api/stats');
  state.categories = state.cachedStats.categories || [];
  return state.cachedStats;
}

// ── Custom select dropdown (desktop only) ────────
// Shows a styled confirmation modal. Returns a Promise that resolves true/false.
export function showConfirmModal(icon, title, message, confirmLabel, cancelLabel, isDestructive) {
  return new Promise((resolve) => {
    const bg = document.createElement('div');
    bg.className = 'scan-modal-bg';
    bg.setAttribute('role', 'dialog');
    bg.setAttribute('aria-modal', 'true');
    const modal = document.createElement('div');
    modal.className = 'scan-modal';
    const iconDiv = document.createElement('div');
    iconDiv.className = 'scan-modal-icon';
    iconDiv.textContent = icon;
    modal.appendChild(iconDiv);
    const h3 = document.createElement('h3');
    h3.textContent = title;
    modal.appendChild(h3);
    const pEl = document.createElement('p');
    pEl.textContent = message;
    modal.appendChild(pEl);
    const actions = document.createElement('div');
    actions.className = 'scan-modal-actions';
    const yesBtn = document.createElement('button');
    yesBtn.className = 'scan-modal-btn-register confirm-yes' + (isDestructive ? ' confirm-destructive' : '');
    yesBtn.textContent = confirmLabel;
    actions.appendChild(yesBtn);
    const noBtn = document.createElement('button');
    noBtn.className = 'scan-modal-btn-cancel confirm-no';
    noBtn.textContent = cancelLabel;
    actions.appendChild(noBtn);
    modal.appendChild(actions);
    bg.appendChild(modal);
    document.body.appendChild(bg);

    const removeTrap = trapFocus(bg);
    function close(val) {
      document.removeEventListener('keydown', onKeyDown);
      removeTrap();
      bg.remove();
      resolve(val);
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') close(false);
    }
    document.addEventListener('keydown', onKeyDown);
    noBtn.onclick = () => { close(false); };
    yesBtn.onclick = () => { close(true); };
    bg.addEventListener('click', (e) => { if (e.target === bg) close(false); });
    // Focus the confirm button for keyboard accessibility
    yesBtn.focus();
  });
}

// Wraps a native <select> with a styled custom dropdown.
// onSelect is called with the chosen value after selection.
// Supports re-calling to refresh options when the native <select> is repopulated.
let _docClickRegistered = false;
export function upgradeSelect(sel, onSelect) {
  if (!sel) return;
  if (window.innerWidth < 640) {
    // On mobile, skip custom UI but still register the callback on native select
    if (onSelect) {
      sel.addEventListener('change', () => onSelect(sel.value));
    }
    return;
  }

  let wrap, trigger, optionsDiv;
  const isNew = !(sel.parentNode && sel.parentNode.classList.contains('custom-select-wrap'));

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
  const cb = wrap._onSelect;

  // Sync trigger text with current selection
  const selectedOpt = sel.options[sel.selectedIndex];
  trigger.textContent = selectedOpt ? selectedOpt.textContent : '';

  let highlighted = -1;

  // Inject search input for searchable selects (desktop only)
  if (sel.dataset.searchable === 'true') {
    const si = document.createElement('input');
    si.className = 'custom-select-search';
    si.type = 'text';
    si.autocomplete = 'off';
    si.spellcheck = false;
    si.placeholder = 'Search...';
    si.setAttribute('aria-label', 'Search options');
    optionsDiv.appendChild(si);
    wrap._searchInput = si;
    si.addEventListener('input', () => {
      const q = si.value.toLowerCase();
      optionsDiv.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.style.display = (!q || opt.textContent.toLowerCase().includes(q)) ? '' : 'none';
      });
      optionsDiv.querySelectorAll('.custom-select-group').forEach(grp => {
        let next = grp.nextElementSibling;
        let anyVisible = false;
        while (next && !next.classList.contains('custom-select-group')) {
          if (next.classList.contains('custom-select-option') && next.style.display !== 'none') {
            anyVisible = true;
            break;
          }
          next = next.nextElementSibling;
        }
        grp.style.display = (q && !anyVisible) ? 'none' : '';
      });
    });
    si.addEventListener('click', e => e.stopPropagation());
    si.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); _close(); trigger.focus(); }
    });
  }

  // Build custom option items (with optgroup support)
  function _addOption(o) {
    if (!o.value && !o.textContent.trim()) return;
    const div = document.createElement('div');
    div.className = 'custom-select-option';
    div.setAttribute('role', 'option');
    div.setAttribute('data-value', o.value);
    div.textContent = o.textContent;
    if (o.value === sel.value) div.classList.add('selected');
    optionsDiv.appendChild(div);
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      _pick(div.getAttribute('data-value'), div.textContent);
    });
  }

  const groups = sel.querySelectorAll('optgroup');
  if (groups.length) {
    groups.forEach((g) => {
      const header = document.createElement('div');
      header.className = 'custom-select-group';
      header.textContent = g.label;
      optionsDiv.appendChild(header);
      g.querySelectorAll('option').forEach(_addOption);
    });
  } else {
    sel.querySelectorAll('option').forEach(_addOption);
  }

  // Only attach trigger/document listeners once
  if (isNew) {
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      _closeAllCustomSelects(wrap);
      const isOpen = wrap.classList.toggle('open');
      trigger.setAttribute('aria-expanded', isOpen);
      highlighted = -1;
      _clearHL();
      if (isOpen && wrap._searchInput) {
        wrap._searchInput.focus();
      }
    });

    trigger.addEventListener('keydown', (e) => {
      if (!wrap.classList.contains('open')) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          _closeAllCustomSelects(wrap);
          wrap.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
          if (wrap._searchInput) {
            wrap._searchInput.focus();
          } else {
            highlighted = 0;
            _updateHL();
          }
        } else if (wrap._searchInput && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          _closeAllCustomSelects(wrap);
          wrap.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
          wrap._searchInput.value = e.key;
          wrap._searchInput.dispatchEvent(new Event('input'));
          wrap._searchInput.focus();
        }
        return;
      }
      const curItems = Array.from(wrap.querySelectorAll('.custom-select-option')).filter(o => o.style.display !== 'none');
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
        trigger.focus();
      }
    });

    // Single delegated document listener instead of one per select
    if (!_docClickRegistered) {
      _docClickRegistered = true;
      document.addEventListener('click', () => { _closeAllCustomSelects(); });
    }
  }

  function _close() {
    wrap.classList.remove('open');
    trigger.setAttribute('aria-expanded', 'false');
    highlighted = -1;
    _clearHL();
    if (wrap._searchInput) {
      wrap._searchInput.value = '';
      optionsDiv.querySelectorAll('.custom-select-option, .custom-select-group').forEach(el => {
        el.style.display = '';
      });
    }
  }
  function _clearHL() {
    wrap.querySelectorAll('.custom-select-option').forEach((o) => { o.classList.remove('highlighted'); });
  }
  function _updateHL() {
    _clearHL();
    const curItems = Array.from(wrap.querySelectorAll('.custom-select-option')).filter(o => o.style.display !== 'none');
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

export function initAllFieldSelects(root = document) {
  const EXCLUDED_CONTEXTS = ['.adv-row', '.wc-row', '.edit-grid'];
  root.querySelectorAll('select.field-select').forEach(sel => {
    const inExcluded = EXCLUDED_CONTEXTS.some(ctx => sel.closest(ctx));
    if (!inExcluded) upgradeSelect(sel);
  });
}

function _closeAllCustomSelects(except) {
  document.querySelectorAll('.custom-select-wrap.open').forEach((w) => {
    if (w !== except) {
      w.classList.remove('open');
      const triggerEl = w.querySelector('.custom-select-trigger');
      if (triggerEl) triggerEl.setAttribute('aria-expanded', 'false');
      if (w._searchInput) {
        w._searchInput.value = '';
        w.querySelectorAll('.custom-select-option, .custom-select-group').forEach(el => {
          el.style.display = '';
        });
      }
    }
  });
}
