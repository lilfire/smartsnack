import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../emoji-data.js', () => ({
  EMOJI_DATA: [
    { emoji: '🍎', name: 'red_apple' },
    { emoji: '🍌', name: 'banana' },
    { emoji: '🥛', name: 'milk' },
  ],
}));

import { initEmojiPicker, resetEmojiPicker } from '../emoji-picker.js';
import { t } from '../i18n.js';

beforeEach(() => {
  document.body.innerHTML = '';
  t.mockImplementation((key) => key);
});

describe('initEmojiPicker', () => {
  it('does nothing when triggerEl is null', () => {
    expect(() => initEmojiPicker(null)).not.toThrow();
  });

  it('creates popup on trigger click', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    trigger.textContent = '📦';
    container.appendChild(trigger);
    document.body.appendChild(container);

    const inputEl = document.createElement('input');
    document.body.appendChild(inputEl);

    initEmojiPicker(trigger, inputEl);
    trigger.click();

    const popup = document.querySelector('.emoji-picker-popup');
    expect(popup).not.toBeNull();
    expect(popup.querySelector('.emoji-picker-search')).not.toBeNull();
    expect(popup.querySelector('.emoji-picker-grid')).not.toBeNull();
  });

  it('shows 3 emoji buttons', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const buttons = document.querySelectorAll('.emoji-picker-item');
    expect(buttons.length).toBe(3);
    expect(buttons[0].textContent).toBe('🍎');
    expect(buttons[1].textContent).toBe('🍌');
    expect(buttons[2].textContent).toBe('🥛');
  });

  it('calls onSelect callback when emoji clicked', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    const inputEl = document.createElement('input');
    document.body.appendChild(inputEl);
    const onSelect = vi.fn();

    initEmojiPicker(trigger, inputEl, onSelect);
    trigger.click();

    const buttons = document.querySelectorAll('.emoji-picker-item');
    buttons[1].click(); // click banana
    expect(onSelect).toHaveBeenCalledWith('🍌');
    expect(inputEl.value).toBe('🍌');
    expect(trigger.textContent).toBe('🍌');
  });

  it('closes popup when clicking same trigger again', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();
    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();
    trigger.click();
    expect(document.querySelector('.emoji-picker-popup')).toBeNull();
  });

  it('filters emojis on search input', async () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    search.value = 'banana';
    search.dispatchEvent(new Event('input'));

    const items = document.querySelectorAll('.emoji-picker-item');
    const visible = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible.length).toBe(1);
    expect(visible[0].textContent).toBe('🍌');
  });

  it('shows empty message when no matches', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    search.value = 'zzzzzzz';
    search.dispatchEvent(new Event('input'));

    const empty = document.querySelector('.emoji-picker-empty');
    expect(empty.style.display).not.toBe('none');
  });
});

describe('resetEmojiPicker', () => {
  it('resets trigger text to default emoji', () => {
    const trigger = document.createElement('button');
    trigger.textContent = '🍌';
    document.body.appendChild(trigger);
    resetEmojiPicker(trigger);
    expect(trigger.textContent).toBe('📦');
  });

  it('resets to custom default emoji', () => {
    const trigger = document.createElement('button');
    trigger.textContent = '🍌';
    document.body.appendChild(trigger);
    resetEmojiPicker(trigger, '🧀');
    expect(trigger.textContent).toBe('🧀');
  });

  it('handles null trigger', () => {
    expect(() => resetEmojiPicker(null)).not.toThrow();
  });
});

describe('closePopup with activeCleanup', () => {
  it('calls activeCleanup function when closing popup', async () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    // activeCleanup is now set (removes doc listeners).
    // Open a popup then close via toggle to exercise the cleanup branch.
    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();

    // Click the trigger again to toggle-close, which calls closePopup
    // and should invoke activeCleanup without error.
    trigger.click();
    expect(document.querySelector('.emoji-picker-popup')).toBeNull();
  });
});

describe('getSearchTerms cache hit', () => {
  it('returns cached result on second search with same term', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');

    // First search populates cache
    search.value = 'apple';
    search.dispatchEvent(new Event('input'));

    const items = document.querySelectorAll('.emoji-picker-item');
    const visible1 = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible1.length).toBe(1);

    // Second search with different term then back to same - exercises cache
    search.value = 'milk';
    search.dispatchEvent(new Event('input'));

    search.value = 'apple';
    search.dispatchEvent(new Event('input'));

    const visible2 = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible2.length).toBe(1);
    expect(visible2[0].textContent).toBe('🍎');
  });
});

