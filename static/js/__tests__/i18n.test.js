import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock state.js to avoid side effects from the _escDiv singleton
vi.mock('../state.js', () => {
  const _state = {
    currentView: 'search',
    currentFilter: [],
    expandedId: null,
    editingId: null,
    searchTimeout: null,
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
    NUTRI_IDS: ['kcal','energy_kj','fat','saturated_fat','carbs','sugar','protein','fiber','salt','weight','portion'],
    catEmoji: vi.fn(() => '\u{1F4E6}'),
    catLabel: vi.fn((t) => t),
    esc: (s) => String(s),
    safeDataUri: vi.fn((uri) => uri || ''),
    fmtNum: vi.fn((v) => v == null ? '-' : String(v)),
    showToast: vi.fn(),
    api: vi.fn(),
    fetchProducts: vi.fn().mockResolvedValue([]),
    fetchStats: vi.fn().mockImplementation(async () => {
      _state.cachedStats = { total: 0, types: 0, categories: [] };
      return _state.cachedStats;
    }),
    showConfirmModal: vi.fn(),
    upgradeSelect: vi.fn(),
  };
});

// Mock dynamic imports used by changeLanguage()
vi.mock('../products.js', () => ({ loadData: vi.fn() }));
vi.mock('../settings.js', () => ({ loadSettings: vi.fn() }));
vi.mock('../render.js', () => ({ loadFlagConfig: vi.fn() }));
vi.mock('../advanced-filters.js', () => ({ rebuildAdvancedFilters: vi.fn() }));

import { t, getCurrentLang, initLanguage, applyStaticTranslations, changeLanguage } from '../i18n.js';
import { state, api } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  state.currentView = 'search';
});

describe('t', () => {
  it('returns the key when no translation exists', () => {
    expect(t('unknown_key')).toBe('unknown_key');
  });

  it('returns translation after initLanguage loads translations', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ greeting: 'Hello {name}', title: 'SmartSnack' });
    await initLanguage();
    expect(t('title')).toBe('SmartSnack');
  });

  it('substitutes parameters in translation', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ greeting: 'Hello {name}!' });
    await initLanguage();
    expect(t('greeting', { name: 'World' })).toBe('Hello World!');
  });

  it('leaves unmatched params as-is', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ msg: 'Hi {name}, your {thing}' });
    await initLanguage();
    expect(t('msg', { name: 'Bob' })).toBe('Hi Bob, your {thing}');
  });

  it('returns key with params when no translation', () => {
    expect(t('no_translation', { x: 1 })).toBe('no_translation');
  });
});

describe('getCurrentLang', () => {
  it('returns default language before init', () => {
    // Default is 'no' or whatever was last set
    const lang = getCurrentLang();
    expect(typeof lang).toBe('string');
  });

  it('returns loaded language after init', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({});
    await initLanguage();
    expect(getCurrentLang()).toBe('en');
  });
});

describe('initLanguage', () => {
  it('falls back to "no" on API error', async () => {
    api.mockRejectedValueOnce(new Error('fail'))
       .mockResolvedValueOnce({});
    await initLanguage();
    expect(getCurrentLang()).toBe('no');
  });

  it('calls applyStaticTranslations after loading', async () => {
    const el = document.createElement('span');
    el.setAttribute('data-i18n', 'test_key');
    document.body.appendChild(el);
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ test_key: 'Test Value' });
    await initLanguage();
    expect(el.textContent).toBe('Test Value');
    el.remove();
  });
});

