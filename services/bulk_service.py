"""Service for bulk operations: refresh from OFF, estimate PQ for all products."""

import logging
import sqlite3
import threading
import time

from config import DB_PATH
from db import get_db
from services import bulk_refresh_state, proxy_service, protein_quality_service

# Re-exported so call sites and test patches on this module keep working.
from services.bulk_off_mapping import (  # noqa: F401
    _build_update_sql,
    _fetch_off_image,
    _map_off_product,
    _parse_off_nutriment,
    _should_update,
)
from services.settings_service import get_off_language_priority

logger = logging.getLogger(__name__)


# Refresh job state is DB-backed for cross-worker visibility: see
# services/bulk_refresh_state.py.
def _open_worker_connection():
    """Open the dedicated SQLite connection for the refresh worker thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _set_off_sync_flag(conn, pid):
    """Mark a product as synced with OFF in the product_flags table."""
    conn.execute(
        "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
        (pid, "is_synced_with_off"),
    )
    conn.commit()


def refresh_from_off():
    """Refresh all products with EAN from OpenFoodFacts."""
    try:
        priority = get_off_language_priority()
    except RuntimeError:
        priority = ["no", "en"]
    conn = get_db()
    rows = conn.execute(
        "SELECT p.id, pe.ean, p.name, p.brand, p.stores, p.ingredients, p.kcal, p.energy_kj, "
        "p.fat, p.saturated_fat, p.carbs, p.sugar, p.protein, p.fiber, p.salt, "
        "p.weight, p.portion, p.image "
        "FROM products p "
        "INNER JOIN product_eans pe ON pe.product_id = p.id AND pe.is_primary = 1"
    ).fetchall()

    total = len(rows)
    updated = 0
    skipped = 0
    errors = []

    for row in rows:
        ean = row["ean"]
        pid = row["id"]
        try:
            # Retry with backoff for transient API errors
            data = None
            last_err = None
            for attempt in range(3):
                try:
                    data = proxy_service.off_product(ean)
                    break
                except RuntimeError as e:
                    last_err = e
                    time.sleep(2 * (attempt + 1))

            if data is None:
                errors.append({"id": pid, "ean": ean, "error": str(last_err)})
                time.sleep(1)
                continue

            if not data.get("product"):
                skipped += 1
                continue

            product = data["product"]
            local = dict(row)
            field_updates = _map_off_product(product, local, priority)

            # Fetch image only if product doesn't already have one
            has_image = bool(row["image"])
            image_uri = _fetch_off_image(product) if not has_image else None

            if not field_updates and not image_uri:
                skipped += 1
                _set_off_sync_flag(conn, pid)
                continue

            # Update product fields
            if field_updates:
                set_clause, vals = _build_update_sql(field_updates)
                conn.execute(
                    f"UPDATE products SET {set_clause} WHERE id = ?",
                    vals + [pid],
                )

            # Update image separately
            if image_uri:
                conn.execute(
                    "UPDATE products SET image = ? WHERE id = ?",
                    (image_uri, pid),
                )

            conn.commit()
            updated += 1
            _set_off_sync_flag(conn, pid)

        except Exception as e:
            logger.error("Error refreshing product %s (EAN %s): %s", pid, ean, e)
            errors.append({"id": pid, "ean": ean, "error": str(e)})

        # Be respectful to the OFF API
        time.sleep(1)

    return {
        "total": total,
        "updated": updated,
        "skipped": skipped,
        "errors": len(errors),
        "error_details": errors[:10],  # Limit detail output
    }


def get_refresh_status():
    """Return a snapshot of the current refresh job state."""
    snapshot = bulk_refresh_state.read_job()
    if not snapshot.get("done"):
        snapshot.pop("report", None)
    return snapshot


def start_refresh_from_off(options=None):
    """Start refresh in a background thread. Returns False if already running.

    The language priority is read here, in Flask request context, and passed
    to the worker thread — get_off_language_priority() needs app context and
    would fail inside the thread.
    """
    priority = get_off_language_priority()
    if not bulk_refresh_state.try_acquire():
        return False
    t = threading.Thread(
        target=_run_refresh, args=(priority, options or {}), daemon=True
    )
    t.start()
    return True


def _run_refresh(priority, options=None):
    """Background thread that refreshes all products from OFF."""
    conn = _open_worker_connection()

    try:
        rows = conn.execute(
            "SELECT p.id, pe.ean, p.name, p.brand, p.stores, p.ingredients, p.kcal, p.energy_kj, "
            "p.fat, p.saturated_fat, p.carbs, p.sugar, p.protein, p.fiber, p.salt, "
            "p.weight, p.portion, p.image "
            "FROM products p "
            "INNER JOIN product_eans pe ON pe.product_id = p.id AND pe.is_primary = 1"
        ).fetchall()

        total = len(rows)
        updated = 0
        skipped = 0
        errors = 0
        report = []

        bulk_refresh_state.update_job(total=total)

        for i, row in enumerate(rows):
            ean = row["ean"]
            pid = row["id"]
            name = row["name"] or ""
            has_image = bool(row["image"])

            bulk_refresh_state.update_job(current=i + 1, ean=ean, name=name, status="fetching")

            try:
                # Retry with backoff for transient API errors
                data = None
                last_err = None
                for attempt in range(3):
                    try:
                        data = proxy_service.off_product(ean)
                        break
                    except RuntimeError as e:
                        last_err = e
                        logger.warning(
                            "OFF API attempt %d/3 failed for EAN %s: %s",
                            attempt + 1, ean, e,
                        )
                        time.sleep(2 * (attempt + 1))  # 2s, 4s backoff

                if data is None:
                    errors += 1
                    report.append(
                        {
                            "name": name,
                            "ean": ean,
                            "status": "error",
                            "reason": str(last_err),
                        }
                    )
                    bulk_refresh_state.update_job(status="error", errors=errors)
                    time.sleep(1)
                    continue

                if not data.get("product"):
                    skipped += 1
                    report.append(
                        {
                            "name": name,
                            "ean": ean,
                            "status": "skipped",
                            "reason": "not_found",
                        }
                    )
                    bulk_refresh_state.update_job(status="skipped", skipped=skipped)
                    time.sleep(1)
                    continue

                product = data["product"]
                local = dict(row)
                field_updates = _map_off_product(product, local, priority)
                image_uri = _fetch_off_image(product) if not has_image else None

                if not field_updates and not image_uri:
                    skipped += 1
                    report.append(
                        {
                            "name": name,
                            "ean": ean,
                            "status": "skipped",
                            "reason": "no_new_data",
                        }
                    )
                    _set_off_sync_flag(conn, pid)
                    bulk_refresh_state.update_job(status="skipped", skipped=skipped)
                    time.sleep(1)
                    continue

                if field_updates:
                    set_clause, vals = _build_update_sql(field_updates)
                    conn.execute(
                        f"UPDATE products SET {set_clause} WHERE id = ?",
                        vals + [pid],
                    )

                if image_uri:
                    conn.execute(
                        "UPDATE products SET image = ? WHERE id = ?",
                        (image_uri, pid),
                    )

                conn.commit()
                updated += 1
                _set_off_sync_flag(conn, pid)
                updated_fields = list(field_updates.keys())
                if image_uri:
                    updated_fields.append("image")
                report.append(
                    {
                        "name": name,
                        "ean": ean,
                        "status": "updated",
                        "fields": updated_fields,
                    }
                )

                bulk_refresh_state.update_job(status="updated", updated=updated)

            except Exception as e:
                conn.rollback()  # discard any partial writes for this product
                logger.error("Error refreshing product %s (EAN %s): %s", pid, ean, e)
                errors += 1
                report.append(
                    {"name": name, "ean": ean, "status": "error", "reason": str(e)}
                )
                bulk_refresh_state.update_job(status="error", errors=errors)

            time.sleep(1)

        # Phase 2: Search by name for products without EAN
        if options and options.get("search_missing"):
            min_certainty = options.get("min_certainty", 100)
            min_completeness = options.get("min_completeness", 75)

            missing_rows = conn.execute(
                "SELECT p.id, p.name, p.brand, p.stores, p.ingredients, p.kcal, p.energy_kj, "
                "p.fat, p.saturated_fat, p.carbs, p.sugar, p.protein, p.fiber, p.salt, "
                "p.weight, p.portion, p.image "
                "FROM products p "
                "WHERE NOT EXISTS (SELECT 1 FROM product_eans pe WHERE pe.product_id = p.id) "
                "AND p.name IS NOT NULL AND p.name != ''"
            ).fetchall()

            phase2_total = len(missing_rows)
            bulk_refresh_state.update_job(total=total + phase2_total)

            for i, row in enumerate(missing_rows):
                pid = row["id"]
                name = row["name"] or ""

                bulk_refresh_state.update_job(current=total + i + 1, ean="", name=name, status="searching")

                try:
                    nutrition = {}
                    for field in (
                        "kcal",
                        "fat",
                        "saturated_fat",
                        "carbs",
                        "sugar",
                        "protein",
                        "fiber",
                        "salt",
                    ):
                        val = row[field]
                        if val is not None:
                            nutrition[field] = float(val)

                    result = proxy_service.off_search(
                        name, nutrition if nutrition else None
                    )
                    products = result.get("products") or []

                    best = None
                    best_comp = -1
                    best_cert = -1
                    for p in products:
                        cert = p.get("certainty", 0)
                        comp = float(p.get("completeness") or 0) * 100
                        if cert < min_certainty or comp < min_completeness:
                            continue
                        if best is None:
                            best = p
                            best_comp = comp
                            best_cert = cert
                        elif cert == best_cert and comp > best_comp:
                            best = p
                            best_comp = comp
                        elif cert < best_cert:
                            break  # sorted by certainty desc, no better match

                    if not best:
                        skipped += 1
                        if not products:
                            report.append(
                                {
                                    "name": name,
                                    "ean": "",
                                    "status": "skipped",
                                    "reason": "no_results",
                                }
                            )
                        else:
                            top = products[0]
                            top_cert = top.get("certainty", 0)
                            top_comp = round(float(top.get("completeness") or 0) * 100)
                            report.append(
                                {
                                    "name": name,
                                    "ean": "",
                                    "status": "skipped",
                                    "reason": "below_threshold",
                                    "detail": f"best: {top_cert}% cert, {top_comp}% comp",
                                }
                            )
                        bulk_refresh_state.update_job(status="skipped", skipped=skipped)
                        time.sleep(1.0)
                        continue

                    local = dict(row)
                    field_updates = _map_off_product(best, local, priority)
                    has_image = bool(row["image"])
                    image_uri = _fetch_off_image(best) if not has_image else None

                    # Store matched EAN into product_eans (not products.ean)
                    matched_ean = best.get("code", "")

                    if not field_updates and not image_uri and not matched_ean:
                        skipped += 1
                        report.append(
                            {
                                "name": name,
                                "ean": "",
                                "status": "skipped",
                                "reason": "no_new_data",
                            }
                        )
                        _set_off_sync_flag(conn, pid)
                        bulk_refresh_state.update_job(status="skipped", skipped=skipped)
                        time.sleep(1.0)
                        continue

                    if field_updates:
                        set_clause, vals = _build_update_sql(field_updates)
                        conn.execute(
                            f"UPDATE products SET {set_clause} WHERE id = ?",
                            vals + [pid],
                        )

                    if matched_ean:
                        conn.execute(
                            "INSERT OR IGNORE INTO product_eans (product_id, ean, is_primary) VALUES (?, ?, 1)",
                            (pid, matched_ean),
                        )

                    if image_uri:
                        conn.execute(
                            "UPDATE products SET image = ? WHERE id = ?",
                            (image_uri, pid),
                        )

                    conn.commit()
                    updated += 1
                    _set_off_sync_flag(conn, pid)
                    updated_fields = list(field_updates.keys())
                    if matched_ean:
                        updated_fields.append("ean")
                    if image_uri:
                        updated_fields.append("image")
                    report.append(
                        {
                            "name": name,
                            "ean": matched_ean or "",
                            "status": "updated",
                            "fields": updated_fields,
                        }
                    )
                    bulk_refresh_state.update_job(status="updated", updated=updated)

                except Exception as e:
                    conn.rollback()  # discard any partial writes for this product
                    logger.error("Error searching product %s (%s): %s", pid, name, e)
                    errors += 1
                    report.append(
                        {"name": name, "ean": "", "status": "error", "reason": str(e)}
                    )
                    bulk_refresh_state.update_job(status="error", errors=errors)

                time.sleep(1.0)

        bulk_refresh_state.update_job(
            done=True,
            running=False,
            updated=updated,
            skipped=skipped,
            errors=errors,
            report=report,
        )
    except Exception as e:
        logger.error("Refresh thread crashed: %s", e, exc_info=True)
        bulk_refresh_state.update_job(done=True, running=False)
    finally:
        conn.close()


def estimate_all_pq():
    """Estimate protein quality for all products with ingredients."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, ingredients FROM products "
        "WHERE ingredients IS NOT NULL AND ingredients != ''"
    ).fetchall()

    total = len(rows)
    updated = 0
    skipped = 0

    for row in rows:
        result = protein_quality_service.estimate(row["ingredients"])
        pdcaas = result.get("est_pdcaas")
        diaas = result.get("est_diaas")

        if pdcaas is None and diaas is None:
            skipped += 1
            continue

        conn.execute(
            "UPDATE products SET est_pdcaas = ?, est_diaas = ? WHERE id = ?",
            (pdcaas, diaas, row["id"]),
        )
        updated += 1

    conn.commit()
    return {"total": total, "updated": updated, "skipped": skipped}
