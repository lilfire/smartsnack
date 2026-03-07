import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, Response

from helpers import _require_json
from services import backup_service

bp = Blueprint("backup", __name__)


@bp.route("/api/backup")
def backup_db():
    payload = backup_service.create_backup()
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        json_str, mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=smartsnack_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"},
    )


@bp.route("/api/restore", methods=["POST"])
def restore_db():
    data = _require_json()
    try:
        message = backup_service.restore_backup(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Restore failed"}), 500
    return jsonify({"message": message})


@bp.route("/api/import", methods=["POST"])
def import_products():
    data = _require_json()
    try:
        message = backup_service.import_products(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Import failed"}), 500
    return jsonify({"message": message})
