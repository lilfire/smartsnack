// ── Infinite Scroll ──────────────────────────────────
import { state, fetchProducts } from './state.js';

const SCROLL_THRESHOLD = 200; // px from bottom to trigger next page

let _scrollHandler = null;
let _getSearchFn = null;

// ── Loading indicator ─────────────────────────────────

function _getLoader() {
  return document.getElementById('scroll-loader');
}

export function showScrollLoader() {
  const el = _getLoader();
  if (el) el.style.display = '';
}

export function hideScrollLoader() {
  const el = _getLoader();
  if (el) el.style.display = 'none';
}

// ── Page loading ──────────────────────────────────────

export async function loadNextPage() {
  const pg = state.pagination;
  if (pg.inFlight) return;
  if (pg.total !== null && pg.offset + pg.pageSize >= pg.total) return;

  const search = _getSearchFn ? _getSearchFn() : '';

  pg.inFlight = true;
  showScrollLoader();
  try {
    const nextOffset = pg.offset + pg.pageSize;
    const data = await fetchProducts(search, state.currentFilter, {
      limit: pg.pageSize,
      offset: nextOffset,
    });
    // Handle {products, total} or plain array (backward compat)
    const products = Array.isArray(data) ? data : (data.products || []);
    const total = Array.isArray(data) ? pg.total : (data.total != null ? data.total : pg.total);
    if (total !== null) pg.total = total;
    if (!products.length) {
      pg.offset = pg.total != null ? pg.total : nextOffset;
      return;
    }
    pg.offset = nextOffset;
    state.cachedResults = state.cachedResults.concat(products);
    // Lazy import to avoid circular dep with render/products
    const { appendResults } = await import('./render.js');
    appendResults(products);
    // Stop listener when all loaded
    if (pg.total !== null && pg.offset + pg.pageSize >= pg.total) {
      teardownInfiniteScroll();
      hideScrollLoader();
    }
  } catch (e) {
    console.error('Infinite scroll fetch failed:', e);
  } finally {
    pg.inFlight = false;
    hideScrollLoader();
  }
}

// ── Scroll listener ───────────────────────────────────

function _onScroll() {
  const pg = state.pagination;
  if (pg.inFlight) return;
  if (pg.total !== null && pg.offset + pg.pageSize >= pg.total) {
    teardownInfiniteScroll();
    return;
  }
  const distFromBottom = document.body.offsetHeight - window.innerHeight - window.scrollY;
  if (distFromBottom <= SCROLL_THRESHOLD) {
    loadNextPage();
  }
}

export function initInfiniteScroll(getSearchFn) {
  teardownInfiniteScroll();
  _getSearchFn = getSearchFn || null;
  const pg = state.pagination;
  // Don't set up listener if all results already loaded
  if (pg.total !== null && pg.offset + pg.pageSize >= pg.total) return;
  _scrollHandler = _onScroll;
  window.addEventListener('scroll', _scrollHandler, { passive: true });
}

export function teardownInfiniteScroll() {
  if (_scrollHandler) {
    window.removeEventListener('scroll', _scrollHandler);
    _scrollHandler = null;
  }
  _getSearchFn = null;
  hideScrollLoader();
}
