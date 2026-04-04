import { describe, it, expect, vi, beforeEach } from 'vitest';
import { initTagInput, getTagsForSave } from '../tags.js';

beforeEach(() => {
  vi.restoreAllMocks();
  // Default fetch mock: return empty suggestions so tests that incidentally
  // trigger focus/fetch don't throw "fetch is not defined".
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve([]),
  });
  document.body.innerHTML = `
    <div id="tag-field-ed">
      <input id="tag-input-ed" value="" />
      <ul id="tag-suggestions-ed" hidden></ul>
    </div>
  `;
});

describe('initTagInput', () => {
  it('initializes with empty tags', () => {
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });

  it('initializes with existing tags and renders pills', () => {
    initTagInput(['Salty', 'Sweet']);
    expect(getTagsForSave()).toEqual(['salty', 'sweet']);
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(2);
  });

  it('trims and lowercases tags', () => {
    initTagInput(['  Hello  ', 'WORLD']);
    expect(getTagsForSave()).toEqual(['hello', 'world']);
  });

  it('deduplicates tags', () => {
    initTagInput(['hello', 'Hello', 'HELLO']);
    expect(getTagsForSave()).toEqual(['hello']);
  });

  it('handles null/undefined input', () => {
    initTagInput(null);
    expect(getTagsForSave()).toEqual([]);
    initTagInput(undefined);
    expect(getTagsForSave()).toEqual([]);
  });
});

describe('getTagsForSave', () => {
  it('flushes uncommitted input text before returning', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'newTag';
    const tags = getTagsForSave();
    expect(tags).toContain('newtag');
    expect(input.value).toBe('');
  });

  it('ignores whitespace-only input', () => {
    initTagInput(['existing']);
    const input = document.getElementById('tag-input-ed');
    input.value = '   ';
    const tags = getTagsForSave();
    expect(tags).toEqual(['existing']);
  });
});

describe('tag pill interactions', () => {
  it('removes a tag when the remove button is clicked', () => {
    initTagInput(['alpha', 'beta']);
    expect(getTagsForSave()).toEqual(['alpha', 'beta']);
    const removeBtn = document.querySelector('.tag-remove[data-tag="alpha"]');
    removeBtn.click();
    expect(getTagsForSave()).toEqual(['beta']);
  });

  it('does not render pills when tag-field-ed is missing', () => {
    document.body.innerHTML = '';
    initTagInput(['test']);
    // Should not throw, tags are still tracked internally
    expect(getTagsForSave()).toEqual(['test']);
  });
});

describe('keyboard interactions', () => {
  it('adds a tag on Enter key (no suggestion highlighted)', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'spicy';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain('spicy');
    expect(input.value).toBe('');
  });

  it('comma key does NOT add a tag', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'sweet';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: ',', bubbles: true }));
    // comma is no longer a trigger — input value should be unchanged
    expect(input.value).toBe('sweet');
    expect(getTagsForSave()).not.toContain('sweet');
  });

  it('removes last tag on Backspace with empty input', () => {
    initTagInput(['alpha', 'beta', 'gamma']);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    // Removes last sorted tag
    const tags = getTagsForSave();
    expect(tags).not.toContain('gamma');
    expect(tags).toContain('alpha');
    expect(tags).toContain('beta');
  });

  it('does not remove tags on Backspace when input has text', () => {
    initTagInput(['alpha']);
    const input = document.getElementById('tag-input-ed');
    input.value = 'ab';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    expect(getTagsForSave()).toContain('alpha');
  });

  it('ignores tags longer than 50 characters', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'a'.repeat(51);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toEqual([]);
  });

  it('ignores empty tag on Enter', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toEqual([]);
  });

  it('Escape clears input and hides dropdown without adding a tag', () => {
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

describe('arrow key navigation', () => {
  async function setupWithSuggestions(suggestions) {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(suggestions),
    });
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

  it('ArrowDown highlights the first li', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    expect(list.hidden).toBe(false);
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
    expect(items[0].classList.contains('highlighted')).toBe(false);
    expect(items[1].classList.contains('highlighted')).toBe(true);
  });

  it('ArrowUp moves highlight back', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    // Go down twice, then up once
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
    const items = list.querySelectorAll('li');
    expect(items[0].classList.contains('highlighted')).toBe(true);
    expect(items[1].classList.contains('highlighted')).toBe(false);
  });

  it('Enter with highlighted item adds that tag', async () => {
    const { input, list } = await setupWithSuggestions(['salty', 'savory']);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    // Second item is now highlighted
    const items = list.querySelectorAll('li');
    expect(items[1].classList.contains('highlighted')).toBe(true);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(getTagsForSave()).toContain('savory');
    expect(getTagsForSave()).not.toContain('salty');
    expect(list.hidden).toBe(true);
  });
});

describe('suggestion list', () => {
  it('hides suggestions on empty input', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(list.hidden).toBe(true);
  });

  it('hides suggestions on blur after delay', () => {
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

  it('focus event triggers fetch with q= and shows dropdown', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.dispatchEvent(new Event('focus', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(global.fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=');
    expect(list.hidden).toBe(false);
    expect(list.querySelectorAll('li').length).toBe(2);
    vi.useRealTimers();
  });

  it('fetches and displays suggestions on input', async () => {
    vi.useFakeTimers();
    const mockSuggestions = ['salty', 'savory'];
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockSuggestions),
    });

    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    expect(global.fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=sal');
    expect(list.hidden).toBe(false);
    expect(list.querySelectorAll('li').length).toBe(2);
    vi.useRealTimers();
  });

  it('hides suggestions when fetch returns empty', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve([]),
    });

    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'xyz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('hides suggestions on fetch error', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));

    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'test';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('adds suggestion on mousedown and clears input', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty']),
    });

    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    const li = list.querySelector('li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(getTagsForSave()).toContain('salty');
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('dropdown does not show already-selected tags', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });

    initTagInput(['salty']);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    const items = list.querySelectorAll('li');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toBe('savory');
    vi.useRealTimers();
  });

  it('Tab completes first visible suggestion', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['salty', 'savory']),
    });

    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'sa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(250);
    await vi.runAllTimersAsync();

    expect(list.hidden).toBe(false);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(getTagsForSave()).toContain('salty');
    vi.useRealTimers();
  });

  it('Tab does nothing when suggestions are hidden', () => {
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = true;
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    // Should not add any tag from suggestion
    expect(getTagsForSave()).toEqual([]);
  });
});

describe('field click', () => {
  it('focuses input when clicking on the tag field', () => {
    initTagInput([]);
    const field = document.getElementById('tag-field-ed');
    const input = document.getElementById('tag-input-ed');
    const focusSpy = vi.spyOn(input, 'focus');
    field.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(focusSpy).toHaveBeenCalled();
  });
});

describe('no input or list elements', () => {
  it('handles missing input element gracefully', () => {
    document.body.innerHTML = '<div id="tag-field-ed"></div>';
    expect(() => initTagInput(['test'])).not.toThrow();
  });
});
