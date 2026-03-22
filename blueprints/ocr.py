"""Blueprint for OCR ingredient extraction endpoint."""

from flask import Blueprint, jsonify

from helpers import _require_json
from services import ocr_service

bp = Blueprint("ocr", __name__)


@bp.route("/api/ocr/ingredients", methods=["POST"])
def ocr_ingredients():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    image = data.get("image", "")
    if not image:
        return jsonify({"error": "No image provided"}), 400

    try:
        text = ocr_service.extract_text(image)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "OCR processing failed"}), 500

    if not text:
        return jsonify({"text": "", "error": "No text found in image"}), 200

    return jsonify({"text": text})
