import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    cachedStats: null,
    cachedResults: [],
    sortCol: 'total_score',
    sortDir: 'desc',
    categories: [],
    imageCache: {},
    advancedFilters: null,
  };
  return {
    state: _state,
    upgradeSelect: vi.fn(),
  };
});

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

vi.mock('../filters.js', () => ({
  updateFilterToggle: vi.fn(),
}));

vi.mock('../render.js', () => ({
  getFlagConfig: vi.fn(() => ({})),
}));

// Mock dynamic import of products.js used inside _triggerReload
vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

import { toggleAdvancedFilters, rebuildAdvancedFilters } from '../advanced-filters.js';
import { state } from '../state.js';

function setupMinimalDOM() {
  document.body.innerHTML = '';

  const panel = document.createElement('div');
  panel.id = 'advanced-filters';
  document.body.appendChild(panel);

  const toggle = document.createElement('button');
  toggle.id = 'adv-filter-toggle';
  document.body.appendChild(toggle);

  const searchInput = document.createElement('input');
  searchInput.id = 'search-input';
  document.body.appendChild(searchInput);

  const searchClear = document.createElement('div');
  searchClear.id = 'search-clear';
  document.body.appendChild(searchClear);

  const filterToggle = document.createElement('div');
  filterToggle.id = 'filter-toggle';
  document.body.appendChild(filterToggle);

  const filterRow = document.createElement('div');
  filterRow.id = 'filter-row';
  document.body.appendChild(filterRow);

  const searchRow = document.createElement('div');
  searchRow.className = 'search-row';
  document.body.appendChild(searchRow);

  return { panel, toggle, searchInput, searchClear, filterToggle, filterRow, searchRow };
}

beforeEach(() => {
  vi.useFakeTimers();
  state.advancedFilters = null;
  state.currentFilter = [];
});

afterEach(() => {
  vi.useRealTimers();
});

describe('toggleAdvancedFilters', () => {
  it('opens the panel when closed', () => {
    const { panel, toggle } = setupMinimalDOM();
    expect(panel.classList.contains('open')).toBe(false);

    toggleAdvancedFilters();

    // requestAnimationFrame adds class asynchronously; advance timers
    vi.runAllTimers();

    expect(panel.classList.contains('open')).toBe(true);
    expect(toggle.classList.contains('has-filter')).toBe(true);
  });

  it('closes the panel when open', () => {
    const { panel, toggle } = setupMinimalDOM();
    // Manually put panel in open state
    panel.classList.add('open');
    toggle.classList.add('has-filter');

    toggleAdvancedFilters();

    expect(panel.classList.contains('open')).toBe(false);
    expect(toggle.classList.contains('has-filter')).toBe(false);
  });

  it('disables search input when opening', () => {
    const { searchInput } = setupMinimalDOM();
    searchInput.value = 'previous search';

    toggleAdvancedFilters();
    vi.runAllTimers();

    expect(searchInput.disabled).toBe(true);
    expect(searchInput.value).toBe('');
  });

  it('re-enables search input when closing', () => {
    const { panel, toggle, searchInput } = setupMinimalDOM();
    panel.classList.add('open');
    searchInput.disabled = true;

    toggleAdvancedFilters();

    expect(searchInput.disabled).toBe(false);
  });

  it('hides filter toggle when opening', () => {
    const { filterToggle } = setupMinimalDOM();
    filterToggle.style.display = '';

    toggleAdvancedFilters();
    vi.runAllTimers();

    expect(filterToggle.style.display).toBe('none');
  });

  it('restores filter toggle when closing', () => {
    const { panel, toggle, filterToggle } = setupMinimalDOM();
    panel.classList.add('open');
    filterToggle.style.display = 'none';

    toggleAdvancedFilters();

    expect(filterToggle.style.display).toBe('');
  });

  it('clears advancedFilters state when closing', () => {
    const { panel, toggle } = setupMinimalDOM();
    panel.classList.add('open');
    state.advancedFilters = '{"logic":"and","children":[]}';

    toggleAdvancedFilters();

    expect(state.advancedFilters).toBeNull();
  });

  it('builds panel content (adv-group) when opening', () => {
    const { panel } = setupMinimalDOM();

    toggleAdvancedFilters();
    vi.runAllTimers();

    expect(panel.querySelector('.adv-group')).not.toBeNull();
  });

  it('does nothing when panel element is missing', () => {
    document.body.innerHTML = '';
    expect(() => toggleAdvancedFilters()).not.toThrow();
  });
});

describe('rebuildAdvancedFilters', () => {
  it('does nothing when panel is not open', () => {
    const { panel } = setupMinimalDOM();
    panel.innerHTML = '<div class="adv-group existing"></div>';

    rebuildAdvancedFilters();

    // Panel was not open so content should be unchanged
    expect(panel.querySelector('.existing')).not.toBeNull();
  });

  it('rebuilds panel content when panel is open', () => {
    const { panel } = setupMinimalDOM();
    panel.classList.add('open');
    panel.innerHTML = '<div class="stale-content"></div>';

    rebuildAdvancedFilters();

    // Stale content should be replaced by fresh adv-group
    expect(panel.querySelector('.stale-content')).toBeNull();
    expect(panel.querySelector('.adv-group')).not.toBeNull();
  });

  it('does nothing when panel element does not exist', () => {
    document.body.innerHTML = '';
    expect(() => rebuildAdvancedFilters()).not.toThrow();
  });
});
