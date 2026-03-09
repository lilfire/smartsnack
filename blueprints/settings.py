"""Blueprint for user settings (language, OFF credentials)."""

from flask import Blueprint, jsonify

from helpers import _require_json, _check_api_key
from config import _MAX_PASSWORD_LEN
from services import settings_service

bp = Blueprint("settings", __name__)


@bp.route("/api/settings/language")
def get_language():
    lang = settings_service.get_language()
    return jsonify({"language": lang})


@bp.route("/api/settings/language", methods=["PUT"])
def set_language():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if "language" not in data:
        return jsonify({"error": "language is required"}), 400
    try:
        lang = settings_service.set_language(data["language"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "language": lang})


@bp.route("/api/settings/off-credentials")
def get_off_credentials():
    denied = _check_api_key()
    if denied:
        return denied
    creds = settings_service.get_off_credentials()
    return jsonify({"off_user_id": creds["off_user_id"], "has_password": bool(creds["off_password"])})


@bp.route("/api/settings/off-credentials", methods=["PUT"])
def set_off_credentials():
    denied = _check_api_key()
    if denied:
        return denied
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    user_id = data.get("off_user_id", "").strip()
    password = data.get("off_password", "")
    if len(password) > _MAX_PASSWORD_LEN:
        return jsonify({"error": "Password too long"}), 400
    try:
        settings_service.set_off_credentials(user_id, password)
    except RuntimeError:
        return jsonify({"error": "encryption_not_configured"}), 500
    return jsonify({"ok": True})
