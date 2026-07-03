// ── Custom select dropdown (desktop only) ────────────
// Extracted from state.js (LSO-1700 file-size constraint). state.js re-exports
// these, so importers can keep using state.js.

// Wraps a native <select> with a styled custom dropdown.
// onSelect is called with the chosen value after selection.
// Supports re-calling to refresh options when the native <select> is repopulated.
let _docClickRegistered = false;
export function upgradeSelect(sel, onSelect) {
  if (!sel) return;
  if (window.innerWidth < 640) {
    // On mobile, skip custom UI but still register the callback on native select.
    // Track the handler on the element so repeated upgradeSelect calls replace
    // the previous listener instead of accumulating duplicates.
    if (onSelect) {
      if (sel._upgradeSelectHandler) sel.removeEventListener('change', sel._upgradeSelectHandler);
      sel._upgradeSelectHandler = () => onSelect(sel.value);
      sel.addEventListener('change', sel._upgradeSelectHandler);
    }
    return;
  }

  let wrap, trigger, optionsDiv;
  const isNew = !(sel.parentNode && sel.parentNode.classList.contains('custom-select-wrap'));

  if (isNew) {
    wrap = document.createElement('div');
    wrap.className = 'custom-select-wrap';
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);

    trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.tabIndex = 0;
    trigger.setAttribute('aria-expanded', 'false');
    wrap.appendChild(trigger);

    optionsDiv = document.createElement('div');
    optionsDiv.className = 'custom-select-options';
    optionsDiv.setAttribute('role', 'listbox');
    wrap.appendChild(optionsDiv);
  } else {
    wrap = sel.parentNode;
    trigger = wrap.querySelector('.custom-select-trigger');
    optionsDiv = wrap.querySelector('.custom-select-options');
    optionsDiv.innerHTML = '';
  }

  // Store callback on the wrapper so refresh calls can use it
  if (onSelect) wrap._onSelect = onSelect;
  const cb = wrap._onSelect;

  // Sync trigger text with current selection
  const selectedOpt = sel.options[sel.selectedIndex];
  trigger.textContent = selectedOpt ? selectedOpt.textContent : '';

  let highlighted = -1;

  // Inject search input for searchable selects (desktop only)
  if (sel.dataset.searchable === 'true') {
    const si = document.createElement('input');
    si.className = 'custom-select-search';
    si.type = 'text';
    si.autocomplete = 'off';
    si.spellcheck = false;
    si.placeholder = 'Search...';
    si.setAttribute('aria-label', 'Search options');
    optionsDiv.appendChild(si);
    wrap._searchInput = si;
    si.addEventListener('input', () => {
      const q = si.value.toLowerCase();
      optionsDiv.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.style.display = (!q || opt.textContent.toLowerCase().includes(q)) ? '' : 'none';
      });
      optionsDiv.querySelectorAll('.custom-select-group').forEach(grp => {
        let next = grp.nextElementSibling;
        let anyVisible = false;
        while (next && !next.classList.contains('custom-select-group')) {
          if (next.classList.contains('custom-select-option') && next.style.display !== 'none') {
            anyVisible = true;
            break;
          }
          next = next.nextElementSibling;
        }
        grp.style.display = (q && !anyVisible) ? 'none' : '';
      });
    });
    si.addEventListener('click', e => e.stopPropagation());
    si.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); _close(); trigger.focus(); }
    });
  }

  // Build custom option items (with optgroup support)
  function _addOption(o) {
    if (!o.value && !o.textContent.trim()) return;
    const div = document.createElement('div');
    div.className = 'custom-select-option';
    div.setAttribute('role', 'option');
    div.setAttribute('data-value', o.value);
    div.textContent = o.textContent;
    if (o.value === sel.value) div.classList.add('selected');
    optionsDiv.appendChild(div);
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      _pick(div.getAttribute('data-value'), div.textContent);
    });
  }

  const groups = sel.querySelectorAll('optgroup');
  if (groups.length) {
    groups.forEach((g) => {
      const header = document.createElement('div');
      header.className = 'custom-select-group';
      header.textContent = g.label;
      optionsDiv.appendChild(header);
      g.querySelectorAll('option').forEach(_addOption);
    });
  } else {
    sel.querySelectorAll('option').forEach(_addOption);
  }

  // Only attach trigger/document listeners once
  if (isNew) {
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      _closeAllCustomSelects(wrap);
      const isOpen = wrap.classList.toggle('open');
      trigger.setAttribute('aria-expanded', isOpen);
      highlighted = -1;
      _clearHL();
      if (isOpen && wrap._searchInput) {
        wrap._searchInput.focus();
      }
    });

    trigger.addEventListener('keydown', (e) => {
      if (!wrap.classList.contains('open')) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          _closeAllCustomSelects(wrap);
          wrap.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
          if (wrap._searchInput) {
            wrap._searchInput.focus();
          } else {
            highlighted = 0;
            _updateHL();
          }
        } else if (wrap._searchInput && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          _closeAllCustomSelects(wrap);
          wrap.classList.add('open');
          trigger.setAttribute('aria-expanded', 'true');
          wrap._searchInput.value = e.key;
          wrap._searchInput.dispatchEvent(new Event('input'));
          wrap._searchInput.focus();
        }
        return;
      }
      const curItems = Array.from(wrap.querySelectorAll('.custom-select-option')).filter(o => o.style.display !== 'none');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        highlighted = Math.min(highlighted + 1, curItems.length - 1);
        _updateHL();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlighted = Math.max(highlighted - 1, 0);
        _updateHL();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlighted >= 0 && highlighted < curItems.length) {
          _pick(curItems[highlighted].getAttribute('data-value'), curItems[highlighted].textContent);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        _close();
        trigger.focus();
      }
    });

    // Single delegated document listener instead of one per select
    if (!_docClickRegistered) {
      _docClickRegistered = true;
      document.addEventListener('click', () => { _closeAllCustomSelects(); });
    }
  }

  function _close() {
    wrap.classList.remove('open');
    trigger.setAttribute('aria-expanded', 'false');
    highlighted = -1;
    _clearHL();
    if (wrap._searchInput) {
      wrap._searchInput.value = '';
      optionsDiv.querySelectorAll('.custom-select-option, .custom-select-group').forEach(el => {
        el.style.display = '';
      });
    }
  }
  function _clearHL() {
    wrap.querySelectorAll('.custom-select-option').forEach((o) => { o.classList.remove('highlighted'); });
  }
  function _updateHL() {
    _clearHL();
    const curItems = Array.from(wrap.querySelectorAll('.custom-select-option')).filter(o => o.style.display !== 'none');
    if (highlighted >= 0 && highlighted < curItems.length) {
      curItems[highlighted].classList.add('highlighted');
      curItems[highlighted].scrollIntoView({ block: 'nearest' });
    }
  }
  function _pick(value, label) {
    sel.value = value;
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    trigger.textContent = label;
    _close();
    if (cb) cb(value);
  }
}

export function initAllFieldSelects(root = document) {
  const EXCLUDED_CONTEXTS = ['.adv-row', '.wc-row', '.edit-grid'];
  root.querySelectorAll('select.field-select').forEach(sel => {
    if (sel.dataset.noCustomSelect) return;
    const inExcluded = EXCLUDED_CONTEXTS.some(ctx => sel.closest(ctx));
    if (!inExcluded) upgradeSelect(sel);
  });
}

function _closeAllCustomSelects(except) {
  document.querySelectorAll('.custom-select-wrap.open').forEach((w) => {
    if (w !== except) {
      w.classList.remove('open');
      const triggerEl = w.querySelector('.custom-select-trigger');
      if (triggerEl) triggerEl.setAttribute('aria-expanded', 'false');
      if (w._searchInput) {
        w._searchInput.value = '';
        w.querySelectorAll('.custom-select-option, .custom-select-group').forEach(el => {
          el.style.display = '';
        });
      }
    }
  });
}
