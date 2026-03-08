# Changelog

All notable changes to SmartSnack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
