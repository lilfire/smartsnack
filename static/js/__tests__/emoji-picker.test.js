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

beforeEach(() => {
  document.body.innerHTML = '';
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
