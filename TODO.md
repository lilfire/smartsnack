# TODO — Duplicate Handling Implementation Plan

## Overview

Implement smart duplicate detection across all product creation flows, using the `is_synced_with_off` flag to determine the correct action. Duplicates are matched by EAN (exact) and name (case-insensitive).

---

## ~~Scenario 1: Register New Product by Barcode + OFF Fetch~~ ✅ COMPLETED

Search for duplicate by EAN and name before inserting.

| Duplicate match | Synced with OFF? | Action |
|---|---|---|
| EAN match | Yes | **Error** — "Product with this EAN already exists" |
| EAN match | No | **Overwrite** — merge OFF data into existing product |
| Name match (no EAN match) | Yes | **Error** — "Product with this name already exists" |
| Name match (no EAN match) | No | **Overwrite** — merge OFF data into existing product |
| No match | — | **Create** new product |

### Implementation Steps

1. **Backend** — `services/product_service.py`:
   - Create `_find_duplicate(ean, name, exclude_id=None)` helper that queries `products` + `product_flags` and returns `{"id", "name", "ean", "match_type", "is_synced_with_off"}` or `None`
   - Update `add_product(data)` to accept optional `on_duplicate` param (`None`/`"overwrite"`)
   - When `from_off=True` and duplicate found and not synced: if `on_duplicate="overwrite"`, call `update_product(dup_id, data)` and return `{"id": dup_id, "merged": True}`
   - When duplicate found and synced: raise `ValueError`
   - When duplicate found, not synced, and no `on_duplicate` set: return 409 with duplicate info so frontend can auto-overwrite

2. **Backend** — `blueprints/products.py`:
   - Pass `on_duplicate` from request JSON to `add_product()`
   - Return 409 with `{"duplicate": {...}}` when duplicate needs resolution

3. **Frontend** — `static/js/products.js` (`registerProduct()`):
   - On 409 response with duplicate info: since this is barcode+OFF (auto-overwrite for unsynced), re-submit with `on_duplicate: "overwrite"`
   - On error (synced duplicate): show error toast as today

---

## ~~Scenario 2: Register New Product by Name (No OFF)~~ ✅ COMPLETED

Search for duplicate by name only (no EAN to check).

| Duplicate match | Synced with OFF? | Action |
|---|---|---|
| Name match | Yes | **Error** — "Product with this name already exists (synced with OFF)" |
| Name match | No | **Ask user**: merge into existing or create new |
| No match | — | **Create** new product |

### Implementation Steps

1. **Backend** — `services/product_service.py`:
   - Reuse `_find_duplicate()` helper
   - When no `from_off` and name duplicate found and not synced: return 409 with `{"duplicate": {...}, "actions": ["merge", "create_new"]}`
   - When synced: raise ValueError

2. **Frontend** — `static/js/products.js` (`registerProduct()`):
   - On 409 with duplicate info: show confirmation modal (reuse `showConfirmModal()` from `static/js/state.js`)
   - Modal options: "Merge into existing" / "Create anyway" / "Cancel"
   - On merge: re-submit with `on_duplicate: "overwrite"`
   - On create anyway: re-submit with `on_duplicate: "allow_duplicate"`

3. **Frontend** — duplicate modal helper:
   - Create `showDuplicateModal(duplicate)` in `static/js/products.js` that shows product name, EAN, and action buttons
   - Returns a Promise resolving to the user's choice

---

## Scenario 3: Edit Product + OFF Fetch

When editing a product and fetching from OFF, the OFF data may match a *different* existing product by EAN or name.

| Duplicate match (different product) | Synced with OFF? | Action |
|---|---|---|
| EAN match | Yes | **Ask user**: delete the duplicate product |
| EAN match | No | **Ask user**: merge duplicate into current product |
| Name match | Yes | **Ask user**: delete the duplicate product |
| Name match | No | **Ask user**: merge duplicate into current product |
| No match (or same product) | — | **Normal update** |

