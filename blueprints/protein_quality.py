"""Blueprint for protein quality CRUD and estimation endpoints."""

from flask import Blueprint, jsonify

from exceptions import ConflictError
from helpers import _require_json
from services import protein_quality_service

bp = Blueprint("protein_quality", __name__)


@bp.route("/api/protein-quality")
def list_protein_quality():
    return jsonify(protein_quality_service.list_entries())


@bp.route("/api/protein-quality", methods=["POST"])
def add_protein_quality():
    try:
        data = _require_json()
        result = protein_quality_service.add_entry(data)
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result), 201


@bp.route("/api/protein-quality/<int:pid>", methods=["PUT"])
def update_protein_quality(pid):
    try:
        data = _require_json()
        protein_quality_service.update_entry(pid, data)
    except LookupError:
        return jsonify({"error": "Not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@bp.route("/api/protein-quality/<int:pid>", methods=["DELETE"])
def delete_protein_quality(pid):
    try:
        protein_quality_service.delete_entry(pid)
    except LookupError:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/estimate-protein-quality", methods=["POST"])
def estimate_protein_quality():
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ingredients = (data.get("ingredients") or "").strip()
    if not ingredients:
        return jsonify({"error": "ingredients required"}), 400
    try:
        result = protein_quality_service.estimate(ingredients)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)
