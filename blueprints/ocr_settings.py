"""Blueprint for OCR provider listing and settings endpoints."""

from flask import Blueprint, jsonify

from config import OCR_BACKENDS
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

    # Validate and process optional models dict
    models = data.get("models")
    if models is not None:
        if not isinstance(models, dict):
            return jsonify({"error": "models must be an object"}), 400
        for provider_key, model_value in models.items():
            if provider_key not in OCR_BACKENDS:
                return jsonify({"error": f"Invalid provider in models: {provider_key}"}), 400
            provider_models = OCR_BACKENDS[provider_key].get("models", [])
            if provider_key == "openrouter":
                # Free-text: reject empty string
                if not model_value or not isinstance(model_value, str):
                    return jsonify({"error": "OpenRouter model must be a non-empty string"}), 400
            elif provider_models:
                if model_value not in provider_models:
                    return jsonify({
                        "error": f"Invalid model '{model_value}' for provider '{provider_key}'"
                    }), 400

    try:
        ocr_settings_service.save_ocr_settings(provider, fallback, models)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})
