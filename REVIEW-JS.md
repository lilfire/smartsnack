# JavaScript Code Review — SmartSnack Frontend

**Date:** 2026-03-09
**Scope:** All 12 `.js` files in `static/js/`
**Reviewer:** Claude (javascript-pro agents)

---

## Critical / High Severity Findings

### Security

| # | File | Lines | Issue |
|---|------|-------|-------|
| 1 | **render.js** | 116, 124, 139 | Unescaped values interpolated into `onclick` JS string context — XSS risk |
| 2 | **filters.js** | 8, 12-13 | Inline `onclick` with string-embedded category names — wrong escaping context |
| 3 | **state.js** | 101 | `iconDiv.innerHTML = icon` — unsanitized HTML injection |
| 4 | **images.js** | 62 | SVG XSS — `img.src` on user-selected SVG data URI can execute scripts |
| 5 | **openfoodfacts.js** | 288, 319 | Unvalidated external URL passed to server-side proxy — SSRF risk |
| 6 | **settings.js** | 84-97 | Inline `onclick` embeds field names with HTML-only escaping, not JS-string escaping |

### Bugs

| # | File | Lines | Issue |
|---|------|-------|-------|
| 7 | **render.js** | 209 | `window.editingId = null` doesn't update `state.editingId` — cancel button broken |
| 8 | **render.js** | 58, 151 | `val.toFixed()` on potentially string values — TypeError |
| 9 | **render.js** | 52 | Star repeat count unclamped — `RangeError` if `val > 6` |
| 10 | **scanner.js** | 96 | `_scanner.clear()` called after `_scanner = null` — guaranteed TypeError |
| 11 | **scanner.js** | 380-383 | New click listener added on every search — accumulates, fires duplicates |
| 12 | **openfoodfacts.js** | 30-31, 149, 217 | `res.ok` never checked on external fetch — silent failures or SyntaxError |
| 13 | **openfoodfacts.js** | 517-518 | `.toFixed(2)` on potentially null values — TypeError |
| 14 | **products.js** | 226-228 | Button reset after `try/catch` instead of `finally` — can stay permanently disabled |
| 15 | **products.js** | 58 | `esc(name)` double-encodes when passed to `textContent`-based modal |
| 16 | **i18n.js** | 43-46 | `data-i18n-html` sets `textContent` instead of `innerHTML` — feature broken |

### Performance

| # | File | Lines | Issue |
|---|------|-------|-------|
| 17 | **render.js** | 222 | Full `innerHTML` replacement on every render — destroys/recreates all DOM |
| 18 | **render.js** | 233-243 | Unbounded parallel image fetches (50+ concurrent requests on first load) |

---

## Medium Severity Findings

### Bugs & Reliability

| # | File | Lines | Issue |
|---|------|-------|-------|
| 19 | **openfoodfacts.js** | 30, 149, 217, 313 | No `AbortController`/timeout on external fetch — UI hangs indefinitely |
| 20 | **products.js** | 217 | `setTimeout(fn, 500)` race condition — fails on slow connections |
| 21 | **scanner.js** | 212 | Same `setTimeout` race with 150ms delay |
| 22 | **filters.js** | 92-95 | `import('./render.js')` has no `.catch()` — unhandled rejection |
| 23 | **filters.js** | 7, 15 | No null-check for `#filter-row` element |
| 24 | **filters.js** | 44-45 | No null-check for `#f-type` element |
| 25 | **settings.js** | 275 | `addCategory` API call has no `try/catch` — unhandled rejection |
| 26 | **settings.js** | 327 | Modal closed before API confirmation in `deleteCategory` |
| 27 | **images.js** | 31-32 | `resizeImage` rejection not caught — sits outside `try` block |
| 28 | **images.js** | 76 | Fallback `||` on `t()` is dead code — `t()` never returns falsy |
| 29 | **emoji-picker.js** | 113-116 | Outside-click uses `!== triggerEl` instead of `!triggerEl.contains()` |
| 30 | **scanner.js** | 37, 126, 136, 362, 428 | Hardcoded English/Norwegian strings bypass i18n |
| 31 | **render.js** | 198-199 | Hardcoded English strings bypass `t()` |
| 32 | **state.js** | 67 | Caller-supplied `opts.headers` silently overwrites default `Content-Type` |
| 33 | **scanner.js** | 12-76 / 110-178 | Full duplication of scanner UI construction (~60 lines copy-pasted) |

