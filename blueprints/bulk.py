"""Blueprint for bulk operations (refresh from OFF, estimate PQ)."""

from flask import Blueprint, Response, jsonify, stream_with_context

from services import bulk_service

bp = Blueprint("bulk", __name__)


@bp.route("/api/bulk/refresh-off", methods=["POST"])
def refresh_off():
    try:
        result = bulk_service.refresh_from_off()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/bulk/refresh-off/stream")
def refresh_off_stream():
    def generate():
        for event_json in bulk_service.refresh_from_off_stream():
            yield f"data: {event_json}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/api/bulk/estimate-pq", methods=["POST"])
def estimate_pq():
    try:
        result = bulk_service.estimate_all_pq()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
