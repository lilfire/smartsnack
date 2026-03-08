"""Blueprint for category CRUD endpoints."""

from flask import Blueprint, jsonify, request

from exceptions import ConflictError
from helpers import _require_json
from services import category_service

bp = Blueprint("categories", __name__)


@bp.route("/api/categories")
def get_categories():
    return jsonify(category_service.list_categories())


@bp.route("/api/categories", methods=["POST"])
def add_category():
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    name = data.get("name", "").strip()
    label = data.get("label", "").strip()
    emoji = data.get("emoji", "\U0001F4E6").strip()
    try:
        category_service.add_category(name, label, emoji)
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Category added"}), 201


@bp.route("/api/categories/<n>", methods=["PUT"])
def update_category(n):
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    label = data.get("label", "").strip()
    emoji = data.get("emoji", "").strip()
    try:
        category_service.update_category(n, label, emoji)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Category updated"})


@bp.route("/api/categories/<n>", methods=["DELETE"])
def delete_category(n):
    move_to = None
    body = request.get_json(silent=True)
    if body:
        move_to = (body.get("move_to") or "").strip() or None
    try:
        count = category_service.delete_category(n, move_to=move_to)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Category deleted", "moved": count or 0})
