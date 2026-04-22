import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../i18n.js', () => ({
  t: vi.fn((key, params) => {
    if (!params) return key;
    return key + Object.entries(params).map(([k, v]) => `:${k}=${v}`).join('');
  }),
}));

import { initTagInput, getTagsForSave } from '../tags.js';

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
  document.body.innerHTML = '<div id="tag-field-ed"></div>';
  mockFetchGet([]);
});

afterEach(() => {
  const overlay = document.getElementById('tag-modal-overlay');
  if (overlay) overlay.remove();
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
    expect(btn.getAttribute('aria-label')).toBe('tag_remove_aria_label:label=crunchy');
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

  it('creates an "Add Tag" button in edit mode', () => {
    initTagInput([]);
    expect(document.getElementById('add-tag-btn')).not.toBeNull();
  });

  it('does not duplicate the Add Tag button on re-init', () => {
    initTagInput([]);
    initTagInput([{ id: 1, label: 'new' }]);
    expect(document.querySelectorAll('#add-tag-btn').length).toBe(1);
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
});

// ── Pill remove interactions ─────────────────────────────────────────────────

describe('pill remove', () => {
  it('removes a tag when x is clicked', () => {
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

// ── Add Tag button ───────────────────────────────────────────────────────────

describe('Add Tag button', () => {
  it('opens a modal when clicked', () => {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    expect(document.getElementById('tag-modal-overlay')).not.toBeNull();
  });

  it('modal contains input, confirm, and cancel buttons', () => {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    expect(document.getElementById('tag-modal-input')).not.toBeNull();
    expect(document.getElementById('tag-modal-confirm')).not.toBeNull();
    expect(document.getElementById('tag-modal-cancel')).not.toBeNull();
  });

  it('modal has correct aria attributes', () => {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    const overlay = document.getElementById('tag-modal-overlay');
    expect(overlay.getAttribute('role')).toBe('dialog');
    expect(overlay.getAttribute('aria-modal')).toBe('true');
  });
});

// ── modal cancel / close ─────────────────────────────────────────────────────

describe('modal cancel and close', () => {
  function openModal() {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
  }

  it('Cancel button closes modal without adding a tag', () => {
    openModal();
    const input = document.getElementById('tag-modal-input');
    input.value = 'sometag';
    document.getElementById('tag-modal-cancel').click();
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
    expect(getTagsForSave()).toEqual([]);
  });

  it('Escape key closes modal without adding a tag', () => {
    openModal();
    const input = document.getElementById('tag-modal-input');
    input.value = 'sometag';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
    expect(getTagsForSave()).toEqual([]);
  });

  it('clicking the overlay backdrop closes modal', () => {
    openModal();
    const overlay = document.getElementById('tag-modal-overlay');
    overlay.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('clicking inside the modal does not close it', () => {
    openModal();
    document.getElementById('tag-modal-input').dispatchEvent(
      new MouseEvent('click', { bubbles: true })
    );
    expect(document.getElementById('tag-modal-overlay')).not.toBeNull();
  });
});

// ── modal confirm / add tag ──────────────────────────────────────────────────

describe('modal confirm', () => {
  function openModal() {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
  }

  it('Confirm button POSTs and adds tag on success, then closes modal', async () => {
    mockFetchPost({ id: 10, label: 'spicy' });
    openModal();
    document.getElementById('tag-modal-input').value = 'spicy';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/tags',
      expect.objectContaining({ method: 'POST' })
    ));
    await vi.waitFor(() => expect(getTagsForSave()).toContain(10));
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('Enter key POSTs and adds tag on success, then closes modal', async () => {
    mockFetchPost({ id: 11, label: 'crunchy' });
    openModal();
    const input = document.getElementById('tag-modal-input');
    input.value = 'crunchy';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/tags',
      expect.objectContaining({ method: 'POST' })
    ));
    await vi.waitFor(() => expect(getTagsForSave()).toContain(11));
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('Confirm with empty input closes modal without adding tag', () => {
    openModal();
    document.getElementById('tag-modal-input').value = '';
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toEqual([]);
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('does not add tag if POST returns non-ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });
    openModal();
    document.getElementById('tag-modal-input').value = 'fail';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(document.getElementById('tag-modal-overlay')).toBeNull());
    expect(getTagsForSave()).toEqual([]);
  });

  it('does not add tag if POST throws', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    openModal();
    document.getElementById('tag-modal-input').value = 'error';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(document.getElementById('tag-modal-overlay')).toBeNull());
    expect(getTagsForSave()).toEqual([]);
  });
});

// ── modal suggestion list ────────────────────────────────────────────────────

describe('modal suggestions', () => {
  async function openModalWithSuggestions(suggestions) {
    vi.useFakeTimers();
    mockFetchGet(suggestions);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    vi.useRealTimers();
  }

  it('fetches suggestions on modal open with empty query', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }, { id: 2, label: 'savory' }]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenCalledWith('/api/tags?q=');
    expect(document.getElementById('tag-modal-suggestions').hidden).toBe(false);
    vi.useRealTimers();
  });

  it('fetches suggestions as user types in modal', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }, { id: 2, label: 'savory' }]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();

    const input = document.getElementById('tag-modal-input');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenCalledWith('/api/tags?q=sa');
    vi.useRealTimers();
  });

  it('hides suggestions when fetch returns empty', async () => {
    vi.useFakeTimers();
    mockFetchGet([]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    expect(document.getElementById('tag-modal-suggestions').hidden).toBe(true);
    vi.useRealTimers();
  });

  it('hides suggestions on fetch error', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    expect(document.getElementById('tag-modal-suggestions').hidden).toBe(true);
    vi.useRealTimers();
  });

  it('does not show already-selected tags in suggestions', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 1, label: 'salty' }, { id: 2, label: 'savory' }]);
    initTagInput([{ id: 1, label: 'salty' }]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    const items = document.querySelectorAll('#tag-modal-suggestions li');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toBe('savory');
    vi.useRealTimers();
  });

  it('clicking a suggestion adds tag and closes modal', async () => {
    await openModalWithSuggestions([{ id: 3, label: 'salty' }, { id: 4, label: 'savory' }]);
    const li = document.querySelector('#tag-modal-suggestions li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain(3);
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('fetches with empty query when input is cleared', async () => {
    vi.useFakeTimers();
    mockFetchGet([]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();

    const input = document.getElementById('tag-modal-input');
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenLastCalledWith('/api/tags?q=');
    vi.useRealTimers();
  });

  it('clicking a suggestion after typing adds tag and closes modal', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 5, label: 'salty' }]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();

    const input = document.getElementById('tag-modal-input');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();

    const li = document.querySelector('#tag-modal-suggestions li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain(5);
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('suggestion li has data-tag-id and data-tag-label', async () => {
    vi.useFakeTimers();
    mockFetchGet([{ id: 9, label: 'umami' }]);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    const li = document.querySelector('#tag-modal-suggestions li');
    expect(li.dataset.tagId).toBe('9');
    expect(li.dataset.tagLabel).toBe('umami');
  });
});

// ── modal arrow key navigation ───────────────────────────────────────────────

describe('modal arrow key navigation', () => {
  async function setupWithSuggestions(suggestions) {
    vi.useFakeTimers();
    mockFetchGet(suggestions);
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    return {
      input: document.getElementById('tag-modal-input'),
      list: document.getElementById('tag-modal-suggestions'),
    };
  }

  it('ArrowDown highlights the first item', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
    expect(items[1].classList.contains('highlighted')).toBe(false);
  });

  it('subsequent ArrowDown advances highlight', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }, { id: 3, label: 'smoky' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowDown does not go past last item', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp moves highlight back', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp with no highlight selects last item', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[items.length - 1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp does not go past first item', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowDown does nothing when list is hidden', async () => {
    const { input, list } = await setupWithSuggestions([]);
    expect(list.hidden).toBe(true);
    expect(() =>
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }))
    ).not.toThrow();
  });

  it('Enter with highlighted suggestion adds that tag and closes modal', async () => {
    const { input, list } = await setupWithSuggestions([
      { id: 1, label: 'salty' }, { id: 2, label: 'savory' }
    ]);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(list.querySelectorAll('li')[1].classList.contains('highlighted')).toBe(true);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain(2);
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });
});

