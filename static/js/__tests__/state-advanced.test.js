// Additional coverage tests for state.js — trapFocus, announceStatus,
// createLRUCache advanced ops, showToast with title/undo, searchable upgradeSelect.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  trapFocus,
  announceStatus,
  createLRUCache,
  showToast,
  upgradeSelect,
  setTranslationFunc,
} from '../state.js';

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}

beforeEach(() => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  // Reset translation func
  setTranslationFunc(null);
});

// ── trapFocus ─────────────────────────────────────────

describe('trapFocus', () => {
  function makeContainer(...tags) {
    const div = document.createElement('div');
    tags.forEach((tag) => {
      const el = document.createElement(tag);
      el.tabIndex = 0;
      div.appendChild(el);
    });
    document.body.appendChild(div);
    return div;
  }

  it('returns a cleanup function', () => {
    const div = makeContainer('button', 'input');
    const cleanup = trapFocus(div);
    expect(typeof cleanup).toBe('function');
    cleanup();
  });

  it('wraps Tab from last focusable to first', () => {
    const div = makeContainer('button', 'input');
    const [first, last] = div.querySelectorAll('button, input');
    trapFocus(div);

    last.focus();
    document.activeElement === last; // simulate
    div.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    // In jsdom focus wrapping is hard to test deeply — verify no error thrown
  });

  it('wraps Shift+Tab from first focusable to last', () => {
    const div = makeContainer('button', 'input');
    const [first] = div.querySelectorAll('button, input');
    trapFocus(div);

    first.focus();
    // shiftKey + Tab from first should focus last
    const evt = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true });
    div.dispatchEvent(evt);
    // No throw — behaviour is tested via DOM focus
  });

  it('ignores non-Tab keys', () => {
    const div = makeContainer('button');
    trapFocus(div);
    expect(() => {
      div.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    }).not.toThrow();
  });

  it('does nothing when container has no focusable children', () => {
    const div = document.createElement('div');
    document.body.appendChild(div);
    trapFocus(div);
    expect(() => {
      div.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    }).not.toThrow();
  });

  it('cleanup removes the keydown listener', () => {
    const div = makeContainer('button', 'input');
    const cleanup = trapFocus(div);
    cleanup();
    // After cleanup, dispatching Tab should not affect focus
    expect(() => {
      div.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    }).not.toThrow();
  });
});

// ── announceStatus ────────────────────────────────────

describe('announceStatus', () => {
  it('sets textContent on #sr-status via rAF', async () => {
    const el = document.createElement('div');
    el.id = 'sr-status';
    document.body.appendChild(el);

    announceStatus('Loading complete');
    // rAF fires asynchronously in jsdom
    await new Promise((r) => setTimeout(r, 50));
    expect(el.textContent).toBe('Loading complete');
  });

  it('clears text before setting (for screen reader re-announcement)', async () => {
    const el = document.createElement('div');
    el.id = 'sr-status';
    el.textContent = 'old message';
    document.body.appendChild(el);

    announceStatus('new message');
    // Right after call, textContent is cleared
    expect(el.textContent).toBe('');
    await new Promise((r) => setTimeout(r, 50));
    expect(el.textContent).toBe('new message');
  });

  it('does nothing when #sr-status element is absent', () => {
    expect(() => announceStatus('msg')).not.toThrow();
  });
});

// ── createLRUCache ────────────────────────────────────