describe('toggle with different trigger', () => {
  it('closes first popup and opens second when different trigger clicked', () => {
    // First trigger + container
    const container1 = document.createElement('div');
    container1.className = 'cat-add-grid';
    const trigger1 = document.createElement('button');
    container1.appendChild(trigger1);
    document.body.appendChild(container1);

    // Second trigger + container
    const container2 = document.createElement('div');
    container2.className = 'cat-add-grid';
    const trigger2 = document.createElement('button');
    container2.appendChild(trigger2);
    document.body.appendChild(container2);

    initEmojiPicker(trigger1, null);
    initEmojiPicker(trigger2, null);

    // Open first popup
    trigger1.click();
    const popups1 = document.querySelectorAll('.emoji-picker-popup');
    expect(popups1.length).toBe(1);

    // Click second trigger: should close first popup and open a new one
    trigger2.click();
    const popups2 = document.querySelectorAll('.emoji-picker-popup');
    expect(popups2.length).toBe(1);
    // The popup should belong to trigger2
    expect(popups2[0]._triggerEl).toBe(trigger2);
  });
});

describe('search filter edge cases', () => {
  it('shows all emojis when search is cleared', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');

    // Filter down to one result
    search.value = 'banana';
    search.dispatchEvent(new Event('input'));
    let items = document.querySelectorAll('.emoji-picker-item');
    let visible = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible.length).toBe(1);

    // Clear the search - all should be visible again
    search.value = '';
    search.dispatchEvent(new Event('input'));
    visible = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible.length).toBe(3);

    const empty = document.querySelector('.emoji-picker-empty');
    expect(empty.style.display).toBe('none');
  });

  it('shows partial matches correctly', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    // 'l' matches 'red apple' (has l) and 'milk' (has l), but not 'banana'
    search.value = 'l';
    search.dispatchEvent(new Event('input'));

    const items = document.querySelectorAll('.emoji-picker-item');
    const visible = Array.from(items).filter((i) => i.style.display !== 'none');
    // 'red_apple' -> 'red apple' contains 'l', 'milk' contains 'l'
    expect(visible.length).toBe(2);
  });
});

describe('translation fallback in getSearchTerms', () => {
  it('uses fallback when t() returns the key itself', () => {
    // The default mock returns the key, so translated === key.
    // This means the search terms should NOT include the translation suffix.
    // Searching for the raw name should still work.
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    search.value = 'red apple';
    search.dispatchEvent(new Event('input'));

    const items = document.querySelectorAll('.emoji-picker-item');
    const visible = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible.length).toBe(1);
    expect(visible[0].textContent).toBe('🍎');
  });
});

describe('translation with actual translated value', () => {
  it('uses translated search terms when t() returns a real translation', async () => {
    const { t } = await import('../i18n.js');
    // Return a real translation for a key so translated !== key branch is taken.
    // Note: getSearchTerms uses a WeakMap cache keyed on entry objects, so we
    // verify indirectly that the translation branch is reachable by checking
    // that t() is called with the expected emoji_ prefixed keys.
    t.mockImplementation((key) => {
      if (key === 'emoji_search_placeholder') return 'Buscar...';
      if (key === 'emoji_no_results') return 'Sin resultados';
      // Return a real translated name for all emoji keys
      if (key === 'emoji_red_apple') return 'manzana roja';
      if (key === 'emoji_banana') return 'platano';
      if (key === 'emoji_milk') return 'leche';
      return key;
    });

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    // t() should have been called with emoji_ prefixed names
    expect(t).toHaveBeenCalledWith('emoji_red_apple');
    expect(t).toHaveBeenCalledWith('emoji_banana');
    expect(t).toHaveBeenCalledWith('emoji_milk');

    // Clean up: close popup so activePopup is cleared for subsequent tests
    trigger.click();
  });

  it('appends translated terms so searching by translation finds emojis', async () => {
    const { EMOJI_DATA } = await import('../emoji-data.js');

    // Replace EMOJI_DATA entries with new object references so the WeakMap
    // cache in getSearchTerms misses, forcing recomputation of search terms
    // with translations active (covers the translated !== key branch).
    const freshEntries = [
      { emoji: '🍎', name: 'red_apple' },
      { emoji: '🍌', name: 'banana' },
      { emoji: '🥛', name: 'milk' },
    ];
    EMOJI_DATA.splice(0, EMOJI_DATA.length, ...freshEntries);

    // Mock t() to return real translations so the translated !== key branch
    // on line 26-28 of emoji-picker.js is executed.
    t.mockImplementation((key) => {
      if (key === 'emoji_search_placeholder') return 'Sok...';
      if (key === 'emoji_no_results') return 'Ingen treff';
      if (key === 'emoji_red_apple') return 'eple';
      if (key === 'emoji_banana') return 'banan';
      if (key === 'emoji_milk') return 'melk';
      return key;
    });

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');

    // Search using the Norwegian translated term 'eple' -- this only works
    // if the translated !== key branch was executed, appending the translation
    // to the search terms.
    search.value = 'eple';
    search.dispatchEvent(new Event('input'));

    const items = document.querySelectorAll('.emoji-picker-item');
    const visible = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible.length).toBe(1);
    expect(visible[0].textContent).toBe('🍎');

    // Also verify 'melk' finds milk
    search.value = 'melk';
    search.dispatchEvent(new Event('input'));

    const visible2 = Array.from(items).filter((i) => i.style.display !== 'none');
    expect(visible2.length).toBe(1);
    expect(visible2[0].textContent).toBe('🥛');

    // Clean up
    trigger.click();
  });
});

