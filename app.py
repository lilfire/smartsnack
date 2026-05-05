"""Flask application factory and entry point for SmartSnack."""

import logging
import os
import sys

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from db import init_db, close_db
from blueprints import register_blueprints
from extensions import limiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    try:
        init_db()
    except Exception as e:
        logger.error("Failed to initialize database: %s", e, exc_info=True)
        sys.exit(1)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

    app.teardown_appcontext(close_db)

    # S5: Rate limiting on all endpoints (stricter limits applied per-blueprint)
    limiter.init_app(app)

    register_blueprints(app)

    if not os.environ.get("SMARTSNACK_API_KEY"):
        logger.warning(
            "SMARTSNACK_API_KEY is not set — backup/restore/import endpoints are publicly accessible"
        )

    @app.before_request
    def csrf_protect():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        if request.headers.get("X-Requested-With") != "SmartSnack":
            return jsonify({"error": "CSRF validation failed"}), 403

    @app.after_request
    def set_security_headers(response):
        # S4: Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.openfoodfacts.org https://*.openfoodfacts.net; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'self'"
        )
        # JS cache-busting
        if response.content_type and "javascript" in response.content_type:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        return jsonify({"error": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_error(e):
        logger.error("Unhandled error: %s", e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
