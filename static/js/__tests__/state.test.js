import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { state, NUTRI_IDS, catEmoji, catLabel, esc, safeDataUri, fmtNum, showToast, api, fetchProducts, fetchStats, showConfirmModal, upgradeSelect } from '../state.js';

// jsdom does not implement scrollIntoView
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function() {};
}

beforeEach(() => {
  state.currentView = 'search';
  state.currentFilter = [];
  state.expandedId = null;
  state.editingId = null;
  state.searchTimeout = null;
  state.cachedStats = null;
  state.cachedResults = [];
  state.sortCol = 'total_score';
  state.sortDir = 'desc';
  state.categories = [];
  state.imageCache = {};
  vi.restoreAllMocks();
});

describe('NUTRI_IDS', () => {
  it('contains all expected nutrition field IDs', () => {
    expect(NUTRI_IDS).toEqual(['kcal', 'energy_kj', 'fat', 'saturated_fat', 'carbs', 'sugar', 'protein', 'fiber', 'salt', 'weight', 'portion']);
  });

  it('is an array', () => {
    expect(Array.isArray(NUTRI_IDS)).toBe(true);
  });
});

describe('catEmoji', () => {
  it('returns emoji for known category', () => {
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    expect(catEmoji('dairy')).toBe('🧀');
  });

  it('returns default package emoji for unknown category', () => {
    state.categories = [];
    expect(catEmoji('unknown')).toBe('📦');
  });

  it('returns default when categories has other items but not matched', () => {
    state.categories = [{ name: 'meat', emoji: '🥩', label: 'Meat' }];
    expect(catEmoji('dairy')).toBe('📦');
  });
});

describe('catLabel', () => {
  it('returns label for known category', () => {
    state.categories = [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }];
    expect(catLabel('dairy')).toBe('Dairy');
  });

  it('returns typeName for unknown category', () => {
    state.categories = [];
    expect(catLabel('unknown')).toBe('unknown');
  });
});

