# SmartSnack

A mobile-first web app for tracking and scoring food products. Search by name or scan barcodes, pull nutrition data from OpenFoodFacts, and compare products using a fully configurable weighted scoring system.

![demo](https://github.com/user-attachments/assets/8d28ed3c-15eb-4cb2-9106-6fc5e5dc4844)


## Features

- **Barcode Scanner** — Scan EAN-13/8 and UPC-A/E barcodes using the device camera. Detected codes auto-lookup product data from OpenFoodFacts.
- **OCR Ingredient Scanning** — Use the device camera to scan ingredient lists via OCR (powered by EasyOCR), with duplicate detection to skip already-registered products.
- **OpenFoodFacts Integration** — Fetch nutrition info, product names, brand, and images by barcode or text search.
- **Configurable Scoring** — 17 weight fields (kcal, sugar, protein, fiber, fat, price, taste, macro %kcal, etc.) each with toggleable enable, weight slider (0–100), direction (lower/higher is better), and formula (MinMax normalization or Direct mapping). Total score is a weighted average from 1–100.
- **Categories** — Create custom categories with built-in emoji picker. Change emoji on existing categories. Auto-create categories when importing products with unknown types. Multi-select filtering on the product list.
- **Advanced Filters** — Filter products by flags, category, and other fields with a dedicated advanced filter panel.
- **EAN Unlock** — Unlock EAN codes for synced products, with direct links to OpenFoodFacts product pages.
- **Backup & Restore** — Full JSON export/import of the database (products, weights, categories).
- **Responsive UI** — Dark theme with custom styled modals and toast notifications, three-tab layout (Search, Register, Settings). Single-column on mobile, multi-column on tablet/desktop.
- **Multi-language** — Norwegian, English, and Swedish UI translations.
- **HTTPS by Default** — Self-signed certificate generated at startup so camera APIs work over LAN.

## Requirements

- **Docker** and **Docker Compose**

That's it. Everything else (Python 3.12, Flask, Gunicorn, OpenSSL) is handled inside the container.

### If running without Docker

- Python 3.12+
- pip packages (see `requirements.txt`):
  - `flask==3.1.0`
  - `gunicorn==23.0.0`
  - `pyopenssl==24.3.0`
  - `cryptography>=43.0.0`
  - `easyocr>=1.7.0` (OCR ingredient scanning)

## Installation

### Docker (recommended)

```bash
git clone https://github.com/lilfire/smartsnack.git
cd smartsnack
docker compose up -d --build
```

The app will be available at:

- **HTTPS:** `https://localhost:5000` (required for camera/barcode scanning)
- **HTTP:** `http://localhost:5001`

> On first launch a self-signed SSL certificate is generated automatically. Accept the browser warning once.

### Manual

```bash
git clone https://github.com/<your-username>/smartsnack.git
cd smartsnack
pip install -r requirements.txt
python app.py
```

The SQLite database is created automatically at startup. Set the `DB_PATH` environment variable to control where it's stored (default: `./smartsnack.sqlite`).

## Project Structure

```
├── app.py                  # Flask app factory, registers blueprints
├── config.py               # All constants: nutrition fields, score config, text limits
├── db.py                   # SQLite connection, schema init with seed data
├── migrations.py           # Structured database migrations
├── exceptions.py           # Custom exception classes
├── helpers.py              # Request parsing and validation
├── translations.py         # i18n system, reads/writes JSON translation files
├── blueprints/             # Route handlers, one file per domain
├── services/               # Business logic, one file per domain
├── templates/              # Jinja2 templates with partials
├── static/
│   ├── js/                 # Modular vanilla JS frontend (14 ES modules)
│   └── css/                # Modular CSS files (15 files)
├── translations/
│   ├── no.json             # Norwegian translations
│   ├── en.json             # English translations
│   └── se.json             # Swedish translations
├── Dockerfile              # Python 3.12-slim + EasyOCR + OpenSSL
├── docker-compose.yml      # Service config, persistent volume
├── entrypoint.sh           # SSL cert generation + Gunicorn startup
└── requirements.txt        # Python dependencies
```

## Testing

### Backend (Python)

```bash
pip install -e ".[dev]"
pytest
```

### Frontend (JavaScript)

Requires Node.js 18+.

```bash
npm install
npm test
```

## Usage

1. Open the app in a browser and go to the **Registrer** (Register) tab.
2. Tap the barcode icon to scan a product, or search OpenFoodFacts by name.
3. Review auto-filled nutrition data, adjust if needed, and save.
4. Switch to the **Søk** (Search) tab to browse and compare products by score.
5. Use **Innstillinger** (Settings) to tune scoring weights, manage categories, or backup/restore data.

## License

MIT
