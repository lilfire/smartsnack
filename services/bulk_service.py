"""Service for bulk operations: refresh from OFF, estimate PQ for all products."""

import base64
import io
import logging
import re
import sqlite3
import threading
import time

from config import DB_PATH, _VALID_COLUMNS
from db import get_db
from services import proxy_service, protein_quality_service
from services.settings_service import get_off_language_priority

logger = logging.getLogger(__name__)


def _build_update_sql(field_updates: dict) -> tuple[str, list]:
    """Build a safe SET clause for UPDATE, validating all field names.

    Raises ValueError if any field name is not in the column whitelist.
    Returns (set_clause_string, ordered_values_list).
    """
    for f in field_updates:
        if f not in _VALID_COLUMNS:
            raise ValueError(f"Invalid column name in update: {f!r}")
    set_clauses = [f"{f} = ?" for f in field_updates]
    return ", ".join(set_clauses), list(field_updates.values())


# ── In-memory refresh job state ──────────────────────
_refresh_job = {
    "running": False,
    "current": 0,
    "total": 0,
    "name": "",
    "ean": "",
    "status": "",
    "updated": 0,
    "skipped": 0,
    "errors": 0,
    "done": False,
}
_refresh_lock = threading.Lock()


def _set_off_sync_flag(conn, pid):
    """Mark a product as synced with OFF in the product_flags table."""
    conn.execute(
        "INSERT OR IGNORE INTO product_flags (product_id, flag) VALUES (?, ?)",
        (pid, "is_synced_with_off"),
    )
    conn.commit()


def _parse_off_nutriment(nutriments, key):
    """Extract a nutriment value from OFF data, preferring per-100g."""
    val = nutriments.get(f"{key}_100g")
    if val is None:
        val = nutriments.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _should_update(off_val, local_val):
    """Return True if we should overwrite the local value with the OFF value.

    Overwrite unless OFF value is empty/zero and local already has a value.
    """
    if off_val is None:
        return False
    if isinstance(off_val, str):
        if not off_val.strip():
            return False
    elif isinstance(off_val, (int, float)):
        if (
            off_val == 0
            and local_val is not None
            and local_val != ""
            and local_val != 0
        ):
            return False
    return True


def _map_off_product(product, local_row, priority=None):
    """Map OFF product data to local DB fields. Returns dict of fields to update.

    ``priority`` is the user's OFF language priority list.  Only the **first**
    (top) language is checked for name and ingredients – if the #1 language
    has no data the field is left unchanged so we don't overwrite with a
    less-preferred language.
    """
    updates = {}
    top_lang = (priority[0] if priority else "no")
    n = product.get("nutriments") or {}

    # Nutrition fields
    nutrition_map = {
        "kcal": "energy-kcal",
        "energy_kj": "energy-kj",
        "fat": "fat",
        "saturated_fat": "saturated-fat",
        "carbs": "carbohydrates",
        "sugar": "sugars",
        "protein": "proteins",
        "fiber": "fiber",
        "salt": "salt",
    }
    for local_field, off_key in nutrition_map.items():
        off_val = _parse_off_nutriment(n, off_key)
        if _should_update(off_val, local_row.get(local_field)):
            if local_field in ("kcal", "energy_kj"):
                updates[local_field] = round(off_val)
            elif local_field == "salt":
                updates[local_field] = round(off_val, 2)
            else:
                updates[local_field] = round(off_val, 1)

    # Name – only use the #1 priority language
    name = (product.get(f"product_name_{top_lang}") or "").strip()
    if name and _should_update(name, local_row.get("name")):
        updates["name"] = name

    # Brand
    brand = product.get("brands") or ""
    if _should_update(brand, local_row.get("brand")):
        updates["brand"] = brand.strip()

    # Stores
    stores = product.get("stores") or ""
    if not stores and product.get("stores_tags"):
        tags = product["stores_tags"]
        if isinstance(tags, list) and tags:
            stores = ", ".join(t.replace("-", " ").title() for t in tags)
    if _should_update(stores, local_row.get("stores")):
        updates["stores"] = stores.strip()

    # Ingredients – only use the #1 priority language
    ing = (product.get(f"ingredients_text_{top_lang}") or "").strip()
    if ing and _should_update(ing, local_row.get("ingredients")):
        updates["ingredients"] = ing

    # Weight (product_quantity)
    qty = product.get("product_quantity")
    if qty:
        try:
            w = round(float(qty))
            if _should_update(w, local_row.get("weight")):
                updates["weight"] = w
        except (ValueError, TypeError):
            pass

    # Portion (serving_size)
    serving = product.get("serving_size") or ""
    m = re.search(r"([\d.]+)\s*g", serving)
    if m:
        try:
            p = round(float(m.group(1)))
            if _should_update(p, local_row.get("portion")):
                updates["portion"] = p
        except (ValueError, TypeError):
            pass

    return updates


