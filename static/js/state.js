// ── LRU Cache ─────────────────────────────────────────
// Returns a Proxy that behaves like a plain object but evicts the least recently
// used entry when the cache grows beyond maxSize.
export const IMAGE_CACHE_MAX_SIZE = 100;

export function createLRUCache(maxSize) {
  // Doubly-linked list sentinel nodes; head.next = MRU, tail.prev = LRU
  const head = { key: null, value: undefined, prev: null, next: null };
  const tail = { key: null, value: undefined, prev: null, next: null };
  head.next = tail;
  tail.prev = head;
  const map = new Map();

  function _remove(node) {
    node.prev.next = node.next;
    node.next.prev = node.prev;
  }
  function _insertMRU(node) {
    node.next = head.next;
    node.prev = head;
    head.next.prev = node;
    head.next = node;
  }

  const impl = {
    _get(key) {
      if (!map.has(key)) return undefined;
      const node = map.get(key);
      _remove(node);
      _insertMRU(node);
      return node.value;
    },
    _set(key, value) {
      if (map.has(key)) {
        const node = map.get(key);
        node.value = value;
        _remove(node);
        _insertMRU(node);
      } else {
        if (map.size >= maxSize) {
          const lru = tail.prev;
          _remove(lru);
          map.delete(lru.key);
        }
        const node = { key, value, prev: null, next: null };
        _insertMRU(node);
        map.set(key, node);
      }
    },
    _delete(key) {
      if (!map.has(key)) return false;
      _remove(map.get(key));
      map.delete(key);
      return true;
    },
    _has(key) { return map.has(key); },
    _map: map,
  };

  const _internal = new Set(['_get', '_set', '_delete', '_has', '_map']);

  return new Proxy(impl, {
    get(target, prop) {
      if (_internal.has(prop) || typeof prop === 'symbol') return target[prop];
      return target._get(prop);
    },
    set(target, prop, value) {
      if (_internal.has(prop)) { target[prop] = value; return true; }
      target._set(prop, value);
      return true;
    },
    deleteProperty(target, prop) {
      target._delete(prop);
      // Always return true: in strict mode, returning false causes
      // `delete obj[key]` to throw a TypeError. Deleting a missing key
      // should be a no-op, matching plain-object semantics.
      return true;
    },
    has(target, prop) {
      return target._has(prop);
    },
    ownKeys(target) {
      return [...target._map.keys()];
    },
    getOwnPropertyDescriptor(target, prop) {
      if (target._map.has(prop)) {
        return { configurable: true, enumerable: true, writable: true, value: target._get(prop) };
      }
      return undefined;
    },
  });
}

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
  imageCache: createLRUCache(IMAGE_CACHE_MAX_SIZE),
  advancedFilters: null,
  pagination: { offset: 0, total: null, inFlight: false, pageSize: 50 },
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

export async function fetchProducts(search, types, opts) {
  const p = new URLSearchParams();
  if (search) p.set('search', search);
  if (types && types.length) p.set('type', types.join(','));
  if (state.advancedFilters) p.set('filters', state.advancedFilters);
  if (opts && opts.limit != null) p.set('limit', String(opts.limit));
  if (opts && opts.offset != null) p.set('offset', String(opts.offset));
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

// Custom select dropdown lives in custom-select.js; re-exported here so
// existing importers keep working.
export { upgradeSelect, initAllFieldSelects } from './custom-select.js';
