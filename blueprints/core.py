"""Blueprint for health check and main page."""

import logging
import sqlite3

from flask import Blueprint, jsonify, render_template

from db import get_db
from config import APP_VERSION, APP_VERSION_SUFFIX

logger = logging.getLogger(__name__)

bp = Blueprint("core", __name__)


@bp.route("/health")
def health():
    try:
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        return jsonify({"status": "ok", "version": APP_VERSION, "products": count})
    except (sqlite3.Error, OSError) as e:
        logger.error("Health check failed: %s", e)
        return jsonify({"status": "error"}), 500


@bp.route("/")
def index():
    version = f"{APP_VERSION}-{APP_VERSION_SUFFIX}" if APP_VERSION_SUFFIX else APP_VERSION
    return render_template("index.html", version=version)
