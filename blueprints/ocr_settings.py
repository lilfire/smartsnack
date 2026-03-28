"""Blueprint for OCR provider listing and settings endpoints."""

from flask import Blueprint, jsonify

from helpers import _require_json
from services import ocr_settings_service

bp = Blueprint("ocr_settings", __name__)


@bp.route("/api/ocr/providers")
def get_providers():
    providers = ocr_settings_service.get_providers()
    return jsonify({"providers": providers})


@bp.route("/api/ocr/settings")
def get_settings():
    settings = ocr_settings_service.get_ocr_settings()
    return jsonify(settings)


@bp.route("/api/ocr/settings", methods=["POST"])
def save_settings():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    provider = data.get("provider")
    if not provider:
        return jsonify({"error": "provider is required"}), 400

    fallback = bool(data.get("fallback_to_tesseract", False))

    try:
        ocr_settings_service.save_ocr_settings(provider, fallback)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})
