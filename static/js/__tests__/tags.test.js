import { describe, it, expect, vi, beforeEach } from 'vitest';
import { initTagInput, getTagsForSave } from '../tags.js';

const DOM = `
  <div id="tag-field-ed">
    <input id="tag-input-ed" value="" />
    <ul id="tag-suggestions-ed" hidden></ul>
  </div>
`;

function mockFetchGet(suggestions) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(suggestions),
  });
}

function mockFetchPost(tag) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: tag !== null,
    json: () => Promise.resolve(tag || {}),
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = DOM;
  mockFetchGet([]);
});

// ── initTagInput ─────────────────────────────────────────────────────────────

describe('initTagInput', () => {
  it('initializes with empty array', () => {
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });

  it('initializes with existing tags', () => {
    initTagInput([{ id: 1, label: 'salty' }, { id: 2, label: 'sweet' }]);
    const ids = getTagsForSave();
    expect(ids).toContain(1);
    expect(ids).toContain(2);
    expect(ids.length).toBe(2);
  });

  it('treats null as empty', () => {
    initTagInput(null);
    expect(getTagsForSave()).toEqual([]);
  });

  it('treats undefined as empty', () => {
    initTagInput(undefined);
    expect(getTagsForSave()).toEqual([]);
  });

  it('renders pills sorted alphabetically by label', () => {
    initTagInput([{ id: 2, label: 'zebra' }, { id: 1, label: 'apple' }]);
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(2);
    expect(pills[0].textContent).toContain('apple');
    expect(pills[1].textContent).toContain('zebra');
  });

  it('pill has data-tag-id and correct aria-label on remove button', () => {
    initTagInput([{ id: 5, label: 'crunchy' }]);
    const pill = document.querySelector('.tag-pill');
    expect(pill.dataset.tagId).toBe('5');
    const btn = pill.querySelector('.tag-remove');
    expect(btn.getAttribute('aria-label')).toBe('Remove tag crunchy');
  });

  it('skips entries missing id or label', () => {
    initTagInput([{ id: 1, label: 'ok' }, null, { label: 'noid' }, { id: 2 }]);
    expect(getTagsForSave()).toEqual([1]);
  });

  it('resets state on re-init', () => {
    initTagInput([{ id: 1, label: 'first' }]);
    initTagInput([{ id: 2, label: 'second' }]);
    const ids = getTagsForSave();
    expect(ids).toEqual([2]);
  });
});

// ── getTagsForSave ───────────────────────────────────────────────────────────

describe('getTagsForSave', () => {
  it('returns integer IDs', () => {
    initTagInput([{ id: 3, label: 'umami' }]);
    const ids = getTagsForSave();
    expect(ids).toEqual([3]);
    expect(typeof ids[0]).toBe('number');
  });

  it('returns empty array when no tags', () => {
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });

  it('flushes uncommitted input text (clears input)', () => {
    initTagInput([{ id: 1, label: 'existing' }]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'uncommitted';
    const ids = getTagsForSave();
    expect(input.value).toBe('');
    // Only the pre-existing tag is returned (uncommitted text is discarded)
    expect(ids).toEqual([1]);
  });

  it('ignores whitespace-only uncommitted input', () => {
    initTagInput([{ id: 1, label: 'existing' }]);
    const input = document.getElementById('tag-input-ed');
    input.value = '   ';
    const ids = getTagsForSave();
    expect(ids).toEqual([1]);
  });
});

// ── Pill remove interactions ─────────────────────────────────────────────────

describe('pill remove', () => {
  it('removes a tag when × is clicked', () => {
    initTagInput([{ id: 1, label: 'alpha' }, { id: 2, label: 'beta' }]);
    const btns = document.querySelectorAll('.tag-remove');
    btns[0].click(); // removes 'alpha' (sorted first)
    const ids = getTagsForSave();
    expect(ids).not.toContain(1);
    expect(ids).toContain(2);
  });

  it('updates pill list after removal', () => {
    initTagInput([{ id: 1, label: 'alpha' }, { id: 2, label: 'beta' }]);
    document.querySelectorAll('.tag-remove')[0].click();
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
  });

  it('does not render pills when tag-field-ed is missing', () => {
    document.body.innerHTML = '';
    expect(() => initTagInput([{ id: 1, label: 'test' }])).not.toThrow();
    expect(getTagsForSave()).toEqual([1]);
  });
});

// ── Keyboard: Enter ──────────────────────────────────────────────────────────

describe('keyboard: Enter', () => {
  it('does nothing on Enter with empty input and no highlight', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toEqual([]);
  });

  it('POSTs and adds tag on Enter with text (no highlight)', async () => {
    mockFetchPost({ id: 10, label: 'spicy' });
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'spicy';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/tags',
      expect.objectContaining({ method: 'POST' })
    ));
    await vi.waitFor(() => expect(getTagsForSave()).toContain(10));
    expect(input.value).toBe('');
  });

  it('does not add tag if POST returns non-ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'fail';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(input.value).toBe(''));
    expect(getTagsForSave()).toEqual([]);
  });

  it('does not add tag if POST throws', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'error';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(input.value).toBe(''));
    expect(getTagsForSave()).toEqual([]);
  });

  it('adds highlighted suggestion on Enter without POSTing', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 5, label: 'salty' }, { id: 6, label: 'savory' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();

    expect(list.hidden).toBe(false);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain(5);
    expect(list.hidden).toBe(true);
    // fetch was GET only, no POST
    expect(global.fetch).not.toHaveBeenCalledWith('/api/tags', expect.anything());
  });
});

// ── Keyboard: Backspace ──────────────────────────────────────────────────────

