"""Blueprint for Open Food Facts integration endpoints."""

from flask import Blueprint, jsonify

from helpers import _require_json
from services import off_service

bp = Blueprint("off", __name__)


@bp.route("/api/off/add-product", methods=["POST"])
def add_product_to_off():
    try:
        data = _require_json()
        response = off_service.add_and_sync_product(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(response)
