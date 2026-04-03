// ── Torch toggle logic for barcode scanner ──────────
import { t } from './i18n.js';

let _torchOn = false;
let _torchTrack = null;

export function createTorchButton() {
  const torchBtn = document.createElement('button');
  torchBtn.id = 'scanner-torch-btn';
  torchBtn.className = 'scanner-torch-btn';
  torchBtn.setAttribute('aria-label', t('torch_toggle_off'));
  torchBtn.setAttribute('aria-pressed', 'false');
  torchBtn.textContent = '\uD83D\uDD26';
  torchBtn.style.display = 'none';
  torchBtn.addEventListener('click', () => toggleTorch());
  return torchBtn;
}

export function checkTorchSupport() {
  try {
    const video = document.querySelector('#scanner-reader video');
    if (!video || !video.srcObject) return;
    const tracks = video.srcObject.getVideoTracks();
    if (!tracks.length) return;
    const track = tracks[0];
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    if (caps.torch) {
      _torchTrack = track;
      const btn = document.getElementById('scanner-torch-btn');
      if (btn) btn.style.display = '';
    }
  } catch(e) {}
}

async function toggleTorch() {
  if (!_torchTrack) return;
  const next = !_torchOn;
  try {
    await _torchTrack.applyConstraints({ advanced: [{ torch: next }] });
    _torchOn = next;
    const btn = document.getElementById('scanner-torch-btn');
    if (btn) {
      btn.classList.toggle('scanner-torch-btn--on', _torchOn);
      btn.setAttribute('aria-pressed', String(_torchOn));
      btn.setAttribute('aria-label', _torchOn ? t('torch_toggle_on') : t('torch_toggle_off'));
    }
  } catch(e) {}
}

export function resetTorch() {
  if (_torchTrack && _torchOn) {
    _torchTrack.applyConstraints({ advanced: [{ torch: false }] }).catch(() => {});
  }
  _torchOn = false;
  _torchTrack = null;
}
