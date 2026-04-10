# Changelog

All notable changes to SmartSnack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.14.0] - 2026-04-10

### Added

- Tag system with shared tag entities, CRUD API, chips UI with autocomplete/suggestions, and per-product assignment
- Multi-backend OCR: 6 providers (Tesseract, Claude Vision, Gemini, GPT-4 Vision, OpenRouter, Groq) with per-provider model selection
- OCR settings UI for choosing provider, model, and fallback preference
- Per-EAN management: products can have multiple EANs, each with independent OFF sync tracking, add/delete, set-primary, and per-EAN OFF fetch/unlock
- Pagination with limit/offset on product list API and infinite scroll on frontend
- OFF language priority: configurable language preference order for Open Food Facts data fetching
- Flashlight/torch toggle button for barcode scanner on mobile
- Structured OCR error responses with categorized error types (token limit, quota, timeout, invalid image, no text)
- Rate limiting via Flask-Limiter (200/min global, 10/min on OCR endpoint)
- GitHub Actions CI: pytest + coverage, vitest + coverage, Docker build, smoke test, and branch name enforcement
- `.env.example` with all supported environment variables
- Tag and EAN data included in backup/restore with legacy fallback support
- 50+ new translation keys for tags, OCR, EAN management, and OFF language settings

### Changed

- Product list API now returns `{products, total}` instead of a flat array
- Tag schema reimplemented from text-based tags to integer FK schema (tags + product_tags tables)
- OCR service redesigned with provider registry and automatic fallback to Tesseract

### Refactored

- Product service split into focused modules: product_crud, product_eans, product_scoring, product_filters, product_duplicate
- Backup service split into backup_core and import_service
- `openfoodfacts.js` split into 6 modules: off-api, off-conflicts, off-duplicates, off-picker, off-review, off-utils
- `settings.js` split into 7 modules: settings-backup, settings-categories, settings-flags, settings-ocr, settings-off, settings-pq, settings-weights

## [0.13.0] - 2026-03-23

### Changed

- Product list layout changed to 3-line format: brand, name, EAN
- Disable scan and OFF fetch buttons for synced products

### Fixed

- Long product names being truncated in search results
- Long category names being cut off in product table
- Product form reset not clearing the type field

### Improved

- Accessibility improvements and UX polish

## [0.12.0] - 2026-03-22

### Improved

- EasyOCR accuracy with image preprocessing and position-based text ordering
- Replaced aggressive thresholding with gentle dual-pass OCR strategy
- Lazy-load numpy in OCR service for faster startup

### Fixed

- Skip name-based duplicate check when EAN is provided

### Added

- Frontend tests for OCR and related modules

## [0.11.0] - 2026-03-22

### Added

- OCR ingredient scanning with image-to-text extraction
- Duplicate skip option when adding products
- EAN unlock feature for synced products
- Flag field filtering in product list
- OpenFoodFacts link displayed for synced products

### Fixed

- Advanced filter bug: load flags before post-filtering
- Filter select reset not clearing value when no previous selection exists
- Android keyboard scroll jump on range inputs
- Filter rerender scope causing unnecessary updates

### Changed

- Brand field included in product search query

## [0.10.0] - 2026-03-22

### Added

- Filter for uncategorized products in category select
- Brand prefix displayed before product name when not already included

### Changed

- Category select in edit modal upgraded with improved styling
- Product list layout: category label moved below its icon, fixed-width columns for category and thumbnail
- Sub-label (EAN/completeness) aligned with product name
- Brand styled consistently within product name

### Fixed

- Score weights losing `formula_max` for direct-formula fields

## [0.9.0] - 2026-03-21

### Added

- Support for uncategorized products (products without a category)
- SQLite database files to .gitignore

### Changed

- Advanced filter number inputs replaced with text inputs using numeric inputMode for better mobile UX
- Improved advanced filter row styling consistency and overflow handling

### Fixed

- Category name validation rejecting valid names with special characters
- Advanced filters test to expect placeholder option from CATEGORY_OPS

## [0.8.0] - 2026-03-21

### Added

- Advanced filters with category filter and is_set/is_not_set operators
- Prompt user to add new products to Open Food Facts after saving
- 7 missing translation keys across all languages
- Translation coverage tests and deduplication of translation keys
- E2e tests and supporting translation keys
- Expanded test coverage for filters, i18n, OFF, render, scanner, settings, app, backup, and categories modules
- Demo image to README

### Changed

- Improved OFF API refresh reliability and fix edge cases
- Auto-close OFF picker on scanner miss and fix bulk image error handling

