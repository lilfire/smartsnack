"""Blueprint for bulk operations (refresh from OFF, estimate PQ)."""

from flask import Blueprint, jsonify

from services import bulk_service

bp = Blueprint("bulk", __name__)


@bp.route("/api/bulk/refresh-off", methods=["POST"])
def refresh_off():
    try:
        result = bulk_service.refresh_from_off()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/bulk/estimate-pq", methods=["POST"])
def estimate_pq():
    try:
        result = bulk_service.estimate_all_pq()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
