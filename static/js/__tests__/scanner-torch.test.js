import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../i18n.js', () => ({
  t: vi.fn((key) => key),
}));

import { createTorchButton, checkTorchSupport, resetTorch } from '../scanner-torch.js';

beforeEach(() => {
  document.body.innerHTML = '';
  resetTorch(); // reset module-level _torchOn and _torchTrack
  vi.clearAllMocks();
});

// Helper: create a scanner-reader with a video and a mock track
function setupScannerWithTrack(torchCapable = true) {
  const container = document.createElement('div');
  container.id = 'scanner-reader';
  const video = document.createElement('video');
  const mockTrack = {
    getCapabilities: () => (torchCapable ? { torch: true } : {}),
    applyConstraints: vi.fn().mockResolvedValue(undefined),
  };
  video.srcObject = { getVideoTracks: () => [mockTrack] };
  container.appendChild(video);
  document.body.appendChild(container);
  return mockTrack;
}

// Helper: flush all microtasks (needed for async toggleTorch)
function flushMicrotasks() {
  return new Promise((r) => setTimeout(r, 0));
}

// ── createTorchButton ─────────────────────────────────

describe('createTorchButton', () => {
  it('creates a button element', () => {
    const btn = createTorchButton();
    expect(btn.tagName).toBe('BUTTON');
  });

  it('has correct id and class', () => {
    const btn = createTorchButton();
    expect(btn.id).toBe('scanner-torch-btn');
    expect(btn.className).toBe('scanner-torch-btn');
  });

  it('sets aria-label to torch_toggle_off initially', () => {
    const btn = createTorchButton();
    expect(btn.getAttribute('aria-label')).toBe('torch_toggle_off');
  });

  it('sets aria-pressed to false initially', () => {
    const btn = createTorchButton();
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('displays the torch emoji', () => {
    const btn = createTorchButton();
    expect(btn.textContent).toBe('\uD83D\uDD26');
  });

  it('is hidden by default (display: none)', () => {
    const btn = createTorchButton();
    expect(btn.style.display).toBe('none');
  });

  it('has a click event listener that does not throw', () => {
    const btn = createTorchButton();
    document.body.appendChild(btn);
    expect(() => btn.click()).not.toThrow();
  });
});

// ── checkTorchSupport ─────────────────────────────────

describe('checkTorchSupport', () => {
  it('does nothing when no #scanner-reader element', () => {
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('does nothing when scanner-reader has no video', () => {
    const div = document.createElement('div');
    div.id = 'scanner-reader';
    document.body.appendChild(div);
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('does nothing when video has no srcObject', () => {
    const container = document.createElement('div');
    container.id = 'scanner-reader';
    const video = document.createElement('video');
    container.appendChild(video);
    document.body.appendChild(container);
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('does nothing when video has empty track list', () => {
    const container = document.createElement('div');
    container.id = 'scanner-reader';
    const video = document.createElement('video');
    video.srcObject = { getVideoTracks: () => [] };
    container.appendChild(video);
    document.body.appendChild(container);
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('does nothing when track has no torch capability', () => {
    setupScannerWithTrack(false);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport();
    expect(document.getElementById('scanner-torch-btn').style.display).toBe('none');
  });

  it('uses empty object when track has no getCapabilities method', () => {
    const container = document.createElement('div');
    container.id = 'scanner-reader';
    const video = document.createElement('video');
    const trackNoGetCaps = {}; // no getCapabilities
    video.srcObject = { getVideoTracks: () => [trackNoGetCaps] };
    container.appendChild(video);
    document.body.appendChild(container);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    expect(() => checkTorchSupport()).not.toThrow();
    expect(document.getElementById('scanner-torch-btn').style.display).toBe('none');
  });

  it('shows torch button when torch capability detected', () => {
    setupScannerWithTrack(true);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport();
    expect(document.getElementById('scanner-torch-btn').style.display).toBe('');
  });

  it('does not crash when torch button is absent from DOM', () => {
    setupScannerWithTrack(true);
    // No button added to DOM
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('silently swallows exceptions during detection', () => {
    const container = document.createElement('div');
    container.id = 'scanner-reader';
    const video = document.createElement('video');
    video.srcObject = { getVideoTracks: () => { throw new Error('permission denied'); } };
    container.appendChild(video);
    document.body.appendChild(container);
    expect(() => checkTorchSupport()).not.toThrow();
  });
});

// ── resetTorch ────────────────────────────────────────

describe('resetTorch', () => {
  it('does nothing when no torch track is set', () => {
    expect(() => resetTorch()).not.toThrow();
  });

  it('calling resetTorch twice is safe', () => {
    resetTorch();
    expect(() => resetTorch()).not.toThrow();
  });

  it('clears track after checkTorchSupport (torch was off)', () => {
    const mockTrack = setupScannerWithTrack(true);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport(); // sets _torchTrack, _torchOn stays false
    mockTrack.applyConstraints.mockClear();

    resetTorch(); // _torchOn=false, so no applyConstraints for turn-off
    expect(mockTrack.applyConstraints).not.toHaveBeenCalled();
  });

  it('turns off torch and clears track when torch was on', async () => {
    const mockTrack = setupScannerWithTrack(true);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport(); // _torchTrack set

    btn.click(); // toggleTorch: on
    await flushMicrotasks();
    expect(btn.getAttribute('aria-pressed')).toBe('true');

    resetTorch();
    expect(mockTrack.applyConstraints).toHaveBeenLastCalledWith({ advanced: [{ torch: false }] });
  });
});

// ── toggleTorch (via button click) ────────────────────

describe('toggleTorch via button click', () => {
  it('does nothing when _torchTrack is null', async () => {
    // resetTorch() already called in beforeEach, so track is null
    const btn = createTorchButton();
    document.body.appendChild(btn);
    btn.click();
    await flushMicrotasks();
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('turns torch ON on first click and updates button state', async () => {
    const mockTrack = setupScannerWithTrack(true);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport();

    btn.click();
    await flushMicrotasks();

    expect(mockTrack.applyConstraints).toHaveBeenCalledWith({ advanced: [{ torch: true }] });
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(btn.classList.contains('scanner-torch-btn--on')).toBe(true);
    expect(btn.getAttribute('aria-label')).toBe('torch_toggle_on');
  });

  it('turns torch OFF on second click and resets button state', async () => {
    const mockTrack = setupScannerWithTrack(true);
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport();

    btn.click(); // on
    await flushMicrotasks();
    btn.click(); // off
    await flushMicrotasks();

    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(btn.classList.contains('scanner-torch-btn--on')).toBe(false);
    expect(btn.getAttribute('aria-label')).toBe('torch_toggle_off');
    expect(mockTrack.applyConstraints).toHaveBeenLastCalledWith({ advanced: [{ torch: false }] });
  });

  it('silently handles applyConstraints rejection', async () => {
    const mockTrack = setupScannerWithTrack(true);
    mockTrack.applyConstraints = vi.fn().mockRejectedValue(new Error('constraint denied'));
    const btn = createTorchButton();
    document.body.appendChild(btn);
    checkTorchSupport();

    btn.click();
    await flushMicrotasks();
    // Error is swallowed; button state unchanged (aria-pressed stays false)
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('does not update button when button absent from DOM during toggle', async () => {
    const mockTrack = setupScannerWithTrack(true);
    // Create button but do NOT add to DOM
    const btn = createTorchButton();
    checkTorchSupport();

    btn.click(); // toggleTorch called with no #scanner-torch-btn in DOM
    await flushMicrotasks();
    // applyConstraints still called
    expect(mockTrack.applyConstraints).toHaveBeenCalledWith({ advanced: [{ torch: true }] });
  });
});