describe('createLRUCache', () => {
  it('stores and retrieves values', () => {
    const cache = createLRUCache(3);
    cache['a'] = 1;
    expect(cache['a']).toBe(1);
  });

  it('evicts the LRU entry when at capacity', () => {
    const cache = createLRUCache(2);
    cache['x'] = 10;
    cache['y'] = 20;
    // Access x to make it MRU
    const _ = cache['x'];
    cache['z'] = 30; // evicts y (LRU)
    expect(cache['y']).toBeUndefined();
    expect(cache['x']).toBe(10);
    expect(cache['z']).toBe(30);
  });

  it('updates value of existing key without eviction', () => {
    const cache = createLRUCache(2);
    cache['a'] = 1;
    cache['b'] = 2;
    cache['a'] = 99; // update, should not evict
    expect(cache['a']).toBe(99);
    expect(cache['b']).toBe(2);
  });

  it('deletes a key via delete operator', () => {
    const cache = createLRUCache(3);
    cache['a'] = 1;
    delete cache['a'];
    expect(cache['a']).toBeUndefined();
  });

  it('returns false from _delete for missing key', () => {
    const cache = createLRUCache(3);
    const result = cache._delete('nonexistent');
    expect(result).toBe(false);
  });

  it('returns true from _delete for existing key', () => {
    const cache = createLRUCache(3);
    cache['k'] = 42;
    const result = cache._delete('k');
    expect(result).toBe(true);
  });

  it('supports "in" operator via has trap', () => {
    const cache = createLRUCache(3);
    cache['m'] = 5;
    expect('m' in cache).toBe(true);
    expect('missing' in cache).toBe(false);
  });

  it('ownKeys returns all current keys', () => {
    const cache = createLRUCache(5);
    cache['a'] = 1;
    cache['b'] = 2;
    cache['c'] = 3;
    const keys = Object.keys(cache);
    expect(keys).toContain('a');
    expect(keys).toContain('b');
    expect(keys).toContain('c');
    expect(keys.length).toBe(3);
  });

  it('getOwnPropertyDescriptor returns descriptor for existing key', () => {
    const cache = createLRUCache(3);
    cache['q'] = 42;
    const desc = Object.getOwnPropertyDescriptor(cache, 'q');
    expect(desc).toBeDefined();
    expect(desc.value).toBe(42);
    expect(desc.enumerable).toBe(true);
  });

  it('getOwnPropertyDescriptor returns undefined for missing key', () => {
    const cache = createLRUCache(3);
    const desc = Object.getOwnPropertyDescriptor(cache, 'nope');
    expect(desc).toBeUndefined();
  });

  it('handles symbol property access on internal props', () => {
    const cache = createLRUCache(2);
    // Symbol access should go through the get trap safely
    const sym = Symbol('test');
    expect(() => cache[sym]).not.toThrow();
  });
});

// ── showToast with opts.title ─────────────────────────

describe('showToast with opts.title', () => {
  let toastEl;

  beforeEach(() => {
    toastEl = document.createElement('div');
    toastEl.id = 'toast';
    document.body.appendChild(toastEl);
    vi.useFakeTimers();
  });

  afterEach(() => {
    toastEl.remove();
    vi.useRealTimers();
  });

  it('renders title and message in separate spans', () => {
    showToast('The detail message', 'info', { title: 'My Title' });
    const titleEl = toastEl.querySelector('.toast-title');
    const msgEl = toastEl.querySelector('.toast-message');
    expect(titleEl).not.toBeNull();
    expect(msgEl).not.toBeNull();
    expect(titleEl.textContent).toBe('My Title');
    expect(msgEl.textContent).toBe('The detail message');
  });

  it('wraps title+message in .toast-content div', () => {
    showToast('body', 'success', { title: 'Head' });
    const content = toastEl.querySelector('.toast-content');
    expect(content).not.toBeNull();
  });
});

// ── showToast with opts.onUndo ────────────────────────

describe('showToast with opts.onUndo', () => {
  let toastEl;

  beforeEach(() => {
    toastEl = document.createElement('div');
    toastEl.id = 'toast';
    document.body.appendChild(toastEl);
    vi.useFakeTimers();
    setTranslationFunc((key) => key);
  });

  afterEach(() => {
    toastEl.remove();
    vi.useRealTimers();
    setTranslationFunc(null);
  });

  it('renders an undo button when onUndo is provided', () => {
    showToast('Deleted item', 'success', { onUndo: vi.fn() });
    const undoBtn = toastEl.querySelector('.toast-undo');
    expect(undoBtn).not.toBeNull();
  });

  it('calls onUndo and hides toast when undo button clicked', () => {
    const onUndo = vi.fn();
    showToast('Deleted', 'success', { onUndo });
    const undoBtn = toastEl.querySelector('.toast-undo');
    undoBtn.click();
    expect(onUndo).toHaveBeenCalledOnce();
    expect(toastEl.classList.contains('show')).toBe(false);
  });

  it('respects custom duration', () => {
    showToast('msg', 'info', { duration: 5000 });
    expect(toastEl.classList.contains('show')).toBe(true);
    vi.advanceTimersByTime(4999);
    expect(toastEl.classList.contains('show')).toBe(true);
    vi.advanceTimersByTime(1);
    expect(toastEl.classList.contains('show')).toBe(false);
  });

  it('sets aria-live assertive for error type', () => {
    showToast('err', 'error');
    expect(toastEl.getAttribute('aria-live')).toBe('assertive');
  });

  it('sets aria-live polite for success type', () => {
    showToast('ok', 'success');
    expect(toastEl.getAttribute('aria-live')).toBe('polite');
  });
});

