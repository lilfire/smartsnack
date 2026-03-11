"""Blueprint for bulk operations (refresh from OFF, estimate PQ)."""

import json
import time

from flask import Blueprint, Response, jsonify, request

from services import bulk_service

bp = Blueprint("bulk", __name__)


@bp.route("/api/bulk/refresh-off", methods=["POST"])
def refresh_off():
    try:
        result = bulk_service.refresh_from_off()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/bulk/refresh-off/start", methods=["POST"])
def refresh_off_start():
    data = request.get_json(silent=True) or {}
    options = {
        "search_missing": bool(data.get("search_missing", False)),
        "min_certainty": min(100, max(0, int(data.get("min_certainty", 50)))),
        "min_completeness": min(100, max(0, int(data.get("min_completeness", 50)))),
    }
    started = bulk_service.start_refresh_from_off(options)
    if not started:
        return jsonify({"error": "already_running"}), 409
    return jsonify({"ok": True})


@bp.route("/api/bulk/refresh-off/status")
def refresh_off_status():
    return jsonify(bulk_service.get_refresh_status())


@bp.route("/api/bulk/refresh-off/stream")
def refresh_off_stream():
    def generate():
        last_sent = None
        while True:
            status = bulk_service.get_refresh_status()
            snapshot = json.dumps(status, sort_keys=True)
            if snapshot != last_sent:
                yield f"data: {snapshot}\n\n"
                last_sent = snapshot
            if status.get("done") or (
                not status.get("running") and not status.get("done")
            ):
                break
            time.sleep(0.3)

    return Response(
        generate(),
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
