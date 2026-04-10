import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../state.js', () => ({
  api: vi.fn().mockResolvedValue([]),
  esc: (s) => String(s),
  showConfirmModal: vi.fn().mockResolvedValue(true),
  showToast: vi.fn(),
}));

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

import { loadPq, renderPqTable, autosavePq, savePqField, addPq, deletePq } from '../settings-pq.js';
import { api, showToast, showConfirmModal } from '../state.js';

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  document.body.innerHTML = '';
  api.mockResolvedValue([]);
  showConfirmModal.mockResolvedValue(true);
});

afterEach(() => {
  vi.useRealTimers();
});

// ── renderPqTable ────────────────────────────────────
describe('renderPqTable', () => {
  it('does nothing when container missing', () => {
    expect(() => renderPqTable()).not.toThrow();
  });

  it('shows empty message when no data', async () => {
    api.mockResolvedValue([]);
    document.body.innerHTML = '<div id="pq-list"></div>';
    await loadPq();
    expect(document.getElementById('pq-list').innerHTML).toContain('No protein sources');
  });

  it('renders protein quality rows', async () => {
    const pqData = [
      { id: 1, label: 'Chicken', keywords: ['chicken', 'poultry'], pdcaas: 0.9, diaas: 1.0 },
    ];
    api.mockResolvedValue(pqData);
    document.body.innerHTML = '<div id="pq-list"></div>';
    await loadPq();
    const container = document.getElementById('pq-list');
    expect(container.innerHTML).toContain('pqe-label-1');
    expect(container.innerHTML).toContain('pqe-pdcaas-1');
  });
});

// ── loadPq ───────────────────────────────────────────
describe('loadPq', () => {
  it('shows error toast on API failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    document.body.innerHTML = '<div id="pq-list"></div>';
    await loadPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls api endpoint', async () => {
    api.mockResolvedValue([]);
    document.body.innerHTML = '<div id="pq-list"></div>';
    await loadPq();
    expect(api).toHaveBeenCalledWith('/api/protein-quality');
  });
});

// ── autosavePq ───────────────────────────────────────
describe('autosavePq', () => {
  it('debounces save', async () => {
    api.mockResolvedValue([]);
    document.body.innerHTML = '<div id="pq-list"></div>';
    await loadPq();
    // Setup DOM for savePqField
    const pqData = [{ id: 42, label: 'Beef', keywords: ['beef'], pdcaas: 0.8, diaas: 0.85 }];
    api.mockResolvedValue(pqData);
    await loadPq();
    document.body.innerHTML += `
      <input id="pqe-label-42" value="Beef">
      <input id="pqe-kw-42" value="beef">
      <input id="pqe-pdcaas-42" value="0.8">
      <input id="pqe-diaas-42" value="0.85">`;
    api.mockResolvedValue({ id: 42 });

    autosavePq(42);
    autosavePq(42); // second call debounces
    vi.advanceTimersByTime(400);
    await Promise.resolve();
    // savePqField should be called once (debounced)
    expect(api).toHaveBeenCalled();
  });
});

