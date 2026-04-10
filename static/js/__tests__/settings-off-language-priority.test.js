import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue({}),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

vi.mock('../products.js', () => ({
  loadData: vi.fn(),
}));

import { loadOffLanguagePriority } from '../settings-off.js';
import { api, showToast } from '../state.js';

/** Return fresh mock data each call to prevent mutation leakage. */
function mockPriority(codes) {
  return { priority: [...(codes || ['no', 'en', 'sv'])] };
}
function mockAllLangs() {
  return {
    languages: ['no', 'en', 'sv', 'de', 'fr'],
  };
}

function setupDom() {
  document.body.innerHTML = `
    <div id="off-lang-priority-list"></div>
    <select id="off-lang-add-select"></select>
    <button id="off-lang-add-btn">Add</button>`;
}

async function loadWithMocks(priorityCodes, allLangs) {
  api
    .mockResolvedValueOnce(priorityCodes ? mockPriority(priorityCodes) : mockPriority())
    .mockResolvedValueOnce(allLangs || mockAllLangs());
  await loadOffLanguagePriority();
}

/** Flush microtask queue so async saves from click handlers complete. */
function flush() {
  return new Promise((r) => setTimeout(r, 0));
}

function getCodes() {
  return [...document.querySelectorAll('.off-lang-item')]
    .map((el) => el.querySelector('.off-lang-code').textContent);
}

beforeEach(async () => {
  // Flush any pending async work from previous test
  await flush();
  vi.clearAllMocks();
  // Reset api mock specifically to clear any leftover once-mock queue
  api.mockReset();
  api.mockResolvedValue({});
  showToast.mockImplementation(() => {});
  document.body.innerHTML = '';
});

// ── Render ──────────────────────────────────────────

describe('Render', () => {
  it('renders priority list with correct items', async () => {
    setupDom();
    await loadWithMocks();

    const items = document.querySelectorAll('.off-lang-item');
    expect(items.length).toBe(3);
    expect(getCodes()).toEqual(['no', 'en', 'sv']);
  });

  it('renders up/down/remove buttons for each item', async () => {
    setupDom();
    await loadWithMocks();

    document.querySelectorAll('.off-lang-item').forEach((item) => {
      expect(item.querySelectorAll('button').length).toBe(3);
    });
  });

  it('disables up button on first item', async () => {
    setupDom();
    await loadWithMocks();

    const firstUpBtn = document.querySelectorAll('.off-lang-item')[0].querySelectorAll('button')[0];
    expect(firstUpBtn.disabled).toBe(true);
  });

  it('disables down button on last item', async () => {
    setupDom();
    await loadWithMocks();

    const items = document.querySelectorAll('.off-lang-item');
    const lastDownBtn = items[items.length - 1].querySelectorAll('button')[1];
    expect(lastDownBtn.disabled).toBe(true);
  });

  it('populates add dropdown excluding already-added languages', async () => {
    setupDom();
    await loadWithMocks();

    const values = [...document.querySelectorAll('#off-lang-add-select option')].map((o) => o.value);
    expect(values).toEqual(['de', 'fr']);
  });

  it('returns early without error when list element missing', async () => {
    await loadWithMocks();
    expect(showToast).not.toHaveBeenCalled();
  });
});

// ── Reorder ─────────────────────────────────────────

describe('Reorder', () => {
  it('move down changes order', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[0].querySelectorAll('button')[1].click();
    await flush();

    expect(getCodes()).toEqual(['en', 'no', 'sv']);
  });

  it('move up changes order', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[2].querySelectorAll('button')[0].click();
    await flush();

    expect(getCodes()).toEqual(['no', 'sv', 'en']);
  });

  it('reorder triggers save API call', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[0].querySelectorAll('button')[1].click();
    await flush();

    expect(api).toHaveBeenCalledWith('/api/settings/off-language-priority', {
      method: 'PUT',
      body: JSON.stringify({ priority:['en', 'no', 'sv'] }),
    });
  });
});

// ── Add ─────────────────────────────────────────────

describe('Add', () => {
  it('adding a language appends it to the list', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.getElementById('off-lang-add-select').value = 'de';
    document.getElementById('off-lang-add-btn').click();
    await flush();

    expect(getCodes()).toEqual(['no', 'en', 'sv', 'de']);
  });

  it('added language is removed from dropdown', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.getElementById('off-lang-add-select').value = 'de';
    document.getElementById('off-lang-add-btn').click();
    await flush();

    const options = [...document.querySelectorAll('#off-lang-add-select option')].map((o) => o.value);
    expect(options).toEqual(['fr']);
  });

  it('add triggers save API call', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.getElementById('off-lang-add-select').value = 'fr';
    document.getElementById('off-lang-add-btn').click();
    await flush();

    expect(api).toHaveBeenCalledWith('/api/settings/off-language-priority', {
      method: 'PUT',
      body: JSON.stringify({ priority:['no', 'en', 'sv', 'fr'] }),
    });
  });

  it('disables add button when all languages are added', async () => {
    setupDom();
    await loadWithMocks(['no', 'en', 'sv', 'de', 'fr']);

    expect(document.getElementById('off-lang-add-btn').disabled).toBe(true);
  });
});

// ── Remove ──────────────────────────────────────────

describe('Remove', () => {
  it('removing a language removes it from the list', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[1].querySelectorAll('button')[2].click();
    await flush();

    expect(getCodes()).toEqual(['no', 'sv']);
  });

  it('cannot remove last language (button disabled)', async () => {
    setupDom();
    await loadWithMocks(['no']);

    const items = document.querySelectorAll('.off-lang-item');
    expect(items.length).toBe(1);
    expect(items[0].querySelectorAll('button')[2].disabled).toBe(true);
  });

  it('remove triggers save API call', async () => {
    setupDom();
    await loadWithMocks();
    api.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[2].querySelectorAll('button')[2].click();
    await flush();

    expect(api).toHaveBeenCalledWith('/api/settings/off-language-priority', {
      method: 'PUT',
      body: JSON.stringify({ priority:['no', 'en'] }),
    });
  });
});

// ── API Integration ─────────────────────────────────

describe('API integration', () => {
  it('loadOffLanguagePriority calls both API endpoints', async () => {
    setupDom();
    await loadWithMocks();

    expect(api).toHaveBeenCalledWith('/api/settings/off-language-priority');
    expect(api).toHaveBeenCalledWith('/api/settings/off-languages');
  });

  it('shows success toast on save', async () => {
    setupDom();
    await loadWithMocks();
    showToast.mockClear();
    api.mockResolvedValue({});

    document.querySelectorAll('.off-lang-item')[0].querySelectorAll('button')[1].click();
    await flush();

    expect(showToast).toHaveBeenCalledWith('toast_off_lang_priority_saved', 'success');
  });

  it('shows error toast on save failure', async () => {
    setupDom();
    await loadWithMocks();
    showToast.mockClear();
    api.mockRejectedValue(new Error('Network error'));

    document.querySelectorAll('.off-lang-item')[0].querySelectorAll('button')[1].click();
    await flush();

    expect(showToast).toHaveBeenCalledWith('toast_save_error', 'error');
  });

  it('shows error toast when loadOffLanguagePriority fails', async () => {
    setupDom();
    api.mockRejectedValue(new Error('fail'));
    await loadOffLanguagePriority();

    expect(showToast).toHaveBeenCalledWith('toast_load_error', 'error');
  });
});
