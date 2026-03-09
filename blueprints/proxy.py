"""Blueprint for proxying images from allowed external domains."""

from flask import Blueprint, request, jsonify, Response

from services import proxy_service

bp = Blueprint("proxy", __name__)


@bp.route("/api/proxy-image")
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
    return Response(data, mimetype=content_type, headers={
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*"})
