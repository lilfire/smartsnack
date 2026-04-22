import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../i18n.js', () => ({ t: vi.fn((k) => k) }));

import { createTorchButton, checkTorchSupport, resetTorch } from '../scanner-torch.js';

function makeMockTrack(torchCapability = true) {
  return {
    getCapabilities: vi.fn(() => (torchCapability ? { torch: true } : {})),
    applyConstraints: vi.fn().mockResolvedValue(undefined),
  };
}

function setupScannerDOM(track) {
  const scannerDiv = document.createElement('div');
  scannerDiv.id = 'scanner-reader';
  const video = document.createElement('video');
  Object.defineProperty(video, 'srcObject', {
    value: { getVideoTracks: () => (track ? [track] : []) },
    configurable: true,
    writable: true,
  });
  scannerDiv.appendChild(video);
  document.body.appendChild(scannerDiv);
  return { scannerDiv, video };
}

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '';
});

afterEach(() => {
  resetTorch();
  document.body.innerHTML = '';
});

describe('createTorchButton', () => {
  it('creates button with correct id and class', () => {
    const btn = createTorchButton();
    expect(btn.id).toBe('scanner-torch-btn');
    expect(btn.className).toBe('scanner-torch-btn');
  });

  it('starts hidden', () => {
    const btn = createTorchButton();
    expect(btn.style.display).toBe('none');
  });

  it('has correct aria attributes', () => {
    const btn = createTorchButton();
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(btn.getAttribute('aria-label')).toBeTruthy();
  });

  it('displays torch emoji', () => {
    const btn = createTorchButton();
    expect(btn.textContent).toBe('🔦');
  });
});

describe('checkTorchSupport', () => {
  it('returns early when no video element found', () => {
    document.body.innerHTML = '<div id="scanner-reader"></div>';
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('returns early when video has no srcObject', () => {
    const scannerDiv = document.createElement('div');
    scannerDiv.id = 'scanner-reader';
    const video = document.createElement('video');
    // srcObject is null by default
    scannerDiv.appendChild(video);
    document.body.appendChild(scannerDiv);
    expect(() => checkTorchSupport()).not.toThrow();
  });

  it('returns early when no video tracks', () => {
    const { scannerDiv } = setupScannerDOM(null);
    expect(() => checkTorchSupport()).not.toThrow();
    scannerDiv.remove();
  });

  it('returns early when track has no torch capability', () => {
    const track = makeMockTrack(false);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    expect(btn.style.display).toBe('none');
    scannerDiv.remove();
  });

  it('reveals button when track supports torch', () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    expect(btn.style.display).toBe('');
    scannerDiv.remove();
  });

  it('handles track without getCapabilities gracefully', () => {
    const track = { getCapabilities: undefined, applyConstraints: vi.fn() };
    const { scannerDiv } = setupScannerDOM(track);
    expect(() => checkTorchSupport()).not.toThrow();
    scannerDiv.remove();
  });

  it('handles exceptions silently', () => {
    const scannerDiv = document.createElement('div');
    scannerDiv.id = 'scanner-reader';
    const video = document.createElement('video');
    Object.defineProperty(video, 'srcObject', {
      get() { throw new Error('no media'); },
      configurable: true,
    });
    scannerDiv.appendChild(video);
    document.body.appendChild(scannerDiv);
    expect(() => checkTorchSupport()).not.toThrow();
  });
});

describe('toggleTorch (via button click)', () => {
  it('does nothing when _torchTrack is not set', async () => {
    const btn = createTorchButton();
    document.body.appendChild(btn);
    btn.click();
    await new Promise((r) => setTimeout(r, 0));
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('toggles torch on when button is clicked with track', async () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(track.applyConstraints).toHaveBeenCalledWith({ advanced: [{ torch: true }] });
    expect(btn.classList.contains('scanner-torch-btn--on')).toBe(true);
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    scannerDiv.remove();
  });

  it('toggles torch off on second click', async () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(track.applyConstraints).toHaveBeenLastCalledWith({ advanced: [{ torch: false }] });
    expect(btn.classList.contains('scanner-torch-btn--on')).toBe(false);
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    scannerDiv.remove();
  });

  it('handles applyConstraints error silently', async () => {
    const track = {
      getCapabilities: vi.fn(() => ({ torch: true })),
      applyConstraints: vi.fn().mockRejectedValue(new Error('NotAllowedError')),
    };
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(btn.getAttribute('aria-pressed')).toBe('false');
    scannerDiv.remove();
  });

  it('updates aria-label to on label after toggling on', async () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(btn.getAttribute('aria-label')).toBe('torch_toggle_on');
    scannerDiv.remove();
  });
});

describe('resetTorch', () => {
  it('resets state without error when not active', () => {
    expect(() => resetTorch()).not.toThrow();
  });

  it('calls applyConstraints to turn off when torch was on', async () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));
    // Torch is now on (_torchOn=true, _torchTrack=track)

    resetTorch();
    expect(track.applyConstraints).toHaveBeenLastCalledWith({ advanced: [{ torch: false }] });
    scannerDiv.remove();
  });

  it('does not call applyConstraints when torch track exists but is off', () => {
    const track = makeMockTrack(true);
    const { scannerDiv } = setupScannerDOM(track);
    const btn = createTorchButton();
    document.body.appendChild(btn);

    checkTorchSupport(); // sets _torchTrack but _torchOn stays false
    const callCountBefore = track.applyConstraints.mock.calls.length;
    resetTorch();
    expect(track.applyConstraints.mock.calls.length).toBe(callCountBefore);
    scannerDiv.remove();
  });
});