describe('esc', () => {
  it('escapes HTML special characters', () => {
    expect(esc('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes ampersand', () => {
    expect(esc('a & b')).toBe('a &amp; b');
  });

  it('escapes double quotes', () => {
    expect(esc('"hello"')).toBe('&quot;hello&quot;');
  });

  it('escapes single quotes', () => {
    expect(esc("it's")).toBe('it&#39;s');
  });

  it('handles empty string', () => {
    expect(esc('')).toBe('');
  });

  it('passes through plain text', () => {
    expect(esc('hello world')).toBe('hello world');
  });
});

describe('safeDataUri', () => {
  it('returns valid data URI for PNG', () => {
    const uri = 'data:image/png;base64,iVBORw0KGgo=';
    expect(safeDataUri(uri)).toBe(uri);
  });

  it('returns valid data URI for JPEG', () => {
    const uri = 'data:image/jpeg;base64,/9j/4AAQSkZJ';
    expect(safeDataUri(uri)).toBe(uri);
  });

  it('returns empty for non-string', () => {
    expect(safeDataUri(null)).toBe('');
    expect(safeDataUri(undefined)).toBe('');
    expect(safeDataUri(123)).toBe('');
  });

  it('returns empty for javascript URI', () => {
    expect(safeDataUri('javascript:alert(1)')).toBe('');
  });

  it('returns empty for invalid data URI', () => {
    expect(safeDataUri('data:text/html;base64,PHNjcmlwdD4=')).toBe('');
  });

  it('handles HTTPS URLs', () => {
    const url = 'https://example.com/image.png';
    const result = safeDataUri(url);
    expect(result).toContain('https://example.com/image.png');
  });

  it('returns empty for invalid URL', () => {
    expect(safeDataUri('not-a-url')).toBe('');
  });
});

describe('fmtNum', () => {
  it('returns dash for null', () => {
    expect(fmtNum(null)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(fmtNum(undefined)).toBe('-');
  });

  it('returns dash for NaN string', () => {
    expect(fmtNum('abc')).toBe('-');
  });

  it('formats integer without decimal', () => {
    expect(fmtNum(5)).toBe('5');
  });

  it('formats decimal with one place', () => {
    expect(fmtNum(5.3)).toBe('5.3');
  });

  it('formats zero', () => {
    expect(fmtNum(0)).toBe('0');
  });

  it('formats string number', () => {
    expect(fmtNum('12.5')).toBe('12.5');
  });
});

describe('showToast', () => {
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

  it('sets toast text and className', () => {
    showToast('Hello', 'success');
    expect(toastEl.firstChild.textContent).toBe('Hello');
    expect(toastEl.className).toBe('toast success show');
  });

  it('removes show class after 3 seconds', () => {
    showToast('Test', 'error');
    expect(toastEl.classList.contains('show')).toBe(true);
    vi.advanceTimersByTime(3000);
    expect(toastEl.classList.contains('show')).toBe(false);
  });

  it('resets timer on subsequent calls', () => {
    showToast('First', 'info');
    vi.advanceTimersByTime(2000);
    showToast('Second', 'success');
    expect(toastEl.firstChild.textContent).toBe('Second');
    vi.advanceTimersByTime(2000);
    expect(toastEl.classList.contains('show')).toBe(true);
    vi.advanceTimersByTime(1000);
    expect(toastEl.classList.contains('show')).toBe(false);
  });
});

describe('api', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns parsed JSON on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{"result":"ok"}'),
    });
    vi.useRealTimers();
    const data = await api('/test');
    expect(data).toEqual({ result: 'ok' });
    // GET requests (no body) should not send Content-Type
    expect(global.fetch).toHaveBeenCalledWith('/test', expect.objectContaining({
      headers: {},
    }));
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve('{"error":"Not found"}'),
    });
    vi.useRealTimers();
    await expect(api('/missing')).rejects.toThrow('Not found');
  });

  it('passes custom options', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{}'),
    });
    vi.useRealTimers();
    await api('/test', { method: 'POST', body: '{"a":1}' });
    expect(global.fetch).toHaveBeenCalledWith('/test', expect.objectContaining({
      method: 'POST',
      body: '{"a":1}',
    }));
  });

  it('handles non-JSON response gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('not json'),
    });
    vi.useRealTimers();
    const data = await api('/test');
    expect(data).toEqual({});
  });
});

describe('fetchProducts', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('[{"id":1,"name":"Test"}]'),
    });
  });

  it('calls api with search param', async () => {
    const result = await fetchProducts('milk', []);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('search=milk'),
      expect.any(Object)
    );
    expect(result).toEqual([{ id: 1, name: 'Test' }]);
  });

  it('calls api with type param', async () => {
    await fetchProducts('', ['dairy', 'meat']);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('type=dairy%2Cmeat'),
      expect.any(Object)
    );
  });

  it('calls api without params when empty', async () => {
    await fetchProducts('', []);
    const url = global.fetch.mock.calls[0][0];
    expect(url).toBe('/api/products?');
  });
});

describe('fetchStats', () => {
  it('updates state.cachedStats and state.categories', async () => {
    const statsData = { total: 10, types: 3, categories: [{ name: 'dairy', emoji: '🧀', label: 'Dairy' }] };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify(statsData)),
    });
    const result = await fetchStats();
    expect(result).toEqual(statsData);
    expect(state.cachedStats).toEqual(statsData);
    expect(state.categories).toEqual([{ name: 'dairy', emoji: '🧀', label: 'Dairy' }]);
  });

  it('sets empty categories when not provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{"total":0,"types":0}'),
    });
    await fetchStats();
    expect(state.categories).toEqual([]);
  });
});

