from flask import Blueprint, jsonify

from services import translation_service

bp = Blueprint("translations", __name__)


@bp.route("/api/languages")
def get_languages():
    return jsonify(translation_service.get_available_languages())


@bp.route("/api/translations/<lang>")
def get_translations(lang):
    try:
        data = translation_service.get_translations(lang)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(data)
