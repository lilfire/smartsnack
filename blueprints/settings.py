from flask import Blueprint, jsonify

from helpers import _require_json
from services import settings_service

bp = Blueprint("settings", __name__)


@bp.route("/api/settings/language")
def get_language():
    lang = settings_service.get_language()
    return jsonify({"language": lang})


@bp.route("/api/settings/language", methods=["PUT"])
def set_language():
    data = _require_json()
    if not data or "language" not in data:
        return jsonify({"error": "language is required"}), 400
    try:
        lang = settings_service.set_language(data["language"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "language": lang})
