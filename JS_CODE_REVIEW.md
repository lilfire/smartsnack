# JavaScript Code Review — SmartSnack

**Date:** 2026-03-09
**Scope:** All 12 `.js` files in `static/js/`
**Methodology:** Each file reviewed independently for bugs, security, performance, and best practices.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| Critical | 25 |
| Warning  | 48 |
| Suggestion | 42 |

### Top themes across the codebase

1. **XSS via inline `onclick` string concatenation** — Server-sourced values (`w.field`, `c.key`, `p.id`) are interpolated into `onclick="fn('...')"` attributes without proper JS-string escaping. `esc()` only handles HTML text context, not attribute or JS contexts, and does not encode single quotes.
2. **Silent error swallowing** — Nearly every `catch` block calls `showToast()` or returns silently. Network errors, JSON parse failures, and DOM errors are indistinguishable to the user and invisible to developers.
3. **`var` used everywhere instead of `const`/`let`** — All 12 files use `var` exclusively despite being ES modules (strict mode). This loses block scoping and allows accidental reassignment.
4. **Event listener accumulation** — `scanner.js` and `openfoodfacts.js` add new `click` delegates to persistent DOM nodes on every search, causing handlers to fire multiple times.
5. **Hardcoded English/Norwegian strings bypassing `t()`** — Dozens of user-visible strings are not translated, breaking i18n for Norwegian and Swedish users.
6. **Fragile `setTimeout`-based sequencing** — Multiple files use hardcoded delays (150–500ms) to wait for async render completion instead of awaiting promises.

---

## File-by-File Findings

---

### 1. `state.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 53–58 | `showToast` crashes if `#toast` is null; no timer deduplication — rapid successive calls cause premature dismissal |
| C2 | Critical | 36–44 | `safeDataUri`/`esc()` does not encode `"` — XSS when output lands in `src="..."` attributes |
| C3 | Critical | 83–87 | Callers access `.total`/`.type_counts` on a potentially empty `cachedStats` object |
| W1 | Warning | 18 | `NUTRI_IDS` uses `var` instead of `const` |
| W2 | Warning | 20–28 | `catEmoji`/`catLabel` do linear scan on every call; duplicated logic |
| W3 | Warning | 62–73 | Timeout/abort errors are untyped; callers cannot distinguish timeout from network failure |
| W4 | Warning | 130–234 | `_docClickRegistered` flag is never resettable; leaked document listener |
| W5 | Warning | 162–163 | Callback stored as expando property on DOM node |
| W6 | Warning | 46–51 | `fmtNum` exported but never imported anywhere — dead code |
| W7 | Warning | 99 | `iconDiv.innerHTML = icon` is an unsanitized injection point |
| S1 | Suggestion | 30–34 | `esc()` allocates a DOM element per call; misses `"` and `'` encoding |
| S2 | Suggestion | 21–27 | Inconsistent `var` + `function()` vs. modern syntax |
| S3 | Suggestion | 91–125 | `showConfirmModal` has no focus trap or Escape key handler |
| S4 | Suggestion | 185–251 | `highlighted` index not reset when select options are refreshed |
| S5 | Suggestion | 65 | `Content-Type: application/json` sent on GET requests unnecessarily |

---

### 2. `app.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 82–86 | `var` + silent `catch` leaves scoring broken without any user feedback |
| C2 | Critical | 89 | Null-unsafe `getElementById('search-input').focus()` crashes init if element absent |
| W1 | Warning | 73–74 | Incomplete `window` getter/setter proxy for `editingId` — maintenance trap |
| S1 | Suggestion | 38–76 | 30+ globals on `window` — namespace under a single object |
| S2 | Suggestion | 84–85 | Two `forEach` loops over same `wc` array can be merged |

---

### 3. `render.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 116 | `c.key` injected raw into `onclick` attribute — XSS via server-sourced column keys |
| C2 | Critical | 124 | `p.id` injected raw into `onclick` attributes — no integer validation |
| C3 | Critical | 209 | Cancel button writes `editingId=null` as bare global instead of `state.editingId` — **edit panel never closes** |
| C4 | Critical | 96–107 | `window._createFromSearch` is stale/undefined when button is clicked |
| W1 | Warning | 29 | Translation strings (`t()` return values) rendered as raw HTML without `esc()` |
| W2 | Warning | 52 | `'\u2605'.repeat()` with unclamped value throws `RangeError` for out-of-range taste scores |
| W3 | Warning | 80–87 | Resize listener at module load time, never removed |
| W4 | Warning | 222 | Monolithic `innerHTML` replacement destroys all DOM state on every re-render |
| W5 | Warning | 233–243 | Images re-fetched (from cache) on every re-render — unnecessary async churn |
| W6 | Warning | 116 | `c.label` rendered without `esc()` |
| W7 | Warning | 199 | Hardcoded English strings "Protein quality (estimated)" and "Estimate" |
| W8 | Warning | 144–152 | Negative score values produce invalid `width:-N%` CSS |
| S1 | Suggestion | all | `var` throughout; should be `const`/`let` |
| S2 | Suggestion | 46 | `COL_UNITS` duplicates config from server — second source of truth |
| S3 | Suggestion | 56–60 | `parseFloat`/`toFixed` on non-numeric values produces `"NaN"` in UI |