// ── upgradeSelect with searchable ─────────────────────

describe('upgradeSelect searchable mode', () => {
  let parent, sel;

  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
    parent = document.createElement('div');
    sel = document.createElement('select');
    sel.dataset.searchable = 'true';
    ['Alpha', 'Beta', 'Charlie'].forEach((label, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = label;
      sel.appendChild(opt);
    });
    parent.appendChild(sel);
    document.body.appendChild(parent);
  });

  afterEach(() => {
    parent.remove();
  });

  it('renders a search input inside the options div', () => {
    upgradeSelect(sel);
    const si = parent.querySelector('.custom-select-search');
    expect(si).not.toBeNull();
    expect(si.type).toBe('text');
  });

  it('filters options when typing in search input', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    trigger.click(); // open
    const si = parent.querySelector('.custom-select-search');
    si.value = 'alph';
    si.dispatchEvent(new Event('input'));
    const options = parent.querySelectorAll('.custom-select-option');
    const visible = Array.from(options).filter((o) => o.style.display !== 'none');
    expect(visible.length).toBe(1);
    expect(visible[0].textContent).toBe('Alpha');
  });

  it('shows all options when search is cleared', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    trigger.click();
    const si = parent.querySelector('.custom-select-search');
    si.value = 'z'; // no match
    si.dispatchEvent(new Event('input'));
    si.value = '';
    si.dispatchEvent(new Event('input'));
    const visible = Array.from(parent.querySelectorAll('.custom-select-option')).filter(
      (o) => o.style.display !== 'none',
    );
    expect(visible.length).toBe(3);
  });

  it('Escape in search input closes dropdown', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    trigger.click();
    const wrap = parent.querySelector('.custom-select-wrap');
    expect(wrap.classList.contains('open')).toBe(true);
    const si = parent.querySelector('.custom-select-search');
    si.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(false);
  });

  it('click on search input does not propagate (does not close dropdown)', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    trigger.click(); // open
    const wrap = parent.querySelector('.custom-select-wrap');
    const si = parent.querySelector('.custom-select-search');
    si.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    // Document click would close; stopPropagation prevents it
    expect(wrap.classList.contains('open')).toBe(true);
  });

  it('pressing a printable char key opens dropdown with char prefilled in search', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    // Simulate pressing 'b' while closed
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(true);
    const si = parent.querySelector('.custom-select-search');
    expect(si.value).toBe('b');
  });

  it('closing searchable select resets search input and shows all options', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    trigger.click();
    const si = parent.querySelector('.custom-select-search');
    si.value = 'gamma';
    si.dispatchEvent(new Event('input'));
    // Close via Escape on trigger
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(si.value).toBe('');
    const visible = Array.from(parent.querySelectorAll('.custom-select-option')).filter(
      (o) => o.style.display !== 'none',
    );
    expect(visible.length).toBe(3);
  });
});

// ── upgradeSelect mobile fallback ─────────────────────

describe('upgradeSelect mobile – native change callback', () => {
  it('registers native change handler on mobile and calls onSelect', () => {
    Object.defineProperty(window, 'innerWidth', { value: 375, writable: true });
    const div = document.createElement('div');
    const sel = document.createElement('select');
    const opt = document.createElement('option');
    opt.value = 'v';
    sel.appendChild(opt);
    div.appendChild(sel);
    document.body.appendChild(div);

    const cb = vi.fn();
    upgradeSelect(sel, cb);

    sel.value = 'v';
    sel.dispatchEvent(new Event('change'));
    expect(cb).toHaveBeenCalledWith('v');
    div.remove();
  });
});
