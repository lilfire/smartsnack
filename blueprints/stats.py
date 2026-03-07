from flask import Blueprint, jsonify

from services import stats_service

bp = Blueprint("stats", __name__)


@bp.route("/api/stats")
def get_stats():
    return jsonify(stats_service.get_stats())
