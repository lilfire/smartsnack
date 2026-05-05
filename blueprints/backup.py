"""Blueprint for backup, restore, and import endpoints."""

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, Response

from extensions import limiter
from helpers import _require_json, _check_api_key
from services import backup_core, import_service

logger = logging.getLogger(__name__)

bp = Blueprint("backup", __name__)


@bp.route("/api/backup")
@limiter.limit("5 per minute")
def backup_db():
    denied = _check_api_key()
    if denied:
        return denied
    include_images = request.args.get("images", "true").lower() == "true"
    payload = backup_core.create_backup(include_images=include_images)
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(
        json_str,
        mimetype="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=smartsnack_backup_{timestamp}.json"
        },
    )


@bp.route("/api/restore", methods=["POST"])
@limiter.limit("5 per minute")
def restore_db():
    denied = _check_api_key()
    if denied:
        return denied
    try:
        data = _require_json()
        message = backup_core.restore_backup(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (OSError, RuntimeError):
        logger.exception("Restore failed")
        return jsonify({"error": "Restore failed"}), 500
    return jsonify({"ok": True, "message": message})


@bp.route("/api/import", methods=["POST"])
@limiter.limit("5 per minute")
def import_products():
    denied = _check_api_key()
    if denied:
        return denied
    try:
        data = _require_json()
        match_criteria = data.pop("match_criteria", "both")
        on_duplicate = data.pop("on_duplicate", "skip")
        merge_priority = data.pop("merge_priority", "keep_existing")
        message = import_service.import_products(
            data,
            match_criteria=match_criteria,
            on_duplicate=on_duplicate,
            merge_priority=merge_priority,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (OSError, RuntimeError):
        logger.exception("Import failed")
        return jsonify({"error": "Import failed"}), 500
    return jsonify({"ok": True, "message": message})