### Fixed

- Taste slider losing value/focus on touch release
- Taste score label showing raw {val} placeholder instead of actual value
- Empty-value checks, Content-Type headers, mobile select, and i18n result counts
- Test pollution by isolating translation files during tests

## [0.7.0] - 2026-03-13

### Added

- Duplicate detection when saving products: detects existing products by EAN or name, with merge/overwrite/allow-duplicate options
- 3-scenario duplicate handling when editing products with OFF data, merging intelligently based on OFF sync status
- Field-level conflict resolution modal letting users pick values per field when merging duplicate products, with bulk "keep all" buttons
- Merge products API endpoint (`POST /api/products/<pid>/merge`) and check-duplicate endpoint (`POST /api/products/<pid>/check-duplicate`)
- Duplicate control dialog for product import with configurable match criteria (EAN/name/both) and duplicate action (skip/overwrite/merge/allow)
- Sync-aware merge logic for imports: uses OFF sync status to determine field priority, with configurable fallback
- Import result reporting for merged, overwritten, and skipped products
- Cache-busting headers for JavaScript files to prevent stale module caching
- ~40 new translation keys across all languages for duplicate, merge, conflict, and import flows
- New `modals.css` with styles for all merge/conflict/duplicate modals
- Expanded UI test coverage for app, openfoodfacts, settings, and other frontend modules
- Improved backend and frontend test coverage to 75%+ branch for all files

### Changed

- OpenFoodFacts integration now fills additional metadata fields (name, EAN, brand, stores, ingredients) and tracks applied fields
- API error responses now include HTTP status code and response data for proper 409 conflict handling
- Taste score slider changed to 0–6 range with average default rounded to nearest 0.5

## [0.6.0] - 2026-03-12

### Added

- Playwright end-to-end tests using pytest-playwright with auto-install of Chromium browser
- @vitest/coverage-v8 for JavaScript test coverage reporting
- 6 missing scanner translation keys to all languages
- Coverage output directories to .gitignore

### Changed

- Full-app code review: bug fixes, security hardening, accessibility improvements, and increased test coverage
- Python code review: fixed issues and added 202 new tests (78% to 89% coverage)
- JavaScript code review: security fixes, strict equality enforcement, and test improvements
- JavaScript test coverage improved from 56.6% to 76.2%
- All Python modules brought to 75%+ test coverage
- HTML templates cleaned up: normalized indentation, improved accessibility, and better structure
- CSS cleanup: removed duplicates, redundancies, and normalized formatting
- Extracted inline style from version badge in base.html to CSS class

### Fixed

- Subtitle flashing "Loading" text on language change
- Missing loadFlagConfig mock in app.test.js
- Stderr warnings in i18n and settings tests by mocking render.js
- Test pollution: use translations_dir fixture in flag/PQ tests
- 3 failing JS tests

## [0.5.0] - 2026-03-11

### Added

- Taste note text field for products
- Completeness score to track product data quality
- Product flags system with dynamic flag management (junction table, settings UI, dark-themed toggle checkboxes, filters)
- Advanced filters with toggle between search and advanced mode, slide-down animation
- Bulk refresh from OpenFoodFacts with progress bar, server-side job state, and "search missing by name" option
- Certainty score for OFF product name search results with nutrition comparison
- Detailed per-product report after OFF refresh shown in full-width modal
- Duplicate check on EAN and name when adding products
- `is_synced_with_off` flag tracking across all OFF data flows

### Changed

- Improved OFF product matching with brand+name boost, category boost, and stricter nutrition similarity
- Search scoring now penalizes extra name words and missing OFF nutrition data
- Brand scoring checks brand words against query, not the reverse
- Show API error message in toast instead of generic "Error saving"
- Show taste score with taste note in expanded product view

### Fixed

- OFF fetch overwriting existing local nutrition values with 0
- 500 error on product name search via OpenFoodFacts
- Import endpoint now skips duplicate products

## [0.4.0] - 2026-03-09

### Added

- Comprehensive backend unit tests for all Python functions (pytest)
- Comprehensive frontend unit tests for all JavaScript functions (Vitest)
- `pyproject.toml` with pytest configuration and dev dependencies
- Node.js >= 18 engine requirement for Vitest 3.x compatibility
- PowerShell test wrapper for Windows development

### Changed

- Taste score input replaced with range slider in edit form

### Fixed

