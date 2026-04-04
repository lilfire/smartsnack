import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

let initTagInput, getTagsForSave;

// Correct DOM structure matching tags.js:
//   #tag-field-ed contains #tag-input-ed and #tag-suggestions-ed
function setupDOM() {
  document.body.innerHTML = `
    <div id="tag-field-ed">
      <input id="tag-input-ed" type="text" />
      <ul id="tag-suggestions-ed" hidden></ul>
    </div>
  `;
}

beforeEach(async () => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  vi.resetModules();
  const mod = await import('../tags.js');
  initTagInput = mod.initTagInput;
  getTagsForSave = mod.getTagsForSave;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// initTagInput — chip rendering
// ---------------------------------------------------------------------------

describe('initTagInput — chip rendering', () => {
  it('renders pills for existing tags inside #tag-field-ed', () => {
    setupDOM();
    initTagInput(['tag1', 'tag2']);

    const field = document.getElementById('tag-field-ed');
    const pills = field.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(2);
    expect(pills[0].textContent).toContain('tag1');
    expect(pills[1].textContent).toContain('tag2');
  });

  it('renders empty field when no tags given', () => {
    setupDOM();
    initTagInput([]);
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('normalizes tags to lowercase and deduplicates', () => {
    setupDOM();
    initTagInput(['Apple', 'APPLE', 'apple']);
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(1);
    expect(pills[0].textContent).toContain('apple');
  });

  it('trims whitespace from tags', () => {
    setupDOM();
    initTagInput(['  snack  ', 'snack']);
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
  });

  it('each pill has a remove button with data-tag attribute', () => {
    setupDOM();
    initTagInput(['snack']);
    const btn = document.querySelector('.tag-remove');
    expect(btn).not.toBeNull();
    expect(btn.dataset.tag).toBe('snack');
    expect(btn.textContent).toBe('\u00D7');
  });

  it('pills are sorted alphabetically', () => {
    setupDOM();
    initTagInput(['zebra', 'apple', 'mango']);
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills[0].textContent).toContain('apple');
    expect(pills[1].textContent).toContain('mango');
    expect(pills[2].textContent).toContain('zebra');
  });

  it('handles null existing tags gracefully', () => {
    setupDOM();
    expect(() => initTagInput(null)).not.toThrow();
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('handles undefined existing tags gracefully', () => {
    setupDOM();
    expect(() => initTagInput(undefined)).not.toThrow();
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('silently handles missing DOM elements', () => {
    document.body.innerHTML = '';
    expect(() => initTagInput(['tag1'])).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// getTagsForSave
// ---------------------------------------------------------------------------

describe('getTagsForSave', () => {
  it('returns current tags as array', () => {
    setupDOM();
    initTagInput(['beta', 'alpha']);
    const tags = getTagsForSave();
    expect(Array.isArray(tags)).toBe(true);
    expect(tags.sort()).toEqual(['alpha', 'beta']);
  });

  it('flushes uncommitted text from input before returning', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'pending';
    const tags = getTagsForSave();
    expect(tags).toContain('pending');
    expect(input.value).toBe('');
  });

  it('does not flush when input value is whitespace-only', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '   ';
    const tags = getTagsForSave();
    expect(tags.length).toBe(0);
  });

  it('returns empty array when no tags and no pending input', () => {
    setupDOM();
    initTagInput([]);
    expect(getTagsForSave()).toEqual([]);
  });

  it('works without a DOM input element', () => {
    document.body.innerHTML = '';
    initTagInput([]);
    expect(() => getTagsForSave()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Enter / comma key — adds a chip
// ---------------------------------------------------------------------------

describe('Enter key — adds a chip', () => {
  it('pressing Enter on input adds a new chip', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'newtag';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(1);
    expect(pills[0].textContent).toContain('newtag');
    expect(input.value).toBe('');
  });

  it('pressing comma key adds a chip', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'commtag';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: ',', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(input.value).toBe('');
  });

  it('Enter with empty input does not add a chip', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('Enter with duplicate tag does not add a chip', () => {
    setupDOM();
    initTagInput(['existing']);
    const input = document.getElementById('tag-input-ed');
    input.value = 'existing';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
  });

  it('Enter prevents form submission', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'test';
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it('Enter hides suggestion list', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = 'something';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(list.hidden).toBe(true);
  });

  it('rejects tags longer than 50 characters', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = 'a'.repeat(51);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Tab key — completes first suggestion
// ---------------------------------------------------------------------------

describe('Tab key — autocomplete completion', () => {
  it('Tab completes the first visible suggestion when list is visible', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    const li = document.createElement('li');
    li.textContent = 'tabcomplete';
    list.appendChild(li);
    list.hidden = false;
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('tabcomplete');
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
  });

  it('Tab does nothing when list is hidden', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = true;
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('Tab does nothing when list is visible but empty', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Backspace key — removes last tag
// ---------------------------------------------------------------------------

describe('Backspace key — removes last tag', () => {
  it('Backspace with empty input removes the last tag alphabetically', () => {
    setupDOM();
    initTagInput(['alpha', 'zebra']);
    expect(document.querySelectorAll('.tag-pill').length).toBe(2);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('alpha');
  });

  it('Backspace with non-empty input does not remove a tag', () => {
    setupDOM();
    initTagInput(['alpha']);
    const input = document.getElementById('tag-input-ed');
    input.value = 'partial';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
  });

  it('Backspace with empty input and no tags is a no-op', () => {
    setupDOM();
    initTagInput([]);
    const input = document.getElementById('tag-input-ed');
    input.value = '';
    expect(() =>
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }))
    ).not.toThrow();
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Remove chip
// ---------------------------------------------------------------------------

describe('Remove chip', () => {
  it('clicking remove button removes the chip', () => {
    setupDOM();
    initTagInput(['removeme', 'keepme']);
    expect(document.querySelectorAll('.tag-pill').length).toBe(2);
    const removeBtn = document.querySelector('.tag-remove[data-tag="removeme"]');
    removeBtn.click();
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('keepme');
    expect(getTagsForSave()).toEqual(['keepme']);
  });

  it('removing last chip leaves empty field', () => {
    setupDOM();
    initTagInput(['only']);
    const btn = document.querySelector('.tag-remove');
    btn.click();
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Field click — focuses input
// ---------------------------------------------------------------------------

describe('Field click — focuses input', () => {
  it('clicking on the field container focuses the input', () => {
    setupDOM();
    initTagInput([]);
    const field = document.getElementById('tag-field-ed');
    const input = document.getElementById('tag-input-ed');
    const focusSpy = vi.spyOn(input, 'focus');
    // Simulate click directly on the field (target === field)
    field.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(focusSpy).toHaveBeenCalled();
  });

  it('clicking on a child element does not steal focus via field handler', () => {
    setupDOM();
    initTagInput([]);
    const field = document.getElementById('tag-field-ed');
    const input = document.getElementById('tag-input-ed');
    const focusSpy = vi.spyOn(input, 'focus');
    // Simulate click on the input itself (target !== field)
    input.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(focusSpy).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Autocomplete — fetch suggestions
// ---------------------------------------------------------------------------

describe('Autocomplete — fetch suggestions', () => {
  it('typing triggers suggestion fetch and renders suggestions', async () => {
    setupDOM();
    initTagInput([]);
    vi.useFakeTimers();

    const mockSuggestions = ['popcorn', 'potato'];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockSuggestions),
    }));

    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');

    input.value = 'pop';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    await vi.runAllTimersAsync();

    expect(fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=pop');
    expect(list.hidden).toBe(false);
    const items = list.querySelectorAll('li');
    expect(items.length).toBe(2);
    expect(items[0].textContent).toBe('popcorn');
    expect(items[1].textContent).toBe('potato');

    vi.useRealTimers();
  });

  it('empty input hides suggestion list without fetching', () => {
    setupDOM();
    initTagInput([]);
    vi.stubGlobal('fetch', vi.fn());
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(list.hidden).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('empty suggestions from fetch hides the list', async () => {
    setupDOM();
    initTagInput([]);
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: () => Promise.resolve([]),
    }));
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = 'xyz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('fetch failure hides suggestion list', async () => {
    setupDOM();
    initTagInput([]);
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.value = 'fail';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('clicking a suggestion adds it as a chip', async () => {
    setupDOM();
    initTagInput([]);
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['popcorn']),
    }));
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    input.value = 'pop';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(list.querySelectorAll('li').length).toBe(1);
    const li = list.querySelector('li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('popcorn');
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });

  it('blur hides suggestion list', async () => {
    setupDOM();
    initTagInput([]);
    vi.useFakeTimers();
    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');
    list.hidden = false;
    input.dispatchEvent(new Event('blur', { bubbles: true }));
    await vi.runAllTimersAsync();
    expect(list.hidden).toBe(true);
    vi.useRealTimers();
  });
});

// ---------------------------------------------------------------------------
// _bindInput early-return — missing DOM elements
// ---------------------------------------------------------------------------

describe('_bindInput — missing DOM elements', () => {
  it('does not throw when input element is missing', () => {
    document.body.innerHTML = '<ul id="tag-suggestions-ed" hidden></ul>';
    expect(() => initTagInput([])).not.toThrow();
  });

  it('does not throw when suggestions list is missing', () => {
    document.body.innerHTML = '<input id="tag-input-ed" type="text" />';
    expect(() => initTagInput([])).not.toThrow();
  });

  it('binds input events even when tag-field-ed container is absent', () => {
    // field-less setup: input and list exist but not inside tag-field-ed
    document.body.innerHTML = `
      <input id="tag-input-ed" type="text" />
      <ul id="tag-suggestions-ed" hidden></ul>
    `;
    expect(() => initTagInput([])).not.toThrow();
    // Enter key should still work (no pills since field absent, but no crash)
    const input = document.getElementById('tag-input-ed');
    input.value = 'x';
    expect(() =>
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    ).not.toThrow();
  });
});
