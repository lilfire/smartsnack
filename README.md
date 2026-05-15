# SmartSnack

A mobile-first web app for tracking and scoring food products. Search by name or scan barcodes, pull nutrition data from OpenFoodFacts, and compare products using a fully configurable weighted scoring system.

![demo](https://github.com/user-attachments/assets/8d28ed3c-15eb-4cb2-9106-6fc5e5dc4844)

## Features

- **Barcode Scanner** — Scan EAN-13/8 and UPC-A/E barcodes using the device camera with flashlight/torch control. Detected codes auto-lookup product data from OpenFoodFacts.

- **OCR Ingredient Scanning** — Use the device camera to scan ingredient lists. A multi-stage pipeline runs behind the chosen provider:
  
  - **Extraction** uses a shared hardened, language-aware vision prompt with explicit rules for multilingual labels (non-target-language words are discarded, no hardcoded allergen vocabulary — the prompt receives the target language and uses the model's own language knowledge).
  - **Locale validation** detects the output language; on mismatch it retries the extraction, then translates, and finally flags `localeMismatch` with the detected language so the UI can surface it.
  - **LLM cleanup** post-processes the raw text with Claude Haiku to capitalize allergens, apply the language's decimal separator, format trace notices, and strip OCR artifacts using metadata from `translations/<lang>.json`.
  
  Six providers are supported: Tesseract (local), Claude Vision, Gemini Vision, GPT-4 Vision (OpenAI), OpenRouter Vision, and Groq Vision. Includes duplicate detection and quota/rate-limit error handling (429 toast notifications).

- **Protein Quality** — Protein quality scoring based on amino acid completeness, integrated into the configurable scoring system.

- **OpenFoodFacts Integration** — Fetch nutrition info, product names, brand, and images by barcode or text search.

- **Configurable Scoring** — 17 weight fields (kcal, sugar, protein, fiber, fat, price, taste, macro %kcal, etc.) each with toggleable enable, weight slider (0–100), direction (lower/higher is better), and formula (MinMax normalization or Direct mapping). Total score is a weighted average from 1–100.

- **Categories** — Create custom categories with built-in emoji picker. Change emoji on existing categories. Auto-create categories when importing products with unknown types. Multi-select filtering on the product list.

- **Advanced Filters** — Filter products by flags, category, and other fields with a dedicated advanced filter panel.

- **EAN Management** — Manage multiple EAN codes per product (add, remove, set primary). Unlock EAN codes for synced products with direct links to OpenFoodFacts product pages. Per-EAN sync state tracking.

- **Tags** — Create and assign shared tags to products for flexible grouping and filtering.

- **Custom Flags** — Define custom boolean flags (e.g., "discontinued") and toggle them per product.

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
  - `flask-limiter==3.8.0`
  - `gunicorn==23.0.0`
  - `pyopenssl==24.3.0`
  - `cryptography==43.0.3`
  - `pytesseract>=0.3.10` (Tesseract OCR backend)
  - `Pillow>=10.0.0` (image processing)
  - `cairosvg>=2.7.0` (SVG rendering)
  - `anthropic>=0.39.0` (Claude OCR backend)
  - `google-genai>=1.0.0` (Gemini OCR backend)
  - `openai>=1.0.0` (OpenAI OCR backend)
  - `groq>=0.9.0` (Groq Vision OCR backend)
  - `langdetect>=1.0.9` (locale validation for OCR output)

## Installation

### Docker (recommended)

```bash
git clone https://github.com/lilfire/smartsnack.git
cd smartsnack
cp .env.example .env          # edit .env and set SMARTSNACK_SECRET_KEY
docker compose up -d --build
```

> `SMARTSNACK_SECRET_KEY` is required. See `.env.example` for all available environment variables.

### Environment variables

| Variable                                                                                          | Required | Purpose                                                                                                                        |
| ------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `SMARTSNACK_SECRET_KEY`                                                                           | yes      | Flask session secret                                                                                                           |
| `SMARTSNACK_API_KEY`                                                                              | optional | API token enforced on write endpoints                                                                                          |
| `DB_PATH`                                                                                         | optional | SQLite path (default `/data/smartsnack.sqlite` in Docker, `./smartsnack.sqlite` locally)                                       |
| `APP_VERSION_SUFFIX`                                                                              | optional | Appended to the version badge in the footer, e.g. `APP_VERSION_SUFFIX=DEV` renders `v0.19-DEV`                                 |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `GROQ_API_KEY` | optional | Enable the matching OCR provider — see [OCR Providers](#ocr-providers). `ANTHROPIC_API_KEY` also enables the OCR cleanup pass. |

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

## OCR Providers

Tesseract runs locally and is always available (no API key needed). The other providers require API keys set as environment variables:

| Provider              | Environment Variable |
| --------------------- | -------------------- |
| Claude Vision         | `ANTHROPIC_API_KEY`  |
| Gemini Vision         | `GEMINI_API_KEY`     |
| GPT-4 Vision (OpenAI) | `OPENAI_API_KEY`     |
| OpenRouter Vision     | `OPENROUTER_API_KEY` |
| Groq Vision           | `GROQ_API_KEY`       |

Providers with a valid key appear automatically in **Settings → OCR**. You can also set a fallback to Tesseract if the selected provider fails.

After the provider extracts text, the output is passed through two shared post-processing stages:

- **Locale validation** (`services/ocr_locale_validator.py`) uses `langdetect` to confirm the result matches the requested language. On mismatch it retries the extraction, then translates the text, and finally flags `localeMismatch=true` with the detected language so the UI can prompt the user.
- **LLM cleanup** (`services/llm_cleanup_service.py`) runs Claude Haiku over the raw text to normalize allergens, decimal separator, and trace notices using the target language's metadata. Cleanup is only invoked when `ANTHROPIC_API_KEY` is set — without it the pipeline returns the raw OCR text and marks `llm_cleanup_skipped=true` in the response.

**Docker users:** pass API keys via a `.env` file or an `environment:` block in `docker-compose.yml`:

```yaml
environment:
  - ANTHROPIC_API_KEY=your_key_here
  - GROQ_API_KEY=your_key_here
```

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
│   ├── product_service.py      # Product facade (delegates to sub-modules)
│   ├── product_crud.py         # Product create/read/update/delete
│   ├── product_duplicate.py    # Duplicate detection logic
│   ├── product_eans.py          # EAN/barcode management
│   ├── product_filters.py      # Product filtering/search
│   ├── product_scoring.py      # Scoring computation
│   ├── ocr_core.py             # OCR orchestration
│   ├── ocr_service.py          # OCR HTTP endpoints helper
│   ├── ocr_settings_service.py # OCR provider settings
│   ├── ocr_backends/           # Per-provider OCR modules
│   │   ├── claude.py
│   │   ├── gemini.py
│   │   ├── groq.py
│   │   ├── openai.py
│   │   ├── openrouter.py
│   │   └── tesseract.py
│   ├── backup_core.py          # Database backup logic
│   ├── import_service.py       # Database import/restore
│   ├── protein_quality_service.py  # Protein quality scoring
│   ├── bulk_service.py
│   ├── category_service.py
│   ├── flag_service.py
│   ├── image_service.py
│   ├── off_service.py          # OpenFoodFacts integration
│   ├── proxy_service.py
│   ├── settings_service.py
│   ├── stats_service.py
│   ├── tag_service.py              # Tag management
│   ├── translation_service.py
│   └── weight_service.py
├── templates/              # Jinja2 templates with partials
├── static/
│   ├── js/                 # Modular vanilla JS frontend (~29 ES modules)
│   │   ├── app.js, state.js, render.js, i18n.js
│   │   ├── products.js, images.js, filters.js, scanner.js, ocr.js, scroll.js
│   │   ├── advanced-filters.js, tags.js, ean-manager.js, scanner-torch.js
│   │   ├── emoji-data.js, emoji-picker.js
│   │   ├── off-api.js, off-conflicts.js, off-duplicates.js
│   │   ├── off-picker.js, off-review.js, off-utils.js
│   │   └── settings-backup.js, settings-categories.js, settings-flags.js,
│   │       settings-ocr.js, settings-off.js, settings-pq.js, settings-weights.js
│   └── css/                # Modular CSS files (16 files)
├── translations/
│   ├── no.json             # Norwegian translations
│   ├── en.json             # English translations
│   └── se.json             # Swedish translations
├── Dockerfile              # Python 3.12-slim + multi-provider OCR + OpenSSL
├── docker-compose.yml      # Service config, persistent volume
├── entrypoint.sh           # SSL cert generation + Gunicorn startup
└── requirements.txt        # Python dependencies
```

## Testing

### Backend (Python)

```bash
pip install -r requirements.txt
python -m pytest
```

### Frontend (JavaScript)

Requires Node.js 18+.

```bash
npx vitest
```

### End-to-end (Playwright)

The `tests/e2e/` suite drives a real browser against an in-process Flask server. Tesseract and Chromium must be available locally; the GitHub Actions `e2e-test` job installs them automatically.

```bash
pip install -r requirements-dev.txt
playwright install chromium
python -m pytest tests/e2e/
```

## Usage

1. Open the app in a browser and go to the **Registrer** (Register) tab.
2. Tap the barcode icon to scan a product, or search OpenFoodFacts by name.
3. Review auto-filled nutrition data, adjust if needed, and save.
4. Switch to the Search tab to browse and compare products by score.
5. Use Settings to tune scoring weights, manage categories, or backup/restore data.



## License

MIT