- XSS: escape quotes in `esc()` for safe use in HTML attributes
- Unescaped labels in innerHTML and wrong toast type on delete
- Multiple security, quality, and maintainability issues across all Python files (32 files reviewed)
- Multiple security and quality issues across all JavaScript files (12 files reviewed)
- Search result product expand not working on click (duplicate event listeners)
- Docker entrypoint "no such file or directory" on Windows
- Database locked error on Docker startup
- Tests failing in VSCode when Flask is not installed
- Deferred Flask-dependent imports in backup_service for pytest compatibility

## [0.3.0] - 2026-03-08

### Added

- Auto-create categories with emoji when importing products with unknown types
- Ability to change emoji on existing categories
- "Create product" button when search returns no results
- Custom styled modals replacing native browser confirm() dialogs
- Toast notifications for errors (replacing silent console.error calls)
- Structured database migrations module (`migrations.py`)

### Changed

- Volume field changed from numeric input to Low/Medium/High dropdown with custom dark theme
- Barcode scan buttons hidden on desktop, shown only on mobile (pointer: coarse media query)
- All combobox and dropdown options sorted alphabetically
- Number input spinner arrows hidden on desktop

### Fixed

- Product list 500 error with error toasts
- Category deletion now prompts user to reassign products instead of silently disabling
- Pre-fill EAN field instead of name when searching by barcode
- Broken language section on settings page
- Translation key format for category names with uppercase letters

## [0.2.0] - 2026-03-08

### Added

- Swedish language support (full UI translation)
- Add product to Open Food Facts via API when EAN barcode is not found, with credential storage in settings
- Emoji picker with search functionality for category creation
- EAN format validation (8-13 digits) on product save
- Macro calorie percentage weights for scoring: protein %kcal, fat %kcal, carbs %kcal
- Version display in the UI footer and health check endpoint
- Dynamic language selection based on available translation files in `translations/`
- Translated formula dropdown options (MinMax/Direct)

### Changed

- Replaced native select elements with custom dark-themed dropdowns on desktop
- Made all settings sections collapsible (hidden by default)
- Redesigned weights section to show only active weights with add/remove controls
- Removed "Reset to default" button for weights
- Split settings page into responsive grid columns for wider screens

### Refactored

- Refactored monolithic `app.js` into 12 ES modules (`state.js`, `i18n.js`, `products.js`, `settings.js`, `scanner.js`, `openfoodfacts.js`, `render.js`, `filters.js`, `images.js`, `emoji-picker.js`, `emoji-data.js`)
- Refactored monolithic `style.css` into 14 modular CSS files
- Refactored Flask monolith into blueprints + service layer architecture (12 blueprints, 12 services)
- Refactored `index.html` into Jinja2 templates with partials

### Fixed

- Security hardening and robustness guards from code review
- Settings page crash caused by dead `renderWeightBar` code
- Category placeholder translation to respect selected language
- Emoji picker positioning and layout on desktop
- Settings section spacing and margin inconsistencies
- Missing static assets in Docker build

## [0.1.0] - 2026-03-06

### Added

- Product management: add, edit, and delete food products with full nutrition data (kcal, carbs, sugar, fat, saturated fat, protein, fiber, salt, weight, portion, volume, price)
- Product search by name or EAN barcode with multi-select category filtering
- Barcode scanner using device camera (EAN-13, EAN-8, UPC-A, UPC-E formats)
- OpenFoodFacts integration: fetch nutrition data, product names, and images by barcode or text search
- Image proxy for OpenFoodFacts product images
- Configurable scoring system with 12+ weighted fields, direction toggle (lower/higher is better), and formula modes (MinMax normalization or Direct mapping)
- Protein quality estimation from ingredient text using 32 pre-loaded protein sources with PDCAAS and DIAAS values
- Custom protein quality entries with multi-language keyword matching
- Category management with emoji labels and localized names
- Product images stored as base64 data URIs (max 2 MB per image)
- Taste score rating (0-6 scale) per product
- Full database backup and restore as JSON (products, weights, categories, protein quality, translations)
- Partial product import from backup files
- Internationalization with Norwegian (default) and English
- Settings page for language selection and scoring weight configuration
- Three-tab UI: Search, Register, Settings
- Dark theme with responsive design (mobile-first, multi-column on wider screens)
- Docker deployment with auto-generated self-signed SSL certificate
- Dual port access: HTTPS on port 5000 (required for camera APIs) and HTTP on port 5001
- Health check endpoint with product count
- SQLite database with WAL mode and automatic schema creation
- Seed data: demo product and default "Snacks" category
- REST API with JSON responses for all operations