### Implementation Steps

1. **Backend** — new endpoint `POST /api/products/<id>/check-duplicate`:
   - Accepts `{"ean": "...", "name": "..."}` from the OFF data about to be applied
   - Calls `_find_duplicate(ean, name, exclude_id=pid)`
   - Returns `{"duplicate": {...}}` or `{"duplicate": null}`

2. **Backend** — `blueprints/products.py`:
   - Add new route for the check-duplicate endpoint

3. **Backend** — merge/delete support:
   - For merge: `POST /api/products/<id>/merge` — takes `source_id`, copies fields from source into target, deletes source
   - For delete: reuse existing `DELETE /api/products/<dup_id>`

4. **Frontend** — `static/js/openfoodfacts.js` (`applyOffProduct()`):
   - After filling form fields from OFF data, if `productId` is set (edit mode):
     - Call `/api/products/<productId>/check-duplicate` with the OFF EAN and name
     - If duplicate found + synced: show modal "Another product with this EAN/name exists and is synced with OFF. Delete the duplicate?"
     - If duplicate found + not synced: show modal "Another product with this EAN/name exists. Merge it into this product?"
     - On delete: call `DELETE /api/products/<dup_id>`, then proceed with update
     - On merge: call `POST /api/products/<productId>/merge` with `source_id=dup_id`, then proceed
     - On cancel: revert form fields or let user decide

---

## Scenario 4: Import Products

Import must support configurable duplicate handling. Settings are sent with the import request.

### Import Settings

| Setting | Options | Default |
|---|---|---|
| `off_search` | `"name_and_ean"`, `"ean"`, `"name"`, `false` | `"name_and_ean"` |
| `duplicate_check` | `true`, `false` | `true` |
| `duplicate_strategy_synced` | `"merge"`, `"skip"`, `"duplicate"` | `"merge"` |
| `duplicate_strategy_unsynced` | `"merge"`, `"skip"`, `"duplicate"` | `"merge"` |

### Processing Order Per Product

1. If `off_search` is enabled and product is NOT already synced with OFF:
   - Search OFF by the configured mode (name+EAN, EAN only, or name only)
   - If found: enrich product data with OFF fields
2. If `duplicate_check` is enabled:
   - Call `_find_duplicate(ean, name)` to check against existing DB products
   - If duplicate found and synced with OFF → apply `duplicate_strategy_synced`
   - If duplicate found and not synced with OFF → apply `duplicate_strategy_unsynced`
   - Strategy actions:
     - `"skip"`: skip this product entirely
     - `"merge"`: update the existing product with imported data
     - `"duplicate"`: insert as a new product (allow duplicate)
3. If no duplicate or duplicate check disabled: insert as new product

### Duplicate Match Cases for Import

| Duplicate match | Synced? | Strategy=skip | Strategy=merge | Strategy=duplicate |
|---|---|---|---|---|
| EAN match | Yes | Skip | Update existing | Insert new |
| EAN match | No | Skip | Update existing | Insert new |
| Name match | Yes | Skip | Update existing | Insert new |
| Name match | No | Skip | Update existing | Insert new |
| No match | — | Insert new | Insert new | Insert new |

### Implementation Steps

1. **Backend** — `services/backup_service.py` (`import_products()`):
   - Accept `settings` dict from request data
   - Import `_find_duplicate()` from `product_service`
   - For each product: apply OFF search (if enabled), then duplicate check (if enabled)
   - Track counts: `added`, `merged`, `skipped` — return in response
   - For merge: update existing product fields, preserve existing values for fields not in import data

2. **Backend** — `blueprints/backup.py`:
   - Extract `settings` from request JSON, pass to `import_products()`

