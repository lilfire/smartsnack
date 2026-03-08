# JavaScript Code Review — SmartSnack

**Date:** 2026-03-08
**Scope:** All 12 files in `static/js/`
**Severity levels:** Critical, High, Medium, Low

---

## Executive Summary

The codebase has **multiple XSS vulnerabilities** stemming from a pervasive pattern of building inline `onclick` attribute strings with user-derived data. This is the single most important architectural issue to address. Other recurring themes include: missing error handling on async operations, `var` usage throughout ES modules, race conditions in shared mutable state, and hardcoded English strings bypassing the i18n system.

### Issue Counts by Severity

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 10 |
| Medium | 20 |
| Low | 22 |

---

## Critical Issues

### 1. XSS in `showConfirmModal` — Unescaped HTML in `innerHTML`
**File:** `state.js:71-89`

`showConfirmModal` accepts `title`, `message`, etc. as raw strings and interpolates them directly into `innerHTML`. The `message` parameter comes from `t('confirm_delete_product', { name: name })` where `name` is an unescaped user-supplied product name. A product named `<img src=x onerror=alert(1)>` would execute script when the delete confirmation opens.

**Fix:** Use `textContent` for text portions, or escape all parameters before interpolation.

### 2. XSS via EAN in `onclick` Strings
**File:** `scanner.js:177, 180-181, 220-221, 306, 309`

The `ean` variable (from barcode scan input) is interpolated directly into HTML `onclick` attribute strings without escaping. A crafted barcode value like `'); alert(1); //` breaks the string literal and executes arbitrary JavaScript. The `esc()` helper is never used here.

**Fix:** Use `document.createElement` + `addEventListener` instead of string-built `onclick` attributes.

### 3. XSS via `onclick` String Injection With Product Names
**File:** `render.js:213`, `settings.js:204, 324`

The `esc()` + `.replace(/'/g, "\\'")` chain used in inline `onclick` attributes is incorrect. `esc()` converts `'` to `&#39;` before the replace runs, so the replace never matches. HTML-encoded content in a JS string inside an HTML attribute is decoded by the HTML parser before the JS engine sees it, creating bypass opportunities.

**Fix:** Replace all inline `onclick` strings with event delegation using `data-*` attributes.

---

## High Severity

### 4. `data-i18n-html` is an XSS Sink
**File:** `i18n.js:45`

The `data-i18n-html` attribute path uses `el.innerHTML = t(key)` to write translated strings. If translation content contains user-influenced data or is served from a compromised source, this is a direct XSS vector.

### 5. `t()` Parameter Substitution is Unsafe for HTML Contexts
**File:** `i18n.js:10-13`

`t(key, params)` substitutes `params` values directly into translation strings. When the result is used in `innerHTML` contexts, unsanitized param values become injection points (e.g., category names from the server containing `<script>`).

### 6. `api()` Parses JSON Before Checking HTTP Status
**File:** `state.js:51-52`

`res.json()` is called before checking `res.ok`. A non-JSON error body (e.g., a 502 gateway HTML page) causes `SyntaxError` that obscures the actual HTTP error.

**Fix:** Check `res.ok` first, then parse body with a try/catch fallback.

### 7. No Fetch Timeout in `api()`
**File:** `state.js:48-54`

No `AbortController` or timeout mechanism. A hanging server blocks the UI indefinitely.

### 8. `saveProduct` Has No `try/catch`
**File:** `products.js:45`

An API failure throws silently; the user gets no error feedback and the edit form may be stuck.

### 9. `deleteProduct` Has No `try/catch`
**File:** `products.js:51`

Same issue — network/server errors propagate silently with no user feedback.

### 10. `_offCtx` Race Condition
**File:** `openfoodfacts.js:20`

`_offCtx` is a module-level singleton. Concurrent `lookupOFF` calls overwrite the shared state, corrupting `prefix` and `productId`. The context should be passed as a parameter through the call chain.

### 11. `window._offPickerProducts` Global Namespace Pollution
**File:** `openfoodfacts.js:83, 141, 145`

The product list is stored on `window` so inline `onclick` handlers can reach it. Same race condition risk as `_offCtx`.

### 12. `p.total_score.toFixed(1)` Without Null Guard
**File:** `render.js`

If `total_score` is `null`/`undefined`, this throws a `TypeError` that aborts the entire render, leaving the product list blank.

### 13. `_searchScanMode` Reset Bug
**File:** `scanner.js:93`

`window._searchScanMode = false` in an inline `onclick` has no effect on the module-scoped `_searchScanMode` variable. If a user closes the search scanner manually, the flag stays `true` permanently, misrouting all subsequent scans.

---

## Medium Severity

### 14. Document Click Listener Accumulates Per `upgradeSelect` Call
**File:** `state.js:193-194`

