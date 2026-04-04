"""Blueprint for tag CRUD endpoints."""
from flask import Blueprint, jsonify

from helpers import _require_json
from services import tag_service

bp = Blueprint("tags", __name__)


@bp.route("/api/tags")
def list_tags():
    return jsonify(tag_service.list_tags())


@bp.route("/api/tags", methods=["POST"])
def create_tag():
    try:
        data = _require_json()
        result = tag_service.create_tag(data.get("label", ""))
    except ValueError as e:
        err = str(e)
        if err == "tag_already_exists":
            return jsonify({"error": err}), 409
        return jsonify({"error": err}), 400
    return jsonify(result), 201


@bp.route("/api/tags/<int:tid>", methods=["DELETE"])
def delete_tag(tid):
    if not tag_service.delete_tag(tid):
        return jsonify({"error": "Tag not found"}), 404
    return jsonify({"ok": True, "message": "Tag deleted"})