describe('showConfirmModal', () => {
  it('resolves true when confirm button clicked', async () => {
    const promise = showConfirmModal('🗑', 'Title', 'Message', 'Yes', 'No');
    const yesBtn = document.querySelector('.confirm-yes');
    expect(yesBtn).not.toBeNull();
    yesBtn.click();
    expect(await promise).toBe(true);
  });

  it('resolves false when cancel button clicked', async () => {
    const promise = showConfirmModal('🗑', 'Title', 'Message', 'Yes', 'No');
    const noBtn = document.querySelector('.confirm-no');
    noBtn.click();
    expect(await promise).toBe(false);
  });

  it('resolves false on Escape key', async () => {
    const promise = showConfirmModal('🗑', 'Title', 'Message', 'Yes', 'No');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(await promise).toBe(false);
  });

  it('resolves false when clicking background', async () => {
    const promise = showConfirmModal('🗑', 'Title', 'Message', 'Yes', 'No');
    const bg = document.querySelector('.scan-modal-bg');
    bg.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(await promise).toBe(false);
  });

  it('sets correct modal content', async () => {
    const promise = showConfirmModal('⚠', 'My Title', 'My Message', 'Confirm', 'Cancel');
    expect(document.querySelector('.scan-modal-icon').textContent).toBe('⚠');
    expect(document.querySelector('.scan-modal h3').textContent).toBe('My Title');
    expect(document.querySelector('.scan-modal p').textContent).toBe('My Message');
    document.querySelector('.confirm-no').click();
    await promise;
  });

  it('removes modal from DOM after resolving', async () => {
    const promise = showConfirmModal('🗑', 'T', 'M', 'Y', 'N');
    document.querySelector('.confirm-yes').click();
    await promise;
    expect(document.querySelector('.scan-modal-bg')).toBeNull();
  });
});