Every `upgradeSelect` call for a new `<select>` adds a permanent `click` listener on `document`. These are never removed and accumulate over the page lifetime.

### 15. `fmtNum` Does Not Guard Against `NaN`
**File:** `state.js:45`

`parseFloat("abc")` returns `NaN`, and `NaN.toFixed(0)` returns `"NaN"`. No `isNaN` guard exists.

### 16. `safeDataUri` Confuses HTML and URL Encoding
**File:** `state.js:39`

For HTTP URLs, `esc()` HTML-encodes the URI (e.g., `&` becomes `&amp;`), breaking URLs with query parameters when used in `src` attributes.

### 17. `resizeImage` Promise Never Settles on Decode Error
**File:** `images.js:42-57`

No `img.onerror` handler. If the data URI is malformed, the promise hangs forever.

### 18. `removeProductImage` Has No Error Handling
**File:** `images.js:60-68`

The `api()` DELETE call has no `try/catch`. A network failure means the user confirmed deletion but gets no feedback that it failed, and state mutations execute regardless.

### 19. `loadCategories` and `deleteCategory` Have Uncaught Rejections
**File:** `settings.js:197-199, 264`

API calls with no `try/catch`; failures produce unhandled promise rejections.

### 20. `loadSettings` Has No Parallel-Execution Guard
**File:** `settings.js:18`

No guard prevents a second invocation before the first resolves, causing unpredictable shared state overwrites.

### 21. `saveWeights` Zeroes Values for Disabled Weights
**File:** `settings.js:182-185`

Disabled weights have no rendered sliders. `parseFloat(null)` returns `NaN`, which resolves to `0` via `|| 0`, silently overwriting stored `formula_min`/`formula_max`.

### 22. Registration Race Condition
**File:** `products.js:192-209`

`switchView('search')` triggers `loadData()`, then `registerProduct` fires a second independent fetch sequence. Two concurrent fetches race to render the same list.

### 23. `selectOffResult` Button Not Reset in `finally`
**File:** `openfoodfacts.js:170-175`

If `applyOffProduct` throws inside the `catch` block, button cleanup is skipped permanently.

### 24. `showOffPickerLoading` Injects `msg` Into `innerHTML` Without Escaping
**File:** `openfoodfacts.js:59`

`msg` comes from `t()` with user-supplied `ean` interpolated. Unescaped HTML injection risk.

### 25. `var el` Redeclared in Same Function Scope
**File:** `openfoodfacts.js:205, 208`

Two `var el` declarations in different `if` blocks share the same function scope due to `var` hoisting.

### 26. `for...in` on API Object
**File:** `render.js`

`for (var sf in sc)` includes inherited enumerable properties. Use `Object.entries()`.

### 27. Function Declaration Inside `if` Block
**File:** `render.js`

`function ev(v)` inside an `if` block is non-standard in sloppy mode. Use `const ev = (v) => ...`.

### 28. Duplicated `isValidEan`
**File:** `render.js`

Local copy duplicates the canonical version in `openfoodfacts.js`. Will silently diverge.

### 29. `loadData` Catch Swallows Errors
**File:** `products.js:71-73`

No `console.error(e)` in catch block. Render crashes are silently absorbed, making debugging impossible.

### 30. `label.textContent` Without Null Guard
**File:** `filters.js:18-33`

`updateFilterToggle` guards `tog` but accesses `label.textContent` unconditionally. Throws if `#filter-toggle-label` is absent.

### 31. Emoji Picker Toggle Fails With Multiple Pickers
**File:** `emoji-picker.js:38`

Clicking trigger B while trigger A's popup is open closes A and returns — requiring a second click on B to open it.

### 32. Network Errors Cached Permanently as `null`
**File:** `images.js:10, 14`

Transient network failures are cached identically to actual 404s, preventing retries for the session.

### 33. Duplicated `showToast` Implementation
**File:** `images.js:71-76`

Re-implements toast logic from `products.js` to avoid circular deps. Changes must be applied in two places.

---

## Low Severity

### 34. 35 Functions Polluting `window`
**File:** `app.js:38-76`

All inline `onclick` dependencies are attached as individual `window` properties. Should be namespaced under a single object (e.g., `window.SS`).

### 35. `var` Used Throughout ES Modules
**Files:** All 12 files

Every file uses `var` despite ES module syntax. `const`/`let` should be used consistently.

### 36. `upgradeSelect` Does Not Handle Tab Key
**File:** `state.js:161-191`

Open dropdown stays visible when Tab moves focus away. WCAG 2.1 keyboard failure.

### 37. `upgradeSelect` `isNew` Check Is Fragile
**File:** `state.js:98`

Relies on CSS class name as initialization state flag. A `WeakSet` would be more robust.

### 38. `fetchStats` Side Effect
**File:** `state.js:63-66`

Silently mutates `state.categories` as a side effect not reflected in the function name.