describe('keyboard: Backspace', () => {
  it('removes last alphabetical tag on Backspace with empty input', () => {
    initTagInput([{ id: 1, label: 'alpha' }, { id: 2, label: 'beta' }, { id: 3, label: 'gamma' }]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    const ids = getTagsForSave();
    expect(ids).not.toContain(3); // 'gamma' is last alphabetically
    expect(ids).toContain(1);
    expect(ids).toContain(2);
  });

  it('does not remove tags on Backspace when input has text', () => {
    initTagInput([{ id: 1, label: 'alpha' }]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'ab';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    expect(getTagsForSave()).toContain(1);
  });

  it('does nothing on Backspace when no tags', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    expect(() =>
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }))
    ).not.toThrow();
    expect(getTagsForSave()).toEqual([]);
  });
});

// ── Keyboard: Escape ─────────────────────────────────────────────────────────

describe('keyboard: Escape', () => {
  it('clears input and hides dropdown without adding tag', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'test';
    list.hidden = false;
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
    expect(getTagsForSave()).toEqual([]);
  });
});

// ── Keyboard: Tab ────────────────────────────────────────────────────────────

describe('keyboard: Tab', () => {
  it('accepts first suggestion on Tab when dropdown is open', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 7, label: 'salty' }, { id: 8, label: 'savory' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();

    expect(list.hidden).toBe(false);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(getTagsForSave()).toContain(7);
    expect(list.hidden).toBe(true);
  });

  it('does nothing on Tab when dropdown is hidden', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = true;
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(getTagsForSave()).toEqual([]);
  });
});

// ── Arrow key navigation ─────────────────────────────────────────────────────

describe('arrow key navigation', () => {
  async function openDropdown(suggestions) {
    vi.useFakeTimers();
    mockFetchGet(suggestions);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    return { input, list };
  }

  it('ArrowDown highlights first item', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    expect(list.hidden).toBe(false);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
    expect(items[1].classList.contains('highlighted')).toBe(false);
  });

  it('subsequent ArrowDown advances highlight', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }, { id: 3, label: 'smoky' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(false);
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowDown at last item stays on last', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp from top stays on first', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp with no highlight selects last item', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp then ArrowDown moves to second', async () => {
    const { input, list } = await openDropdown([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
    expect(items[1].classList.contains('highlighted')).toBe(false);
  });

  it('ArrowDown does nothing when list is hidden', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    expect(() =>
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }))
    ).not.toThrow();
  });
});

// ── Suggestion fetch & display ───────────────────────────────────────────────

describe('suggestion list', () => {
  it('focus triggers GET with empty q and shows dropdown', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }, { id: 2, label: 'savory' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.dispatchEvent(new Event('focus', { bubbles: true }));
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    expect(global.fetch).toHaveBeenCalledWith('/api/tags?q=');
    expect(list.hidden).toBe(false);
    expect(list.querySelectorAll('li').length).toBe(2);
  });

  it('typing debounces and fetches suggestions', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    expect(global.fetch).toHaveBeenCalledWith('/api/tags?q=sal');
    expect(list.hidden).toBe(false);
    expect(list.querySelectorAll('li').length).toBe(1);
  });

  it('hides dropdown on empty input', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(list.hidden).toBe(true);
  });

  it('hides dropdown when fetch returns no results', async () => {
    vi.useFakeTimers();
    mockFetchGet([]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'xyz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    expect(list.hidden).toBe(true);
  });

  it('hides dropdown on fetch error', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = 'err';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    expect(list.hidden).toBe(true);
  });

  it('hides dropdown on blur after delay', () => {
    vi.useFakeTimers();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.dispatchEvent(new Event('blur', { bubbles: true }));
    vi.advanceTimersByTime(200);
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('filters already-selected tags by ID from suggestions', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }, { id: 2, label: 'savory' }]);
    initTagInput([{ id: 1, label: 'salty' }]); // salty already selected
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    const items = list.querySelectorAll('li');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toBe('savory');
  });

  it('clicking suggestion adds tag and clears input', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 3, label: 'salty' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();

    const li = list.querySelector('li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain(3);
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
  });

  it('suggestion li has data-tag-id and data-tag-label', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 9, label: 'umami' }]);
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'um';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    const li = document.querySelector('#tag-suggestions-ed li');
    expect(li.dataset.tagId).toBe('9');
    expect(li.dataset.tagLabel).toBe('umami');
  });
});

// ── Field click ──────────────────────────────────────────────────────────────

describe('field click', () => {
  it('focuses input when clicking on field background', () => {
    initTagInput([]);
    const field = document.getElementById('tag-field-ed');
    const input = document.getElementById('tag-input-ed');
    const focusSpy = vi.spyOn(input, 'focus');
    field.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(focusSpy).toHaveBeenCalled();
  });
});

// ── Missing DOM elements ─────────────────────────────────────────────────────

describe('missing DOM elements', () => {
  it('safe no-op when tag-field-ed is absent', () => {
    document.body.innerHTML = '';
    expect(() => initTagInput([{ id: 1, label: 'test' }])).not.toThrow();
    expect(getTagsForSave()).toEqual([1]);
  });

  it('safe no-op when input and list are absent', () => {
    document.body.innerHTML = '<div id="tag-field-ed"></div>';
    expect(() => initTagInput([])).not.toThrow();
  });

  it('getTagsForSave works when input element is absent', () => {
    document.body.innerHTML = '';
    initTagInput([{ id: 4, label: 'x' }]);
    expect(() => getTagsForSave()).not.toThrow();
    expect(getTagsForSave()).toEqual([4]);
  });
});
