"""Blueprint for Open Food Facts integration endpoints."""

import logging

from flask import Blueprint, jsonify

from helpers import _require_json
from services import image_service, off_service, product_crud

bp = Blueprint("off", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/off/add-product", methods=["POST"])
def add_product_to_off():
    try:
        data = _require_json()
        result = off_service.add_product_to_off(data)
        response = {
            "ok": True,
            "status_verbose": result.get("status_verbose", "fields saved"),
            "image_uploaded": False,
            "image_warning": None,
            "synced_flag_set": False,
        }
        product_id = data.get("product_id")
        if product_id is not None:
            try:
                pid = int(product_id)
            except (TypeError, ValueError):
                pid = None
            if pid:
                code = (data.get("code") or "").strip() or None
                image = image_service.get_image(pid)
                if image:
                    try:
                        off_service.upload_image_to_off(code, image)
                        response["image_uploaded"] = True
                    except (ValueError, RuntimeError) as img_err:
                        logger.warning(
                            "OFF image upload failed for product %s: %s", pid, img_err
                        )
                        response["image_warning"] = str(img_err)
                try:
                    product_crud.mark_product_synced_with_off(pid, code)
                    response["synced_flag_set"] = True
                except Exception as flag_err:
                    logger.error(
                        "Failed to set is_synced_with_off for product %s: %s",
                        pid,
                        flag_err,
                    )
        return jsonify(response)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
