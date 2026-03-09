# Changelog

All notable changes to SmartSnack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