describe('upgradeSelect', () => {
  let sel, parent;

  beforeEach(() => {
    parent = document.createElement('div');
    document.body.appendChild(parent);
    sel = document.createElement('select');
    const opt1 = document.createElement('option');
    opt1.value = 'a';
    opt1.textContent = 'Alpha';
    const opt2 = document.createElement('option');
    opt2.value = 'b';
    opt2.textContent = 'Beta';
    sel.appendChild(opt1);
    sel.appendChild(opt2);
    parent.appendChild(sel);
    // upgradeSelect only works on desktop (width >= 640)
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
  });

  afterEach(() => {
    parent.remove();
  });

  it('skips upgrade on mobile (width < 640)', () => {
    Object.defineProperty(window, 'innerWidth', { value: 320, writable: true });
    upgradeSelect(sel);
    expect(parent.querySelector('.custom-select-wrap')).toBeNull();
  });

  it('creates custom select wrapper on desktop', () => {
    upgradeSelect(sel);
    expect(parent.querySelector('.custom-select-wrap')).not.toBeNull();
    expect(parent.querySelector('.custom-select-trigger')).not.toBeNull();
    expect(parent.querySelector('.custom-select-options')).not.toBeNull();
  });

  it('syncs trigger text with selected option', () => {
    sel.value = 'a';
    upgradeSelect(sel);
    expect(parent.querySelector('.custom-select-trigger').textContent).toBe('Alpha');
  });

  it('calls onSelect callback when option picked', () => {
    const cb = vi.fn();
    upgradeSelect(sel, cb);
    const options = parent.querySelectorAll('.custom-select-option');
    options[1].click();
    expect(cb).toHaveBeenCalledWith('b');
  });

  it('does nothing when sel is null', () => {
    expect(() => upgradeSelect(null)).not.toThrow();
  });

  it('refreshes options on re-call', () => {
    upgradeSelect(sel);
    const opt3 = document.createElement('option');
    opt3.value = 'c';
    opt3.textContent = 'Charlie';
    sel.appendChild(opt3);
    upgradeSelect(sel);
    const options = parent.querySelectorAll('.custom-select-option');
    expect(options.length).toBe(3);
  });

  it('preserves onSelect callback when re-called without one', () => {
    const cb = vi.fn();
    upgradeSelect(sel, cb);
    // Re-call without passing onSelect
    upgradeSelect(sel);
    const options = parent.querySelectorAll('.custom-select-option');
    options[1].click();
    expect(cb).toHaveBeenCalledWith('b');
  });

  it('opens dropdown on trigger click and toggles open class', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    trigger.click();
    expect(wrap.classList.contains('open')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    // Click again to close
    trigger.click();
    expect(wrap.classList.contains('open')).toBe(false);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('opens dropdown on Enter key when closed', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
  });

  it('opens dropdown on Space key when closed', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(true);
  });

  it('navigates with ArrowDown and ArrowUp when open', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    // Open with ArrowDown (sets highlighted to 0)
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(true);
    let options = wrap.querySelectorAll('.custom-select-option');
    expect(options[0].classList.contains('highlighted')).toBe(true);

    // ArrowDown to move to second item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    options = wrap.querySelectorAll('.custom-select-option');
    expect(options[1].classList.contains('highlighted')).toBe(true);
    expect(options[0].classList.contains('highlighted')).toBe(false);

    // ArrowDown at last item stays at last item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    options = wrap.querySelectorAll('.custom-select-option');
    expect(options[1].classList.contains('highlighted')).toBe(true);

    // ArrowUp to move back to first item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    options = wrap.querySelectorAll('.custom-select-option');
    expect(options[0].classList.contains('highlighted')).toBe(true);

    // ArrowUp at first item stays at first item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    options = wrap.querySelectorAll('.custom-select-option');
    expect(options[0].classList.contains('highlighted')).toBe(true);
  });

  it('selects highlighted item on Enter when open', () => {
    const cb = vi.fn();
    upgradeSelect(sel, cb);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    // Open and highlight first item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    // Move to second item
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    // Select with Enter
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(cb).toHaveBeenCalledWith('b');
    expect(wrap.classList.contains('open')).toBe(false);
  });

  it('closes dropdown on Escape key', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    trigger.click();
    expect(wrap.classList.contains('open')).toBe(true);
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(false);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('closes other open selects when opening a new one', () => {
    // Create first select
    upgradeSelect(sel);
    const trigger1 = parent.querySelector('.custom-select-trigger');
    const wrap1 = parent.querySelector('.custom-select-wrap');

    // Create second select
    const sel2 = document.createElement('select');
    const opt = document.createElement('option');
    opt.value = 'x';
    opt.textContent = 'X-ray';
    sel2.appendChild(opt);
    parent.appendChild(sel2);
    upgradeSelect(sel2);

    // Open first
    trigger1.click();
    expect(wrap1.classList.contains('open')).toBe(true);

    // Open second - first should close
    const trigger2 = parent.querySelectorAll('.custom-select-trigger')[1];
    trigger2.click();
    expect(wrap1.classList.contains('open')).toBe(false);
  });

  it('handles optgroup elements', () => {
    // Create select with optgroups
    const grpSel = document.createElement('select');
    const group = document.createElement('optgroup');
    group.label = 'Group 1';
    const gOpt = document.createElement('option');
    gOpt.value = 'g1';
    gOpt.textContent = 'G-One';
    group.appendChild(gOpt);
    grpSel.appendChild(group);
    parent.appendChild(grpSel);

    upgradeSelect(grpSel);
    const groupHeader = parent.querySelector('.custom-select-group');
    expect(groupHeader).not.toBeNull();
    expect(groupHeader.textContent).toBe('Group 1');
    const options = parent.querySelectorAll('.custom-select-option');
    // Should have the option from the optgroup
    expect(options.length).toBeGreaterThanOrEqual(1);
  });

  it('skips empty options in _addOption', () => {
    const emptySel = document.createElement('select');
    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '';
    emptySel.appendChild(emptyOpt);
    const realOpt = document.createElement('option');
    realOpt.value = 'real';
    realOpt.textContent = 'Real';
    emptySel.appendChild(realOpt);
    parent.appendChild(emptySel);

    upgradeSelect(emptySel);
    const wrap = emptySel.parentNode;
    const options = wrap.querySelectorAll('.custom-select-option');
    // Empty option should be skipped
    expect(options.length).toBe(1);
    expect(options[0].textContent).toBe('Real');
  });

  it('closes all custom selects on document click', () => {
    upgradeSelect(sel);
    const trigger = parent.querySelector('.custom-select-trigger');
    const wrap = parent.querySelector('.custom-select-wrap');
    trigger.click();
    expect(wrap.classList.contains('open')).toBe(true);
    // Click elsewhere on document
    document.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(wrap.classList.contains('open')).toBe(false);
  });
});

