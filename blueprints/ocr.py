"""Blueprint for OCR ingredient extraction endpoint."""

from flask import Blueprint, jsonify

from extensions import limiter
from helpers import _require_json
from services import ocr_service, llm_cleanup_service

bp = Blueprint("ocr", __name__)


@bp.route("/api/ocr/ingredients", methods=["POST"])
@limiter.limit("10 per minute")
def ocr_ingredients():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    image = data.get("image", "")
    if not image:
        return jsonify({"error": "No image provided"}), 400

    lang = data.get("lang", "no")

    try:
        text = ocr_service.extract_text(image)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "OCR processing failed"}), 500

    if not text:
        return jsonify({"text": "", "llm_cleanup_skipped": True, "error": "No text found in image"}), 200

    result = llm_cleanup_service.cleanup_ingredients(text, lang)
    return jsonify({"text": result["text"], "llm_cleanup_skipped": result["llm_cleanup_skipped"]})
