"""Blueprint for user settings (language, OFF credentials)."""

from flask import Blueprint, jsonify

from helpers import _require_json, _check_api_key
from config import _MAX_PASSWORD_LEN, OFF_SUPPORTED_LANGUAGES
from services import settings_service, ocr_service

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
    return jsonify(
        {
            "off_user_id": creds["off_user_id"],
            "has_password": bool(creds["off_password"]),
        }
    )


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


@bp.route("/api/settings/ocr")
def get_ocr_settings():
    current = settings_service.get_ocr_backend()
    backends = ocr_service.get_available_backends()
    return jsonify({"current_backend": current, "available_backends": backends})


@bp.route("/api/settings/off-languages")
def get_off_languages():
    return jsonify({"languages": OFF_SUPPORTED_LANGUAGES})


@bp.route("/api/settings/off-language-priority")
def get_off_language_priority():
    priority = settings_service.get_off_language_priority()
    return jsonify({"priority": priority})


@bp.route("/api/settings/off-language-priority", methods=["PUT"])
def set_off_language_priority():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    priority = data.get("priority")
    if not isinstance(priority, list):
        return jsonify({"error": "priority must be a list"}), 400
    if not priority:
        return jsonify({"error": "priority must not be empty"}), 400
    if not all(isinstance(item, str) and item.strip() for item in priority):
        return jsonify({"error": "priority must be a list of non-empty strings"}), 400
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for item in priority:
        item = item.strip()
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    settings_service.set_off_language_priority(deduped)
    return jsonify({"priority": deduped})


@bp.route("/api/settings/ocr", methods=["PUT"])
def set_ocr_settings():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    backend_id = data.get("backend", "")
    if not backend_id:
        return jsonify({"error": "backend is required"}), 400
    from config import OCR_BACKENDS
    if backend_id not in OCR_BACKENDS:
        return jsonify({"error": f"Unrecognized OCR backend '{backend_id}'"}), 400
    # Check availability before storing
    backends = {b["id"]: b for b in ocr_service.get_available_backends()}
    if not backends[backend_id]["available"]:
        return jsonify({"error": f"Backend '{backend_id}' is not available (missing API key)"}), 400
    settings_service.set_ocr_backend(backend_id)
    return jsonify({"ok": True, "backend": backend_id})
