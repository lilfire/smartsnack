"""Blueprint for category CRUD endpoints."""

from flask import Blueprint, jsonify, request

from exceptions import ConflictError
from helpers import _require_json, _validate_category_name
from services import category_service

bp = Blueprint("categories", __name__)


@bp.route("/api/categories")
def get_categories():
    return jsonify(category_service.list_categories())


@bp.route("/api/categories", methods=["POST"])
def add_category():
    try:
        data = _require_json()
        name = data.get("name", "").strip()
        label = data.get("label", "").strip()
        emoji = data.get("emoji", "\U0001F4E6").strip()
        category_service.add_category(name, label, emoji)
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Category added"}), 201


@bp.route("/api/categories/<name>", methods=["PUT"])
def update_category(name):
    err = _validate_category_name(name)
    if err:
        return jsonify({"error": err}), 400
    try:
        data = _require_json()
        label = data.get("label", "").strip()
        emoji = data.get("emoji", "").strip()
        category_service.update_category(name, label, emoji)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Category updated"})


@bp.route("/api/categories/<name>", methods=["DELETE"])
def delete_category(name):
    err = _validate_category_name(name)
    if err:
        return jsonify({"error": err}), 400
    move_to = None
    body = request.get_json(silent=True)
    if body:
        raw = body.get("move_to")
        move_to = raw.strip() if isinstance(raw, str) and raw.strip() else None
    try:
        count = category_service.delete_category(name, move_to=move_to)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Category deleted", "moved": count or 0})
