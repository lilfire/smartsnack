"""Blueprint for Open Food Facts integration endpoints."""

from flask import Blueprint, jsonify

from helpers import _require_json
from services import off_service

bp = Blueprint("off", __name__)


@bp.route("/api/off/add-product", methods=["POST"])
def add_product_to_off():
    try:
        data = _require_json()
        result = off_service.add_product_to_off(data)
        return jsonify({"ok": True, "status_verbose": result.get("status_verbose", "fields saved")})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
