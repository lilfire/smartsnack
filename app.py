"""Flask application factory and entry point for SmartSnack."""

import logging
import sys

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from db import init_db, close_db
from blueprints import register_blueprints

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

    register_blueprints(app)

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
