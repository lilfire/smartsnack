"""Blueprint for product CRUD endpoints."""

from flask import Blueprint, request, jsonify

from helpers import _require_json
from services import product_service

bp = Blueprint("products", __name__)


@bp.route("/api/products")
def get_products():
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "").strip()
    advanced_filters = request.args.get("filters", "").strip() or None
    try:
        results = product_service.list_products(search, type_filter, advanced_filters)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(results)


@bp.route("/api/products", methods=["POST"])
def add_product():
    try:
        data = _require_json()
        on_duplicate = data.pop("on_duplicate", None)
        result = product_service.add_product(data, on_duplicate=on_duplicate)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if "duplicate" in result:
        return jsonify(result), 409
    status = 200 if result.get("merged") else 201
    return jsonify(result), status


@bp.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    try:
        data = _require_json()
        product_service.update_product(pid, data)
    except LookupError:
        return jsonify({"error": "Product not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Product updated"})


@bp.route("/api/products/<int:pid>/check-duplicate", methods=["POST"])
def check_duplicate(pid):
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ean = data.get("ean", "")
    name = data.get("name", "")
    dup = product_service.check_duplicate_for_edit(pid, ean, name)
    return jsonify({"duplicate": dup})


@bp.route("/api/products/<int:pid>/merge", methods=["POST"])
def merge_product(pid):
    try:
        data = _require_json()
        source_id = data.get("source_id")
        if not source_id or not isinstance(source_id, int):
            raise ValueError("source_id is required and must be an integer")
        choices = data.get("choices") or {}
        product_service.merge_products(pid, source_id, choices=choices)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "Products merged"})


@bp.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    found = product_service.delete_product(pid)
    if not found:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"ok": True, "message": "Deleted"})