### Accessibility

| # | File | Lines | Issue |
|---|------|-------|-------|
| 34 | **state.js** | 93-127 | `showConfirmModal` has no focus trap or Escape key handler |
| 35 | **openfoodfacts.js** | 53-101 | OFF picker modal has no ARIA roles, focus management, or keyboard trap |

---

## Low Severity / Systemic Findings

### Codebase-Wide Patterns (all 12 files)

1. **`var` everywhere** — All files use `var` exclusively despite being ES modules (strict mode). Should be `const`/`let`.
2. **`function()` callbacks** — Arrow functions are never used. `function(x) { ... }` everywhere when `x => ...` is cleaner.
3. **String concatenation for HTML** — No file uses template literals. Complex HTML built with `+` is hard to read and audit.
4. **`innerHTML` + `onclick` pattern** — Multiple files build interactive HTML via string concatenation with inline handlers instead of `createElement` + `addEventListener`.
5. **`t()` fallback `||` is dead code** — `t()` returns the key itself when missing, so `t('key') || 'fallback'` never reaches the fallback. Appears in images.js, products.js, openfoodfacts.js, settings.js.
6. **Magic number `setTimeout` delays** — scanner.js alone has 7 different hardcoded delays (100ms-5000ms) as timing workarounds.

### Per-File Low-Severity Items

| File | Issue |
|------|-------|
| **state.js** | `esc()` creates a new DOM element per call — cache a singleton div |
| **state.js** | `catEmoji`/`catLabel` do linear `Array.find` — use a Map |
| **render.js** | 155-line monolith `renderResults` — needs decomposition |
| **render.js** | Pervasive inline styles belong in CSS |
| **render.js** | `safeDataUri` imported but never used (dead import) |
| **products.js** | `saveProduct`/`registerProduct` share ~35 lines of duplicated field-collection |
| **products.js** | Redundant manual form reset overlaps with `NUTRI_IDS` loop |
| **i18n.js** | `new RegExp` allocated per parameter per `t()` call — use single-pass regex |
| **i18n.js** | Four separate `querySelectorAll` traversals in `applyStaticTranslations` |
| **settings.js** | Stats-line update pattern repeated 5 times — extract a helper |
| **settings.js** | `parseFloat('') \|\| 0` coerces empty to `0` instead of `null` |
| **emoji-picker.js** | `getSearchTerms()` recomputed on every keystroke for every emoji — cache at build |
| **emoji-picker.js** | `setTimeout` for document listener unnecessary since `stopPropagation` is already called |
| **emoji-data.js** | Array is mutable — `Object.freeze()` should be applied |
| **openfoodfacts.js** | Nutriment fallback chains should use `??` instead of nested ternaries |
| **openfoodfacts.js** | URL built via string concat — should use `URLSearchParams` |

---

## Top 10 Recommended Fixes (Priority Order)

1. **Fix `_scanner.clear()` null deref** (scanner.js:96) — crashes at runtime
2. **Fix `window.editingId` vs `state.editingId`** (render.js:209) — cancel button broken
3. **Fix accumulated click listeners** (scanner.js:380) — duplicate fires on search
4. **Add `res.ok` checks on external fetch** (openfoodfacts.js) — silent failures
5. **Replace inline `onclick` HTML with `addEventListener`** (render.js, filters.js, settings.js) — XSS surface
6. **Add timeouts to external fetch calls** (openfoodfacts.js) — indefinite hang
7. **Clamp star repeat value** (render.js:52) — RangeError crash
8. **Fix double-encoding in `showConfirmModal` calls** (products.js:58) — display bug
9. **Fix `data-i18n-html` to use `innerHTML`** (i18n.js:45) — feature doesn't work
10. **Convert `var` to `const`/`let`** (all files) — prevents scoping bugs
