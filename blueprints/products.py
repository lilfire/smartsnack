"""Blueprint for product CRUD endpoints."""

from flask import Blueprint, request, jsonify

from helpers import _require_json
from services import product_service

bp = Blueprint("products", __name__)


@bp.route("/api/products")
def get_products():
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "").strip()
    try:
        results = product_service.list_products(search, type_filter)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(results)


@bp.route("/api/products", methods=["POST"])
def add_product():
    try:
        data = _require_json()
        result = product_service.add_product(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result), 201


@bp.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    try:
        data = _require_json()
        product_service.update_product(pid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Product updated"})


@bp.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    found = product_service.delete_product(pid)
    if not found:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"ok": True, "message": "Deleted"})