---

### 4. `products.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 11 | `numOrNull` crashes on missing DOM elements — no null guard |
| C2 | Critical | 176–179 | `window._pendingImage` cleared even on upload failure; stale image attaches to wrong product |
| C3 | Critical | 217–224 | Hardcoded `setTimeout(500)` races against async `loadData` render cycle |
| W1 | Warning | all | `var` throughout |
| W2 | Warning | 20–38 | Inconsistent optional-element guard between text and numeric fields |
| W3 | Warning | 64 | **Success toast uses `'error'` type** — red notification for successful delete |
| W4 | Warning | 143, 152 | Re-reads `f-ean` from DOM instead of reusing validated variable |
| W5 | Warning | 74–78 | Stats and filters rebuilt on every search keystroke |
| S1 | Suggestion | 2 | `esc` imported but never used — dead import |
| S2 | Suggestion | 128 | Magic number `250` for debounce — extract as named constant |

---

### 5. `images.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 18 | Catch block silently swallows all fetch errors including transient ones |
| C2 | Critical | 30–41 | `FileReader.onerror` never set — silent failure on read error |
| C3 | Critical | 30–31 | `async` `onload` callback — unhandled rejection if `resizeImage` rejects |
| W1 | Warning | 66 | HTML entity passed to `innerHTML` injection point in `showConfirmModal` |
| W2 | Warning | 9, 33, 68 | URL built by string concat — should use `encodeURIComponent` |
| W3 | Warning | 28 | Hardcoded `10 * 1024 * 1024` magic number, not config-driven |
| W4 | Warning | 60 | `img.onerror` resolves with corrupt input instead of rejecting |
| S1 | Suggestion | all | `var` throughout |
| S2 | Suggestion | 25–43 | Nested async-in-callback — wrap `FileReader` in a Promise |
| S3 | Suggestion | 51–58 | Missing canvas background fill — transparent PNGs become black JPEGs |
| S4 | Suggestion | 6–18 | Concurrent calls to `loadProductImage(id)` fire duplicate fetches |

---

### 6. `i18n.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 44–45 | `data-i18n-html` uses `textContent` not `innerHTML` — feature is broken |
| W1 | Warning | 29–36 | `initLanguage` ignores failed `loadTranslations` — UI shows raw keys silently |
| W2 | Warning | 58–62 | Language persisted to server before DOM is updated; no error handling |
| W3 | Warning | 65–70 | `loadSettings()` and `loadData()` not awaited — unhandled rejections |
| S1 | Suggestion | 10–11 | `new RegExp` per param per `t()` call — use `replaceAll` |
| S2 | Suggestion | 39–55 | Four `querySelectorAll` passes — collapse to one compound selector |
| S3 | Suggestion | 63–70 | Two-branch view reload is brittle as new views are added |

---

### 7. `settings.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 83–96 | XSS via `w.field` in inline `onclick` strings — single quotes not escaped |
| C2 | Critical | 251, 257 | Unhandled rejection in `updateCategoryLabel`/`updateCategoryEmoji` |
| C3 | Critical | 427–432 | `deletePq` has no error handling |
| C4 | Critical | 449, 464 | Fire-and-forget async in `handleRestore`/`handleImport`; missing `FileReader.onerror` |
| W1 | Warning | 23–66 | Loading state shown as complete even after partial failure |
| W2 | Warning | 192–201 | DOM vs in-memory dual source of truth in `saveWeights` |
| W3 | Warning | 56–57 | Silent failure if current lang missing from language list |
| W4 | Warning | 482–483 | No null guard for `#restore-drop` in `initRestoreDragDrop` |
| W5 | Warning | 150–184 | Missing null guards on `getElementById` in weight handlers |
| W6 | Warning | 34–37 | `desc` property silently dropped from `SCORE_CFG_MAP` after `loadSettings()` |
| S1 | Suggestion | 73–112 | Replace string-concat HTML with imperative DOM + listeners |
| S2 | Suggestion | 389–390 | `_pqSaveTimers` entries never deleted after firing |
| S3 | Suggestion | 254+ | `fetchStats` + DOM update repeated in 5 places — extract helper |
| S4 | Suggestion | 302 | `esc()` on option `value` attributes corrupts `&` characters |

---

### 8. `filters.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 12 | Single-quote not escaped in `onclick` attribute — XSS via category name |
| C2 | Critical | 36–40 | `toggleFilters` dereferences DOM nodes without null checks |
| W1 | Warning | 92 | `rerender` calls `.value` on potentially-null `#search-input` |
| W2 | Warning | 65–73 | `setSort` accepts unvalidated column name |
| S1 | Suggestion | 91 | Missing `.catch()` on dynamic import in `rerender` |
| S2 | Suggestion | 53–56 | Manual select restore loop is redundant |

---

