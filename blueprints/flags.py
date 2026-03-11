"""Blueprint for product flag CRUD endpoints."""

from flask import Blueprint, jsonify

from exceptions import ConflictError
from helpers import _require_json
from services import flag_service

bp = Blueprint("flags", __name__)


@bp.route("/api/flags")
def get_flags():
    return jsonify(flag_service.list_flags())


@bp.route("/api/flag-config")
def get_flag_config():
    return jsonify(flag_service.get_flag_config())


@bp.route("/api/flags", methods=["POST"])
def add_flag():
    try:
        data = _require_json()
        name = data.get("name", "").strip()
        label = data.get("label", "").strip()
        flag_service.add_flag(name, label)
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Flag added"}), 201


@bp.route("/api/flags/<name>", methods=["PUT"])
def update_flag(name):
    try:
        data = _require_json()
        label = data.get("label", "").strip()
        flag_service.update_flag_label(name, label)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Flag updated"})


@bp.route("/api/flags/<name>", methods=["DELETE"])
def delete_flag(name):
    try:
        count = flag_service.delete_flag(name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Flag deleted", "removed_from": count})
