import { describe, it, expect } from 'vitest';
import { EMOJI_DATA } from '../emoji-data.js';

describe('EMOJI_DATA', () => {
  it('is an array', () => {
    expect(Array.isArray(EMOJI_DATA)).toBe(true);
  });

  it('has at least 100 entries', () => {
    expect(EMOJI_DATA.length).toBeGreaterThanOrEqual(100);
  });

  it('each entry has emoji and name properties', () => {
    EMOJI_DATA.forEach((entry, i) => {
      expect(entry).toHaveProperty('emoji');
      expect(entry).toHaveProperty('name');
      expect(typeof entry.emoji).toBe('string');
      expect(typeof entry.name).toBe('string');
      expect(entry.emoji.length).toBeGreaterThan(0);
      expect(entry.name.length).toBeGreaterThan(0);
    });
  });

  it('has no duplicate names', () => {
    const names = EMOJI_DATA.map((e) => e.name);
    const unique = new Set(names);
    expect(unique.size).toBe(names.length);
  });

  it('has no duplicate emojis', () => {
    const emojis = EMOJI_DATA.map((e) => e.emoji);
    const unique = new Set(emojis);
    expect(unique.size).toBe(emojis.length);
  });

  it('names use snake_case format', () => {
    EMOJI_DATA.forEach((entry) => {
      expect(entry.name).toMatch(/^[a-z][a-z0-9_]*$/);
    });
  });

  it('includes common food emojis', () => {
    const names = EMOJI_DATA.map((e) => e.name);
    expect(names).toContain('bread');
    expect(names).toContain('milk');
    expect(names).toContain('cheese');
    expect(names).toContain('meat');
    expect(names).toContain('fish');
  });
});