def _fetch_off_image(product):
    """Fetch and resize product image from OFF. Returns base64 data URI or None."""
    img_url = (
        product.get("image_front_url")
        or product.get("image_url")
        or product.get("image_front_small_url")
        or ""
    )
    if not img_url:
        return None
    try:
        img_data, content_type = proxy_service.proxy_image(img_url)
        # Resize to max 400px using PIL if available
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(img_data))
            max_dim = 400
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                buf = io.BytesIO()
                fmt = "JPEG" if "jpeg" in content_type else "PNG"
                img.save(buf, format=fmt, quality=85)
                img_data = buf.getvalue()
                if fmt == "JPEG":
                    content_type = "image/jpeg"
                else:
                    content_type = "image/png"
        except Exception:
            pass  # PIL not available or image can't be processed, use original size

        b64 = base64.b64encode(img_data).decode("ascii")
        mime = content_type.split(";")[0].strip()
        data_uri = f"data:{mime};base64,{b64}"
        # Check size limit (2 MB)
        if len(data_uri) > 2 * 1024 * 1024:
            return None
        return data_uri
    except Exception as e:
        logger.debug("Failed to fetch image for product: %s", e)
        return None


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
    with _refresh_lock:
        snapshot = dict(_refresh_job)
    if not snapshot.get("done"):
        snapshot.pop("report", None)
    return snapshot


def start_refresh_from_off(options=None):
    """Start refresh in a background thread. Returns False if already running."""
    with _refresh_lock:
        if _refresh_job["running"]:
            return False
        _refresh_job.update(
            running=True,
            current=0,
            total=0,
            name="",
            ean="",
            status="",
            updated=0,
            skipped=0,
            errors=0,
            done=False,
        )
        _refresh_job.pop("report", None)
    t = threading.Thread(target=_run_refresh, args=(options or {},), daemon=True)
    t.start()
    return True


def _run_refresh(options=None):
    """Background thread that refreshes all products from OFF."""
    try:
        priority = get_off_language_priority()
    except RuntimeError:
        priority = ["no", "en"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")

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

        with _refresh_lock:
            _refresh_job["total"] = total

        for i, row in enumerate(rows):
            ean = row["ean"]
            pid = row["id"]
            name = row["name"] or ""
            has_image = bool(row["image"])

            with _refresh_lock:
                _refresh_job.update(
                    current=i + 1,
                    ean=ean,
                    name=name,
                    status="fetching",
                )

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
                    with _refresh_lock:
                        _refresh_job.update(status="error", errors=errors)
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
                    with _refresh_lock:
                        _refresh_job.update(status="skipped", skipped=skipped)
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
                    with _refresh_lock:
                        _refresh_job.update(status="skipped", skipped=skipped)
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

                with _refresh_lock:
                    _refresh_job.update(status="updated", updated=updated)

            except Exception as e:
                logger.error("Error refreshing product %s (EAN %s): %s", pid, ean, e)
                errors += 1
                report.append(
                    {"name": name, "ean": ean, "status": "error", "reason": str(e)}
                )
                with _refresh_lock:
                    _refresh_job.update(status="error", errors=errors)

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
            with _refresh_lock:
                _refresh_job["total"] = total + phase2_total

            for i, row in enumerate(missing_rows):
                pid = row["id"]
                name = row["name"] or ""

                with _refresh_lock:
                    _refresh_job.update(
                        current=total + i + 1,
                        ean="",
                        name=name,
                        status="searching",
                    )

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
                        with _refresh_lock:
                            _refresh_job.update(status="skipped", skipped=skipped)
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
                        with _refresh_lock:
                            _refresh_job.update(status="skipped", skipped=skipped)
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
                    with _refresh_lock:
                        _refresh_job.update(status="updated", updated=updated)

                except Exception as e:
                    logger.error("Error searching product %s (%s): %s", pid, name, e)
                    errors += 1
                    report.append(
                        {"name": name, "ean": "", "status": "error", "reason": str(e)}
                    )
                    with _refresh_lock:
                        _refresh_job.update(status="error", errors=errors)

                time.sleep(1.0)

        with _refresh_lock:
            _refresh_job.update(
                done=True,
                running=False,
                updated=updated,
                skipped=skipped,
                errors=errors,
                report=report,
            )
    except Exception as e:
        logger.error("Refresh thread crashed: %s", e, exc_info=True)
        with _refresh_lock:
            _refresh_job.update(done=True, running=False)
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
