import logging

from flask import Blueprint, jsonify, render_template

from db import get_db
from config import APP_VERSION

logger = logging.getLogger(__name__)

bp = Blueprint("core", __name__)


@bp.route("/health")
def health():
    try:
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        return jsonify({"status": "ok", "version": APP_VERSION, "products": count})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error"}), 500


@bp.route("/")
def index():
    return render_template("index.html")
