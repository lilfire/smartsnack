// Comprehensive error scenario tests for modules that make fetch/API calls.
// Uses the real state.js api() to test HTTP error codes end-to-end.
// Each HTTP status code exercises the same error-handling branch in api().
import { describe, it, expect, vi, afterEach } from 'vitest';

// Do NOT mock state.js here — these tests exercise the real api() function
// with global.fetch patched to return controlled responses.

afterEach(() => { vi.restoreAllMocks(); });

// ── state.js api() — HTTP error codes ────────────────

describe('state.js api() - HTTP 400 Bad Request', () => {
  it('throws an error with the response message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 400,
      text: () => Promise.resolve('{"error":"Bad request"}'),
    });
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Bad request');
  });
});

describe('state.js api() - HTTP 401 Unauthorized', () => {
  it('throws an error with status message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 401,
      text: () => Promise.resolve('{"error":"Unauthorized"}'),
    });
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Unauthorized');
  });
});

describe('state.js api() - HTTP 403 Forbidden', () => {
  it('throws an error with Forbidden message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 403,
      text: () => Promise.resolve('{"error":"Forbidden"}'),
    });
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Forbidden');
  });
});

describe('state.js api() - HTTP 404 Not Found', () => {
  it('throws with 404 message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 404,
      text: () => Promise.resolve('{"error":"Not found"}'),
    });
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Not found');
  });
});

describe('state.js api() - HTTP 500 Internal Server Error', () => {
  it('throws with server error message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500,
      text: () => Promise.resolve('{"error":"Internal server error"}'),
    });
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Internal server error');
  });
});

describe('state.js api() - Network failure', () => {
  it('propagates fetch rejection', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network unavailable'));
    const { api } = await import('../state.js');
    await expect(api('/test')).rejects.toThrow('Network unavailable');
  });
});

describe('state.js api() - Malformed JSON', () => {
  it('returns {} when response body is not valid JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('not valid json {{'),
    });
    const { api } = await import('../state.js');
    const result = await api('/test');
    expect(result).toEqual({});
  });
});

describe('state.js api() - Error status attached', () => {
  it('attaches status code to thrown error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 503,
      text: () => Promise.resolve('{"error":"Service Unavailable"}'),
    });
    const { api } = await import('../state.js');
    let caught;
    try { await api('/test'); } catch (e) { caught = e; }
    expect(caught).toBeDefined();
    expect(caught.status).toBe(503);
  });
});

// ── state.js fetchProducts() — error scenarios ────────

describe('state.js fetchProducts() - network error', () => {
  it('throws on network failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('offline'));
    const { fetchProducts } = await import('../state.js');
    await expect(fetchProducts('test', [])).rejects.toThrow('offline');
  });
});

describe('state.js fetchProducts() - HTTP 500', () => {
  it('throws on server error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500,
      text: () => Promise.resolve('{"error":"Server error"}'),
    });
    const { fetchProducts } = await import('../state.js');
    await expect(fetchProducts('', [])).rejects.toThrow('Server error');
  });
});
