import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initTagInput, getTagsForSave } from '../tags.js';

beforeEach(() => {
  vi.restoreAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve([]),
  });
  document.body.innerHTML = '<div id="tag-field-ed"></div>';
});

afterEach(() => {
  // Clean up any open modals
  const overlay = document.getElementById('tag-modal-overlay');
  if (overlay) overlay.remove();
});

// ─── initTagInput ────────────────────────────────────────────────────────────

describe('initTagInput', () => {
  it('initializes with empty tags', () => {
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });

  it('initializes with existing tags and renders pills', () => {
    initTagInput(['Salty', 'Sweet']);
    expect(getTagsForSave().sort()).toEqual(['salty', 'sweet']);
    expect(document.querySelectorAll('.tag-pill').length).toBe(2);
  });

  it('trims and lowercases tags', () => {
    initTagInput(['  Hello  ', 'WORLD']);
    expect(getTagsForSave().sort()).toEqual(['hello', 'world']);
  });

  it('deduplicates tags', () => {
    initTagInput(['hello', 'Hello', 'HELLO']);
    expect(getTagsForSave()).toEqual(['hello']);
  });

  it('handles null input', () => {
    initTagInput(null);
    expect(getTagsForSave()).toEqual([]);
  });

  it('handles undefined input', () => {
    initTagInput(undefined);
    expect(getTagsForSave()).toEqual([]);
  });

  it('creates an "Add Tag" button in edit mode', () => {
    initTagInput([]);
    expect(document.getElementById('add-tag-btn')).not.toBeNull();
  });

  it('does not duplicate the Add Tag button on re-init', () => {
    initTagInput([]);
    initTagInput(['new']);
    expect(document.querySelectorAll('#add-tag-btn').length).toBe(1);
  });

  it('does not render pills or button when tag-field-ed is missing', () => {
    document.body.innerHTML = '';
    expect(() => initTagInput(['test'])).not.toThrow();
    expect(getTagsForSave()).toEqual(['test']);
  });
});

// ─── getTagsForSave ──────────────────────────────────────────────────────────

describe('getTagsForSave', () => {
  it('returns current tags array', () => {
    initTagInput(['alpha', 'beta']);
    expect(getTagsForSave().sort()).toEqual(['alpha', 'beta']);
  });

  it('returns empty array when no tags', () => {
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });
});

// ─── tag pill interactions ───────────────────────────────────────────────────

describe('tag pill interactions', () => {
  it('renders remove buttons with data-tag attribute', () => {
    initTagInput(['alpha']);
    const btn = document.querySelector('.tag-remove[data-tag="alpha"]');
    expect(btn).not.toBeNull();
  });

  it('removes a tag when the remove button is clicked', () => {
    initTagInput(['alpha', 'beta']);
    document.querySelector('.tag-remove[data-tag="alpha"]').click();
    expect(getTagsForSave()).not.toContain('alpha');
    expect(getTagsForSave()).toContain('beta');
  });

  it('re-renders pills after removal', () => {
    initTagInput(['alpha', 'beta']);
    document.querySelector('.tag-remove[data-tag="alpha"]').click();
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
  });
});

// ─── Add Tag button ──────────────────────────────────────────────────────────

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

// ─── modal cancel / close ────────────────────────────────────────────────────

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

// ─── modal confirm / add tag ─────────────────────────────────────────────────

describe('modal confirm', () => {
  function openModal() {
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
  }

  it('Confirm button adds typed tag and closes modal', () => {
    openModal();
    document.getElementById('tag-modal-input').value = 'spicy';
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toContain('spicy');
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('Enter key adds typed tag and closes modal', () => {
    openModal();
    const input = document.getElementById('tag-modal-input');
    input.value = 'crunchy';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain('crunchy');
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('Confirm with empty input closes modal without adding tag', () => {
    openModal();
    document.getElementById('tag-modal-input').value = '';
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toEqual([]);
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('trims and lowercases tag on confirm', () => {
    openModal();
    document.getElementById('tag-modal-input').value = '  SALTY  ';
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toContain('salty');
  });

  it('ignores tags longer than 50 characters', () => {
    openModal();
    document.getElementById('tag-modal-input').value = 'a'.repeat(51);
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toEqual([]);
  });

  it('ignores duplicate tags', () => {
    initTagInput(['existing']);
    document.getElementById('add-tag-btn').click();
    document.getElementById('tag-modal-input').value = 'existing';
    document.getElementById('tag-modal-confirm').click();
    expect(getTagsForSave()).toEqual(['existing']);
  });
});

// ─── modal suggestion list ───────────────────────────────────────────────────

describe('modal suggestions', () => {
  async function openModalWithSuggestions(suggestions) {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(suggestions),
    });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    // Initial fetch on open (empty query)
    await vi.runAllTimersAsync();
    vi.useRealTimers();
  }

  it('fetches suggestions on modal open with empty query', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=');
    expect(document.getElementById('tag-modal-suggestions').hidden).toBe(false);
    vi.useRealTimers();
  });

  it('fetches suggestions as user types in modal', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync(); // clear initial fetch

    const input = document.getElementById('tag-modal-input');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=sa');
    vi.useRealTimers();
  });

  it('hides suggestions when fetch returns empty', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ json: () => Promise.resolve([]) });
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
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });
    initTagInput(['salty']);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync();
    const items = document.querySelectorAll('#tag-modal-suggestions li');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toBe('savory');
    vi.useRealTimers();
  });

  it('clicking a suggestion adds tag and closes modal', async () => {
    await openModalWithSuggestions(['salty', 'savory']);
    const li = document.querySelector('#tag-modal-suggestions li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain('salty');
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });

  it('fetches with empty query when input is cleared', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ json: () => Promise.resolve([]) });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync(); // initial fetch

    const input = document.getElementById('tag-modal-input');
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenLastCalledWith('/api/products/tags/suggestions?q=');
    vi.useRealTimers();
  });

  it('clicking a suggestion after typing adds tag and closes modal', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty']),
    });
    initTagInput([]);
    document.getElementById('add-tag-btn').click();
    await vi.runAllTimersAsync(); // initial fetch

    const input = document.getElementById('tag-modal-input');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();
    vi.useRealTimers();

    const li = document.querySelector('#tag-modal-suggestions li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain('salty');
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });
});

// ─── modal arrow key navigation ──────────────────────────────────────────────

describe('modal arrow key navigation', () => {
  async function setupWithSuggestions(suggestions) {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(suggestions),
    });
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
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
    expect(items[1].classList.contains('highlighted')).toBe(false);
  });

  it('subsequent ArrowDown advances highlight', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory', 'smoky']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowDown does not go past last item', async () => {
    const { input, list } = await setupWithSuggestions(['salty']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp moves highlight back', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp with no highlight selects last item', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[items.length - 1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp does not go past first item', async () => {
    const { input, list } = await setupWithSuggestions(['salty']);
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

  it('Enter with highlighted suggestion adds that tag', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    // second item highlighted
    expect(list.querySelectorAll('li')[1].classList.contains('highlighted')).toBe(true);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain('savory');
    expect(document.getElementById('tag-modal-overlay')).toBeNull();
  });
});
