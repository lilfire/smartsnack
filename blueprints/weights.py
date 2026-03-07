from flask import Blueprint, jsonify

from helpers import _require_json
from services import weight_service

bp = Blueprint("weights", __name__)


@bp.route("/api/weights")
def get_weights():
    return jsonify(weight_service.get_weights())


@bp.route("/api/weights", methods=["PUT"])
def update_weights():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    try:
        weight_service.update_weights(data)
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Weights updated"})