describe('safeDataUri - additional branches', () => {
  it('handles HTTP URLs (not just HTTPS)', () => {
    const url = 'http://example.com/image.png';
    const result = safeDataUri(url);
    expect(result).toContain('http://example.com/image.png');
  });

  it('returns empty string when URL constructor throws on malformed URL-like string', () => {
    // A string that matches /^https?:\/\// but is an invalid URL
    const result = safeDataUri('http://');
    expect(result).toBe('');
  });

  it('returns valid data URI for gif', () => {
    const uri = 'data:image/gif;base64,R0lGODlh';
    expect(safeDataUri(uri)).toBe(uri);
  });

  it('returns valid data URI for webp', () => {
    const uri = 'data:image/webp;base64,UklGR';
    expect(safeDataUri(uri)).toBe(uri);
  });

  it('returns empty for data URI with invalid characters', () => {
    expect(safeDataUri('data:image/png;base64,invalid chars!')).toBe('');
  });
});

describe('esc - additional branches', () => {
  it('returns empty string for null', () => {
    expect(esc(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(esc(undefined)).toBe('');
  });

  it('handles string with already-escaped-looking content', () => {
    // &amp; in input should be double-escaped
    expect(esc('&amp;')).toBe('&amp;amp;');
  });

  it('handles empty string', () => {
    expect(esc('')).toBe('');
  });

  it('handles numeric input coerced to string', () => {
    // Numbers are not null, so they go through textContent
    expect(esc(0)).toBe('0');
  });
});

describe('fmtNum - additional edge cases', () => {
  it('formats negative numbers', () => {
    expect(fmtNum(-5)).toBe('-5');
  });

  it('formats negative decimals', () => {
    expect(fmtNum(-3.7)).toBe('-3.7');
  });

  it('formats very large numbers', () => {
    expect(fmtNum(1000000)).toBe('1000000');
  });

  it('formats very small decimals', () => {
    expect(fmtNum(0.1)).toBe('0.1');
  });

  it('returns dash for empty string', () => {
    expect(fmtNum('')).toBe('-');
  });

  it('formats string integer', () => {
    expect(fmtNum('42')).toBe('42');
  });
});

describe('showToast - additional branches', () => {
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

  it('does nothing when toast element is missing', () => {
    toastEl.remove();
    expect(() => showToast('msg', 'info')).not.toThrow();
  });

  it('clears previous timer when called twice rapidly', () => {
    const clearSpy = vi.spyOn(global, 'clearTimeout');
    showToast('First', 'info');
    showToast('Second', 'success');
    // clearTimeout should have been called for the first timer
    expect(clearSpy).toHaveBeenCalled();
    expect(toastEl.firstChild.textContent).toBe('Second');
    // Only the second timer should fire
    vi.advanceTimersByTime(3000);
    expect(toastEl.classList.contains('show')).toBe(false);
  });
});

describe('api - additional branches', () => {
  it('uses generic error message when response has no error field', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('{}'),
    });
    try {
      await api('/fail');
    } catch (e) {
      expect(e.message).toBe('Request failed: 500');
      expect(e.status).toBe(500);
    }
  });

  it('merges custom headers with defaults', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{}'),
    });
    await api('/test', { headers: { 'X-Custom': 'yes' } });
    // GET requests (no body) should not send Content-Type, only custom headers
    expect(global.fetch).toHaveBeenCalledWith('/test', expect.objectContaining({
      headers: { 'X-Custom': 'yes' },
    }));
  });
});

describe('fetchProducts - additional branches', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('[]'),
    });
  });

  it('includes advancedFilters when set', async () => {
    state.advancedFilters = 'sugar<10';
    await fetchProducts('', []);
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('filters=sugar%3C10');
    state.advancedFilters = null;
  });
});
