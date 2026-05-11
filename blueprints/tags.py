"""Blueprint for tag CRUD endpoints."""

from flask import Blueprint, request, jsonify

from helpers import _require_json
from services import tag_service

bp = Blueprint("tags", __name__)


@bp.route("/api/tags", methods=["GET"])
def list_tags():
    q = request.args.get("q")
    if q is not None:
        return jsonify(tag_service.search_tags(q))
    return jsonify(tag_service.list_tags())


@bp.route("/api/tags", methods=["POST"])
def create_tag():
    try:
        data = _require_json()
        label = data.get("label", "")
        tag = tag_service.create_tag(label)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(tag), 201


@bp.route("/api/tags/<int:tag_id>", methods=["GET"])
def get_tag(tag_id):
    tag = tag_service.get_tag(tag_id)
    if tag is None:
        return jsonify({"error": "Tag not found"}), 404
    return jsonify(tag)


@bp.route("/api/tags/<int:tag_id>", methods=["PUT"])
def update_tag(tag_id):
    try:
        data = _require_json()
        label = data.get("label", "")
        tag = tag_service.update_tag(tag_id, label)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if tag is None:
        return jsonify({"error": "Tag not found"}), 404
    return jsonify(tag)


@bp.route("/api/tags/<int:tag_id>", methods=["DELETE"])
def delete_tag(tag_id):
    deleted = tag_service.delete_tag(tag_id)
    if not deleted:
        return jsonify({"error": "Tag not found"}), 404
    return jsonify({"ok": True})
