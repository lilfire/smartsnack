# SmartSnack

Flask + vanilla JS web app for tracking and scoring Norwegian food products. SQLite database, Docker-ready.

## Running Locally

```bash
pip install -r requirements.txt
DB_PATH=./smartsnack.sqlite python app.py
```

- `DB_PATH` defaults to `/data/smartsnack.sqlite` (Docker path) — override for local dev
- Docker alternative: `docker compose up -d --build` (HTTPS :5000, HTTP :5001)

## Testing & Linting

- **Backend**: `pytest` — run with `python -m pytest` from the project root
- **Frontend**: `vitest` — run with `npx vitest` (requires Node.js >= 18)
- No linter is configured.

## Project Structure

- `app.py` — Flask app factory, creates app and registers blueprints
- `config.py` — All constants: nutrition fields, valid columns, score config, text limits, SQL fragments
- `db.py` — SQLite connection (`get_db()`/`close_db()`), schema init with seed data
- `helpers.py` — Request parsing and validation (`_require_json`, `_num`, `_validate_keywords`)
- `translations.py` — i18n system, reads/writes JSON files in `translations/`
- `blueprints/` — Route handlers, one file per domain. Each exports a `bp` Blueprint, registered in `blueprints/__init__.py` via `register_blueprints()`
- `services/` — Business logic, one file per domain. Blueprints call service functions; services call `get_db()`
- `static/js/` — Vanilla JS frontend modules (no framework, no build step)
- `static/css/` — Modular CSS files
- `templates/` — Jinja2 templates (`base.html` is the main SPA shell)
- `translations/` — JSON files per language (no.json, en.json, se.json)

## Conventions

- **Blueprint-Service separation**: Blueprints are thin — parse request, call service, return JSON. All business logic and DB queries live in `services/`.
- **New blueprints**: Define `bp = Blueprint("name", __name__)`, then import and register in `blueprints/__init__.py`.
- **API responses**: All routes return JSON via `jsonify()`. Errors return `{"error": "message"}` with appropriate HTTP status.
- **Database**: Use `get_db()` from `db.py`. Parameterized queries only — never string-interpolate user values. Dynamic column names must be validated against `config.py` constants. No ORM.
- **No migrations**: Schema is in `init_db()` in `db.py` using `CREATE TABLE IF NOT EXISTS`. New columns need `ALTER TABLE` logic there.
- **Config-driven**: Nutrition fields, valid columns, text limits, and score config are centralized in `config.py`. Do not hardcode elsewhere.
- **Naming**: Internal helpers use leading underscore (`_require_json`, `_num`). Public service functions do not.
- **Frontend**: Vanilla JavaScript, no frameworks, no bundler. Modular files in `static/js/`.
- **Language**: Default is Norwegian (`"no"`). Supported: Norwegian, English, Swedish.
- **Images**: Stored as base64 data URIs in the SQLite `image` column, not as files on disk.

## Scoring Formula

The total score formula in `_score_product` (`services/product_service.py`) is intentional — **do not change it**.

- Each field's score `s` is 0–100 (normalized via minmax or direct formula).
- `scores[field] = s * weight / 100` — the field's weighted contribution.
- `weighted_score_sum += s * weight` — accumulated across all scored fields.
- `total_score = weighted_score_sum / (num_scored_fields * 100)`.

The denominator is `num_scored_fields * 100`, NOT the sum of weights. This treats 100 as the baseline weight: fields with `weight > 100` boost the total above a simple average, fields with `weight < 100` reduce it. This is the intended design — weights act as amplifiers relative to a 100-baseline, not as proportional shares.
