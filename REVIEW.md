# SmartSnack Python Code Review

**Date**: 2026-03-09
**Scope**: All 32 `.py` files across core, blueprints, and services
**Standard**: PEP 8 + Google Python Style Guide

---

## Executive Summary

The codebase is well-structured with excellent blueprint-service separation, consistent error handling, and clean import organization. The main areas needing attention are **security** (authentication, CORS, encryption) and some **data integrity** edge cases.

| Severity | Count |
|----------|-------|
| High     | 5     |
| Medium   | 16    |
| Low      | 53    |

---

## High Severity Issues

### H1. Insecure default encryption key (`services/settings_service.py:25`)
- **Category**: Security
- **Description**: The Fernet encryption key for OFF passwords uses a hardcoded default (`SMARTSNACK_SECRET_KEY` env var with a fallback). Anyone with source access can decrypt stored passwords.
- **Fix**: Require the env var at startup; fail fast if not set.

### H2. CORS origin derived from user-controlled headers (`blueprints/proxy.py:21-26`)
- **Category**: Security
- **Description**: `Access-Control-Allow-Origin` is constructed from `X-Forwarded-Proto` and `request.host`, both user-controlled. An attacker can forge headers to make the server emit a CORS allow for any origin.
- **Fix**: Use a configured origin whitelist, or `"*"` if the proxied images are public.

### H3. Backup endpoint has no authentication (`blueprints/backup.py:17-29`)
- **Category**: Security
- **Description**: `/api/backup` dumps the entire database (products, images, categories) as JSON with no auth. Anyone who can reach the server can exfiltrate the full dataset.
- **Fix**: Add authentication middleware or API key requirement.

### H4. OFF credentials endpoint has no authentication (`blueprints/settings.py:33-49`)
- **Category**: Security
- **Description**: `/api/settings/off-credentials` GET exposes the Open Food Facts user ID, and PUT allows overwriting credentials, both without authentication.
- **Fix**: Add authentication.

### H5. Ineffective `fcntl` shared locks (`translations.py:152-153, 171-172`)
- **Category**: Bug
- **Description**: File locks use `LOCK_SH` (shared) for both read and write operations. Shared locks don't prevent concurrent writes, making the locking mechanism ineffective for preventing race conditions.
- **Fix**: Use `LOCK_EX` (exclusive) for write operations.

---

## Medium Severity Issues

### M1. Non-atomic translation writes during restore (`services/backup_service.py:219-272`)
- **Category**: Data Integrity
- **Description**: Database rollback does not undo file-based translation changes, leaving inconsistent state if the DB transaction fails after translations are written.

### M2. Legacy XOR-encrypted passwords never re-encrypted (`services/settings_service.py:41-52`)
- **Category**: Security
- **Description**: Passwords encrypted with the old weak XOR method are decrypted on read but never re-encrypted with Fernet, so weak encryption persists indefinitely.

### M3. `update_product` returns success for non-existent products (`blueprints/products.py:32-39`)
- **Category**: Bug
- **Description**: SQLite `UPDATE` silently affects 0 rows. The endpoint returns `{"ok": true}` even when the product doesn't exist. Should return 404.

### M4. Restore/import accept unbounded JSON payloads (`blueprints/backup.py:32-55`)
- **Category**: Security
- **Description**: No `MAX_CONTENT_LENGTH` configured. Backup files with base64 images can be very large, creating a denial-of-service vector.

### M5. Overly broad `except Exception` in health check (`blueprints/core.py:21`)
- **Category**: Quality
- **Description**: Catches all exceptions including `AttributeError`/`TypeError`. Should narrow to `sqlite3.Error` or `OSError`.

### M6. Proxy endpoint as potential SSRF vector (`blueprints/proxy.py:12`)
- **Category**: Security
- **Description**: URL parameter passed directly to service. If domain whitelist is bypassable (DNS rebinding, open redirects), this becomes SSRF.

### M7. `estimate_protein_quality` missing error handling (`blueprints/protein_quality.py:50-60`)
- **Category**: Bug
- **Description**: The `estimate` service call is not wrapped in try/except unlike every other service call in that file. `ValueError` results in a raw 500 instead of a clean 400 JSON response.

### M8. `_num` and `_safe_float` are near-duplicates (`helpers.py:19-39`)
- **Category**: Maintainability
- **Description**: Both functions convert to float with finite check. `_num` handles `None`/empty string, `_safe_float` does not. Could be consolidated.

### M9. `init_db` uses bare string concatenation for ALTER TABLE (`db.py`)
- **Category**: Maintainability
- **Description**: Schema migration logic uses string formatting for column names in ALTER TABLE statements. While the values come from config (not user input), this pattern is fragile.

### M10. No `__all__` exports in any module
- **Category**: Style
- **Description**: No module defines `__all__`, making the public API implicit. This affects tooling support and `from module import *` behavior.

