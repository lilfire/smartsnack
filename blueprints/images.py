from flask import Blueprint, jsonify

from helpers import _require_json
from services import image_service

bp = Blueprint("images", __name__)


@bp.route("/api/products/<int:pid>/image")
def get_product_image(pid):
    image = image_service.get_image(pid)
    if image is None:
        return jsonify({"error": "No image"}), 404
    return jsonify({"image": image})


@bp.route("/api/products/<int:pid>/image", methods=["PUT"])
def set_product_image(pid):
    data = _require_json()
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    try:
        found = image_service.set_image(pid, data.get("image", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not found:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": "Image saved"})


@bp.route("/api/products/<int:pid>/image", methods=["DELETE"])
def delete_product_image(pid):
    found = image_service.delete_image(pid)
    if not found:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": "Image removed"})
