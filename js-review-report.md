# JavaScript Codebase Review Report

**Project:** SmartSnack
**Date:** 2026-03-11
**Scope:** All 13 JavaScript source files in `static/js/`

---

## Summary

| Metric | Value |
|---|---|
| Total files reviewed | 13 |
| Findings fixed | 7 |
| Findings deferred | 6 |
| New tests added | 7 (across 3 files) |
| Baseline (before) | 244 passed / 8 failed |
| Final result | 268 passed / 3 failed |

---

## Phase 1 — Discovery

- **Source files:** 13 JS files in `static/js/`
- **Test files:** 13 test files in `static/js/__tests__/` (including pre-existing `advanced-filters.test.js`)
- **Test runner:** Vitest 3.2.4 with jsdom environment
- **No `.mjs` files found**

---

## Phase 3 — Findings Fixed (by category)

### Security — innerHTML with unescaped user-controlled data (3 fixes)

| File | Fix |
|---|---|
| `render.js:146` | `catEmoji(p.type)` concatenated into innerHTML without escaping — wrapped with `esc()` |
| `scanner.js:370-371` | `catEmoji(p.type)` concatenated into innerHTML without escaping — wrapped with `esc()` |
| `scanner.js:376` | `catLabel(p.type)` concatenated into innerHTML without escaping — wrapped with `esc()` |

### Implicit type coercion — `==` vs `===` (1 fix)

| File | Fix |
|---|---|
| `render.js:238` | `p.volume == 1`, `p.volume == 2`, `p.volume == 3` changed to strict `===` comparisons |

### Deprecated patterns — `var` usage (1 fix)

| File | Fix |
|---|---|
| `app.js:94,105` | `var wc` and `var searchInput` changed to `const` |

### Unused variables (2 fixes)

| File | Fix |
|---|---|
| `images.js:48` | Unused `reject` parameter in `new Promise((resolve, reject) => ...)` — removed |
| `openfoodfacts.js:542` | Unused `const res` from `await api(...)` — removed variable assignment |

---

## Findings Deferred (with reason)

| File | Finding | Reason |
|---|---|---|
| `state.js` | `showToast()` accesses `document.getElementById('toast')` without null guard | Element is guaranteed present in the SPA shell template |
| `products.js` | Multiple `getElementById()` calls without null guards | All target IDs are statically present in the SPA shell; guards would obscure real bugs |
| `i18n.js` | `el.innerHTML = t(...)` at line 44 | Values come from server-controlled translation files, not user input |
| `openfoodfacts.js` | `return await` inside try/catch blocks | Required for proper error catching — correct async/await usage |
| `settings.js` | innerHTML assignments with API data | All user-controlled fields already escaped with `esc()` |
| `emoji-data.js` | No issues | Static data file with no executable logic |

---

## Phase 4 — New Tests Added

### render.test.js (+2 tests)
- `getFlagConfig` — returns the internal config object
- `loadFlagConfig` — fetches from `/api/flag-config` and stores result; handles fetch failure gracefully

### filters.test.js (+2 tests)
- `rerender` — calls `renderResults` via dynamic import with search query
- `rerender` — uses empty string when search-input element is absent

### products.test.js (+2 tests + 1 mock fix)
- `loadData` — calls fetchStats, buildFilters, fetchProducts, and renderResults in sequence
- `loadData` — shows error toast when fetchStats fails
- **Mock fix:** Added missing `getFlagConfig` to render.js mock (fixed 4 pre-existing failures)
- **DOM fix:** Added missing `f-taste_note` input to registerProduct test setup (fixed 1 pre-existing failure)

---

## Final Test Suite Result vs Baseline

| | Tests Passed | Tests Failed | Test Files Passed | Test Files Failed |
|---|---|---|---|---|
| **Baseline** | 244 | 8 | 9 | 3 |
| **Final** | 268 | 3 | 11 | 2 |
| **Delta** | +24 | -5 | +2 | -1 |

### Remaining 3 failures (pre-existing, unrelated to this review)
- `app.test.js` (2 failures) — Missing `addFlag` export in settings.js mock
- `openfoodfacts.test.js` (1 failure) — `searchOFF` test expects direct OFF API call but implementation now uses server proxy

---

## Files Modified

### Source files (5)
- `static/js/app.js` — `var` → `const` (2 instances)
- `static/js/images.js` — Removed unused `reject` parameter
- `static/js/openfoodfacts.js` — Removed unused variable assignment
- `static/js/render.js` — Escaped `catEmoji()` in innerHTML; strict equality for volume comparisons
- `static/js/scanner.js` — Escaped `catEmoji()` and `catLabel()` in innerHTML (3 instances)

### Test files (3)
- `static/js/__tests__/render.test.js` — Added getFlagConfig and loadFlagConfig tests
- `static/js/__tests__/filters.test.js` — Added rerender tests
- `static/js/__tests__/products.test.js` — Added loadData tests; fixed mock gaps
