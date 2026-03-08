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
