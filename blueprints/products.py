"""Blueprint for product CRUD endpoints."""

from flask import Blueprint, request, jsonify

from helpers import _require_json
from services import product_service
from config import DEFAULT_PAGE_SIZE

bp = Blueprint("products", __name__)


@bp.route("/api/products")
def get_products():
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type")
    advanced_filters = request.args.get("filters", "").strip() or None
    try:
        limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400
    try:
        result = product_service.list_products(search, type_filter, advanced_filters, limit, offset)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)


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


@bp.route("/api/products/tags/suggestions", methods=["GET"])
def tag_suggestions():
    if "q" not in request.args:
        return jsonify([])
    prefix = request.args.get("q", "").strip()
    return jsonify(product_service.get_tag_suggestions(prefix))


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


@bp.route("/api/products/<int:pid>/unsync", methods=["POST"])
def unsync_product(pid):
    """Remove the is_synced_with_off flag from a product."""
    try:
        product_service.set_system_flag(pid, "is_synced_with_off", False)
    except (LookupError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@bp.route("/api/products/<int:pid>/check-duplicate", methods=["POST"])
def check_duplicate(pid):
    try:
        data = _require_json()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ean = data.get("ean", "")
    name = data.get("name", "")
    dup, a_synced = product_service.check_duplicate_for_edit(pid, ean, name)
    return jsonify({"duplicate": dup, "a_is_synced_with_off": a_synced})


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


@bp.route("/api/products/<int:pid>/eans")
def list_eans(pid):
    try:
        eans = product_service.list_eans(pid)
    except LookupError:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(eans)


@bp.route("/api/products/<int:pid>/eans", methods=["POST"])
def add_ean(pid):
    try:
        data = _require_json()
        ean = data.get("ean", "")
        result = product_service.add_ean(pid, ean)
    except LookupError:
        return jsonify({"error": "Product not found"}), 404
    except ValueError as e:
        err = str(e)
        if err == "ean_already_exists":
            return jsonify({"error": err}), 409
        return jsonify({"error": err}), 400
    return jsonify(result), 201


@bp.route("/api/products/<int:pid>/eans/<int:ean_id>", methods=["DELETE"])
def delete_ean(pid, ean_id):
    try:
        product_service.delete_ean(pid, ean_id)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "message": "EAN deleted"})


@bp.route("/api/products/<int:pid>/eans/<int:ean_id>/set-primary", methods=["PATCH"])
def set_primary_ean(pid, ean_id):
    try:
        product_service.set_primary_ean(pid, ean_id)
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True, "message": "Primary EAN updated"})