3. **Frontend** — `static/js/settings.js` (`handleImport()`):
   - Before file upload, show import settings panel:
     - OFF search mode dropdown
     - Duplicate check toggle (default on)
     - Strategy for synced duplicates (dropdown: Skip/Merge/Allow duplicate)
     - Strategy for unsynced duplicates (dropdown: Skip/Merge/Allow duplicate)
   - Include settings in the POST body alongside products

4. **Frontend** — `templates/base.html`:
   - Add import settings HTML elements in the import/backup section

---

## Shared Implementation Tasks

### Backend Helper — `_find_duplicate()` in `services/product_service.py`

```
def _find_duplicate(ean, name, exclude_id=None):
    """Find an existing product matching by EAN or name.

    Returns dict with id, name, ean, match_type, is_synced_with_off
    or None if no duplicate found.
    """
    - Check EAN match first (if ean is provided and non-empty)
    - Then check name match (case-insensitive, if name is provided)
    - Exclude exclude_id from results
    - Join with product_flags to check is_synced_with_off
```

### Translations — `translations/no.json`, `en.json`, `se.json`

New keys needed:
- `duplicate_found_title` — "Duplicate found"
- `duplicate_found_synced` — "A product with this {match_type} already exists and is synced with OFF"
- `duplicate_found_unsynced` — "A product with this {match_type} already exists"
- `duplicate_action_merge` — "Merge"
- `duplicate_action_delete` — "Delete duplicate"
- `duplicate_action_create_new` — "Create anyway"
- `duplicate_action_skip` — "Skip"
- `duplicate_action_allow` — "Allow duplicate"
- `import_setting_off_search` — "Search OpenFoodFacts"
- `import_setting_duplicate_check` — "Check for duplicates"
- `import_setting_strategy_synced` — "If duplicate is synced with OFF"
- `import_setting_strategy_unsynced` — "If duplicate is not synced"
- `import_result_merged` — "{count} merged"

### Tests — `tests/test_product_service.py`

- `_find_duplicate()`: EAN match, name match, exclude_id, synced vs unsynced
- `add_product()` with `on_duplicate="overwrite"`: merge into existing
- `add_product()` with synced duplicate: error
- `import_products()` with merge strategy: updates existing
- `import_products()` with skip strategy: skips
- `import_products()` with duplicate strategy: allows duplicate
- Check-duplicate endpoint: returns correct duplicate info

---

## Files to Modify

| File | Change |
|---|---|
| `services/product_service.py` | Add `_find_duplicate()`, update `add_product()` |
| `blueprints/products.py` | Pass `on_duplicate`, add check-duplicate endpoint |
| `services/backup_service.py` | Import settings + merge/skip/duplicate logic |
| `blueprints/backup.py` | Pass settings through |
| `static/js/products.js` | Duplicate modal, update `registerProduct()` |
| `static/js/openfoodfacts.js` | Duplicate check during edit OFF fetch |
| `static/js/settings.js` | Import settings UI |
| `templates/base.html` | Import settings HTML |
| `translations/*.json` | New translation keys |
| `tests/test_product_service.py` | New duplicate handling tests |

---

## Verification Checklist

- [ ] `python -m pytest` — all tests pass
- [ ] Create product by barcode + OFF: synced duplicate → error
- [ ] Create product by barcode + OFF: unsynced duplicate → auto-overwrite
- [ ] Create product by name: synced duplicate → error
- [ ] Create product by name: unsynced duplicate → merge/create dialog
- [ ] Edit product + OFF: duplicate synced → delete duplicate dialog
- [ ] Edit product + OFF: duplicate unsynced → merge dialog
- [ ] Import with duplicate_check=true, strategy=merge → merges
- [ ] Import with duplicate_check=true, strategy=skip → skips
- [ ] Import with duplicate_check=true, strategy=duplicate → allows duplicate
- [ ] Import with duplicate_check=false → inserts all
- [ ] Import with off_search enabled → enriches products from OFF
- [ ] `npx vitest` — frontend tests pass (if applicable)