### 9. `openfoodfacts.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 32, 147, 215 | No `res.ok` check before `.json()` — raw `fetch()` with no error handling |
| C2 | Critical | 515–516 | `.toFixed(2)` on potentially null `est_pdcaas`/`est_diaas` — crash |
| C3 | Critical | 298 | `window._pendingImage` global side-effect with no cleanup |
| W1 | Warning | 135–140 | Event listener accumulates on every search result update |
| W2 | Warning | 305, 506 | Hardcoded English strings bypass i18n |
| W3 | Warning | 154–173 | No URL scheme validation before `esc()` in `img src` |
| W4 | Warning | 20, 354, 455 | Race condition in `_offCtx` module-level shared state |
| S1 | Suggestion | 235–307 | `applyOffProduct` is a 70-line function — decompose |
| S2 | Suggestion | 238–247 | Repetitive nutriment lookup — extract helper |
| S3 | Suggestion | 76, 83 | Hardcoded English placeholder text |
| S4 | Suggestion | 2, 5 | Duplicate `showToast` import from same module |

---

### 10. `scanner.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 380–383 | Click listener accumulates on every search — handlers fire multiple times |
| C2 | Critical | 406–408 | Full product object PUT clobbers server-side fields |
| C3 | Critical | 85, 91 | Fragile `setTimeout` sequencing for dynamic imports |
| W1 | Warning | 27, 126 | Hardcoded English strings bypass i18n |
| W2 | Warning | 96 | `_scanner.stop()` errors silently swallowed — camera may stay active |
| W3 | Warning | 213 | `data-product-id` selector built via string concat with unvalidated ID |
| W4 | Warning | 330–331, 358–366 | Mixed hardcoded English and Norwegian strings in search status |
| W5 | Warning | 362–363 | Wrong translation key (`toast_save_error`) shown for network errors |
| S1 | Suggestion | 20–75, 119–178 | `openScanner` and `openSearchScanner` are 90% identical — deduplicate |
| S2 | Suggestion | 43–54 | Scanner config object duplicated verbatim |
| S3 | Suggestion | 212–218 | Magic timeout (150ms) for scroll-to-highlight |

---

### 11. `emoji-picker.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 106 | Expando property `popup._triggerEl` on DOM node — memory leak risk |
| C2 | Critical | 33 | Duplicate `click` listeners accumulate on re-renders (especially `#cat-emoji-trigger`) |
| C3 | Critical | 125–133 | Document listeners orphaned if popup is removed externally |
| W1 | Warning | 85–100 | `getSearchTerms` recomputed on every keystroke — cache at build time |
| W2 | Warning | 51–52 | `t()` called twice per key; fallback check is always redundant |
| W3 | Warning | all | `var` throughout |
| W4 | Warning | 45–57 | No ARIA role/label on popup or search input |
| S1 | Suggestion | `closePopup` | Focus not returned to trigger on close |
| S2 | Suggestion | grid | No arrow-key navigation within emoji grid |

---

### 12. `emoji-data.js`

| ID | Severity | Line(s) | Issue |
|----|----------|---------|-------|
| C1 | Critical | 41, 100 | `🥜` duplicated with inconsistent names (`peanuts` / `nuts`) |
| C2 | Critical | 127, 136 | `🍶` duplicated with inconsistent names (`sake` / `bottle`) |
| C3 | Critical | 94, 145 | `🫕` duplicated with inconsistent names (`fondue` / `cooking_pot`) |
| W1 | Warning | 6 | `var` used instead of `const` for a never-reassigned module export |
| W2 | Warning | 137–138 | `🫚` (ginger root) possibly mislabelled — verify Unicode name |
| S1 | Suggestion | 6 | Array and entries are mutable; consider `Object.freeze` |
| S2 | Suggestion | — | Search terms could be pre-computed to avoid per-keystroke i18n lookups |

---

## Priority Recommendations

### Immediate fixes (functional bugs)

1. **`render.js:209`** — Cancel button writes to wrong variable; edit panel cannot close
2. **`products.js:64`** — Success delete toast styled as error (red)
3. **`i18n.js:44–45`** — `data-i18n-html` feature is completely broken
4. **`emoji-data.js`** — 3 duplicate emoji entries cause double rendering in picker

### Security fixes

5. **`esc()` in `state.js`** — Does not encode `"` or `'`; unsafe for attribute contexts. Replace with a character-map implementation
6. **`filters.js:12`, `settings.js:83–96`, `render.js:116`** — Inline `onclick` string concatenation with server data. Migrate to `addEventListener` after `innerHTML`

### Reliability fixes

7. **`scanner.js:380`, `openfoodfacts.js:137`** — Event listener accumulation. Attach delegation once at modal creation, not on every search
8. **`products.js:11`** — `numOrNull` null-dereference crash
9. **`openfoodfacts.js:32,147,215`** — Missing `res.ok` check on raw `fetch()` calls
10. **`images.js:30–41`** — Missing `FileReader.onerror`; unhandled async rejection in `onload`

### Code quality (batch)

11. Replace `var` with `const`/`let` across all 12 files
12. Replace hardcoded `setTimeout` sequencing with promise chains
13. Pass all user-visible strings through `t()` for i18n