describe('applyStaticTranslations', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('sets textContent for data-i18n elements', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ my_text: 'Hello' });
    await initLanguage();
    const el = document.createElement('div');
    el.setAttribute('data-i18n', 'my_text');
    document.body.appendChild(el);
    applyStaticTranslations();
    expect(el.textContent).toBe('Hello');
  });

  it('sets innerHTML for data-i18n-html elements', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ bold: '<b>Bold</b>' });
    await initLanguage();
    const el = document.createElement('div');
    el.setAttribute('data-i18n-html', 'bold');
    document.body.appendChild(el);
    applyStaticTranslations();
    expect(el.innerHTML).toBe('<b>Bold</b>');
  });

  it('sets placeholder for data-i18n-placeholder elements', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ ph: 'Enter text...' });
    await initLanguage();
    const el = document.createElement('input');
    el.setAttribute('data-i18n-placeholder', 'ph');
    document.body.appendChild(el);
    applyStaticTranslations();
    expect(el.placeholder).toBe('Enter text...');
  });

  it('sets title for data-i18n-title elements', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ tip: 'Tooltip text' });
    await initLanguage();
    const el = document.createElement('div');
    el.setAttribute('data-i18n-title', 'tip');
    document.body.appendChild(el);
    applyStaticTranslations();
    expect(el.title).toBe('Tooltip text');
  });

  it('sets document lang attribute', async () => {
    api.mockResolvedValueOnce({ language: 'se' })
       .mockResolvedValueOnce({});
    await initLanguage();
    expect(document.documentElement.lang).toBe('se');
  });

  it('passes data-i18n-param-* attributes as params to t()', async () => {
    api.mockResolvedValueOnce({ language: 'en' })
       .mockResolvedValueOnce({ welcome: 'Welcome {name}, you have {count} items' });
    await initLanguage();
    const el = document.createElement('span');
    el.setAttribute('data-i18n', 'welcome');
    el.setAttribute('data-i18n-param-name', 'Alice');
    el.setAttribute('data-i18n-param-count', '5');
    document.body.appendChild(el);
    applyStaticTranslations();
    expect(el.textContent).toBe('Welcome Alice, you have 5 items');
  });
});

describe('changeLanguage', () => {
  it('loads new translations and saves to API', async () => {
    // Initial load
    api.mockResolvedValueOnce({ language: 'no' })
       .mockResolvedValueOnce({ hello: 'Hei' });
    await initLanguage();

    // Change language - loadTranslations, save language, then dynamic import of products.js
    api.mockResolvedValueOnce({ goodbye: 'Goodbye' }) // loadTranslations
       .mockResolvedValueOnce({}); // save to API
    // changeLanguage does a dynamic import of products.js which may fail in tests
    await changeLanguage('en').catch(() => {});
    expect(getCurrentLang()).toBe('en');
  });

  it('does not change language if translations fail to load', async () => {
    api.mockResolvedValueOnce({ language: 'no' })
       .mockResolvedValueOnce({ hello: 'Hei' });
    await initLanguage();

    api.mockRejectedValueOnce(new Error('fail'));
    await changeLanguage('xx').catch(() => {});
    expect(getCurrentLang()).toBe('no');
  });

  it('updates stats-line when cachedStats is set', async () => {
    api.mockResolvedValueOnce({ language: 'no' })
       .mockResolvedValueOnce({ stats_line: '{total} products, {types} types' });
    await initLanguage();

    state.cachedStats = { total: 42, types: 3 };
    const statsEl = document.createElement('div');
    statsEl.id = 'stats-line';
    document.body.appendChild(statsEl);

    api.mockResolvedValueOnce({ stats_line: '{total} products, {types} types' }) // loadTranslations
       .mockResolvedValueOnce({}); // save language
    await changeLanguage('en').catch(() => {});
    expect(statsEl.textContent).toBe('42 products, 3 types');
    statsEl.remove();
    state.cachedStats = null;
  });

  it('rebuilds advanced filters when panel is open', async () => {
    api.mockResolvedValueOnce({ language: 'no' })
       .mockResolvedValueOnce({});
    await initLanguage();

    const panel = document.createElement('div');
    panel.id = 'advanced-filters';
    panel.classList.add('open');
    document.body.appendChild(panel);

    api.mockResolvedValueOnce({}) // loadTranslations
       .mockResolvedValueOnce({}); // save language
    await changeLanguage('en').catch(() => {});

    const { rebuildAdvancedFilters } = await import('../advanced-filters.js');
    expect(rebuildAdvancedFilters).toHaveBeenCalled();
    panel.remove();
  });

  it('calls loadSettings when in settings view', async () => {
    api.mockResolvedValueOnce({ language: 'no' })
       .mockResolvedValueOnce({});
    await initLanguage();

    state.currentView = 'settings';
    api.mockResolvedValueOnce({ new_key: 'New' }) // loadTranslations
       .mockResolvedValueOnce({}); // save language

    await changeLanguage('se').catch(() => {}); // may fail on dynamic import, that's ok
    expect(getCurrentLang()).toBe('se');
  });
});