### 39. `changeLanguage` Does Not Check API Save Result
**File:** `i18n.js:61`

If the save fails, the UI language changes but server state is not updated.

### 40. Multiple DOM Scans in `applyStaticTranslations`
**File:** `i18n.js:39-54`

Four separate `querySelectorAll` calls walking the entire DOM; should be collapsed into one.

### 41. Stats-Line Update Pattern Duplicated 5 Times
**File:** `settings.js:223, 230, 247, 259, 297-298`

Extract into a `refreshStatsLine()` helper.

### 42. `handleRestore` and `handleImport` Nearly Identical
**File:** `settings.js:383-412`

Should share a common inner function.

### 43. `numOrNull` Defined Twice
**File:** `products.js:18, 136`

Identical function in both `saveProduct` and `registerProduct`. Extract to module scope.

### 44. `t` Parameter Shadows Translation Import
**File:** `products.js:80`

`forEach` callback parameter named `t` shadows the `t` import from `i18n.js`.

### 45. `window._pendingImage` Undeclared Global
**File:** `products.js:165`

Should live on `state.pendingImage`.

### 46. `querySelector` Depends on Exact `onclick` Text
**Files:** `products.js:212`, `scanner.js:157`

Selectors encode knowledge of another module's rendered HTML. Use `data-product-id` attributes.

### 47. `setTimeout` Timing Hacks for Async Sequencing
**File:** `scanner.js:66, 201, 335`

`setTimeout(..., 300)` to delay dynamic imports is a race condition on slow devices.

### 48. Duplicated Scanner Open/Start Logic
**File:** `scanner.js`

`openScanner` and `openSearchScanner` share ~40 lines of identical code.

### 49. Hardcoded English/Norwegian Strings Bypassing `t()`
**Files:** `scanner.js`, `render.js`, `openfoodfacts.js`

Multiple user-facing strings hardcoded instead of using the i18n system.

### 50. Duplicate Emoji Entries in Dataset
**File:** `emoji-data.js`

`🥜` (peanuts/nuts), `🍶` (sake/bottle), `🫕` (fondue/cooking_pot) each appear twice.

### 51. `🫚` Mislabelled as "ginger"
**File:** `emoji-data.js`

This Unicode character is actually an olive oil emoji, not ginger.

### 52. No ARIA Roles on Emoji Picker
**File:** `emoji-picker.js`

No `role="dialog"`, `aria-modal`, or focus trapping.

### 53. Emoji Search Terms Not Memoized
**File:** `emoji-picker.js:88-93`

`getSearchTerms()` called per entry per keystroke (~200 translation lookups per keystroke).

### 54. Emoji Picker DOM Rebuilt on Every Open
**File:** `emoji-picker.js:56-71`

~200 `createElement` + `addEventListener` calls per click. Should be cached.

### 55. `_weightSaving` Flag Not in `finally` Block
**File:** `settings.js:176-193`

The flag reset should use `try/finally` to guarantee it is always cleared.

---

## Architectural Recommendations

### 1. Replace Inline `onclick` With Event Delegation (Priority: Highest)
The root cause of most XSS vulnerabilities, the global `window` pollution, the fragile `querySelector` selectors, and CSP incompatibility is the pattern of embedding data in `onclick` string attributes. Migrating to `data-*` attributes with delegated `addEventListener` calls eliminates all of these in one change:

```js
// Instead of:
'<button onclick="deleteProduct(' + id + ',\'' + esc(name) + '\')">'

// Use:
'<button data-action="delete" data-id="' + id + '">'
// Then one delegated listener:
container.addEventListener('click', e => {
  const btn = e.target.closest('[data-action="delete"]');
  if (btn) deleteProduct(btn.dataset.id);
});
```

### 2. Convert `var` to `const`/`let` Project-Wide
Every file uses ES modules (`import`/`export`) and `async`/`await`, which means the target browsers fully support `const`/`let`. Block scoping prevents real bugs (e.g., the `var el` redeclaration in `openfoodfacts.js`).

### 3. Add Error Boundaries to All Async Functions
Many `async` functions lack `try/catch`. At minimum, every user-triggered async action should catch errors and show a toast. Consider a wrapper:

```js
function withErrorToast(fn) {
  return async (...args) => {
    try { return await fn(...args); }
    catch (e) { console.error(e); showToast(t('toast_network_error'), 'error'); }
  };
}
```

### 4. Centralize `showToast`
Move `showToast` into `state.js` to eliminate the duplicate in `images.js` and the circular dependency workaround.

### 5. Pass Context as Parameters, Not Module-Level Singletons
`_offCtx` in `openfoodfacts.js`, `_scannerCtx` in `scanner.js`, and `_scanPickerEan` in `scanner.js` are all mutable singletons that create race conditions. Thread them as function parameters instead.