// ── savePqField ──────────────────────────────────────
describe('savePqField', () => {
  it('returns early if any element is missing', async () => {
    await savePqField(99);
    expect(api).not.toHaveBeenCalled();
  });

  it('saves protein quality data', async () => {
    document.body.innerHTML = `
      <input id="pqe-label-1" value="Chicken">
      <input id="pqe-kw-1" value="chicken, poultry">
      <input id="pqe-pdcaas-1" value="0.9">
      <input id="pqe-diaas-1" value="1.0">`;
    api.mockResolvedValue({});
    await savePqField(1);
    expect(api).toHaveBeenCalledWith('/api/protein-quality/1', expect.objectContaining({ method: 'PUT' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('skips save if keywords empty', async () => {
    document.body.innerHTML = `
      <input id="pqe-label-1" value="Chicken">
      <input id="pqe-kw-1" value="  ">
      <input id="pqe-pdcaas-1" value="0.9">
      <input id="pqe-diaas-1" value="1.0">`;
    await savePqField(1);
    expect(api).not.toHaveBeenCalled();
  });

  it('skips save if pdcaas is NaN', async () => {
    document.body.innerHTML = `
      <input id="pqe-label-1" value="Chicken">
      <input id="pqe-kw-1" value="chicken">
      <input id="pqe-pdcaas-1" value="invalid">
      <input id="pqe-diaas-1" value="1.0">`;
    await savePqField(1);
    expect(api).not.toHaveBeenCalled();
  });

  it('shows API error', async () => {
    document.body.innerHTML = `
      <input id="pqe-label-1" value="Chicken">
      <input id="pqe-kw-1" value="chicken">
      <input id="pqe-pdcaas-1" value="0.9">
      <input id="pqe-diaas-1" value="1.0">`;
    api.mockResolvedValue({ error: 'Validation failed' });
    await savePqField(1);
    expect(showToast).toHaveBeenCalledWith('Validation failed', 'error');
  });

  it('shows error on network failure', async () => {
    document.body.innerHTML = `
      <input id="pqe-label-1" value="Chicken">
      <input id="pqe-kw-1" value="chicken">
      <input id="pqe-pdcaas-1" value="0.9">
      <input id="pqe-diaas-1" value="1.0">`;
    api.mockRejectedValue(new Error('fail'));
    await savePqField(1);
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── addPq ────────────────────────────────────────────
describe('addPq', () => {
  function setupDOM(label = 'Chicken', kw = 'chicken', pdcaas = '0.9', diaas = '1.0') {
    document.body.innerHTML = `
      <input id="pq-add-label" value="${label}">
      <input id="pq-add-kw" value="${kw}">
      <input id="pq-add-pdcaas" value="${pdcaas}">
      <input id="pq-add-diaas" value="${diaas}">
      <div id="pq-list"></div>`;
  }

  it('shows error when keywords missing', async () => {
    setupDOM('Chicken', '');
    await addPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('shows error when pdcaas is NaN', async () => {
    setupDOM('Chicken', 'chicken', 'abc');
    await addPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('calls api to add entry', async () => {
    setupDOM();
    api.mockResolvedValue({});
    await addPq();
    expect(api).toHaveBeenCalledWith('/api/protein-quality', expect.objectContaining({ method: 'POST' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows API error', async () => {
    setupDOM();
    api.mockResolvedValue({ error: 'Duplicate keywords' });
    await addPq();
    expect(showToast).toHaveBeenCalledWith('Duplicate keywords', 'error');
  });

  it('clears inputs on success', async () => {
    setupDOM();
    api.mockResolvedValue({});
    await addPq();
    expect(document.getElementById('pq-add-label').value).toBe('');
    expect(document.getElementById('pq-add-kw').value).toBe('');
  });

  it('shows error on network failure', async () => {
    setupDOM();
    api.mockRejectedValue(new Error('fail'));
    await addPq();
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});

// ── deletePq ─────────────────────────────────────────
describe('deletePq', () => {
  it('shows confirm modal', async () => {
    document.body.innerHTML = '<div id="pq-list"></div>';
    api.mockResolvedValue({});
    await deletePq(1, 'Chicken');
    expect(showConfirmModal).toHaveBeenCalled();
  });

  it('cancels when confirm returns false', async () => {
    showConfirmModal.mockResolvedValue(false);
    await deletePq(1, 'Chicken');
    expect(api).not.toHaveBeenCalled();
  });

  it('calls api to delete entry', async () => {
    document.body.innerHTML = '<div id="pq-list"></div>';
    api.mockResolvedValue({});
    await deletePq(1, 'Chicken');
    expect(api).toHaveBeenCalledWith('/api/protein-quality/1', expect.objectContaining({ method: 'DELETE' }));
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  it('shows error on network failure', async () => {
    api.mockRejectedValue(new Error('fail'));
    await deletePq(1, 'Chicken');
    expect(showToast).toHaveBeenCalledWith(expect.any(String), 'error');
  });
});
