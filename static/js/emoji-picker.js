// ── Emoji Picker with Search ────────────────────────
import { EMOJI_DATA } from './emoji-data.js';
import { t } from './i18n.js';

var activePopup = null;
var activeCleanup = null;

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

function getSearchTerms(entry) {
  // Combine: translation keywords (comma-separated) + name (underscore-split)
  var key = 'emoji_' + entry.name;
  var translated = t(key);
  var terms = entry.name.replace(/_/g, ' ');
  if (translated !== key) {
    terms += ',' + translated;
  }
  return terms.toLowerCase();
}

export function initEmojiPicker(triggerEl, inputEl, onSelect) {
  if (!triggerEl) return;

  triggerEl.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();

    // Toggle: close if already open from this trigger
    if (activePopup) {
      var wasThisTrigger = (activePopup._triggerEl === triggerEl);
      closePopup();
      if (wasThisTrigger) return;
    }

    // Build popup
    var popup = document.createElement('div');
    popup.className = 'emoji-picker-popup';

    var search = document.createElement('input');
    search.className = 'emoji-picker-search';
    search.type = 'text';
    search.placeholder = t('emoji_search_placeholder') !== 'emoji_search_placeholder'
      ? t('emoji_search_placeholder') : 'Search...';
    popup.appendChild(search);

    var grid = document.createElement('div');
    grid.className = 'emoji-picker-grid';
    popup.appendChild(grid);

    // Build emoji buttons
    var buttons = [];
    EMOJI_DATA.forEach(function(entry) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'emoji-picker-item';
      btn.textContent = entry.emoji;
      btn.title = entry.name.replace(/_/g, ' ');
      btn.addEventListener('click', function() {
        if (inputEl) inputEl.value = entry.emoji;
        triggerEl.textContent = entry.emoji;
        closePopup();
        if (onSelect) onSelect(entry.emoji);
      });
      grid.appendChild(btn);
      buttons.push({ btn: btn, entry: entry });
    });

    // Search filtering
    var emptyMsg = document.createElement('div');
    emptyMsg.className = 'emoji-picker-empty';
    emptyMsg.textContent = t('emoji_no_results') !== 'emoji_no_results'
      ? t('emoji_no_results') : 'No matches';
    emptyMsg.style.display = 'none';
    grid.appendChild(emptyMsg);

    search.addEventListener('input', function() {
      var q = search.value.trim().toLowerCase();
      var anyVisible = false;
      buttons.forEach(function(item) {
        if (!q) {
          item.btn.style.display = '';
          anyVisible = true;
        } else {
          var terms = getSearchTerms(item.entry);
          var match = terms.indexOf(q) !== -1;
          item.btn.style.display = match ? '' : 'none';
          if (match) anyVisible = true;
        }
      });
      emptyMsg.style.display = anyVisible ? 'none' : '';
    });

    // Insert popup inline after the .cat-add-grid container
    var container = triggerEl.closest('.cat-add-grid') || triggerEl.parentNode;
    container.insertAdjacentElement('afterend', popup);

    popup._triggerEl = triggerEl;
    activePopup = popup;

    // Focus search
    search.focus();

    // Close on outside click
    function onDocClick(ev) {
      if (!popup.contains(ev.target) && ev.target !== triggerEl) {
        closePopup();
      }
    }
    // Close on Escape
    function onKeyDown(ev) {
      if (ev.key === 'Escape') {
        closePopup();
      }
    }

    setTimeout(function() {
      document.addEventListener('click', onDocClick);
      document.addEventListener('keydown', onKeyDown);
    }, 0);

    activeCleanup = function() {
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
