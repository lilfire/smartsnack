"""Service for managing protein quality entries and ingredient estimation."""

import re
import sqlite3

from db import get_db
from config import _PQ_MAX_LABEL_LEN
from exceptions import ConflictError
from helpers import _safe_float, _validate_keywords
from translations import (
    _pq_label,
    _pq_keywords,
    _pq_all_keywords,
    _get_current_lang,
    _set_translation_key,
    _delete_translation_key,
)


def list_entries() -> list:
    """Return all protein quality entries with labels and keywords."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, pdcaas, diaas FROM protein_quality ORDER BY id"
    ).fetchall()
    result = []
    for r in rows:
        keywords = _pq_keywords(r["name"])
        result.append(
            {
                "id": r["id"],
                "name": r["name"],
                "keywords": keywords,
                "pdcaas": r["pdcaas"],
                "diaas": r["diaas"],
                "label": _pq_label(r["name"]),
            }
        )
    return result


def add_entry(data: dict) -> dict:
    """Add a new protein quality entry."""
    name = data.get("name", "").strip()
    keywords = data.get("keywords", [])
    pdcaas = data.get("pdcaas")
    diaas = data.get("diaas")
    label = data.get("label", "").strip()
    if not name:
        name = label or (keywords[0] if keywords else "")
    if not name or not keywords or pdcaas is None or diaas is None:
        raise ValueError("keywords, pdcaas and diaas are required")
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")
    if not name:
        raise ValueError("Invalid name")
    validated_kws, kw_err = _validate_keywords(keywords)
    if kw_err or validated_kws is None:
        raise ValueError(kw_err or "Invalid keywords")
    keywords = validated_kws
    if isinstance(label, str) and len(label) > _PQ_MAX_LABEL_LEN:
        raise ValueError(f"label exceeds max length of {_PQ_MAX_LABEL_LEN}")
    pdcaas_f = _safe_float(pdcaas, "pdcaas")
    diaas_f = _safe_float(diaas, "diaas")
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO protein_quality (name, pdcaas, diaas) VALUES (?,?,?)",
            (name, pdcaas_f, diaas_f),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ConflictError(
            "Protein quality entry with this name already exists"
        ) from None
    new_id = cur.lastrowid
    lang = _get_current_lang()
    if label:
        _set_translation_key(f"pq_{name}_label", {lang: label})
    kw_str = ", ".join(keywords)
    _set_translation_key(f"pq_{name}_keywords", {lang: kw_str})
    return {"ok": True, "id": new_id, "name": name}


def update_entry(pid, data):
    conn = get_db()
    existing = conn.execute(
        "SELECT id, name FROM protein_quality WHERE id=?", (pid,)
    ).fetchone()
    if not existing:
        raise LookupError("Not found")
    pq_name = existing["name"]
    lang = _get_current_lang()
    updates = []
    params = []
    for field in ("pdcaas", "diaas"):
        if field in data:
            updates.append(f"{field}=?")
            params.append(_safe_float(data[field], field))
    if updates:
        params.append(pid)
        conn.execute(
            f"UPDATE protein_quality SET {','.join(updates)} WHERE id=?", params
        )
        conn.commit()
    if "keywords" in data:
        kws, kw_err = _validate_keywords(data["keywords"])
        if kw_err:
            raise ValueError(kw_err)
        _set_translation_key(f"pq_{pq_name}_keywords", {lang: ", ".join(kws)})
    if "label" in data:
        label = data["label"].strip()
        if len(label) > _PQ_MAX_LABEL_LEN:
            raise ValueError(f"label exceeds max length of {_PQ_MAX_LABEL_LEN}")
        _set_translation_key(f"pq_{pq_name}_label", {lang: label})


def delete_entry(pid):
    conn = get_db()
    existing = conn.execute(
        "SELECT name FROM protein_quality WHERE id=?", (pid,)
    ).fetchone()
    if not existing:
        raise LookupError("Not found")
    pq_name = existing["name"]
    conn.execute("DELETE FROM protein_quality WHERE id=?", (pid,))
    conn.commit()
    _delete_translation_key(f"pq_{pq_name}_label")
    _delete_translation_key(f"pq_{pq_name}_keywords")


def _load_protein_quality_table() -> list:
    """Load PQ table with pre-compiled keyword regex patterns."""
    conn = get_db()
    rows = conn.execute(
        "SELECT name, pdcaas, diaas FROM protein_quality ORDER BY id"
    ).fetchall()
    table = []
    for r in rows:
        keywords = _pq_all_keywords(r["name"])
        patterns = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in keywords]
        table.append((r["name"], patterns, r["pdcaas"], r["diaas"]))
    return table


def estimate(ingredients: str) -> dict:
    """Estimate protein quality scores from an ingredients string."""
    if not ingredients:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}

    text = ingredients.lower()
    tokens_raw = re.split(r"[,;()\[\]\/\\|•\n]+", text)
    tokens = [t.strip() for t in tokens_raw if t.strip()]

    pq_table = _load_protein_quality_table()
    matched = []
    for pos, token in enumerate(tokens):
        for pq_name, patterns, pdcaas, diaas in pq_table:
            for pattern in patterns:
                if pattern.search(token):
                    matched.append((pos, pdcaas, diaas, pq_name))
                    break

    if not matched:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}

    seen = set()
    deduped = []
    for pos, pdcaas, diaas, pq_name in matched:
        key = (round(pdcaas, 2), round(diaas, 2))
        if key not in seen:
            seen.add(key)
            deduped.append((pos, pdcaas, diaas, pq_name))

    total_w = sum(1.0 / (pos + 1) for pos, *_ in deduped)
    if total_w == 0:
        return {"est_pdcaas": None, "est_diaas": None, "sources": []}
    w_pdcaas = (
        sum((1.0 / (pos + 1)) * pdcaas for pos, pdcaas, diaas, _ in deduped) / total_w
    )
    w_diaas = (
        sum((1.0 / (pos + 1)) * diaas for pos, pdcaas, diaas, _ in deduped) / total_w
    )

    return {
        "est_pdcaas": round(min(w_pdcaas, 1.0), 3),
        "est_diaas": round(min(w_diaas, 1.2), 3),
        "sources": [_pq_label(pq_name) for _, _, _, pq_name in deduped],
    }
