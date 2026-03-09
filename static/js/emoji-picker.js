// ── Emoji Picker with Search ────────────────────────
import { EMOJI_DATA } from './emoji-data.js';
import { t } from './i18n.js';

let activePopup = null;
let activeCleanup = null;

function closePopup() {
  if (activePopup) {
    activePopup.remove();
    activePopup = null;
  }
  if (activeCleanup) {
    activeCleanup();
    activeCleanup = null;
  }
}

// Cache search terms per entry to avoid recomputing on every keystroke
const _searchTermsCache = new WeakMap();
function getSearchTerms(entry) {
  if (_searchTermsCache.has(entry)) return _searchTermsCache.get(entry);
  const key = 'emoji_' + entry.name;
  const translated = t(key);
  let terms = entry.name.replace(/_/g, ' ');
  if (translated !== key) {
    terms += ',' + translated;
  }
  const result = terms.toLowerCase();
  _searchTermsCache.set(entry, result);
  return result;
}

export function initEmojiPicker(triggerEl, inputEl, onSelect) {
  if (!triggerEl) return;

  triggerEl.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();

    // Toggle: close if already open from this trigger
    if (activePopup) {
      const wasThisTrigger = (activePopup._triggerEl === triggerEl);
      closePopup();
      if (wasThisTrigger) return;
    }

    // Build popup
    const popup = document.createElement('div');
    popup.className = 'emoji-picker-popup';

    const search = document.createElement('input');
    search.className = 'emoji-picker-search';
    search.type = 'text';
    search.placeholder = t('emoji_search_placeholder') !== 'emoji_search_placeholder'
      ? t('emoji_search_placeholder') : 'Search...';
    popup.appendChild(search);

    const grid = document.createElement('div');
    grid.className = 'emoji-picker-grid';
    popup.appendChild(grid);

    // Build emoji buttons
    const buttons = [];
    EMOJI_DATA.forEach((entry) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'emoji-picker-item';
      btn.textContent = entry.emoji;
      btn.title = entry.name.replace(/_/g, ' ');
      btn.addEventListener('click', () => {
        if (inputEl) inputEl.value = entry.emoji;
        triggerEl.textContent = entry.emoji;
        closePopup();
        if (onSelect) onSelect(entry.emoji);
      });
      grid.appendChild(btn);
      buttons.push({ btn: btn, entry: entry });
    });

    // Search filtering
    const emptyMsg = document.createElement('div');
    emptyMsg.className = 'emoji-picker-empty';
    emptyMsg.textContent = t('emoji_no_results') !== 'emoji_no_results'
      ? t('emoji_no_results') : 'No matches';
    emptyMsg.style.display = 'none';
    grid.appendChild(emptyMsg);

    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      let anyVisible = false;
      buttons.forEach((item) => {
        if (!q) {
          item.btn.style.display = '';
          anyVisible = true;
        } else {
          const terms = getSearchTerms(item.entry);
          const match = terms.indexOf(q) !== -1;
          item.btn.style.display = match ? '' : 'none';
          if (match) anyVisible = true;
        }
      });
      emptyMsg.style.display = anyVisible ? 'none' : '';
    });

    // Insert popup inline after the .cat-add-grid container
    const container = triggerEl.closest('.cat-add-grid') || triggerEl.parentNode;
    container.insertAdjacentElement('afterend', popup);

    popup._triggerEl = triggerEl;
    activePopup = popup;

    // Focus search
    search.focus();

    // Close on outside click — use contains() to handle child elements of trigger
    const onDocClick = (ev) => {
      if (!popup.contains(ev.target) && !triggerEl.contains(ev.target)) {
        closePopup();
      }
    };
    // Close on Escape
    const onKeyDown = (ev) => {
      if (ev.key === 'Escape') {
        closePopup();
      }
    };

    setTimeout(() => {
      document.addEventListener('click', onDocClick);
      document.addEventListener('keydown', onKeyDown);
    }, 0);

    activeCleanup = () => {
      document.removeEventListener('click', onDocClick);
      document.removeEventListener('keydown', onKeyDown);
    };
  });
}

export function resetEmojiPicker(triggerEl, defaultEmoji) {
  if (triggerEl) {
    triggerEl.textContent = defaultEmoji || '\u{1F4E6}';
  }
}