// ── Missing DOM elements ─────────────────────────────────────────────────────

describe('missing DOM elements', () => {
  it('safe no-op when tag-field-ed is absent', () => {
    document.body.innerHTML = '';
    expect(() => initTagInput([{ id: 1, label: 'test' }])).not.toThrow();
    expect(getTagsForSave()).toEqual([1]);
  });

  it('safe no-op when field is present but empty (button gets created)', () => {
    document.body.innerHTML = '<div id="tag-field-ed"></div>';
    expect(() => initTagInput([])).not.toThrow();
    expect(document.getElementById('add-tag-btn')).not.toBeNull();
  });

  it('getTagsForSave works when field element is absent', () => {
    document.body.innerHTML = '';
    initTagInput([{ id: 4, label: 'x' }]);
    expect(() => getTagsForSave()).not.toThrow();
    expect(getTagsForSave()).toEqual([4]);
  });
});

// ── Tag edge cases ────────────────────────────────────────────────────────────

describe('tag edge cases', () => {
  it('does not add duplicate tag (same id)', async () => {
    initTagInput([{ id: 1, label: 'alpha' }]);
    mockFetchPost({ id: 1, label: 'alpha' });
    document.getElementById('add-tag-btn').click();
    document.getElementById('tag-modal-input').value = 'alpha';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(document.getElementById('tag-modal-overlay')).toBeNull());
    expect(getTagsForSave()).toEqual([1]);
  });

  it('handles tag with special characters safely in text content', async () => {
    mockFetchPost({ id: 20, label: '<b>bold</b>' });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    document.getElementById('tag-modal-input').value = '<b>bold</b>';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(getTagsForSave()).toContain(20));
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(1);
    expect(pills[0].textContent).toContain('<b>bold</b>');
  });

  it('trims whitespace from tag input before POST', async () => {
    mockFetchPost({ id: 30, label: 'trimmed' });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    document.getElementById('tag-modal-input').value = '  trimmed  ';
    document.getElementById('tag-modal-confirm').click();
    await vi.waitFor(() => {
      const postCall = global.fetch.mock.calls.find(c => c[1] && c[1].method === 'POST');
      expect(postCall).toBeTruthy();
      const body = JSON.parse(postCall[1].body);
      expect(body.label).toBe('trimmed');
    });
  });

  it('empty input after trim closes modal without POST', () => {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    document.getElementById('tag-modal-input').value = '   ';
    document.getElementById('tag-modal-confirm').click();
    expect(global.fetch).not.toHaveBeenCalledWith('/api/tags', expect.anything());
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('removes all tags one by one', () => {
    initTagInput([{ id: 1, label: 'a' }, { id: 2, label: 'b' }, { id: 3, label: 'c' }]);
    while (document.querySelectorAll('.tag-remove').length > 0) {
      document.querySelectorAll('.tag-remove')[0].click();
    }
    expect(getTagsForSave()).toEqual([]);
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });
});
