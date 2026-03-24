"""Blueprint for proxying images and API requests from allowed external domains."""

import logging

from flask import Blueprint, request, jsonify, Response

from extensions import limiter
from services import proxy_service

logger = logging.getLogger(__name__)

bp = Blueprint("proxy", __name__)


@bp.route("/api/proxy-image")
@limiter.limit("30 per minute")
def proxy_image():
    url = request.args.get("url", "")
    try:
        data, content_type = proxy_service.proxy_image(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return Response(
        data,
        mimetype=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )


@bp.route("/api/off/search", methods=["GET", "POST"])
def off_search():
    nutrition = None
    category = ""
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        query = body.get("q", "")
        category = body.get("category", "")
        raw_nutrition = body.get("nutrition")
        if isinstance(raw_nutrition, dict):
            nutrition = {}
            for k, v in raw_nutrition.items():
                try:
                    nutrition[k] = float(v)
                except (TypeError, ValueError):
                    continue
            if not nutrition:
                nutrition = None
    else:
        query = request.args.get("q", "")
    try:
        data = proxy_service.off_search(query, nutrition, category)
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception:
        logger.exception("OFF search failed")
        return jsonify({"error": "Search failed"}), 500


@bp.route("/api/off/product/<code>")
def off_product(code):
    try:
        data = proxy_service.off_product(code)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(data)