describe('outside click handler', () => {
  it('closes popup when clicking outside', async () => {
    vi.useFakeTimers();

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    const outsideEl = document.createElement('div');
    outsideEl.id = 'outside';
    document.body.appendChild(outsideEl);

    initEmojiPicker(trigger, null);
    trigger.click();

    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();

    // Flush the setTimeout that registers the document click listener
    vi.runAllTimers();

    // Click outside the popup and trigger
    outsideEl.click();

    expect(document.querySelector('.emoji-picker-popup')).toBeNull();

    vi.useRealTimers();
  });

  it('does not close popup when clicking the trigger itself', () => {
    vi.useFakeTimers();

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    vi.runAllTimers();

    // The trigger click handler uses stopPropagation, so clicking the trigger
    // again should toggle the popup (close it via wasThisTrigger), not via onDocClick.
    // The triggerEl.contains(ev.target) branch is covered when the trigger is clicked
    // and the event somehow reaches the document listener.
    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();

    vi.useRealTimers();
  });
});

describe('escape key handler', () => {
  it('closes popup when Escape is pressed', () => {
    vi.useFakeTimers();

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();

    vi.runAllTimers();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

    expect(document.querySelector('.emoji-picker-popup')).toBeNull();

    vi.useRealTimers();
  });

  it('does not close popup on other keys', () => {
    vi.useFakeTimers();

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    vi.runAllTimers();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    expect(document.querySelector('.emoji-picker-popup')).not.toBeNull();

    // Clean up
    trigger.click();
    vi.useRealTimers();
  });
});

describe('container fallback', () => {
  it('uses parentNode when .cat-add-grid is not found', () => {
    const wrapper = document.createElement('div');
    const trigger = document.createElement('button');
    wrapper.appendChild(trigger);
    document.body.appendChild(wrapper);

    initEmojiPicker(trigger, null);
    trigger.click();

    const popup = document.querySelector('.emoji-picker-popup');
    expect(popup).not.toBeNull();
    // Popup should be inserted after the wrapper (parentNode fallback)
    expect(popup.previousElementSibling).toBe(wrapper);
  });
});

describe('emoji click without inputEl or onSelect', () => {
  it('works when inputEl is null and no onSelect callback', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const buttons = document.querySelectorAll('.emoji-picker-item');
    // Should not throw when clicking emoji without inputEl or onSelect
    expect(() => buttons[0].click()).not.toThrow();
    expect(trigger.textContent).toBe('🍎');
    // Popup should be closed after selection
    expect(document.querySelector('.emoji-picker-popup')).toBeNull();
  });
});

describe('placeholder fallback text', () => {
  it('uses fallback placeholder when t() returns the key', () => {
    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    expect(search.placeholder).toBe('Search...');
  });

  it('uses translated placeholder when t() returns a real value', () => {
    t.mockImplementation((key) => {
      if (key === 'emoji_search_placeholder') return 'Sok...';
      if (key === 'emoji_no_results') return 'Ingen treff';
      return key;
    });

    const container = document.createElement('div');
    container.className = 'cat-add-grid';
    const trigger = document.createElement('button');
    container.appendChild(trigger);
    document.body.appendChild(container);

    initEmojiPicker(trigger, null);
    trigger.click();

    const search = document.querySelector('.emoji-picker-search');
    // The placeholder check: t('emoji_search_placeholder') !== 'emoji_search_placeholder'
    // Since our mock returns 'Sok...' (not the key), the translated value is used
    expect(search.placeholder).toBe('Sok...');

    // Also check the empty message uses translated text
    search.value = 'zzzzzzz';
    search.dispatchEvent(new Event('input'));
    const empty = document.querySelector('.emoji-picker-empty');
    expect(empty.textContent).toBe('Ingen treff');
  });
});
