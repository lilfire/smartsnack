import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

let initTagInput, getTagsForSave;

function setupDOM() {
  document.body.innerHTML = `
    <div id="tag-container-ed"></div>
    <div class="tag-autocomplete-wrapper">
      <input id="tag-input-ed" type="text" />
      <ul id="tag-suggestions-ed" hidden></ul>
    </div>
  `;
}

beforeEach(async () => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  // Re-import to reset module-level _tags state
  vi.resetModules();
  const mod = await import('../tags.js');
  initTagInput = mod.initTagInput;
  getTagsForSave = mod.getTagsForSave;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('initTagInput — chip rendering', () => {
  it('renders pills for existing tags in #tag-container-ed', () => {
    setupDOM();
    initTagInput(['tag1', 'tag2']);

    const container = document.getElementById('tag-container-ed');
    const pills = container.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(2);
    // tags are sorted alphabetically
    expect(pills[0].textContent).toContain('tag1');
    expect(pills[1].textContent).toContain('tag2');
  });

  it('renders empty container when no tags', () => {
    setupDOM();
    initTagInput([]);

    const container = document.getElementById('tag-container-ed');
    expect(container.querySelectorAll('.tag-pill').length).toBe(0);
  });

  it('normalizes tags to lowercase and deduplicates', () => {
    setupDOM();
    initTagInput(['Apple', 'APPLE', 'apple']);

    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(1);
    expect(pills[0].textContent).toContain('apple');
  });

  it('each pill has a remove button with data-tag attribute', () => {
    setupDOM();
    initTagInput(['snack']);

    const btn = document.querySelector('.tag-remove');
    expect(btn).not.toBeNull();
    expect(btn.dataset.tag).toBe('snack');
  });

  it('handles null/undefined existing tags gracefully', () => {
    setupDOM();
    initTagInput(null);
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);

    initTagInput(undefined);
    expect(document.querySelectorAll('.tag-pill').length).toBe(0);
  });
});

describe('getTagsForSave', () => {
  it('returns current tags as array', () => {
    setupDOM();
    initTagInput(['beta', 'alpha']);

    const tags = getTagsForSave();
    expect(Array.isArray(tags)).toBe(true);
    expect(tags.sort()).toEqual(['alpha', 'beta']);
  });
});

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

  it('Enter prevents form submission (e.preventDefault called)', () => {
    setupDOM();
    initTagInput([]);

    const input = document.getElementById('tag-input-ed');
    input.value = 'test';
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    input.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
  });
});

describe('Remove chip', () => {
  it('clicking remove button removes the chip', () => {
    setupDOM();
    initTagInput(['removeme', 'keepme']);

    expect(document.querySelectorAll('.tag-pill').length).toBe(2);

    const removeBtn = document.querySelector('.tag-remove[data-tag="removeme"]');
    removeBtn.click();

    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('keepme');

    const tags = getTagsForSave();
    expect(tags).toEqual(['keepme']);
  });
});

describe('Autocomplete', () => {
  it('typing in input triggers suggestion fetch and renders suggestions', async () => {
    setupDOM();
    initTagInput([]);

    const mockSuggestions = ['popcorn', 'potato'];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockSuggestions),
    }));

    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');

    input.value = 'pop';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    // Wait for debounce (200ms) + async fetch
    await vi.waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/products/tags/suggestions?q=pop');
    }, { timeout: 500 });

    await vi.waitFor(() => {
      expect(list.hidden).toBe(false);
      expect(list.querySelectorAll('li').length).toBe(2);
      expect(list.querySelectorAll('li')[0].textContent).toBe('popcorn');
      expect(list.querySelectorAll('li')[1].textContent).toBe('potato');
    }, { timeout: 500 });
  });

  it('clicking a suggestion adds it as a chip', async () => {
    setupDOM();
    initTagInput([]);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: () => Promise.resolve(['popcorn']),
    }));

    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');

    input.value = 'pop';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    await vi.waitFor(() => {
      expect(list.querySelectorAll('li').length).toBe(1);
    }, { timeout: 500 });

    // mousedown on suggestion
    const li = list.querySelector('li');
    li.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

    expect(document.querySelectorAll('.tag-pill').length).toBe(1);
    expect(document.querySelector('.tag-pill').textContent).toContain('popcorn');
    expect(input.value).toBe('');
    expect(list.hidden).toBe(true);
  });

  it('empty input hides suggestion list', () => {
    setupDOM();
    initTagInput([]);

    const input = document.getElementById('tag-input-ed');
    const list = document.getElementById('tag-suggestions-ed');

    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    expect(list.hidden).toBe(true);
  });
});

describe('DOM timing', () => {
  it('initTagInput works when called after form HTML is in DOM', () => {
    // Start with empty body, then inject form HTML, then call initTagInput
    document.body.innerHTML = '';

    // Simulate late DOM injection (like products.js does after innerHTML assignment)
    document.body.innerHTML = `
      <div id="tag-container-ed"></div>
      <div class="tag-autocomplete-wrapper">
        <input id="tag-input-ed" type="text" />
        <ul id="tag-suggestions-ed" hidden></ul>
      </div>
    `;

    // Now call initTagInput — should find the elements
    initTagInput(['late1', 'late2']);

    const pills = document.querySelectorAll('.tag-pill');
    expect(pills.length).toBe(2);
    expect(pills[0].textContent).toContain('late1');
    expect(pills[1].textContent).toContain('late2');

    // Input binding should also work
    const input = document.getElementById('tag-input-ed');
    input.value = 'late3';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(document.querySelectorAll('.tag-pill').length).toBe(3);
  });

  it('initTagInput silently handles missing DOM elements', () => {
    // No DOM elements at all
    document.body.innerHTML = '';
    expect(() => initTagInput(['tag1'])).not.toThrow();
  });
});