### M11. Inconsistent exception chaining (`services/off_service.py`, `services/proxy_service.py`)
- **Category**: Quality
- **Description**: `RuntimeError` is raised without `from e`, losing the original traceback. Should use `raise RuntimeError("msg") from e`.

### M12. `score_product` has deeply nested conditionals (`services/product_service.py`)
- **Category**: Maintainability
- **Description**: The scoring logic has multiple levels of nesting making it hard to follow and test.

### M13. `http://` URLs accepted but not upgraded to HTTPS (`services/proxy_service.py:20`)
- **Category**: Security
- **Description**: Proxy accepts both HTTP and HTTPS schemes. Since it fetches from openfoodfacts.org, allowing plaintext HTTP exposes request metadata.

### M14. Missing input validation on URL path parameters (`blueprints/categories.py:32, 44`)
- **Category**: Quality
- **Description**: `update_category` and `delete_category` accept `<name>` from URL path without length/character validation. `_validate_category_name` exists but isn't used here.

### M15. Dense chained `or` expression (`blueprints/categories.py:49`)
- **Category**: Style
- **Description**: `(body.get("move_to") or "").strip() or None` doesn't handle non-string types that valid JSON could produce (e.g., integer for `move_to`).

### M16. Unused logger in several modules
- **Category**: Quality
- **Description**: Some modules define `logger = logging.getLogger(__name__)` but never use it, or use `print()` instead.

---

## Low Severity Issues

| # | File | Issue | Category |
|---|------|-------|----------|
| L1 | `blueprints/__init__.py` | Missing type hint on `register_blueprints(app)` | Style |
| L2 | `blueprints/core.py` | Health check bypasses service layer (direct DB query) | Maintainability |
| L3 | All blueprints | Route handlers lack docstrings | Style |
| L4 | `blueprints/off.py:16` | Line exceeds 79 characters | Style |
| L5 | `blueprints/settings.py:45-49` | `off_user_id` has no length validation | Quality |
| L6 | `blueprints/settings.py:6` | Importing private `_MAX_PASSWORD_LEN` from config | Style |
| L7 | `config.py` | Magic numbers in score config without explanation | Maintainability |
| L8 | `config.py` | Long lines in SQL fragment constants | Style |
| L9 | `db.py` | `close_db` exception parameter unused | Quality |
| L10 | `exceptions.py` | Single custom exception -- could add more for clarity | Maintainability |
| L11-L53 | Various | Minor PEP 8 spacing, missing type hints, inconsistent string quotes | Style |

---

## Positive Highlights

1. **Exemplary blueprint-service separation** -- Blueprints are genuinely thin: parse request, call service, return JSON.
2. **Consistent error response contract** -- Every error returns `{"error": "message"}` with appropriate HTTP status. Exception-to-status mapping (`ValueError`->400, `LookupError`->404, `ConflictError`->409, `RuntimeError`->502) is applied consistently.
3. **Centralized `_require_json()` helper** -- Eliminates scattered `request.get_json()` with inconsistent error handling.
4. **Type-safe route parameters** -- Product IDs use `<int:pid>`, providing automatic 404 on non-integer values.
5. **Correct logging style** -- `logging.getLogger(__name__)` and `%s`-style formatting (not f-strings).
6. **Module docstrings on every file** -- Every Python file has a clear, concise module docstring.
7. **Clean import organization** -- All files follow PEP 8 import ordering with proper grouping.
8. **Parameterized queries throughout** -- No SQL injection vectors found in any service file.
9. **Config-driven architecture** -- Nutrition fields, valid columns, and score config are centralized in `config.py`.

---

## Prioritized Recommendations

| Priority | Action | Issues |
|----------|--------|--------|
| **1 - Critical** | Require `SMARTSNACK_SECRET_KEY` env var, fail if missing | H1 |
| **2 - Critical** | Fix CORS origin -- don't derive from user headers | H2 |
| **3 - Critical** | Add authentication for backup and credentials endpoints | H3, H4 |
| **4 - Important** | Use `LOCK_EX` for write operations in translations.py | H5 |
| **5 - Important** | Return 404 from `update_product` when product not found | M3 |
| **6 - Important** | Add try/except to `estimate_protein_quality` | M7 |
| **7 - Important** | Configure `MAX_CONTENT_LENGTH` | M4 |
| **8 - Improve** | Make translation restore atomic (write to temp files first) | M1 |
| **9 - Improve** | Re-encrypt legacy XOR passwords on read | M2 |
| **10 - Improve** | Narrow exception types, add exception chaining | M5, M11 |
| **11 - Polish** | Consolidate `_num`/`_safe_float`, add docstrings | M8, L3 |
| **12 - Polish** | Add `__all__`, type hints, fix line lengths | M10, L1-L53 |
